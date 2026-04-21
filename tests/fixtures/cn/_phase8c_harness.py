# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Phase 8c CN antecedent walker labeled regression harness.

Structural port of ``tests/fixtures/tw/_phase8b_harness.py`` (Phase 8b).
Loads ``tests/fixtures/cn/antecedent_labels_cn.json`` and runs
``check_antecedent_basis_cn`` on the 10 real CN fixtures + 3 synthetic
tw_contamination fixtures, then diffs walker output against the labels
by ``(fixture, claim_id, term, reference_form)`` tuple.

Two documented divergences from the TW harness:

* **ADR-110** — strict category validation. Unknown ``category`` values
  exit 3 at load time. TW silently passes them through
  (``_phase8b_harness.py`` line 176). Validator lives inside
  ``_check_structural_invariants_cn``.

* **ADR-111** — ``round`` field + bidirectional halt with per-round
  ``resolved_by`` satisfaction. Additions halt unless every new finding
  matches a current-round ``resolved_by``; unprotected drops halt unless
  every removed finding matches a current-round ``resolved_by``.
  Protect_violations (protected drops) remain hard-fail exit 1 with NO
  ``resolved_by`` escape hatch even if round matches. TW has no round
  field; TW halts one-directionally on additions only (plus exit-1 on
  protected drops).

Standalone test utility, not a pytest test. Underscore-prefixed filename
so pytest does not collect it.

Run from the project root::

    python tests/fixtures/cn/_phase8c_harness.py --format markdown
    python tests/fixtures/cn/_phase8c_harness.py --format json

Exit codes
==========

* 0 — all gates pass
* 1 — protect_violations > 0 (HARD FAIL, no resolved_by escape hatch)
* 2 — unresolved new/removed findings > 0 (HALT for labeling)
* 3 — fixture or labels file missing, OR structural invariant violation
      (includes unknown category id per ADR-110)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# File lives at tests/fixtures/cn/_phase8c_harness.py:
# parents[0]=cn, [1]=fixtures, [2]=tests, [3]=repo root.
_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from patentlint.analysis.cn_claims import check_antecedent_basis_cn  # noqa: E402
from patentlint.parser.docx_loader import load_docx_cn  # noqa: E402
from patentlint.parser.sections_cn import extract_cn_sections_from_docx  # noqa: E402

LABELS_PATH = _REPO_ROOT / "tests/fixtures/cn/antecedent_labels_cn.json"

# Fixture index mirrors the TW baseline postship file. The gitignored
# cn/local/ baseline is produced by _capture_baseline_cn.py and includes
# BOTH the 10 real cn/local fixtures and the 3 synthetic fixtures at
# cn/synthetic/. Harness reads only the fixture key → fixture_path map.
FIXTURE_INDEX = _REPO_ROOT / "tests/fixtures/cn/local/baseline_phase8c.json"


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
            f"  (run tests/fixtures/cn/local/_capture_baseline_cn.py first)",
            file=sys.stderr,
        )
        sys.exit(3)
    with FIXTURE_INDEX.open(encoding="utf-8") as fh:
        return json.load(fh)


