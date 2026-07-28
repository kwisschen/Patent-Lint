# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
"""TW spec-support drift-test harness (lightweight).

Mirrors `_phase8b_harness.py` (antecedent walker) but for the spec-support
extractor (`check_spec_support_tw`). Bootstrapped 2026-05-29 to enable
the spec-support FP drain accumulated in the report queue (#106, #108,
#130, #133 already shipped via PR #144; #107, #109, #110, #111, #129,
#131, #132 pending).

Differs from the antecedent harness in that there is no labels file with
`protect:true` / `legit_drafting_error` categories - the spec-support
domain is simpler (no chain inheritance, no parallel-invention nuance).
Drift detection compares current findings to a committed baseline:

  - **Removed findings** = walker silenced something it used to emit.
    Good when intended (a fix is silencing FPs); flag for human review
    if a fix wasn't expected to touch it.
  - **Added findings** = walker now emits something new. ALMOST ALWAYS
    a regression. HARD FAIL.

Usage:

    # Capture a fresh baseline (e.g., after a labels reset):
    python tests/fixtures/tw/_spec_support_harness.py --capture

    # Drift-check (default): compare current walker output against baseline:
    python tests/fixtures/tw/_spec_support_harness.py --format json

Exit codes:

  * 0 - drift gates pass (added == 0; removed counted but informational)
  * 1 - added > 0 (HARD FAIL, regression)
  * 3 - fixture index missing on disk
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT))

from patentlint.analysis.tw_spec_support import check_spec_support_tw  # noqa: E402
from patentlint.parser.docx_loader import load_docx_tw  # noqa: E402
from patentlint.parser.sections_tw import extract_tw_sections  # noqa: E402

# Re-use the antecedent harness's fixture index - same set of TW docx
# fixtures, same fixture-key scheme. Bootstrapping a separate index file
# would diverge the two harnesses pointlessly.
FIXTURE_INDEX = (
    _REPO_ROOT / "tests/fixtures/tw/local/baseline_phase8b_postship.json"
)
BASELINE_PATH = _REPO_ROOT / "tests/fixtures/tw/spec_support_baseline.json"


def _git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, check=False,
    ).stdout.strip() or "unknown"


def _load_fixture_index() -> dict:
    if not FIXTURE_INDEX.exists():
        print(
            f"FATAL: fixture index not found at {FIXTURE_INDEX}\n"
            "  (run tests/fixtures/tw/local/_capture_baseline_postship.py first)",
            file=sys.stderr,
        )
        sys.exit(3)
    return json.loads(FIXTURE_INDEX.read_text())


def _walker_findings(index: dict) -> dict[str, list[dict]]:
    """Run check_spec_support_tw on every fixture; return
    {fixture_key: [{claim_id, phrase}, ...]}. Skips synthetic / tw_contamination
    fixtures (those are CN-side artifacts in the shared index)."""
    findings: dict[str, list[dict]] = {}
    for key, rec in index["fixtures"].items():
        if key.startswith("tw_contamination"):
            continue
        fixture_path = (_REPO_ROOT / rec["fixture_path"]).resolve()
        if not fixture_path.exists():
            print(f"WARN: fixture {key!r} missing at {fixture_path}", file=sys.stderr)
            continue
        loaded = load_docx_tw(fixture_path)
        doc = extract_tw_sections(loaded.paragraphs)
        per_fixture: list[dict] = []
        for ut in check_spec_support_tw(doc):
            per_fixture.append({
                "claim_id": ut.claim_number,
                "phrase": ut.phrase,
            })
        # Sort for stable diffs across runs
        per_fixture.sort(key=lambda d: (d["claim_id"], d["phrase"]))
        findings[key] = per_fixture
    return findings


def _capture(index: dict) -> None:
    findings = _walker_findings(index)
    total = sum(len(v) for v in findings.values())
    snapshot = {
        "metadata": {
            "commit": _git_head(),
            "fixture_count": len(findings),
            "total_findings": total,
            "implementation_function": (
                "patentlint.analysis.tw_spec_support.check_spec_support_tw"
            ),
            "note": (
                "Drift baseline for TW spec-support extractor. Captured via "
                "tests/fixtures/tw/_spec_support_harness.py --capture. "
                "Re-capture after every walker change that intentionally "
                "shifts the spec-support output set."
            ),
        },
        "fixtures": findings,
    }
    BASELINE_PATH.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n"
    )
    print(f"Captured baseline: {total} findings across {len(findings)} fixtures.")
    print(f"  → {BASELINE_PATH}")


def _compare(index: dict, fmt: str) -> int:
    if not BASELINE_PATH.exists():
        print(
            f"FATAL: baseline snapshot not found at {BASELINE_PATH}\n"
            "  (run this harness with --capture first)",
            file=sys.stderr,
        )
        return 3
    baseline = json.loads(BASELINE_PATH.read_text())
    baseline_set: set[tuple] = set()
    for key, items in baseline["fixtures"].items():
        for it in items:
            baseline_set.add((key, it["claim_id"], it["phrase"]))
    current_findings = _walker_findings(index)
    current_set: set[tuple] = set()
    for key, items in current_findings.items():
        for it in items:
            current_set.add((key, it["claim_id"], it["phrase"]))
    removed = sorted(baseline_set - current_set)
    added = sorted(current_set - baseline_set)
    head = _git_head()
    if fmt == "json":
        print(json.dumps({
            "git_head": head,
            "fixture_count": len(current_findings),
            "baseline_count": len(baseline_set),
            "current_count": len(current_set),
            "removed_count": len(removed),
            "added_count": len(added),
            "removed_sample": [
                {"fixture": r[0], "claim_id": r[1], "phrase": r[2]} for r in removed[:20]
            ],
            "added_sample": [
                {"fixture": a[0], "claim_id": a[1], "phrase": a[2]} for a in added[:20]
            ],
            "added_is_hard_fail": True,
        }, indent=2, ensure_ascii=False))
    else:
        print("# TW spec-support drift report")
        print(f"- commit: `{head}`")
        print(f"- baseline findings: {len(baseline_set)}")
        print(f"- current findings: {len(current_set)}")
        print(f"- removed: **{len(removed)}** (silenced - review intent)")
        print(f"- added: **{len(added)}** (regression - HARD FAIL if > 0)")
        if removed:
            print("\n## Removed (sample)")
            for r in removed[:20]:
                print(f"- `{r[0]}` c{r[1]} `{r[2]}`")
        if added:
            print("\n## Added (regression)")
            for a in added[:20]:
                print(f"- `{a[0]}` c{a[1]} `{a[2]}`")
    return 1 if added else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", action="store_true",
                        help="Capture a fresh baseline (overwrites existing).")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args()
    index = _load_fixture_index()
    if args.capture:
        _capture(index)
        return 0
    return _compare(index, args.format)


if __name__ == "__main__":
    sys.exit(main())
