# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""Tests for TW claims structural checks (Phase 7C-2, checks #11-19)."""

from __future__ import annotations

import pytest

from patentlint.analysis.tw_claims import (
    check_circular_dependency,
    check_claims_sequential,
    check_dependency_format,
    check_forward_dependency,
    check_ref_numeral_parens,
    check_self_dependent,
    check_single_sentence,
    check_subject_consistency,
    check_transition_phrase,
)
from patentlint.models import Claim, TwPatentDocument, TwPatentType


def _make_doc(**kwargs) -> TwPatentDocument:
    """Build a TwPatentDocument with sensible defaults."""
    defaults = dict(
        patent_type=TwPatentType.INVENTION,
        title="一種裝置",
        technical_field=["本發明涉及一種裝置。"],
        prior_art=["已知有相關技術。"],
        disclosure=["本發明提供一種解決方案。"],
        embodiment=["參照圖1說明實施方式。"],
        claims=[],
    )
    defaults.update(kwargs)
    return TwPatentDocument(**defaults)


def _claim(num: int, text: str, independent: bool = True,
           deps: list[int] | None = None, multi_dep: bool = False) -> Claim:
    return Claim(
        id=num,
        text=text,
        independent=independent,
        dependencies=deps or [],
        multiple_dependent=multi_dep,
    )


# ── Check 11: Sequential ────────────────────────────────────────────────


class TestClaimsSequential:
    def test_sequential_pass(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置，其特徵在於包含一基座。"),
            _claim(2, "2. 如請求項1所述之裝置，其中該基座為金屬。",
                   independent=False, deps=[1]),
        ])
        result = check_claims_sequential(doc)
        assert result[0].status == "pass"

    def test_single_claim_pass(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種方法。"),
        ])
        result = check_claims_sequential(doc)
        assert result[0].status == "pass"

    def test_gap_amend(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置。"),
            _claim(2, "2. 如請求項1所述之裝置。", independent=False, deps=[1]),
            _claim(4, "4. 如請求項1所述之裝置。", independent=False, deps=[1]),
        ])
        result = check_claims_sequential(doc)
        assert result[0].status == "amend"
        assert "expected 3" in result[0].details

    def test_no_claims_pass(self):
        doc = _make_doc(claims=[])
        result = check_claims_sequential(doc)
        assert result[0].status == "pass"


# ── Check 12: Dependency Format ──────────────────────────────────────────


class TestDependencyFormat:
    def test_recognized_format_pass(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置，其特徵在於包含一基座。"),
            _claim(2, "2. 如請求項1所述之裝置，其中該基座為金屬。",
                   independent=False, deps=[1]),
        ])
        result = check_dependency_format(doc)
        assert result[0].status == "pass"

    def test_unrecognized_format_amend(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置，其特徵在於包含一基座。"),
            _claim(2, "2. 根據權利要求1之裝置，其中該基座為金屬。",
                   independent=False, deps=[1]),
        ])
        result = check_dependency_format(doc)
        assert result[0].status == "amend"
        assert result[0].details_params["count"] == "1"

    def test_mixed_formats(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置，其特徵在於包含一基座。"),
            _claim(2, "2. 如請求項1之裝置，其中包含一蓋板。",
                   independent=False, deps=[1]),
            _claim(3, "3. 根據權利要求1之裝置，其中包含一底板。",
                   independent=False, deps=[1]),
        ])
        result = check_dependency_format(doc)
        assert result[0].status == "amend"
        assert result[0].details_params["count"] == "1"

    def test_no_dependents_pass(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置。"),
        ])
        result = check_dependency_format(doc)
        assert result[0].status == "pass"


# ── Check 13: Self-Dependent ─────────────────────────────────────────────


class TestSelfDependent:
    def test_no_self_dep_pass(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置。"),
            _claim(2, "2. 如請求項1所述之裝置。", independent=False, deps=[1]),
        ])
        result = check_self_dependent(doc)
        assert result[0].status == "pass"

    def test_self_dep_amend(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置。"),
            _claim(2, "2. 如請求項2所述之裝置。", independent=False, deps=[2]),
        ])
        result = check_self_dependent(doc)
        assert result[0].status == "amend"
        assert "2" in result[0].details_params["claims"]

    def test_no_claims_pass(self):
        doc = _make_doc(claims=[])
        result = check_self_dependent(doc)
        assert result[0].status == "pass"


# ── Check 14: Circular Dependency ────────────────────────────────────────


class TestCircularDependency:
    def test_no_circular_pass(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置。"),
            _claim(2, "2. 如請求項1所述之裝置。", independent=False, deps=[1]),
            _claim(3, "3. 如請求項2所述之裝置。", independent=False, deps=[2]),
        ])
        result = check_circular_dependency(doc)
        assert result[0].status == "pass"

    def test_circular_a_b_a_amend(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置。"),
            _claim(2, "2. 如請求項3所述之裝置。", independent=False, deps=[3]),
            _claim(3, "3. 如請求項2所述之裝置。", independent=False, deps=[2]),
        ])
        result = check_circular_dependency(doc)
        assert result[0].status == "amend"
        assert "claims" in result[0].details_params

    def test_no_claims_pass(self):
        doc = _make_doc(claims=[])
        result = check_circular_dependency(doc)
        assert result[0].status == "pass"


# ── Check 15: Forward Dependency ─────────────────────────────────────────


