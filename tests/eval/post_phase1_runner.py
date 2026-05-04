# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Post-Phase-1 orchestrator.

When the Phase 1 background re-judging run produces
`tests/eval/phase2b_results_supplement_v2.json`, this script:

1. Runs `calibrate_confidence_threshold` and writes a per-jurisdiction
   precision-by-bucket report
2. Runs `discover_clusters` and writes per-jurisdiction
   safe-silence + recall-mining cluster reports
3. Generates a single summary writeup in CC Output indexing all
   reports + recommended next-step commit set

Idempotent: each report writes to a deterministic filename. Re-runs
safely overwrite outputs.

Usage:
    python -m tests.eval.post_phase1_runner

    # or with a specific verdicts file:
    python -m tests.eval.post_phase1_runner \\
        tests/eval/phase2b_results_supplement_v2.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

PATENTLINT_ROOT = Path("/Users/chrischen/Documents/Projects/Patent-Lint")
ICLOUD_OUT = Path(
    "/Users/chrischen/Library/Mobile Documents/com~apple~CloudDocs/CC Output"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Post-Phase-1 orchestrator: calibration + clusters + summary."
    )
    parser.add_argument(
        "verdicts_path",
        nargs="?",
        default=str(PATENTLINT_ROOT / "tests/eval/phase2b_results_supplement_v2.json"),
        help="Path to phase2b_results JSON (default: supplement_v2)."
    )
    args = parser.parse_args()

    verdicts_path = Path(args.verdicts_path)
    if not verdicts_path.exists():
        print(f"ERROR: verdicts file not found at {verdicts_path}", file=sys.stderr)
        print(
            "Phase 1 background run may not have completed yet. Check "
            "/tmp/phase2b_supplement_v2.log for progress.",
            file=sys.stderr
        )
        return 1

    today = date.today().isoformat()
    stem = verdicts_path.stem  # e.g. "phase2b_results_supplement_v2"

    calib_json = PATENTLINT_ROOT / f"tests/eval/{stem}_calibration.json"
    calib_md = ICLOUD_OUT / f"{today}_{stem}_calibration.md"
    cluster_md = ICLOUD_OUT / f"{today}_{stem}_clusters.md"
    cluster_json = PATENTLINT_ROOT / f"tests/eval/{stem}_clusters.json"
    summary_md = ICLOUD_OUT / f"{today}_{stem}_summary.md"

    print(f"[1/3] Running calibration → {calib_md}")
    from tests.eval.calibrate_confidence_threshold import calibrate, render_report as render_calib
    calib_result = calibrate(verdicts_path)
    calib_json.write_text(
        json.dumps(calib_result, ensure_ascii=False, indent=2)
    )
    calib_md.write_text(render_calib(calib_result), encoding="utf-8")

    print(f"[2/3] Running cluster discovery → {cluster_md}")
    from tests.eval.discover_clusters import discover, render_report as render_clusters
    cluster_result = discover(verdicts_path, top_n=30)
    cluster_json.write_text(
        json.dumps(cluster_result, ensure_ascii=False, indent=2, default=str)
    )
    cluster_md.write_text(render_clusters(cluster_result), encoding="utf-8")

    print(f"[3/3] Writing summary → {summary_md}")
    lines: list[str] = []
    lines.append(f"# Post-Phase-1 analysis summary — {today}\n")
    lines.append(f"Source verdicts: `{verdicts_path}`\n")
    lines.append(f"- Drafts judged: {len(calib_result.get('per_jurisdiction', {}))}\n")
    lines.append("\n## Per-jurisdiction precision summary\n")
    lines.append("| Juris | Total | legit | wfp | coverage | absolute_strict | suggested T_high |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for juris, p in sorted(calib_result.get("per_jurisdiction", {}).items()):
        # Find first threshold ≥70% precision with bucket_size ≥10
        suggested = None
        for row in p.get("by_threshold", []):
            if row["bucket_precision"] >= 0.70 and row["bucket_size"] >= 10:
                suggested = row["threshold"]
                break
        lines.append(
            f"| {juris} | {p['total_findings']} | {p['legit_drafting_error']} | "
            f"{p['walker_fp']} | {p['coverage_gap']} | "
            f"{100*p['absolute_strict_precision']:.1f}% | "
            f"{suggested if suggested else 'N/A'} |"
        )

    lines.append("\n## Reports\n")
    lines.append(f"- Calibration: [`{calib_md.name}`]({calib_md})")
    lines.append(f"- Clusters: [`{cluster_md.name}`]({cluster_md})")
    lines.append(f"- Calibration JSON: `{calib_json}`")
    lines.append(f"- Clusters JSON: `{cluster_json}`")

    lines.append("\n## Recommended next commits\n")
    lines.append("1. **Phase 5 threshold calibration commit** — update `frontend/src/lib/confidenceTier.js::TIER_THRESHOLDS` per-jurisdiction with the suggested T_high values from the table above. Also update `analysis/utils.py::compute_confidence_score` if signal correlation analysis (see `feedback_target_metric_high_conf_bucket.md`) recommends signal direction flips.")
    lines.append("2. **Phase 3 walker recall mining commits** — pick top 3-5 safe-silence clusters (≥10 wfp + 0 legit + currently emitted) from the cluster report. Each cluster gets one walker commit with full 4-gate validation. ADR-111 dual-labeling required for shifting changes.")
    lines.append("3. **Phase 2 walker prefix-fallback tightening** — review cluster exemplars for over-bridge classes (short-Latin-uppercase + CJK residual; short intro + ≥2× longer reference). One commit per shape, ADR-111 dual-labeling.")
    lines.append("4. **Phase 5 frontend tier rendering** — once thresholds are known and the formula is validated, integrate `confidenceTier` helper into `AntecedentBasisCard.jsx`. Add tier-disclosure UX (default-show high-conf, collapse medium under 'Less certain', hide low). Locale strings × 6 (en/de/zh-TW/zh-CN/ja/ko) per ADR-085 + ADR-144 native register.")

    lines.append("\n## Halt conditions to verify before next steps\n")
    lines.append("- [ ] Phase 1 cost stayed under $120 cap")
    lines.append("- [ ] No `protect_violation` introduced in Phase 0/4/5 commits (verified via harness gates per-commit)")
    lines.append("- [ ] Pytest 2229+ passing (current suite size; verify post-commit)")
    lines.append("- [ ] All 3 harnesses (CN/TW/US) report `protect_violations: 0`")

    summary_md.write_text("\n".join(lines), encoding="utf-8")
    print("\nDone.")
    print(f"Summary: {summary_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
