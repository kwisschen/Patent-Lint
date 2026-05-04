# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Cluster-discovery tool for Phase 3 walker recall mining.

Reads a `phase2b_results*.json` ensemble-verdict file, extracts every
verdict tagged `coverage_gap` (walker missed an intro that exists in
the chain) or `walker_fp` (walker over-emitted), groups them by
SIGNATURE (term-tail, term-prefix, structural shape, jurisdiction),
and ranks clusters by:

  - safe-silence ratio (wfp / (wfp + legit)) — clusters with high
    walker_fp + zero legit are safe to silence via narrow walker
    guards (the methodology that drove R32–R48 commits)
  - recall yield (coverage_gap count) — clusters where the walker
    missed intros are mining targets for Phase 3 (extending intro
    extractors to recognize the missed pattern)

Output: precision-push-friendly cluster table sorted by yield, with
example findings to manually classify before each Phase 3 mining
commit.

Usage:
    python -m tests.eval.discover_clusters \\
        tests/eval/phase2b_results_supplement_v2.json \\
        --top-clusters 30 \\
        --output-report .../2026-05-05_phase3-clusters.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

PATENTLINT_ROOT = Path("/Users/chrischen/Documents/Projects/Patent-Lint")
sys.path.insert(0, str(PATENTLINT_ROOT / "src"))

# Re-use the calibration tool's join logic (re-runs walker, joins by
# (patent_id, claim_id, term)). This script is a sibling — adds cluster
# signature extraction + ranking on top.
from .phase2b_judging import (  # noqa: E402
    CORPUS_PARQUET_DIR,
    load_corpus_records,
    run_walker_on_draft,
)


# Cluster signatures — each finding is mapped to a tuple of signature
# strings; clustering aggregates over these.
def _term_tail_3(term: str) -> str:
    """Trailing 3 chars (CJK) or 3 token suffix (Latin)."""
    if not term:
        return ""
    if any(0x4E00 <= ord(c) <= 0x9FFF for c in term):
        return term[-3:] if len(term) >= 3 else term
    toks = term.split()
    return " ".join(toks[-2:]) if len(toks) >= 2 else term


def _term_head_3(term: str) -> str:
    """Leading 3 chars (CJK) or 2-token prefix (Latin)."""
    if not term:
        return ""
    if any(0x4E00 <= ord(c) <= 0x9FFF for c in term):
        return term[:3]
    toks = term.split()
    return " ".join(toks[:2]) if len(toks) >= 2 else term


def _structural_shape(term: str) -> str:
    """Cheap structural fingerprint of the term."""
    if not term:
        return "empty"
    has_paren_num = bool(re.search(r"\(\d+\)", term))
    has_ordinal_zh = bool(re.match(r"^第[一二三四五六七八九十0-9]+", term))
    is_ascii_upper = term.isascii() and term.replace(" ", "").isupper()
    is_short = len(term) <= 3
    is_long = len(term) >= 8
    has_punct_internal = bool(re.search(r"[、，;:]", term))
    flags = []
    if has_paren_num:
        flags.append("PAREN_NUM")
    if has_ordinal_zh:
        flags.append("ORDINAL_ZH")
    if is_ascii_upper:
        flags.append("ASCII_UPPER")
    if is_short:
        flags.append("SHORT")
    if is_long:
        flags.append("LONG")
    if has_punct_internal:
        flags.append("INTERNAL_PUNCT")
    return ":".join(flags) if flags else "PLAIN"


