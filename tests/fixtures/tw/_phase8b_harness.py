# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""Phase 8b TW antecedent walker labeled regression harness.

Loads ``tests/fixtures/tw/antecedent_labels.json`` and runs
``check_antecedent_basis`` on the 10-fixture corpus, then diffs walker
output against the labels by ``(fixture, claim_id, term, reference_form)``
tuple. Hard-fails on protect-violations; halts on new (unlabeled)
findings.

This is a standalone test utility, not a pytest test. Underscore-prefixed
so pytest does not collect it.

Run from the project root::

    python tests/fixtures/tw/_phase8b_harness.py --format markdown
    python tests/fixtures/tw/_phase8b_harness.py --format json

Exit codes
==========

* 0 — all gates pass
* 1 — protect_violations > 0 (HARD FAIL)
* 2 — new_findings > 0 (HALT for labeling)
* 3 — fixture or labels file missing, OR structural invariant violation
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# File lives at tests/fixtures/tw/_phase8b_harness.py:
# parents[0]=tw, [1]=fixtures, [2]=tests, [3]=repo root.
_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from patentlint.analysis.tw_claims import check_antecedent_basis  # noqa: E402
from patentlint.parser.docx_loader import load_docx_tw  # noqa: E402
from patentlint.parser.sections_tw import extract_tw_sections  # noqa: E402

LABELS_PATH = _REPO_ROOT / "tests/fixtures/tw/antecedent_labels.json"

# The fixture-path map lives in the gitignored postship baseline. The
# harness reads only the fixture key → fixture_path mapping; the actual
# walker output is recomputed from disk on every run.
FIXTURE_INDEX = (
    _REPO_ROOT / "tests/fixtures/tw/local/baseline_phase8b_postship.json"
)


# ── Helpers ──────────────────────────────────────────────────────────────


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
        sys.exit(3)
    with LABELS_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _load_fixture_index() -> dict:
    if not FIXTURE_INDEX.exists():
        print(
            f"FATAL: fixture index not found at {FIXTURE_INDEX}\n"
            f"  (run tests/fixtures/tw/local/_capture_baseline_postship.py first)",
            file=sys.stderr,
        )
        sys.exit(3)
    with FIXTURE_INDEX.open(encoding="utf-8") as fh:
        return json.load(fh)


def _walker_actual_set(index: dict) -> tuple[dict[tuple, dict], int]:
    """Run check_antecedent_basis on every fixture and return the
    (key → issue dict) map plus the number of fixtures processed.

    Each issue dict from the walker has keys
    ``{claim_id, term, reference_form, claim_text, suggested_match,
    cross_ref}``. We key by ``(fixture_key, claim_id, term, reference_form)``
    so the harness can diff against the labels file directly.
    """
    actual: dict[tuple, dict] = {}
    fixture_count = 0
    for key, rec in index["fixtures"].items():
        fixture_path = (_REPO_ROOT / rec["fixture_path"]).resolve()
        if not fixture_path.exists():
            print(
                f"FATAL: fixture {key!r} missing on disk at {fixture_path}",
                file=sys.stderr,
            )
            sys.exit(3)
        loaded = load_docx_tw(fixture_path)
        doc = extract_tw_sections(loaded.paragraphs)
        for issue in check_antecedent_basis(doc):
            tup = (
                key,
                issue["claim_id"],
                issue["term"],
                issue["reference_form"],
            )
            actual[tup] = issue
        fixture_count += 1
    return actual, fixture_count


def _check_structural_invariants(labels: list[dict]) -> None:
    """Exit 3 if any label has both protect:true and resolved_by set."""
    for lab in labels:
        if lab.get("protect") and lab.get("resolved_by"):
            tup = (
                lab["fixture"],
                lab["claim_id"],
                lab["term"],
                lab["reference_form"],
            )
            print(
                f"STRUCTURAL FAIL: protect:true entry has resolved_by set: {tup}",
                file=sys.stderr,
            )
            sys.exit(3)


