# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""Phase 2c spot-check checklist generator.

Reads Phase 2b results JSON(s), samples cases for Christopher/Claire review,
writes a markdown checklist to CC Output. Mirrors the borderline review
pattern (CC Output/2026-05-02_phase2a-borderline-review-checklist.md) that
worked well for Phase 2a.

Sample composition (per design Phase 2c):
- Pass 1: 15 unanimous walker_fp verdicts (stratified by jurisdiction +
  applicant_type) — quick rubber-stamp confirms walker FP rate
- Pass 2: 10-15 high-impact disagreements:
    1. Opus-resolved drafts where Opus disagreed with both Sonnet AND gpt
    2. Cases where the verdict differs by jurisdiction or applicant-type
    3. One representative per novel disagreement cluster
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

CC_OUTPUT_DIR = Path(
    "/Users/chrischen/Library/Mobile Documents/com~apple~CloudDocs/CC Output"
)


def load_verdicts(paths: list[Path]) -> list[dict]:
    """Load all verdicts from one or more Phase 2b results JSONs.

    Each verdict gets its source patent_id, jurisdiction, applicant_type,
    + the ensemble verdict for each finding inside.
    """
    out: list[dict] = []
    for p in paths:
        if not p.exists():
            print(f"  skip (missing): {p}")
            continue
        d = json.loads(p.read_text())
        for entry in d.get("verdicts", []):
            ensemble = entry.get("ensemble", {})
            patent_id = entry.get("patent_id")
            jurisdiction = entry.get("jurisdiction")
            applicant_type = entry.get("applicant_type")
            findings = ensemble.get("findings", [])
            final = ensemble.get("final_verdicts", [])
            sonnet = (ensemble.get("sonnet") or {}).get("verdicts", [])
            gpt = (ensemble.get("gpt_mini") or {}).get("verdicts", [])
            opus = (ensemble.get("opus") or {}).get("verdicts", []) if ensemble.get("opus") else []

            sonnet_by_idx = {i: v for i, v in enumerate(sonnet)}
            gpt_by_idx = {i: v for i, v in enumerate(gpt)}
            opus_by_idx = {i: v for i, v in enumerate(opus)}

            for i, (f, fv) in enumerate(zip(findings, final)):
                s = sonnet_by_idx.get(i)
                g = gpt_by_idx.get(i)
                o = opus_by_idx.get(i)
                out.append({
                    "patent_id": patent_id,
                    "jurisdiction": jurisdiction,
                    "applicant_type": applicant_type,
                    "claim_id": f.get("claim_id"),
                    "term": f.get("term"),
                    "reference_form": f.get("reference_form"),
                    "context_before": f.get("context_before"),
                    "context_after": f.get("context_after"),
                    "final_category": fv.get("category"),
                    "final_reasoning": fv.get("reasoning"),
                    "sonnet_category": s.get("category") if s else None,
                    "sonnet_reasoning": s.get("reasoning") if s else "",
                    "gpt_category": g.get("category") if g else None,
                    "gpt_reasoning": g.get("reasoning") if g else "",
                    "opus_category": o.get("category") if o else None,
                    "opus_reasoning": o.get("reasoning") if o else "",
                    "used_opus": ensemble.get("used_opus", False),
                })
    return out


def sample_unanimous_walker_fp(
    verdicts: list[dict], n: int, seed: int = 20260502
) -> list[dict]:
    """Pass 1: stratified sample of n unanimous walker_fp verdicts.

    Unanimous = Sonnet, gpt-5-mini, and (if used) Opus all said walker_fp.
    Stratified by jurisdiction × applicant_type.
    """
    rng = random.Random(seed)
    candidates = [
        v for v in verdicts
        if v["sonnet_category"] == "walker_fp"
        and v["gpt_category"] == "walker_fp"
        and (v["opus_category"] is None or v["opus_category"] == "walker_fp")
        and v["final_category"] == "walker_fp"
    ]
    if not candidates:
        return []
    by_strat: dict[tuple, list[dict]] = defaultdict(list)
    for c in candidates:
        by_strat[(c["jurisdiction"], c["applicant_type"] or "unknown")].append(c)
    out: list[dict] = []
    strata = list(by_strat.keys())
    rng.shuffle(strata)
    while len(out) < n and any(by_strat.values()):
        for s in strata:
            if not by_strat[s]:
                continue
            out.append(by_strat[s].pop())
            if len(out) >= n:
                break
    return out