def discover(verdicts_path: Path, top_n: int) -> dict:
    print(f"Loading verdicts from {verdicts_path}")
    payload = json.loads(verdicts_path.read_text())
    verdict_drafts = payload.get("verdicts", [])
    print(f"  {len(verdict_drafts)} judged drafts")

    pids_in_play = {v["patent_id"] for v in verdict_drafts if v.get("patent_id")}

    print(f"Loading corpus from {CORPUS_PARQUET_DIR}")
    records = load_corpus_records(CORPUS_PARQUET_DIR)
    records = [r for r in records if r.get("patent_id") in pids_in_play]
    print(f"  filtered to {len(records)} relevant records")

    print("Re-running walker for finding metadata...")
    walker_by_pid: dict[str, list[dict]] = {}
    for rec in records:
        pid = rec.get("patent_id")
        try:
            issues, _ = run_walker_on_draft(rec)
            walker_by_pid[pid] = issues
        except Exception as exc:
            print(f"  walker error on {pid}: {exc!r}", file=sys.stderr)

    # Cluster collection: signature -> (jurisdiction -> Counter of categories)
    # plus exemplar findings (up to 3 per cluster) for review.
    cluster_data: dict[str, dict] = defaultdict(lambda: {
        "jurisdiction_categories": defaultdict(Counter),
        "exemplars": [],
    })

    for vd in verdict_drafts:
        pid = vd.get("patent_id")
        juris = vd.get("jurisdiction", "")
        if not pid or pid not in walker_by_pid:
            continue
        # Build (claim_id, term) -> finding map for this draft
        by_key: dict[tuple, dict] = {}
        for iss in walker_by_pid[pid]:
            k = (iss["claim_id"], iss["term"])
            if k not in by_key:
                by_key[k] = iss

        for fv in vd.get("ensemble", {}).get("final_verdicts", []):
            cid = fv.get("claim_id")
            term = fv.get("term", "") or ""
            cat = fv.get("category", "ambig")
            if cid is None:
                continue
            iss = by_key.get((cid, term))
            ref_form = (iss or {}).get("reference_form", "") if iss else ""

            # CURRENT-WALKER FILTER: only include findings whose pattern
            # the CURRENT walker still emits. Critical for Phase 3 mining
            # to avoid burning effort on patterns already fixed by R34-R48.
            #
            # Rules:
            #   walker_fp + iss is None → CURRENT walker no longer emits
            #     this term; safely skip (already fixed by prior rounds).
            #   walker_fp + iss not None → CURRENT walker still emits;
            #     mining target.
            #   coverage_gap → CURRENT walker still missing the intro
            #     (whether or not the same term is emitted); always include.
            #   legit/ambig/diag_misattr + iss is None → walker silenced;
            #     informational, not a mining target — skip.
            #   legit/ambig/diag_misattr + iss not None → still emits;
            #     include for completeness baseline.
            if cat in ("walker_fp", "legit_drafting_error", "ambig",
                       "diagnostic_mis_attribution"):
                if iss is None:
                    continue

            # Three signature granularities for clustering — each finding
            # contributes to all three.
            sigs = [
                ("TAIL", juris, _term_tail_3(term)),
                ("HEAD", juris, _term_head_3(term)),
                ("SHAPE", juris, _structural_shape(term)),
            ]
            for sig_kind, sig_juris, sig_value in sigs:
                key = f"{sig_kind}|{sig_juris}|{sig_value}"
                cluster_data[key]["jurisdiction_categories"][sig_juris][cat] += 1
                if len(cluster_data[key]["exemplars"]) < 3:
                    cluster_data[key]["exemplars"].append({
                        "patent_id": pid,
                        "claim_id": cid,
                        "term": term,
                        "reference_form": ref_form,
                        "category": cat,
                        "reasoning": fv.get("reasoning", "")[:160],
                    })

    # Score clusters: rank by combined yield-and-purity
    cluster_rows: list[dict] = []
    for key, data in cluster_data.items():
        sig_kind, sig_juris, sig_value = key.split("|", 2)
        cat_counts = data["jurisdiction_categories"][sig_juris]
        total = sum(cat_counts.values())
        wfp = cat_counts.get("walker_fp", 0)
        legit = cat_counts.get("legit_drafting_error", 0)
        coverage = cat_counts.get("coverage_gap", 0)
        # Mining safety: high wfp + zero legit means safe-silence
        safe_silence_target = wfp >= 10 and legit == 0
        # Recall mining target: high coverage_gap count
        recall_mining_target = coverage >= 5
        cluster_rows.append({
            "signature_kind": sig_kind,
            "jurisdiction": sig_juris,
            "signature_value": sig_value,
            "total": total,
            "walker_fp": wfp,
            "legit": legit,
            "coverage_gap": coverage,
            "ambig": cat_counts.get("ambig", 0),
            "diag_misattr": cat_counts.get("diagnostic_mis_attribution", 0),
            "safe_silence_target": safe_silence_target,
            "recall_mining_target": recall_mining_target,
            "exemplars": data["exemplars"],
        })

    # Sort: safe-silence targets first (highest wfp, zero legit), then
    # recall-mining targets (highest coverage_gap)
    safe_silence = sorted(
        [c for c in cluster_rows if c["safe_silence_target"]],
        key=lambda c: -c["walker_fp"],
    )[:top_n]
    recall_mining = sorted(
        [c for c in cluster_rows if c["recall_mining_target"]],
        key=lambda c: -c["coverage_gap"],
    )[:top_n]
    return {
        "drafts_judged": len(verdict_drafts),
        "drafts_with_walker_data": sum(1 for p in walker_by_pid if walker_by_pid[p]),
        "safe_silence_clusters": safe_silence,
        "recall_mining_clusters": recall_mining,
    }