def _compute_diff(labels_doc: dict, actual: dict[tuple, dict]) -> dict:
    """Build the diff payload (gates + per-category stats + delta lists)."""
    labels = labels_doc["labels"]
    categories = labels_doc["metadata"]["categories"]

    active_labels = [lab for lab in labels if not lab.get("resolved_by")]
    resolved_labels = [lab for lab in labels if lab.get("resolved_by")]

    expected_map: dict[tuple, dict] = {}
    protected: set[tuple] = set()
    for lab in active_labels:
        key = (
            lab["fixture"],
            lab["claim_id"],
            lab["term"],
            lab["reference_form"],
        )
        expected_map[key] = lab
        if lab.get("protect") is True:
            protected.add(key)

    expected = set(expected_map.keys())
    actual_keys = set(actual.keys())

    new_findings = sorted(actual_keys - expected)
    removed_findings = sorted(expected - actual_keys)
    protect_violations = [k for k in removed_findings if k in protected]

    cat_stats: dict[str, dict[str, int]] = {
        cat["id"]: {
            "labeled": 0,
            "still_flagged": 0,
            "removed": 0,
            "removed_protected": 0,
        }
        for cat in categories
    }
    for lab in labels:
        cid = lab["category"]
        if cid not in cat_stats:
            continue
        cat_stats[cid]["labeled"] += 1
        key = (
            lab["fixture"],
            lab["claim_id"],
            lab["term"],
            lab["reference_form"],
        )
        if key in actual_keys:
            cat_stats[cid]["still_flagged"] += 1
        else:
            cat_stats[cid]["removed"] += 1
            if lab.get("protect") is True:
                cat_stats[cid]["removed_protected"] += 1

    return {
        "categories": [c["id"] for c in categories],
        "cat_stats": cat_stats,
        "expected_map": expected_map,
        "actual_keys": actual_keys,
        "expected": expected,
        "new_findings": new_findings,
        "removed_findings": removed_findings,
        "protect_violations": protect_violations,
        "protected": protected,
        "active_count": len(active_labels),
        "resolved_count": len(resolved_labels),
        "resolved_labels": resolved_labels,
    }


def _exit_code(diff: dict) -> int:
    if diff["protect_violations"]:
        return 1
    if diff["new_findings"]:
        return 2
    return 0


# ── Renderers ────────────────────────────────────────────────────────────


def _render_markdown(
    labels_doc: dict, diff: dict, fixture_count: int, commit: str
) -> str:
    labels = labels_doc["labels"]
    schema_version = labels_doc["metadata"]["schema_version"]
    actual_keys = diff["actual_keys"]
    new_findings = diff["new_findings"]
    removed_findings = diff["removed_findings"]
    protect_violations = diff["protect_violations"]
    cat_stats = diff["cat_stats"]
    expected_map = diff["expected_map"]

    out: list[str] = []
    out.append("# Phase 8b harness report")
    out.append("")
    out.append(f"**Commit**: {commit}")
    out.append(f"**Labels version**: {schema_version}")
    active_count = diff["active_count"]
    resolved_count = diff["resolved_count"]
    out.append(
        f"**Label count**: {len(labels)} "
        f"({active_count} active, {resolved_count} resolved)"
    )
    out.append(f"**Fixture count**: {fixture_count}")
    out.append(f"**Walker finding count**: {len(actual_keys)}")
    out.append("")
    out.append("## Gates")
    out.append("")
    nf_status = "PASS" if not new_findings else "FAIL"
    pv_status = "PASS" if not protect_violations else "FAIL"
    out.append(
        f"- [{nf_status}] new_findings: {len(new_findings)} (HALT if > 0)"
    )
    out.append(
        f"- [{pv_status}] protect_violations: {len(protect_violations)} "
        f"(HARD FAIL if > 0)"
    )
    out.append("")
    out.append("## Category distribution")
    out.append("")
    out.append(
        "| category | labeled | still_flagged | removed | removed_protected |"
    )
    out.append("|---|---:|---:|---:|---:|")
    for cid in diff["categories"]:
        s = cat_stats[cid]
        out.append(
            f"| {cid} | {s['labeled']} | {s['still_flagged']} | "
            f"{s['removed']} | {s['removed_protected']} |"
        )
    out.append("")
    out.append("## Resolved entries")
    out.append("")
    resolved_labels = diff["resolved_labels"]
    if resolved_labels:
        out.append("| fixture | claim | term | category | resolved_by |")
        out.append("|---|---|---|---|---|")
        for lab in resolved_labels:
            out.append(
                f"| {lab['fixture']} | {lab['claim_id']} | {lab['term']} | "
                f"{lab['category']} | {lab['resolved_by']} |"
            )
    else:
        out.append("None")
    out.append("")
    out.append("## New findings (unlabeled) — HALT if any")
    out.append("")
    if new_findings:
        out.append("| fixture | claim | term | ref_form |")
        out.append("|---|---|---|---|")
        for k in new_findings:
            out.append(f"| {k[0]} | {k[1]} | {k[2]} | {k[3]} |")
    else:
        out.append("None")
    out.append("")
    out.append("## Removed findings")
    out.append("")
    if removed_findings:
        out.append(
            "| fixture | claim | term | ref_form | category | protected |"
        )
        out.append("|---|---|---|---|---|---|")
        for k in removed_findings:
            lab = expected_map[k]
            out.append(
                f"| {k[0]} | {k[1]} | {k[2]} | {k[3]} | "
                f"{lab['category']} | {lab.get('protect', False)} |"
            )
    else:
        out.append("None")
    out.append("")
    out.append("## Protect violations — HARD FAIL if any")
    out.append("")
    if protect_violations:
        out.append("| fixture | claim | term | category | notes |")
        out.append("|---|---|---|---|---|")
        for k in protect_violations:
            lab = expected_map[k]
            out.append(
                f"| {k[0]} | {k[1]} | {k[2]} | "
                f"{lab['category']} | {lab.get('notes', '')} |"
            )
    else:
        out.append("None")
    out.append("")

    return "\n".join(out)