def sample_disagreements(
    verdicts: list[dict], n: int, seed: int = 20260502
) -> list[dict]:
    """Pass 2: stratified sample of n disagreement cases.

    Priority order:
    1. Opus-resolved cases where Opus disagreed with both Sonnet and gpt
    2. Sonnet ↔ gpt disagreement (no Opus called or Opus matched one of them)
    3. Novel disagreement clusters (one rep per (final_category, sonnet_cat) pair)
    """
    rng = random.Random(seed)
    # Tier 1: Opus disagrees with both
    tier1 = [
        v for v in verdicts
        if v["used_opus"]
        and v["opus_category"] is not None
        and v["opus_category"] != v["sonnet_category"]
        and v["opus_category"] != v["gpt_category"]
    ]
    # Tier 2: Sonnet/gpt disagreement
    tier2 = [
        v for v in verdicts
        if v["sonnet_category"]
        and v["gpt_category"]
        and v["sonnet_category"] != v["gpt_category"]
        and v not in tier1
    ]
    rng.shuffle(tier1)
    rng.shuffle(tier2)
    out: list[dict] = []
    out.extend(tier1[: max(2, n // 3)])
    out.extend(tier2[: n - len(out)])
    # Dedupe novel clusters: keep at most 2 per (final, sonnet) pair
    cluster_count: Counter = Counter()
    final_out: list[dict] = []
    for v in out:
        key = (v["final_category"], v["sonnet_category"])
        if cluster_count[key] >= 2:
            continue
        cluster_count[key] += 1
        final_out.append(v)
        if len(final_out) >= n:
            break
    return final_out


def render_case(case: dict, idx: int, kind: str) -> str:
    lines = []
    lines.append(f"## Case {idx}: {case['patent_id']} (claim {case['claim_id']}) — `{case['term']}`")
    lines.append(f"_(jurisdiction={case['jurisdiction']}, applicant_type={case['applicant_type']}, kind={kind})_")
    lines.append("")
    lines.append("**Walker finding:**")
    lines.append(f"- term: `{case['term']}`")
    lines.append(f"- reference_form: `{case['reference_form']}`")
    lines.append(f"- context_before: `{case['context_before']}`")
    lines.append(f"- context_after: `{case['context_after']}`")
    lines.append("")
    lines.append(f"**Final verdict:** `{case['final_category']}` "
                 f"(Opus used: {case['used_opus']})")
    lines.append(f"**Final reasoning:** {case['final_reasoning']}")
    lines.append("")
    lines.append(f"**Sonnet:** {case['sonnet_category']} — {case['sonnet_reasoning']}")
    lines.append(f"**gpt-5-mini:** {case['gpt_category']} — {case['gpt_reasoning']}")
    if case["opus_category"]:
        lines.append(f"**Opus:** {case['opus_category']} — {case['opus_reasoning']}")
    lines.append("")
    lines.append("**Christopher's verdict:** [ ] confirm  [ ] contest  [ ] ?  ")
    lines.append("**Note:**")
    lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Phase 2c spot-check checklist from Phase 2b results."
    )
    parser.add_argument(
        "--results",
        nargs="+",
        type=Path,
        required=True,
        help="Phase 2b results JSON file(s) — can pass multiple to combine.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output path for the checklist MD.",
    )
    parser.add_argument(
        "--label",
        type=str,
        default="phase2c",
        help="Label for the checklist title (e.g., 'cn-tw' or 'us').",
    )
    parser.add_argument("--n-unanimous", type=int, default=15)
    parser.add_argument("--n-disagreements", type=int, default=15)
    args = parser.parse_args()

    print(f"Loading results from {args.results}")
    verdicts = load_verdicts(args.results)
    print(f"Loaded {len(verdicts)} finding-level verdicts")

    unanimous = sample_unanimous_walker_fp(verdicts, args.n_unanimous)
    disagreements = sample_disagreements(verdicts, args.n_disagreements)

    print(f"Sampled: {len(unanimous)} unanimous walker_fp, "
          f"{len(disagreements)} disagreements")

    lines: list[str] = []
    lines.append(f"# Phase 2c Spot-Check Checklist — {args.label}")
    lines.append("")
    lines.append("**Date:** 2026-05-02")
    lines.append("**For:** Christopher / Claire — round 1 walker-round trigger evidence sanity check.")
    lines.append("")
    lines.append("**Mark each `[ ]`:**")
    lines.append("- `[confirm]` Verdict is correct — ensemble was right")
    lines.append("- `[contest]` Verdict is wrong — would silence/over-flag")
    lines.append("- `[?]` Genuinely ambiguous")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"## Pass 1 — Unanimous walker_fp confirms ({len(unanimous)} cases)")
    lines.append("")
    lines.append("Quick rubber-stamp pass. ≥80% confirm rate ships the entire walker_fp bucket to walker-round.")
    lines.append("")
    for i, c in enumerate(unanimous, 1):
        lines.append(render_case(c, i, "unanimous_walker_fp"))
    lines.append("")
    lines.append(f"## Pass 2 — High-impact disagreements ({len(disagreements)} cases)")
    lines.append("")
    lines.append("Hand-picked: Opus-disputed (Tier 1) + Sonnet↔gpt disagreement (Tier 2).")
    lines.append("")
    for i, c in enumerate(disagreements, 1):
        lines.append(render_case(c, i, "disagreement"))
    lines.append("")
    lines.append("## Tally to compute when complete")
    lines.append("")
    lines.append(f"- Pass 1: {len(unanimous)} cases — confirm: ___ / contest: ___ / ?: ___")
    lines.append(f"- Pass 2: {len(disagreements)} cases — confirm: ___ / contest: ___ / ?: ___")
    lines.append("")
    lines.append("If Pass 2 contest rate >20%, trigger targeted re-judge (~$8-10).")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Checklist written to {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
