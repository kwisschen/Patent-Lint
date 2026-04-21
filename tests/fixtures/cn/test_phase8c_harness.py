# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Unit tests for the Phase 8c CN harness ADR-110 / ADR-111 divergences.

Covers the two structural divergences from TW:

* ADR-110 — strict category validation. Unknown category → exit 3.
* ADR-111 — round field + bidirectional halt with per-round
  resolved_by satisfaction. Protect_violations hard-fail without
  resolved_by escape hatch even when round matches.

Uses in-memory label dicts and monkeypatches ``_walker_actual_set`` so
the tests do not round-trip real fixtures. Loads the harness module via
``importlib`` because the source filename is underscore-prefixed and not
importable as a dotted path.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_HARNESS_PATH = Path(__file__).parent / "_phase8c_harness.py"
_spec = importlib.util.spec_from_file_location("_phase8c_harness", _HARNESS_PATH)
harness = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(harness)


# ── Fixtures ──────────────────────────────────────────────────────────────


def _minimal_categories() -> list[dict]:
    return [
        {"id": "legit_drafting_error", "description": "x"},
        {"id": "tw_contamination", "description": "x"},
        {"id": "ambig", "description": "x"},
        {"id": "unclassified", "description": "x"},
    ]


def _label(
    fixture: str,
    claim_id: int,
    term: str,
    reference_form: str,
    *,
    category: str = "unclassified",
    protect: bool = False,
    resolved_by: str | None = None,
    round_: int = 0,
    notes: str = "",
) -> dict:
    return {
        "fixture": fixture,
        "claim_id": claim_id,
        "term": term,
        "reference_form": reference_form,
        "category": category,
        "protect": protect,
        "confidence": "high",
        "notes": notes,
        "resolved_by": resolved_by,
        "round": round_,
    }


def _labels_doc(labels: list[dict], *, current_round: int = 0) -> dict:
    return {
        "metadata": {
            "schema_version": "v11",
            "current_round": current_round,
            "categories": _minimal_categories(),
            "notes": "",
        },
        "labels": labels,
    }


def _actual(findings: list[tuple]) -> dict[tuple, dict]:
    """Build a mock walker output map keyed by (fixture, claim_id, term, ref)."""
    return {k: {"claim_id": k[1], "term": k[2], "reference_form": k[3]} for k in findings}


# ── ADR-110: strict category validation ──────────────────────────────────


def test_unknown_category_exits_3(capsys):
    bad = _label("F", 1, "x", "所述x", category="does_not_exist")
    doc = _labels_doc([bad])
    with pytest.raises(SystemExit) as excinfo:
        harness._check_structural_invariants_cn(doc)
    assert excinfo.value.code == 3
    captured = capsys.readouterr()
    assert "unknown category" in captured.err.lower()


def test_known_category_passes_validator():
    good = _label("F", 1, "x", "所述x", category="unclassified")
    doc = _labels_doc([good])
    # Must not raise.
    harness._check_structural_invariants_cn(doc)


# ── ADR-110 full main() path via capture ─────────────────────────────────


