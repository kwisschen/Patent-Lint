# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Calibrate per-jurisdiction confidence-score thresholds against
ensemble-verdict ground truth.

Reads a `phase2b_results*.json` file (the ensemble-verdict supplement
from `phase2b_judging.py`), re-runs the walker on the corresponding
corpus drafts (so each finding carries the freshly-computed
`confidence_score`), joins the walker findings to verdicts on
`(patent_id, claim_id, term)`, and outputs a precision-by-threshold
table per jurisdiction.

The output is the calibration data for Phase 5 of the precision-push
plan — pick the lowest threshold T_high per jurisdiction where
high-conf-bucket precision ≥ 70%.

Usage:
    python -m tests.eval.calibrate_confidence_threshold \\
        tests/eval/phase2b_results_supplement_v2.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

PATENTLINT_ROOT = Path("/Users/chrischen/Documents/Projects/Patent-Lint")
sys.path.insert(0, str(PATENTLINT_ROOT / "src"))

# These imports load the production walker — `run_walker_on_draft`
# constructs the doc from corpus claims and runs `check_antecedent_basis*`
# which now emits `confidence_score` on every issue.
from .phase2b_judging import (  # noqa: E402
    CORPUS_PARQUET_DIR,
    load_corpus_records,
    run_walker_on_draft,
)

# Threshold candidates (per plan §Phase 5: "candidate thresholds 70/75/80/85").
THRESHOLDS = [60, 65, 70, 75, 80, 85, 90]


def _walker_key(claim_id: int, term: str, reference_form: str) -> tuple:
    """Stable join key between walker issues and verdicts.

    Verdicts only carry (claim_id, term); walker issues carry
    (claim_id, term, reference_form). When multiple findings share
    (claim_id, term) — e.g. two distinct reference forms `the X` and
    `said X` — the walker has multiple findings but the verdict is one
    judgment. Strategy: when joining, allow the verdict to apply to
    the highest-confidence walker finding for that (claim_id, term)
    pair. The remaining walker findings inherit the same verdict
    (conservative: same logical defect, same judgment).
    """
    return (claim_id, term)


