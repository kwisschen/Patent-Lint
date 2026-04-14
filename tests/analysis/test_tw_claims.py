# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""Tests for TW claims structural checks (Phase 7C-2, checks #11-19)."""

from __future__ import annotations

from patentlint.analysis.tw_claims import (
    check_circular_dependency,
    check_claims_sequential,
    check_claims_symbol_table_consistency,
    check_cn_terminology,
    check_dependency_format,
    check_forward_dependency,
    check_multi_dep_alternative,
    check_multi_dep_on_multi_dep,
    check_ref_numeral_parens,
    check_self_dependent,
    check_single_sentence,
    check_spec_drawing_ref,
    check_subject_consistency,
    check_title_subject_match,
    check_transition_phrase,
)
from patentlint.models import Claim, SymbolEntry, TwPatentDocument, TwPatentType


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
        assert result[0].details_params["expected"] == 3
        assert result[0].details_params["found"] == 4

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
        assert result[0].details_params["count"] == 1
        assert result[0].details_params["claims"] == [2]

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
        assert result[0].details_params["count"] == 1
        assert result[0].details_params["claims"] == [3]

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
        assert 2 in result[0].details_params["claims"]

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
        assert 2 in result[0].details_params["claims"]

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
        assert result[0].details_params["count"] == 1
        assert result[0].details_params["claims"] == [1]

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
        assert result[0].details_params["count"] == 1
        assert result[0].details_params["claims"] == [1]

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
        assert result[0].details_params["count"] == 1
        assert result[0].details_params["claims"] == [2]

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
        assert result[0].details_params["count"] == 1
        assert result[0].details_params["claims"] == [1]

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


# ── Check 20: CN Terminology ───────────────────────────────────────────────


class TestCnTerminology:
    def test_no_cn_terms_pass(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置，其特徵在於包含一基座。"),
        ])
        result = check_cn_terminology(doc)
        assert result[0].status == "pass"

    def test_single_cn_term_verify(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置，如权利要求1所述。"),
        ])
        result = check_cn_terminology(doc)
        assert result[0].status == "verify"
        assert "权利要求" in result[0].details_params["detail"]

    def test_multiple_cn_terms_verify(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置，如权利要求1所述，背景技术中提及。"),
        ])
        result = check_cn_terminology(doc)
        assert result[0].status == "verify"
        assert "权利要求" in result[0].details_params["detail"]
        assert "背景技术" in result[0].details_params["detail"]

    def test_reference_is_none(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置。"),
        ])
        result = check_cn_terminology(doc)
        assert result[0].reference is None

    def test_no_claims_pass(self):
        doc = _make_doc(claims=[])
        result = check_cn_terminology(doc)
        assert result[0].status == "pass"


# ── Check 21: Spec/Drawing Reference ──────────────────────────────────────


class TestSpecDrawingRef:
    def test_clean_claims_pass(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置，其特徵在於包含一基座。"),
        ])
        result = check_spec_drawing_ref(doc)
        assert result[0].status == "pass"

    def test_如圖所示_amend(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置，如圖所示包含一基座。"),
        ])
        result = check_spec_drawing_ref(doc)
        assert result[0].status == "amend"
        assert "如圖所示" in result[0].details_params["detail"]

    def test_如圖N所示_amend(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置，如圖1所示包含一基座。"),
        ])
        result = check_spec_drawing_ref(doc)
        assert result[0].status == "amend"
        assert "如圖1所示" in result[0].details_params["detail"]

    def test_如說明書所述_amend(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置，如說明書所述包含一基座。"),
        ])
        result = check_spec_drawing_ref(doc)
        assert result[0].status == "amend"
        assert "如說明書所述" in result[0].details_params["detail"]

    def test_參見圖_amend(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置，參見圖3中之結構。"),
        ])
        result = check_spec_drawing_ref(doc)
        assert result[0].status == "amend"

    def test_no_claims_pass(self):
        doc = _make_doc(claims=[])
        result = check_spec_drawing_ref(doc)
        assert result[0].status == "pass"


# ── Check 22: Multi-dep on Multi-dep ──────────────────────────────────────