def _walker_actual_set(index: dict) -> tuple[dict[tuple, dict], int]:
    """Run check_antecedent_basis_cn on every fixture and return the
    (key → issue dict) map plus the number of fixtures processed.

    Each issue dict from the walker has keys
    ``{claim_id, term, reference_form, claim_text, suggested_match,
    cross_ref}`` (plus ``category`` on the Q1 tw_contamination path).
    Keys are ``(fixture_key, claim_id, term, reference_form)`` tuples so
    the harness can diff against the labels file directly.
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
        loaded = load_docx_cn(fixture_path)
        doc = extract_cn_sections_from_docx(loaded.sections)
        for issue in check_antecedent_basis_cn(doc):
            tup = (
                key,
                issue["claim_id"],
                issue["term"],
                issue["reference_form"],
            )
            actual[tup] = issue
        fixture_count += 1
    return actual, fixture_count


def _validate_category_enum(labels_doc: dict) -> None:
    """ADR-110: strict reject of labels whose ``category`` is not in the
    schema-declared metadata.categories[].id set. Diverges from TW,
    which silently passes unknown categories through.
    """
    valid_ids = {c["id"] for c in labels_doc["metadata"]["categories"]}
    for lab in labels_doc["labels"]:
        if lab.get("category") not in valid_ids:
            tup = (
                lab.get("fixture"),
                lab.get("claim_id"),
                lab.get("term"),
                lab.get("reference_form"),
            )
            print(
                f"STRUCTURAL FAIL: label has unknown category "
                f"{lab.get('category')!r} (not in metadata.categories): {tup}",
                file=sys.stderr,
            )
            sys.exit(3)


def _check_structural_invariants_cn(labels_doc: dict) -> None:
    """Exit 3 on any of:

    1. (TW-inherited) label has both protect:true and resolved_by set.
    2. (ADR-110) label has unknown category.
    3. (ADR-111) label is missing the round field, or metadata is missing
       current_round.
    """
    _validate_category_enum(labels_doc)

    metadata = labels_doc["metadata"]
    if "current_round" not in metadata or not isinstance(
        metadata["current_round"], int
    ):
        print(
            "STRUCTURAL FAIL: metadata.current_round missing or not int "
            "(ADR-111)",
            file=sys.stderr,
        )
        sys.exit(3)

    for lab in labels_doc["labels"]:
        if lab.get("protect") and lab.get("resolved_by"):
            tup = (
                lab["fixture"],
                lab["claim_id"],
                lab["term"],
                lab["reference_form"],
            )
            print(
                f"STRUCTURAL FAIL: protect:true entry has resolved_by set: "
                f"{tup}",
                file=sys.stderr,
            )
            sys.exit(3)
        if "round" not in lab or not isinstance(lab["round"], int):
            tup = (
                lab.get("fixture"),
                lab.get("claim_id"),
                lab.get("term"),
                lab.get("reference_form"),
            )
            print(
                f"STRUCTURAL FAIL: label missing int round field "
                f"(ADR-111): {tup}",
                file=sys.stderr,
            )
            sys.exit(3)


def _label_key(lab: dict) -> tuple:
    return (
        lab["fixture"],
        lab["claim_id"],
        lab["term"],
        lab["reference_form"],
    )


def _compute_diff(labels_doc: dict, actual: dict[tuple, dict]) -> dict:
    """Build the diff payload (gates + per-category stats + delta lists).

    ADR-111: ``current_round`` scopes which resolved_by entries satisfy
    the halt. Additions and unprotected drops both halt unless every
    delta finding matches a current-round resolved_by entry.
    Protect_violations (protected drops) remain hard-fail with no
    resolved_by escape hatch.
    """
    labels = labels_doc["labels"]
    categories = labels_doc["metadata"]["categories"]
    current_round = labels_doc["metadata"]["current_round"]

    active_labels = [lab for lab in labels if not lab.get("resolved_by")]
    resolved_labels = [lab for lab in labels if lab.get("resolved_by")]

    expected_map: dict[tuple, dict] = {}
    protected: set[tuple] = set()
    for lab in active_labels:
        key = _label_key(lab)
        expected_map[key] = lab
        if lab.get("protect") is True:
            protected.add(key)
    # ADR-111 revision 2026-04-13: resolved labels are DURABLY expected
    # across rounds. current_round scoping applies only to the
    # bidirectional halt satisfaction check (see current_round_resolutions
    # below), not to the expected set. Without this, round-N new-shape
    # labels become ghosts the moment current_round advances to N+1.
    for lab in resolved_labels:
        key = _label_key(lab)
        expected_map[key] = lab

    expected = set(expected_map.keys())
    actual_keys = set(actual.keys())

    new_findings = sorted(actual_keys - expected)
    removed_findings = sorted(expected - actual_keys)
    protect_violations = [k for k in removed_findings if k in protected]

    # ADR-111 revision 2026-04-13: current_round_resolutions is used only
    # for UI classification (telling the reader which drops/additions were
    # satisfied by the round currently in flight). Halt satisfaction is
    # durable across rounds: once a label is resolved_by-tagged, its key
    # is permanently in `expected` (additions side) and permanently
    # excluded from unresolved_removed (drops side).
    current_round_resolutions: dict[tuple, dict] = {
        _label_key(lab): lab
        for lab in labels
        if lab.get("resolved_by") and lab.get("round") == current_round
    }
    resolved_keys_current = set(current_round_resolutions.keys())
    resolved_keys_all = {
        _label_key(lab) for lab in labels if lab.get("resolved_by")
    }

    # Additions: any emission NOT in expected is "new". Since expected
    # already includes resolved labels durably, true new_findings are by
    # construction unresolved. Halt unless a current-round resolved_by
    # entry explicitly credits the emission (kept for R1-style seeding
    # where the walker emits a key not yet in the label file).
    unresolved_new = [k for k in new_findings if k not in resolved_keys_current]
    # Drops: unprotected drops halt unless the label is resolved_by-tagged
    # in ANY round (durable). Protected drops take the exit-1 path with
    # no escape hatch.
    unprotected_removed = [k for k in removed_findings if k not in protected]
    unresolved_removed = [
        k for k in unprotected_removed if k not in resolved_keys_all
    ]

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
        # ADR-110 guarantees cid is in cat_stats by load-time validation.
        cat_stats[cid]["labeled"] += 1
        key = _label_key(lab)
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
        "unresolved_new": unresolved_new,
        "unresolved_removed": unresolved_removed,
        "protected": protected,
        "active_count": len(active_labels),
        "resolved_count": len(resolved_labels),
        "resolved_labels": resolved_labels,
        "current_round": current_round,
        "current_round_resolution_count": len(current_round_resolutions),
    }


def _exit_code(diff: dict) -> int:
    # ADR-111: protect_violations hard-fail has no resolved_by escape hatch.
    if diff["protect_violations"]:
        return 1
    if diff["unresolved_new"] or diff["unresolved_removed"]:
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
    unresolved_new = diff["unresolved_new"]
    unresolved_removed = diff["unresolved_removed"]
    cat_stats = diff["cat_stats"]
    expected_map = diff["expected_map"]

    out: list[str] = []
    out.append("# Phase 8c harness report (CN)")
    out.append("")
    out.append(f"**Commit**: {commit}")
    out.append(f"**Labels version**: {schema_version}")
    out.append(f"**Current round (ADR-111)**: {diff['current_round']}")
    out.append(
        f"**Current-round resolutions**: {diff['current_round_resolution_count']}"
    )
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
    un_status = "PASS" if not unresolved_new else "FAIL"
    ur_status = "PASS" if not unresolved_removed else "FAIL"
    pv_status = "PASS" if not protect_violations else "FAIL"
    out.append(
        f"- [{un_status}] unresolved_new: {len(unresolved_new)} "
        f"(HALT if > 0; additions satisfied by current-round resolved_by)"
    )
    out.append(
        f"- [{ur_status}] unresolved_removed: {len(unresolved_removed)} "
        f"(HALT if > 0; unprotected drops satisfied by current-round resolved_by)"
    )
    out.append(
        f"- [{pv_status}] protect_violations: {len(protect_violations)} "
        f"(HARD FAIL if > 0; no resolved_by escape hatch)"
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
        out.append("| fixture | claim | term | category | round | resolved_by |")
        out.append("|---|---|---|---|---:|---|")
        for lab in resolved_labels:
            out.append(
                f"| {lab['fixture']} | {lab['claim_id']} | {lab['term']} | "
                f"{lab['category']} | {lab.get('round', '')} | "
                f"{lab['resolved_by']} |"
            )
    else:
        out.append("None")
    out.append("")
    out.append("## New findings (unlabeled) — HALT if unresolved")
    out.append("")
    if new_findings:
        out.append("| fixture | claim | term | ref_form | resolved? |")
        out.append("|---|---|---|---|---|")
        for k in new_findings:
            tag = "current-round" if k not in unresolved_new else "UNRESOLVED"
            out.append(f"| {k[0]} | {k[1]} | {k[2]} | {k[3]} | {tag} |")
    else:
        out.append("None")
    out.append("")
    out.append("## Removed findings")
    out.append("")
    if removed_findings:
        out.append(
            "| fixture | claim | term | ref_form | category | protected | resolved? |"
        )
        out.append("|---|---|---|---|---|---|---|")
        for k in removed_findings:
            lab = expected_map[k]
            is_prot = lab.get("protect", False)
            if is_prot:
                tag = "PROTECT_VIOLATION"
            elif k in unresolved_removed:
                tag = "UNRESOLVED"
            else:
                tag = "current-round"
            out.append(
                f"| {k[0]} | {k[1]} | {k[2]} | {k[3]} | "
                f"{lab['category']} | {is_prot} | {tag} |"
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
    labels_doc: dict,
    diff: dict,
    fixture_count: int,
    commit: str,
    exit_code: int,
) -> str:
    labels = labels_doc["labels"]
    schema_version = labels_doc["metadata"]["schema_version"]
    actual_keys = diff["actual_keys"]
    new_findings = diff["new_findings"]
    removed_findings = diff["removed_findings"]
    protect_violations = diff["protect_violations"]
    unresolved_new = diff["unresolved_new"]
    unresolved_removed = diff["unresolved_removed"]
    cat_stats = diff["cat_stats"]
    expected_map = diff["expected_map"]

    active_count = diff["active_count"]
    resolved_count = diff["resolved_count"]
    payload = {
        "commit": commit,
        "labels_version": schema_version,
        "current_round": diff["current_round"],
        "current_round_resolution_count": diff["current_round_resolution_count"],
        "label_count": len(labels),
        "active_count": active_count,
        "resolved_count": resolved_count,
        "fixture_count": fixture_count,
        "walker_finding_count": len(actual_keys),
        "gates": {
            "unresolved_new": {
                "count": len(unresolved_new),
                "pass": len(unresolved_new) == 0,
            },
            "unresolved_removed": {
                "count": len(unresolved_removed),
                "pass": len(unresolved_removed) == 0,
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
                "resolved_this_round": k not in unresolved_new,
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
                "resolved_this_round": (
                    expected_map[k].get("protect", False) is False
                    and k not in unresolved_removed
                ),
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
                "round": lab.get("round"),
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
        description="Phase 8c CN antecedent walker labeled regression harness"
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Report format (default: markdown)",
    )
    args = parser.parse_args()

    labels_doc = _load_labels()
    _check_structural_invariants_cn(labels_doc)
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