class TestForwardDependency:
    def test_no_forward_pass(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置。"),
            _claim(2, "2. 如請求項1所述之裝置。", independent=False, deps=[1]),
        ])
        result = check_forward_dependency(doc)
        assert result[0].status == "pass"

    def test_forward_ref_amend(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置。"),
            _claim(2, "2. 如請求項3所述之裝置。", independent=False, deps=[3]),
            _claim(3, "3. 如請求項1所述之裝置。", independent=False, deps=[1]),
        ])
        result = check_forward_dependency(doc)
        assert result[0].status == "amend"
        assert "2" in result[0].details_params["claims"]

    def test_no_claims_pass(self):
        doc = _make_doc(claims=[])
        result = check_forward_dependency(doc)
        assert result[0].status == "pass"


# ── Check 16: Single Sentence ────────────────────────────────────────────


class TestSingleSentence:
    def test_all_single_pass(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置，其特徵在於包含一基座。"),
        ])
        result = check_single_sentence(doc)
        assert result[0].status == "pass"

    def test_period_in_middle_amend(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置。其特徵在於包含一基座。"),
        ])
        result = check_single_sentence(doc)
        assert result[0].status == "amend"
        assert result[0].details_params["count"] == "1"

    def test_no_period_amend(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置，其特徵在於包含一基座"),
        ])
        result = check_single_sentence(doc)
        assert result[0].status == "amend"

    def test_no_claims_pass(self):
        doc = _make_doc(claims=[])
        result = check_single_sentence(doc)
        assert len(result) == 0 or result[0].status == "pass"


# ── Check 17: Reference Numeral Parentheses ──────────────────────────────


class TestRefNumeralParens:
    def test_all_in_parens_pass(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置，包含一基座(101)及一蓋板(102)。"),
        ])
        result = check_ref_numeral_parens(doc)
        assert result[0].status == "pass"

    def test_bare_numeral_verify(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置，包含一基座101及一蓋板102。"),
        ])
        result = check_ref_numeral_parens(doc)
        assert result[0].status == "verify"
        assert result[0].details_params["count"] == "1"

    def test_no_numerals_pass(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種方法，包含以下步驟。"),
        ])
        result = check_ref_numeral_parens(doc)
        assert result[0].status == "pass"

    def test_measurement_not_flagged(self):
        """100°C, 50mm should not be flagged as bare reference numerals."""
        doc = _make_doc(claims=[
            _claim(1, "1. 一種方法，其特徵在於溫度100°C及厚度50mm。"),
        ])
        result = check_ref_numeral_parens(doc)
        assert result[0].status == "pass"

    def test_ordinal_not_flagged(self):
        """第100 should not be flagged as a bare reference numeral."""
        doc = _make_doc(claims=[
            _claim(1, "1. 一種方法，其特徵在於第100步驟。"),
        ])
        result = check_ref_numeral_parens(doc)
        assert result[0].status == "pass"


# ── Check 18: Subject Consistency ────────────────────────────────────────


class TestSubjectConsistency:
    def test_consistent_pass(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置，其特徵在於包含一基座。"),
            _claim(2, "2. 如請求項1所述之裝置，其中該基座為金屬。",
                   independent=False, deps=[1]),
        ])
        result = check_subject_consistency(doc)
        assert result[0].status == "pass"

    def test_mismatch_verify(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置，其特徵在於包含一基座。"),
            _claim(2, "2. 如請求項1所述之方法，其中該基座為金屬。",
                   independent=False, deps=[1]),
        ])
        result = check_subject_consistency(doc)
        assert result[0].status == "verify"
        assert result[0].details_params["count"] == "1"

    def test_bare_之_format_pass(self):
        """如請求項N之裝置 — bare 之 without 所述."""
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置，其特徵在於包含一基座。"),
            _claim(2, "2. 如請求項1之裝置，其中該基座為金屬。",
                   independent=False, deps=[1]),
        ])
        result = check_subject_consistency(doc)
        assert result[0].status == "pass"

    def test_no_dependents_pass(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置。"),
        ])
        result = check_subject_consistency(doc)
        assert result[0].status == "pass"


# ── Check 19: Transition Phrase ──────────────────────────────────────────


class TestTransitionPhrase:
    def test_with_characteristic_pass(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置，其特徵在於包含一基座。"),
        ])
        result = check_transition_phrase(doc)
        assert result[0].status == "pass"

    def test_with_improvement_pass(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置，其改良在於包含一基座。"),
        ])
        result = check_transition_phrase(doc)
        assert result[0].status == "pass"

    def test_with_包含_pass(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置，包含一基座及一蓋板。"),
        ])
        result = check_transition_phrase(doc)
        assert result[0].status == "pass"

    def test_with_包括_pass(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置，包括一基座及一蓋板。"),
        ])
        result = check_transition_phrase(doc)
        assert result[0].status == "pass"

    def test_missing_verify(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置，由一基座及一蓋板組成。"),
        ])
        result = check_transition_phrase(doc)
        assert result[0].status == "verify"
        assert result[0].details_params["count"] == "1"

    def test_only_dependents_pass(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置，其特徵在於包含一基座。"),
            _claim(2, "2. 如請求項1所述之裝置，其中該基座為金屬。",
                   independent=False, deps=[1]),
        ])
        # Only claim 1 is independent and has 其特徵在於
        result = check_transition_phrase(doc)
        assert result[0].status == "pass"

    def test_no_independent_claims_pass(self):
        """Edge case: only dependent claims (no independent) → PASS."""
        doc = _make_doc(claims=[
            _claim(1, "1. 如請求項0所述之裝置。", independent=False, deps=[0]),
        ])
        result = check_transition_phrase(doc)
        assert result[0].status == "pass"

    def test_with_其中包括_pass(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置，其中包括一基座及一蓋板。"),
        ])
        result = check_transition_phrase(doc)
        assert result[0].status == "pass"