class TestMultiDepOnMultiDep:
    def test_no_multi_deps_pass(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置。"),
            _claim(2, "2. 如請求項1所述之裝置。", independent=False, deps=[1]),
        ])
        result = check_multi_dep_on_multi_dep(doc)
        assert result[0].status == "pass"

    def test_multi_dep_on_single_dep_pass(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置。"),
            _claim(2, "2. 如請求項1所述之裝置。", independent=False, deps=[1]),
            _claim(3, "3. 如請求項1或2中任一項所述之裝置。",
                   independent=False, deps=[1, 2], multi_dep=True),
        ])
        result = check_multi_dep_on_multi_dep(doc)
        assert result[0].status == "pass"

    def test_direct_multi_on_multi_amend(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置。"),
            _claim(2, "2. 如請求項1所述之裝置。", independent=False, deps=[1]),
            _claim(3, "3. 如請求項1或2中任一項所述之裝置。",
                   independent=False, deps=[1, 2], multi_dep=True),
            _claim(5, "5. 如請求項3或2中任一項所述之裝置。",
                   independent=False, deps=[3, 2], multi_dep=True),
        ])
        result = check_multi_dep_on_multi_dep(doc)
        assert result[0].status == "amend"
        assert 5 in result[0].details_params["claims"]

    def test_indirect_multi_on_multi_amend(self):
        """Claim 5 (multi) → claim 4 (single) → claim 3 (multi) → claim 1."""
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置。"),
            _claim(2, "2. 如請求項1所述之裝置。", independent=False, deps=[1]),
            _claim(3, "3. 如請求項1或2中任一項所述之裝置。",
                   independent=False, deps=[1, 2], multi_dep=True),
            _claim(4, "4. 如請求項3所述之裝置。", independent=False, deps=[3]),
            _claim(5, "5. 如請求項2或4中任一項所述之裝置。",
                   independent=False, deps=[2, 4], multi_dep=True),
        ])
        result = check_multi_dep_on_multi_dep(doc)
        assert result[0].status == "amend"
        assert 5 in result[0].details_params["claims"]

    def test_no_claims_pass(self):
        doc = _make_doc(claims=[])
        result = check_multi_dep_on_multi_dep(doc)
        assert result[0].status == "pass"


# ── Check 23: Multi-dep Alternative Form ──────────────────────────────────


class TestMultiDepAlternative:
    def test_no_multi_deps_pass(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置。"),
        ])
        result = check_multi_dep_alternative(doc)
        assert result[0].status == "pass"

    def test_with_或_pass(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置。"),
            _claim(2, "2. 如請求項1所述之裝置。", independent=False, deps=[1]),
            _claim(3, "3. 如請求項1或2所述之裝置。",
                   independent=False, deps=[1, 2], multi_dep=True),
        ])
        result = check_multi_dep_alternative(doc)
        assert result[0].status == "pass"

    def test_with_任一項_pass(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置。"),
            _claim(2, "2. 如請求項1所述之裝置。", independent=False, deps=[1]),
            _claim(3, "3. 如請求項1至2中任一項所述之裝置。",
                   independent=False, deps=[1, 2], multi_dep=True),
        ])
        result = check_multi_dep_alternative(doc)
        assert result[0].status == "pass"

    def test_conjunctive_form_amend(self):
        doc = _make_doc(claims=[
            _claim(1, "1. 一種裝置。"),
            _claim(2, "2. 如請求項1所述之裝置。", independent=False, deps=[1]),
            _claim(3, "3. 如請求項1及2所述之裝置。",
                   independent=False, deps=[1, 2], multi_dep=True),
        ])
        result = check_multi_dep_alternative(doc)
        assert result[0].status == "amend"
        assert 3 in result[0].details_params["claims"]

    def test_no_claims_pass(self):
        doc = _make_doc(claims=[])
        result = check_multi_dep_alternative(doc)
        assert result[0].status == "pass"


# ── Check 24: Title Subject Match ─────────────────────────────────────────


class TestTitleSubjectMatch:
    def test_title_matches_pass(self):
        doc = _make_doc(
            title="一種裝置",
            claims=[_claim(1, "1. 一種裝置，其特徵在於包含一基座。")],
        )
        result = check_title_subject_match(doc)
        assert result[0].status == "pass"

    def test_title_no_overlap_verify(self):
        doc = _make_doc(
            title="一種通訊系統",
            claims=[_claim(1, "1. 一種裝置，其特徵在於包含一基座。")],
        )
        result = check_title_subject_match(doc)
        assert result[0].status == "verify"
        assert "title" in result[0].details_params
        assert "subjects" in result[0].details_params

    def test_title_partial_overlap_pass(self):
        doc = _make_doc(
            title="裝置",
            claims=[_claim(1, "1. 一種裝置，其特徵在於包含一基座。")],
        )
        result = check_title_subject_match(doc)
        assert result[0].status == "pass"

    def test_no_title_pass(self):
        doc = _make_doc(
            title="",
            claims=[_claim(1, "1. 一種裝置。")],
        )
        result = check_title_subject_match(doc)
        assert result[0].status == "pass"

    def test_no_claims_pass(self):
        doc = _make_doc(title="一種裝置", claims=[])
        result = check_title_subject_match(doc)
        assert result[0].status == "pass"


# ── Check 25: Claims Symbol Table Consistency ─────────────────────────────