def _render_json(
    labels_doc: dict, diff: dict, fixture_count: int, commit: str, exit_code: int
) -> str:
    labels = labels_doc["labels"]
    schema_version = labels_doc["metadata"]["schema_version"]
    actual_keys = diff["actual_keys"]
    new_findings = diff["new_findings"]
    removed_findings = diff["removed_findings"]
    protect_violations = diff["protect_violations"]
    cat_stats = diff["cat_stats"]
    expected_map = diff["expected_map"]

    active_count = diff["active_count"]
    resolved_count = diff["resolved_count"]
    payload = {
        "commit": commit,
        "labels_version": schema_version,
        "label_count": len(labels),
        "active_count": active_count,
        "resolved_count": resolved_count,
        "fixture_count": fixture_count,
        "walker_finding_count": len(actual_keys),
        "gates": {
            "new_findings": {
                "count": len(new_findings),
                "pass": len(new_findings) == 0,
            },
            "protect_violations": {
                "count": len(protect_violations),
                "pass": len(protect_violations) == 0,
            },
        },
        "category_distribution": [
            {"category": cid, **cat_stats[cid]} for cid in diff["categories"]
        ],
        "new_findings": [
            {
                "fixture": k[0],
                "claim_id": k[1],
                "term": k[2],
                "reference_form": k[3],
            }
            for k in new_findings
        ],
        "removed_findings": [
            {
                "fixture": k[0],
                "claim_id": k[1],
                "term": k[2],
                "reference_form": k[3],
                "category": expected_map[k]["category"],
                "protect": expected_map[k].get("protect", False),
            }
            for k in removed_findings
        ],
        "protect_violations": [
            {
                "fixture": k[0],
                "claim_id": k[1],
                "term": k[2],
                "reference_form": k[3],
                "category": expected_map[k]["category"],
                "notes": expected_map[k].get("notes", ""),
            }
            for k in protect_violations
        ],
        "resolved_entries": [
            {
                "fixture": lab["fixture"],
                "claim_id": lab["claim_id"],
                "term": lab["term"],
                "reference_form": lab["reference_form"],
                "category": lab["category"],
                "resolved_by": lab["resolved_by"],
            }
            for lab in diff["resolved_labels"]
        ],
        "exit_code": exit_code,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


# ── Driver ───────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Phase 8b TW antecedent walker labeled regression harness"
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Report format (default: markdown)",
    )
    args = parser.parse_args()

    labels_doc = _load_labels()
    _check_structural_invariants(labels_doc["labels"])
    index = _load_fixture_index()
    actual, fixture_count = _walker_actual_set(index)
    diff = _compute_diff(labels_doc, actual)
    exit_code = _exit_code(diff)
    commit = _git_head()

    if args.format == "json":
        print(_render_json(labels_doc, diff, fixture_count, commit, exit_code))
    else:
        print(_render_markdown(labels_doc, diff, fixture_count, commit))

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
