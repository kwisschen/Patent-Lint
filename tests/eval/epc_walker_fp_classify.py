# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""Run the EPC walker against the corpus produced by epc_corpus_pull.py
and produce a classification + threshold-calibration JSON.

For each .txt fixture in tests/fixtures/epc/local/:
  1. Parse claims via parse_claims_epc
  2. Run check_antecedent_basis_epc + check_spec_support_epc
  3. Tag every finding with metadata (claim_id, term, confidence)
  4. Aggregate counts per draft + global precision baseline

Output: tests/fixtures/epc/local/walker_calibration.json with:
  - per-draft finding counts
  - global walker output (totals across all drafts)
  - candidate threshold cutoffs at p25/p50/p75/p90 confidence

This mirrors the CN/TW phase-2b calibration pattern but without
LLM verdicts — the EPC walker FP rate measurement v1 only produces
the confidence-distribution surface, leaving verdict labels to a
manual spot-check or a future LLM judge pass.

Usage:
  python3 tests/eval/epc_walker_fp_classify.py
  python3 tests/eval/epc_walker_fp_classify.py --corpus tests/fixtures/epc/local
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from patentlint.analysis.epc_claims import (
    check_antecedent_basis_epc,
    check_spec_support_epc,
)
from patentlint.parser.claims_epc import parse_claims_epc
from patentlint.parser.sections_epc import (
    extract_claims_section_epc,
    extract_description_section_epc,
)


def classify_corpus(corpus_dir: Path) -> dict:
    """Run the EPC walker over every .txt fixture and aggregate findings."""
    results: dict = {
        "per_draft": [],
        "totals": {
            "drafts": 0,
            "antecedent_findings": 0,
            "spec_support_findings": 0,
            "drafts_with_zero_findings": 0,
        },
        "confidence_distribution": Counter(),
    }

    txt_files = sorted(corpus_dir.glob("*.txt"))
    if not txt_files:
        return results

    for txt_path in txt_files:
        full_text = txt_path.read_text(encoding="utf-8")
        claims_section = extract_claims_section_epc(full_text)
        description = extract_description_section_epc(full_text)
        claims = parse_claims_epc(claims_section)
        if not claims:
            results["per_draft"].append({
                "pub": txt_path.stem,
                "skipped": "no_claims_parsed",
            })
            continue

        _, ab_issues = check_antecedent_basis_epc(claims)
        _, ss_terms = check_spec_support_epc(claims, description)

        per_draft = {
            "pub": txt_path.stem,
            "claim_count": len(claims),
            "ab_count": len(ab_issues),
            "ss_count": len(ss_terms),
            "word_count": len(full_text.split()),
        }

        # Confidence distribution for antecedent findings — used to
        # calibrate TIER_THRESHOLDS.EPC
        for issue in ab_issues:
            if isinstance(issue, dict):
                conf = issue.get("confidence_score")
                if isinstance(conf, (int, float)):
                    bucket = int(conf // 10) * 10
                    results["confidence_distribution"][bucket] += 1

        results["per_draft"].append(per_draft)
        results["totals"]["drafts"] += 1
        results["totals"]["antecedent_findings"] += len(ab_issues)
        results["totals"]["spec_support_findings"] += len(ss_terms)
        if not ab_issues and not ss_terms:
            results["totals"]["drafts_with_zero_findings"] += 1

    # Convert Counter to dict for JSON serialisation
    results["confidence_distribution"] = dict(sorted(results["confidence_distribution"].items()))

    # Derive percentile thresholds from the confidence distribution
    total_findings = sum(results["confidence_distribution"].values())
    if total_findings > 0:
        # Cumulative distribution
        cumulative = 0
        percentile_marks = {}
        for bucket in sorted(results["confidence_distribution"].keys()):
            cumulative += results["confidence_distribution"][bucket]
            pct = cumulative / total_findings * 100
            percentile_marks[bucket] = pct
        results["percentile_marks"] = percentile_marks

        # Suggest TIER_THRESHOLDS based on distribution: high tier at the
        # top 25% of findings, low tier excludes the bottom 25%.
        thresholds: list[int] = []
        cumulative = 0
        sorted_buckets = sorted(results["confidence_distribution"].keys())
        for target_pct in [25, 50, 75, 90]:
            cum = 0
            for bucket in sorted_buckets:
                cum += results["confidence_distribution"][bucket]
                if cum / total_findings * 100 >= target_pct:
                    thresholds.append(bucket)
                    break
        if len(thresholds) == 4:
            results["suggested_thresholds"] = {
                "p25": thresholds[0],
                "p50": thresholds[1],
                "p75": thresholds[2],
                "p90": thresholds[3],
                "recommended_TIER_THRESHOLDS_EPC": {
                    "high": thresholds[2],   # p75 — top quartile
                    "low": thresholds[0],    # p25 — exclude bottom
                },
            }

    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=Path("tests/fixtures/epc/local"))
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    if not args.corpus.is_dir():
        print(f"Corpus directory not found: {args.corpus}")
        return 1

    results = classify_corpus(args.corpus)
    out_path = args.output or (args.corpus / "walker_calibration.json")
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    totals = results["totals"]
    print(f"Drafts analyzed: {totals['drafts']}")
    print(f"Antecedent findings: {totals['antecedent_findings']}")
    print(f"Spec support findings: {totals['spec_support_findings']}")
    print(f"Drafts with zero findings: {totals['drafts_with_zero_findings']}")
    if "suggested_thresholds" in results:
        suggested = results["suggested_thresholds"]["recommended_TIER_THRESHOLDS_EPC"]
        print(f"Suggested TIER_THRESHOLDS.EPC: {suggested}")
    print(f"Full report at: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