class TestClaimsSymbolTableConsistency:
    def test_all_consistent_pass(self):
        doc = _make_doc(
            claims=[_claim(1, "1. 一種裝置，包含一基座(101)及一蓋板(102)。")],
            symbol_table=[
                SymbolEntry(numeral="101", name="基座"),
                SymbolEntry(numeral="102", name="蓋板"),
            ],
        )
        result = check_claims_symbol_table_consistency(doc)
        assert result[0].status == "pass"

    def test_numeral_in_claims_not_table_verify(self):
        doc = _make_doc(
            claims=[_claim(1, "1. 一種裝置，包含一基座(101)及一蓋板(102)。")],
            symbol_table=[
                SymbolEntry(numeral="101", name="基座"),
            ],
        )
        result = check_claims_symbol_table_consistency(doc)
        assert result[0].status == "verify"
        payload = result[0].details_params["numerals_with_locations"]
        assert isinstance(payload, list)
        assert payload == [{"numeral": "102", "claims": [1]}]

    def test_empty_symbol_table_pass(self):
        doc = _make_doc(
            claims=[_claim(1, "1. 一種裝置，包含一基座(101)。")],
            symbol_table=[],
        )
        result = check_claims_symbol_table_consistency(doc)
        assert result[0].status == "pass"

    def test_table_has_extra_numerals_passes(self):
        """Symbol table entries not used in claims are NOT a defect."""
        doc = _make_doc(
            claims=[_claim(1, "1. 一種裝置，包含一基座(101)。")],
            symbol_table=[
                SymbolEntry(numeral="101", name="基座"),
                SymbolEntry(numeral="200", name="外殼"),
            ],
        )
        result = check_claims_symbol_table_consistency(doc)
        assert result[0].status == "pass"

    def test_no_claims_numerals_pass(self):
        """No claims means no claim numerals — early return pass."""
        doc = _make_doc(
            claims=[],
            symbol_table=[SymbolEntry(numeral="101", name="基座")],
        )
        result = check_claims_symbol_table_consistency(doc)
        assert result[0].status == "pass"
        assert result[0].message_key == "check.tw.claims.symbolTableConsistency.noClaimNumerals"

    def test_zero_claim_numerals_with_populated_table_passes(self):
        """Regression for 110P000368: claims have no (N) refs, symbol table populated.

        Per 施行細則 §19, reference numerals in claims are optional. The
        consistency check must early-return PASS, not flag every symbol
        table entry as 'in 符號說明 but not claims'.
        """
        doc = _make_doc(
            claims=[
                _claim(1, "1. 一種裝置，包括一底座及一框架。"),
            ],
            symbol_table=[
                SymbolEntry(numeral="10", name="底座"),
                SymbolEntry(numeral="20", name="框架"),
                SymbolEntry(numeral="30", name="支撐件"),
            ],
        )
        result = check_claims_symbol_table_consistency(doc)
        assert len(result) == 1
        assert result[0].status == "pass"
        assert result[0].message_key == "check.tw.claims.symbolTableConsistency.noClaimNumerals"

    def test_structured_details_params_with_locations(self):
        """Verify structured details_params includes claim-number locations."""
        doc = _make_doc(
            claims=[
                _claim(1, "1. 一種裝置，包括一底座(99)。"),
                _claim(3, "3. 如請求項1所述的裝置，其中該底座(99)及框架(100)。",
                       independent=False, deps=[1]),
            ],
            symbol_table=[
                SymbolEntry(numeral="10", name="底座"),
            ],
        )
        result = check_claims_symbol_table_consistency(doc)
        assert result[0].status == "verify"
        payload = result[0].details_params["numerals_with_locations"]
        assert isinstance(payload, list)
        # Numerals sorted numerically: 99, 100 (not lexically: 100, 99)
        assert payload == [
            {"numeral": "99", "claims": [1, 3]},
            {"numeral": "100", "claims": [3]},
        ]

    def test_structured_payload_uses_correct_key_name(self):
        """The details_params key must be 'numerals_with_locations'.

        This name is the registry key in detailsFormatter.js. If renamed,
        the frontend formatter will not detect the structured payload and
        will pass it raw to t(), producing '[object Object]' in output.
        """
        doc = _make_doc(
            claims=[
                _claim(1, "1. 一種裝置(99)。"),
            ],
            symbol_table=[SymbolEntry(numeral="10", name="底座")],
        )
        result = check_claims_symbol_table_consistency(doc)
        assert "numerals_with_locations" in result[0].details_params


# ── Check 26: Antecedent Basis ────────────────────────────────────────────


# TestAntecedentBasis removed in Phase 8b — the legacy check returned a
# CheckItem; the new BFS walker returns list[dict] of per-occurrence
# findings. Walker tests live in tests/analysis/test_tw_walker.py.