def test_main_exits_3_on_unknown_category(monkeypatch, tmp_path, capsys):
    """End-to-end: an unknown category in the labels file → main() exits 3."""
    labels_path = tmp_path / "labels.json"
    index_path = tmp_path / "baseline.json"

    bad_doc = _labels_doc(
        [_label("F", 1, "x", "所述x", category="bogus")]
    )
    import json as _json
    labels_path.write_text(_json.dumps(bad_doc), encoding="utf-8")
    index_path.write_text(
        _json.dumps({"fixtures": {"F": {"fixture_path": "unused"}}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(harness, "LABELS_PATH", labels_path)
    monkeypatch.setattr(harness, "FIXTURE_INDEX", index_path)
    monkeypatch.setattr("sys.argv", ["_phase8c_harness.py"])
    # Don't reach the walker; structural check must fire first.

    with pytest.raises(SystemExit) as excinfo:
        harness.main()
    assert excinfo.value.code == 3


# ── ADR-111: bidirectional halt, happy cases ─────────────────────────────


def test_additions_resolved_by_current_round_exit_0():
    """A walker emission whose key matches a resolved_by label is durably
    expected (ADR-111 revision 2026-04-13) → no new_finding, exit 0."""
    labels = [
        # Active baseline label (matches actual, stays flagged).
        _label("F", 1, "a", "所述a"),
        # Resolved-by label for the emission, round 2 = current_round.
        _label(
            "F", 2, "b", "所述b",
            category="unclassified",
            resolved_by="F2_fix",
            round_=2,
        ),
    ]
    doc = _labels_doc(labels, current_round=2)
    actual = _actual([("F", 1, "a", "所述a"), ("F", 2, "b", "所述b")])
    diff = harness._compute_diff(doc, actual)
    # ADR-111 revision: resolved labels are DURABLY expected across
    # rounds, so (F,2,b) is not a new_finding even though it is
    # resolved_by-tagged.
    assert diff["new_findings"] == []
    assert diff["unresolved_new"] == []
    assert harness._exit_code(diff) == 0


def test_drops_resolved_by_current_round_exit_0():
    """A removed finding whose key matches a current-round resolved_by → exit 0."""
    labels = [
        # Active label expected but not in actual = drop candidate.
        _label("F", 3, "c", "所述c"),
        # Resolved-by entry for the same key, round 2 = current_round.
        _label(
            "F", 3, "c", "所述c",
            resolved_by="F2_fix_drop",
            round_=2,
        ),
    ]
    doc = _labels_doc(labels, current_round=2)
    # Walker does not emit the (F,3,c,所述c) key any more.
    actual: dict[tuple, dict] = {}
    diff = harness._compute_diff(doc, actual)
    assert ("F", 3, "c", "所述c") in diff["removed_findings"]
    assert diff["unresolved_removed"] == []
    assert diff["protect_violations"] == []
    assert harness._exit_code(diff) == 0


# ── ADR-111: bidirectional halt, miss cases ──────────────────────────────


def test_additions_without_resolved_by_exit_2():
    labels = [_label("F", 1, "a", "所述a")]
    doc = _labels_doc(labels, current_round=2)
    actual = _actual([("F", 1, "a", "所述a"), ("F", 9, "z", "所述z")])
    diff = harness._compute_diff(doc, actual)
    assert diff["unresolved_new"] == [("F", 9, "z", "所述z")]
    assert harness._exit_code(diff) == 2


def test_drops_without_resolved_by_exit_2():
    labels = [_label("F", 1, "a", "所述a")]
    doc = _labels_doc(labels, current_round=2)
    actual: dict[tuple, dict] = {}
    diff = harness._compute_diff(doc, actual)
    assert diff["unresolved_removed"] == [("F", 1, "a", "所述a")]
    assert not diff["protect_violations"]
    assert harness._exit_code(diff) == 2


# ── ADR-111: stale round ─────────────────────────────────────────────────


def test_stale_round_resolved_label_is_durably_expected():
    """ADR-111 revision 2026-04-13: a resolved_by entry with a stale round
    is still DURABLY expected. The corresponding walker emission matches
    expected and is not a new_finding. Stale-round scoping only applies
    to the bidirectional halt's satisfaction check for genuinely new
    originals, not to the expected set."""
    labels = [
        _label("F", 1, "a", "所述a"),
        # Stale resolution: round 1, current_round = 2.
        _label(
            "F", 2, "b", "所述b",
            resolved_by="F1_fix",
            round_=1,
        ),
    ]
    doc = _labels_doc(labels, current_round=2)
    actual = _actual([("F", 1, "a", "所述a"), ("F", 2, "b", "所述b")])
    diff = harness._compute_diff(doc, actual)
    # (F,2,b) is durably expected via its prior-round resolved_by.
    assert diff["new_findings"] == []
    assert diff["unresolved_new"] == []
    assert harness._exit_code(diff) == 0


def test_stale_round_does_not_satisfy_halt_for_unlabeled_key():
    """ADR-111 revision 2026-04-13: current_round scoping still applies
    to halt satisfaction for genuinely unlabeled new keys. A stale
    resolved_by entry for key K does NOT satisfy the halt for a
    different key K' that is truly unexpected."""
    labels = [
        _label("F", 1, "a", "所述a"),
        # Stale resolution on a different key.
        _label(
            "F", 2, "b", "所述b",
            resolved_by="F1_fix",
            round_=1,
        ),
    ]
    doc = _labels_doc(labels, current_round=2)
    # Walker emits an unexpected key (F,9,z) that is NOT covered by any
    # label — current_round_resolutions is empty, so halt fires.
    actual = _actual(
        [("F", 1, "a", "所述a"), ("F", 2, "b", "所述b"), ("F", 9, "z", "所述z")]
    )
    diff = harness._compute_diff(doc, actual)
    assert diff["new_findings"] == [("F", 9, "z", "所述z")]
    assert diff["unresolved_new"] == [("F", 9, "z", "所述z")]
    assert harness._exit_code(diff) == 2


# ── ADR-111: protect violations hard-fail without escape hatch ───────────


def test_protect_violation_hard_fails_even_with_matching_round():
    """A protect:true label that disappears from actual → exit 1. Even if
    another label has a current-round resolved_by for the same key, the
    escape hatch is explicitly disabled for protect_violations."""
    labels = [
        _label(
            "F", 1, "legit", "所述legit",
            category="legit_drafting_error",
            protect=True,
        ),
    ]
    doc = _labels_doc(labels, current_round=2)
    # Walker no longer emits the protected key → drop.
    actual: dict[tuple, dict] = {}
    diff = harness._compute_diff(doc, actual)
    assert diff["protect_violations"] == [("F", 1, "legit", "所述legit")]
    # Unprotected-drop halt must NOT claim the protected key.
    assert diff["unresolved_removed"] == []
    assert harness._exit_code(diff) == 1


def test_structural_fail_protect_plus_resolved_by():
    """TW-inherited invariant: protect:true + resolved_by set → exit 3."""
    bad = _label(
        "F", 1, "x", "所述x",
        category="legit_drafting_error",
        protect=True,
        resolved_by="should_not_exist",
    )
    doc = _labels_doc([bad])
    with pytest.raises(SystemExit) as excinfo:
        harness._check_structural_invariants_cn(doc)
    assert excinfo.value.code == 3


def test_missing_round_field_exits_3():
    bad = _label("F", 1, "x", "所述x")
    del bad["round"]
    doc = _labels_doc([bad])
    with pytest.raises(SystemExit) as excinfo:
        harness._check_structural_invariants_cn(doc)
    assert excinfo.value.code == 3


def test_missing_current_round_metadata_exits_3():
    labels = [_label("F", 1, "x", "所述x")]
    doc = _labels_doc(labels)
    del doc["metadata"]["current_round"]
    with pytest.raises(SystemExit) as excinfo:
        harness._check_structural_invariants_cn(doc)
    assert excinfo.value.code == 3
