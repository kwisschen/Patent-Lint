# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""Phase 1 US antecedent walker labeled regression harness (bootstrap).

Structural port of ``tests/fixtures/{cn,tw}/_phase{8c,8b}_harness.py``
adapted to the US bootstrap shape:

* **Fixture pool** is the Patent-Analyst round-1 corpus (parquet records),
  not local docx files. The 705 US drafts are loaded via
  ``round1_corpus_harness.load_corpus('US')``; each ``patent_id`` is the
  fixture key.
* **Labels file** is ``tests/fixtures/us/antecedent_labels_us.json``,
  built from Phase 2b ensemble verdicts via
  ``scripts/bootstrap_us_labels.py``. Labels are seeded with
  ``confidence: phase2b_ensemble_confN`` and ``round: 0`` (sentinel for
  unmutated bootstrap state).
* **Walker entry point** is ``check_antecedent_basis(claims)`` — takes
  ``list[Claim]`` directly (no UsPatentDocument wrapper).

Three gates (parity with CN/TW):

* ``unresolved_new`` — walker emitted a finding NOT in labels file.
* ``unresolved_removed`` — labels file has finding walker no longer emits.
* ``protect_violations`` — protect:true label silenced. HARD FAIL.

Standalone utility. Underscore-prefixed so pytest does not collect.

Run::

    python tests/fixtures/us/_phase1_harness.py
    python tests/fixtures/us/_phase1_harness.py --format json
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

from patentlint.analysis.claims import check_antecedent_basis  # noqa: E402
from tests.eval.round1_corpus_harness import load_corpus, _build_doc  # noqa: E402

LABELS_PATH = _REPO_ROOT / "tests/fixtures/us/antecedent_labels_us.json"


def _git_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(_REPO_ROOT), text=True
        ).strip()
    except Exception:
        return "unknown"


def _load_labels() -> dict:
    if not LABELS_PATH.exists():
        print(f"FATAL: labels file not found at {LABELS_PATH}", file=sys.stderr)
        print("  Run: python scripts/bootstrap_us_labels.py", file=sys.stderr)
        sys.exit(3)
    with LABELS_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _walker_actual_set() -> tuple[dict[tuple, dict], int]:
    """Run check_antecedent_basis on the round-1 US corpus.

    Returns (key_to_issue_dict, fixture_count) where each key is
    ``(patent_id, claim_id, term, reference_form)``.
    """
    drafts = load_corpus("US")
    actual: dict[tuple, dict] = {}
    fixture_count = 0
    for rec in drafts:
        pid = rec.get("patent_id")
        if not pid:
            continue
        claims = _build_doc(rec, "US")
        if claims is None:
            continue
        try:
            results = check_antecedent_basis(claims)
        except Exception:
            continue
        for issue in results:
            if not isinstance(issue, dict):
                continue
            tup = (
                pid,
                issue.get("claim_id"),
                issue.get("term"),
                issue.get("reference_form"),
            )
            actual[tup] = issue
        fixture_count += 1
    return actual, fixture_count


def _label_keys(labels_obj: dict) -> tuple[set[tuple], dict[tuple, dict]]:
    by_key: dict[tuple, dict] = {}
    keys: set[tuple] = set()
    for lab in labels_obj.get("labels", []):
        key = (
            lab.get("fixture"),
            lab.get("claim_id"),
            lab.get("term"),
            lab.get("reference_form"),
        )
        keys.add(key)
        by_key[key] = lab
    return keys, by_key


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args()

    labels_obj = _load_labels()
    label_keys, label_by_key = _label_keys(labels_obj)
    actual_by_key, fixture_count = _walker_actual_set()
    actual_keys = set(actual_by_key.keys())

    # Active = not yet resolved (resolved_by is None or 0). Bootstrap
    # state has resolved_by == None across the board.
    active_keys = {k for k, lab in label_by_key.items() if not lab.get("resolved_by")}

    new_findings = actual_keys - label_keys  # walker emits, labels don't have
    removed_findings = active_keys - actual_keys  # labels have, walker no longer emits
    protected_drops = {
        k for k in removed_findings if label_by_key[k].get("protect")
    }

    unresolved_new = len(new_findings)
    unresolved_removed = len(removed_findings - protected_drops)
    protect_violations = len(protected_drops)

    head = _git_head()
    if args.format == "json":
        print(json.dumps({
            "git_head": head,
            "fixture_count": fixture_count,
            "unresolved_new": unresolved_new,
            "unresolved_removed": unresolved_removed,
            "protect_violations": protect_violations,
            "label_keys_count": len(label_keys),
            "active_keys_count": len(active_keys),
            "actual_keys_count": len(actual_keys),
        }, indent=2))
    else:
        print("# US Phase 1 Walker Harness")
        print(f"\n- git head: {head}")
        print(f"- fixture count: {fixture_count}")
        print(f"- labels total: {len(label_keys)} ({len(active_keys)} active)")
        print(f"- walker findings: {len(actual_keys)}")
        print()
        print(
            f"- [{'PASS' if unresolved_new == 0 else 'FAIL'}] "
            f"unresolved_new: {unresolved_new} "
            f"(HALT if > 0; new walker findings not in labels)"
        )
        print(
            f"- [{'PASS' if unresolved_removed == 0 else 'FAIL'}] "
            f"unresolved_removed: {unresolved_removed} "
            f"(HALT if > 0; labels missing from walker — non-protected)"
        )
        print(
            f"- [{'PASS' if protect_violations == 0 else 'FAIL'}] "
            f"protect_violations: {protect_violations} "
            f"(HARD FAIL if > 0; protect:true label silenced)"
        )
        print()
        if protect_violations > 0:
            print("## Protect violations — HARD FAIL")
            print("| fixture | claim | term | category | notes |")
            print("|---|---|---|---|---|")
            for k in sorted(protected_drops)[:50]:
                lab = label_by_key[k]
                print(
                    f"| {k[0]} | {k[1]} | {k[2]} | "
                    f"{lab.get('category', '')} | {lab.get('notes', '')[:80]} |"
                )

    if protect_violations > 0:
        return 1
    if unresolved_new > 0 or unresolved_removed > 0:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