def render_report(result: dict) -> str:
    lines: list[str] = []
    lines.append("# Phase 3 cluster discovery\n")
    lines.append(
        f"- Drafts judged: {result['drafts_judged']}\n"
        f"- Drafts with walker output: {result['drafts_with_walker_data']}\n"
    )
    lines.append("\n## Safe-silence targets (≥10 wfp, 0 legit)\n")
    lines.append(
        "Clusters where the walker over-emits with no risk to legit "
        "findings. Methodology that drove R32–R48 commits.\n"
    )
    lines.append(
        "| sig_kind | juris | signature | wfp | legit | coverage | ambig |"
    )
    lines.append("|---|---|---|---:|---:|---:|---:|")
    for c in result["safe_silence_clusters"]:
        lines.append(
            f"| {c['signature_kind']} | {c['jurisdiction']} | "
            f"`{c['signature_value']}` | {c['walker_fp']} | {c['legit']} | "
            f"{c['coverage_gap']} | {c['ambig']} |"
        )
    if result["safe_silence_clusters"]:
        lines.append("\n### Top exemplars\n")
        for c in result["safe_silence_clusters"][:5]:
            lines.append(f"\n**`{c['signature_kind']}|{c['jurisdiction']}|{c['signature_value']}`** "
                         f"({c['walker_fp']} wfp / {c['legit']} legit)\n")
            for ex in c["exemplars"]:
                lines.append(f"- claim {ex['claim_id']}: term=`{ex['term']}` "
                             f"ref=`{ex['reference_form']}` cat={ex['category']}")
                lines.append(f"  - {ex['reasoning']}")

    lines.append("\n\n## Recall-mining targets (≥5 coverage_gap)\n")
    lines.append(
        "Clusters where the walker MISSED intros that exist in the chain.\n"
        "Each cluster represents a pattern the intro-extractor doesn't yet recognize.\n"
    )
    lines.append(
        "| sig_kind | juris | signature | coverage | wfp | legit | ambig |"
    )
    lines.append("|---|---|---|---:|---:|---:|---:|")
    for c in result["recall_mining_clusters"]:
        lines.append(
            f"| {c['signature_kind']} | {c['jurisdiction']} | "
            f"`{c['signature_value']}` | {c['coverage_gap']} | "
            f"{c['walker_fp']} | {c['legit']} | {c['ambig']} |"
        )
    if result["recall_mining_clusters"]:
        lines.append("\n### Top recall-mining exemplars\n")
        for c in result["recall_mining_clusters"][:5]:
            lines.append(f"\n**`{c['signature_kind']}|{c['jurisdiction']}|{c['signature_value']}`** "
                         f"({c['coverage_gap']} coverage_gap)\n")
            for ex in c["exemplars"]:
                if ex["category"] != "coverage_gap":
                    continue
                lines.append(f"- claim {ex['claim_id']}: term=`{ex['term']}` "
                             f"ref=`{ex['reference_form']}`")
                lines.append(f"  - {ex['reasoning']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Discover walker-FP and coverage-gap clusters from verdicts."
    )
    parser.add_argument("verdicts_path", type=str)
    parser.add_argument("--top-clusters", type=int, default=30)
    parser.add_argument("--output-json", type=str, default=None)
    parser.add_argument("--output-report", type=str, default=None)
    args = parser.parse_args()

    result = discover(Path(args.verdicts_path), args.top_clusters)
    if args.output_json:
        Path(args.output_json).write_text(
            json.dumps(result, ensure_ascii=False, indent=2, default=str)
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