def _load_walker_findings_by_pid(records: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for rec in records:
        pid = rec.get("patent_id")
        if not pid:
            continue
        try:
            issues, _ = run_walker_on_draft(rec)
        except Exception as exc:
            print(f"  walker error on {pid}: {exc!r}", file=sys.stderr)
            continue
        out[pid] = issues
    return out


def calibrate(verdicts_path: Path) -> dict:
    print(f"Loading verdicts from {verdicts_path}")
    payload = json.loads(verdicts_path.read_text())
    verdict_drafts = payload.get("verdicts", [])
    print(f"  {len(verdict_drafts)} judged drafts")

    pids_in_play = {v["patent_id"] for v in verdict_drafts if v.get("patent_id")}

    print(f"Loading corpus from {CORPUS_PARQUET_DIR}")
    records = load_corpus_records(CORPUS_PARQUET_DIR)
    records = [r for r in records if r.get("patent_id") in pids_in_play]
    print(f"  filtered to {len(records)} relevant records")

    print("Re-running walker for confidence_score...")
    walker_by_pid = _load_walker_findings_by_pid(records)

    # Per-jurisdiction collection: list of (confidence_score, category) pairs.
    # `category` is one of {walker_fp, coverage_gap, legit_drafting_error,
    # diagnostic_mis_attribution, ambig}. For precision math, walker_fp
    # is the false-positive denominator and legit_drafting_error is the
    # true-positive numerator (the rest are non-decision verdicts).
    per_juris: dict[str, list[tuple[int, str]]] = defaultdict(list)

    join_hits = 0
    join_misses = 0
    for vd in verdict_drafts:
        pid = vd.get("patent_id")
        juris = vd.get("jurisdiction", "")
        if not pid or pid not in walker_by_pid:
            continue
        # Build (claim_id, term) -> max-conf finding map for this draft
        walker_issues = walker_by_pid[pid]
        by_key: dict[tuple, dict] = {}
        for iss in walker_issues:
            k = _walker_key(iss["claim_id"], iss["term"], iss.get("reference_form", ""))
            existing = by_key.get(k)
            if existing is None or iss.get("confidence_score", 0) > existing.get("confidence_score", 0):
                by_key[k] = iss

        ensemble = vd.get("ensemble", {})
        for fv in ensemble.get("final_verdicts", []):
            cid = fv.get("claim_id")
            term = fv.get("term")
            cat = fv.get("category", "ambig")
            if cid is None or term is None:
                continue
            k = (cid, term)
            iss = by_key.get(k)
            if iss is None:
                join_misses += 1
                continue
            join_hits += 1
            score = int(iss.get("confidence_score", 80))
            per_juris[juris].append((score, cat))

    print(
        f"Join: {join_hits} verdicts matched walker findings; "
        f"{join_misses} verdicts unmatched (walker output drift)"
    )

    # Compute precision-by-threshold per jurisdiction
    out: dict = {
        "join_hits": join_hits,
        "join_misses": join_misses,
        "per_jurisdiction": {},
    }
    for juris in sorted(per_juris.keys()):
        rows = per_juris[juris]
        legit_total = sum(1 for _, c in rows if c == "legit_drafting_error")
        wfp_total = sum(1 for _, c in rows if c == "walker_fp")
        coverage_total = sum(1 for _, c in rows if c == "coverage_gap")
        ambig_total = sum(1 for _, c in rows if c == "ambig")
        diag_total = sum(1 for _, c in rows if c == "diagnostic_mis_attribution")
        denom_total = legit_total + wfp_total
        absolute_precision = (
            legit_total / denom_total if denom_total > 0 else 0.0
        )

        threshold_table: list[dict] = []
        for t in THRESHOLDS:
            bucket_legit = sum(
                1 for s, c in rows if s >= t and c == "legit_drafting_error"
            )
            bucket_wfp = sum(1 for s, c in rows if s >= t and c == "walker_fp")
            bucket_size = sum(1 for s, _ in rows if s >= t)
            bucket_denom = bucket_legit + bucket_wfp
            bucket_precision = (
                bucket_legit / bucket_denom if bucket_denom > 0 else 0.0
            )
            threshold_table.append({
                "threshold": t,
                "bucket_size": bucket_size,
                "bucket_legit": bucket_legit,
                "bucket_wfp": bucket_wfp,
                "bucket_precision": round(bucket_precision, 4),
                "bucket_pct_of_total": (
                    round(bucket_size / len(rows), 4) if rows else 0.0
                ),
            })

        out["per_jurisdiction"][juris] = {
            "total_findings": len(rows),
            "legit_drafting_error": legit_total,
            "walker_fp": wfp_total,
            "coverage_gap": coverage_total,
            "ambig": ambig_total,
            "diagnostic_mis_attribution": diag_total,
            "absolute_strict_precision": round(absolute_precision, 4),
            "by_threshold": threshold_table,
        }
    return out


def render_report(result: dict) -> str:
    lines: list[str] = []
    lines.append("# Confidence-threshold calibration\n")
    lines.append(
        f"- Join hits: {result['join_hits']}, "
        f"misses: {result['join_misses']}\n"
    )
    for juris, payload in sorted(result["per_jurisdiction"].items()):
        lines.append(f"\n## {juris}\n")
        lines.append(
            f"- Total findings (judged): {payload['total_findings']}\n"
            f"- legit_drafting_error: {payload['legit_drafting_error']}\n"
            f"- walker_fp: {payload['walker_fp']}\n"
            f"- coverage_gap: {payload['coverage_gap']}\n"
            f"- ambig: {payload['ambig']}\n"
            f"- diagnostic_mis_attribution: {payload['diagnostic_mis_attribution']}\n"
            f"- Absolute strict §112(b) precision: "
            f"{100*payload['absolute_strict_precision']:.1f}%\n"
        )
        lines.append("| threshold | bucket size | legit | wfp | precision | % of total |")
        lines.append("|---:|---:|---:|---:|---:|---:|")
        for row in payload["by_threshold"]:
            lines.append(
                f"| {row['threshold']} | {row['bucket_size']} | "
                f"{row['bucket_legit']} | {row['bucket_wfp']} | "
                f"{100*row['bucket_precision']:.1f}% | "
                f"{100*row['bucket_pct_of_total']:.1f}% |"
            )
        # Suggest the lowest threshold that achieves ≥70% bucket precision
        suggestions = [
            r for r in payload["by_threshold"]
            if r["bucket_precision"] >= 0.70 and r["bucket_size"] >= 10
        ]
        if suggestions:
            best = min(suggestions, key=lambda r: r["threshold"])
            lines.append(
                f"\n**Suggested T_high: {best['threshold']}** — "
                f"bucket precision {100*best['bucket_precision']:.1f}%, "
                f"{best['bucket_size']} findings ({100*best['bucket_pct_of_total']:.0f}% of total).\n"
            )
        else:
            lines.append(
                "\n**No threshold reaches 70% bucket precision with bucket_size ≥ 10.**\n"
            )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Calibrate confidence-score thresholds against verdicts."
    )
    parser.add_argument("verdicts_path", type=str,
                        help="Path to phase2b_results*.json file.")
    parser.add_argument("--output-json", type=str, default=None,
                        help="Optional output JSON path.")
    parser.add_argument("--output-report", type=str, default=None,
                        help="Optional output Markdown report path.")
    args = parser.parse_args()

    result = calibrate(Path(args.verdicts_path))
    if args.output_json:
        Path(args.output_json).write_text(
            json.dumps(result, ensure_ascii=False, indent=2)
        )
        print(f"JSON written to {args.output_json}")
    if args.output_report:
        Path(args.output_report).write_text(render_report(result), encoding="utf-8")
        print(f"Report written to {args.output_report}")
    else:
        print(render_report(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
