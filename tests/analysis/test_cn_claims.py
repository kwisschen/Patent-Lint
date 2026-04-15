# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Tests for patentlint.analysis.cn_claims."""

from patentlint.analysis.cn_claims import (
    check_claims_sequential,
    check_claims_spec_reference,
    check_dependency_format,
    check_dependent_ordering,
    check_forward_dependency,
    check_multi_multi_dependency,
    check_reference_numeral_parentheses,
    check_self_dependent,
    check_single_sentence,
    check_subject_name_consistency,
    check_transition_phrase,
    check_tw_terminology,
)
from patentlint.models import Claim, CnPatentDocument


def _claim(id: int, text: str, independent: bool = True,
           dependencies: list[int] | None = None,
           multiple_dependent: bool = False) -> Claim:
    return Claim(
        id=id, text=text, independent=independent,
        dependencies=dependencies or [],
        multiple_dependent=multiple_dependent,
    )


def _cn_doc(claims: list[Claim]) -> CnPatentDocument:
    return CnPatentDocument(claims=claims)


# ── Check 9: Sequential ──────────────────────────────────────────────────


class TestClaimsSequential:
    def test_sequential_pass(self):
        doc = _cn_doc([_claim(1, "A。"), _claim(2, "B。"), _claim(3, "C。")])
        results = check_claims_sequential(doc)
        assert results[0].status == "pass"

    def test_gap_amend(self):
        doc = _cn_doc([_claim(1, "A。"), _claim(2, "B。"), _claim(5, "C。")])
        results = check_claims_sequential(doc)
        assert results[0].status == "amend"
        assert results[0].details_params["expected"] == 3
        assert results[0].details_params["found"] == 5

    def test_empty_pass(self):
        doc = _cn_doc([])
        results = check_claims_sequential(doc)
        assert results[0].status == "pass"


# ── Check 10: Dependency format ───────────────────────────────────────────


class TestDependencyFormat:
    def test_proper_format_pass(self):
        doc = _cn_doc([
            _claim(1, "1. 一种装置，其特征在于包括模块。"),
            _claim(2, "2. 如权利要求1所述的装置，其特征在于还包括部件。",
                   independent=False, dependencies=[1]),
        ])
        results = check_dependency_format(doc)
        assert results[0].status == "pass"

    def test_missing_format_amend(self):
        doc = _cn_doc([
            _claim(1, "1. 一种装置，其特征在于包括模块。"),
            _claim(2, "2. 根据装置1，其特征在于还包括部件。",
                   independent=False, dependencies=[1]),
        ])
        results = check_dependency_format(doc)
        assert results[0].status == "amend"
        assert results[0].details_params["count"] == 1
        assert results[0].details_params["claims"] == [2]

    def test_multi_dep_format_pass(self):
        doc = _cn_doc([
            _claim(1, "1. 一种装置。"),
            _claim(2, "2. 一种方法。"),
            _claim(3, "3. 如权利要求1至2中任一项所述的装置，还包括部件。",
                   independent=False, dependencies=[1, 2], multiple_dependent=True),
        ])
        results = check_dependency_format(doc)
        assert results[0].status == "pass"

    def test_no_dependents_pass(self):
        doc = _cn_doc([_claim(1, "1. 一种装置。")])
        results = check_dependency_format(doc)
        assert results[0].status == "pass"


# ── Check 11: Self-dependent ─────────────────────────────────────────────


class TestSelfDependent:
    def test_no_self_dep_pass(self):
        doc = _cn_doc([
            _claim(1, "A。"),
            _claim(2, "B。", independent=False, dependencies=[1]),
        ])
        results = check_self_dependent(doc)
        assert results[0].status == "pass"

    def test_self_dep_amend(self):
        doc = _cn_doc([
            _claim(1, "A。"),
            _claim(2, "B。", independent=False, dependencies=[2]),
        ])
        results = check_self_dependent(doc)
        assert results[0].status == "amend"
        assert 2 in results[0].details_params["claims"]


# ── Check 12: Forward dependency ──────────────────────────────────────────


class TestForwardDependency:
    def test_no_forward_pass(self):
        doc = _cn_doc([
            _claim(1, "A。"),
            _claim(2, "B。", independent=False, dependencies=[1]),
        ])
        results = check_forward_dependency(doc)
        assert results[0].status == "pass"

    def test_forward_amend(self):
        doc = _cn_doc([
            _claim(1, "A。", independent=False, dependencies=[3]),
            _claim(2, "B。"),
            _claim(3, "C。"),
        ])
        results = check_forward_dependency(doc)
        assert results[0].status == "amend"
        assert 1 in results[0].details_params["claims"]


# ── Check 13: Single sentence ────────────────────────────────────────────


class TestSingleSentence:
    def test_proper_pass(self):
        doc = _cn_doc([
            _claim(1, "1. 一种装置，其特征在于包括处理模块。"),
        ])
        results = check_single_sentence(doc)
        assert results[0].status == "pass"

    def test_multiple_periods_amend(self):
        doc = _cn_doc([
            _claim(1, "1. 一种装置。其特征在于包括处理模块。"),
        ])
        results = check_single_sentence(doc)
        assert results[0].status == "amend"
        assert results[0].details_params["count"] == 1
        assert results[0].details_params["claims"] == [1]

    def test_no_period_amend(self):
        doc = _cn_doc([
            _claim(1, "1. 一种装置，其特征在于包括处理模块"),
        ])
        results = check_single_sentence(doc)
        assert results[0].status == "amend"

    def test_period_not_at_end_amend(self):
        doc = _cn_doc([
            _claim(1, "1. 一种装置。  "),  # period not at end after strip? Actually strip makes it end
        ])
        results = check_single_sentence(doc)
        # After strip, "1. 一种装置。" ends with 。 and has exactly 1 → pass
        assert results[0].status == "pass"


# ── Check 14: Reference numeral parentheses ───────────────────────────────


class TestRefNumeralParentheses:
    def test_parenthesized_pass(self):
        doc = _cn_doc([
            _claim(1, "1. 一种装置，包括处理模块(101)和存储模块(102)。"),
        ])
        results = check_reference_numeral_parentheses(doc)
        assert results[0].status == "pass"

    def test_bare_numeral_verify(self):
        doc = _cn_doc([
            _claim(1, "1. 一种装置，包括处理模块101和存储模块102。"),
        ])
        results = check_reference_numeral_parentheses(doc)
        assert results[0].status == "verify"
        assert results[0].details_params["count"] == 1
        assert results[0].details_params["claims"] == [1]

    def test_no_numerals_pass(self):
        doc = _cn_doc([
            _claim(1, "1. 一种装置，其特征在于包括处理模块。"),
        ])
        results = check_reference_numeral_parentheses(doc)
        assert results[0].status == "pass"

    def test_mixed_pass_and_bare(self):
        doc = _cn_doc([
            _claim(1, "1. 一种装置，包括模块(101)。"),
            _claim(2, "2. 如权利要求1所述的装置，还包括部件201。",
                   independent=False, dependencies=[1]),
        ])
        results = check_reference_numeral_parentheses(doc)
        assert results[0].status == "verify"
        assert results[0].details_params["count"] == 1
        assert results[0].details_params["claims"] == [2]


# ── Check 15: Subject name consistency ────────────────────────────────────


class TestSubjectNameConsistency:
    def test_consistent_pass(self):
        doc = _cn_doc([
            _claim(1, "1. 一种数据处理装置，其特征在于包括模块。"),
            _claim(2, "2. 如权利要求1所述的数据处理装置，其特征在于还包括部件。",
                   independent=False, dependencies=[1]),
        ])
        results = check_subject_name_consistency(doc)
        assert results[0].status == "pass"

    def test_inconsistent_verify(self):
        doc = _cn_doc([
            _claim(1, "1. 一种数据处理装置，其特征在于包括模块。"),
            _claim(2, "2. 如权利要求1所述的信号处理系统，其特征在于还包括部件。",
                   independent=False, dependencies=[1]),
        ])
        results = check_subject_name_consistency(doc)
        assert results[0].status == "verify"

    def test_no_dependents_pass(self):
        doc = _cn_doc([_claim(1, "1. 一种装置。")])
        results = check_subject_name_consistency(doc)
        assert results[0].status == "pass"


# ── Check 16: Transition phrase ───────────────────────────────────────────


class TestTransitionPhrase:
    def test_has_transition_pass(self):
        doc = _cn_doc([
            _claim(1, "1. 一种装置，其特征在于包括处理模块。"),
        ])
        results = check_transition_phrase(doc)
        assert results[0].status == "pass"

    def test_missing_transition_verify(self):
        doc = _cn_doc([
            _claim(1, "1. 一种装置，包括处理模块。"),
        ])
        results = check_transition_phrase(doc)
        assert results[0].status == "verify"
        assert results[0].details_params["count"] == 1
        assert results[0].details_params["claims"] == [1]

    def test_alternative_transitions(self):
        doc = _cn_doc([
            _claim(1, "1. 一种装置，其特征是包括处理模块。"),
            _claim(2, "2. 一种方法，其改进在于包括步骤。"),
        ])
        results = check_transition_phrase(doc)
        assert results[0].status == "pass"


# ── Check 17: TW terminology ─────────────────────────────────────────────


class TestTwTerminology:
    def test_no_tw_pass(self):
        doc = _cn_doc([_claim(1, "1. 一种装置。")])
        results = check_tw_terminology(doc)
        assert results[0].status == "pass"

    def test_tw_simplified_verify(self):
        doc = _cn_doc([_claim(1, "1. 根据请求项1所述的装置。")])
        results = check_tw_terminology(doc)
        assert results[0].status == "verify"

    def test_tw_traditional_verify(self):
        doc = _cn_doc([_claim(1, "1. 根據請求項1所述的裝置。")])
        results = check_tw_terminology(doc)
        assert results[0].status == "verify"


# ── Check 18: Spec reference ─────────────────────────────────────────────


class TestClaimsSpecReference:
    def test_no_ref_pass(self):
        doc = _cn_doc([_claim(1, "1. 一种装置，其特征在于包括模块。")])
        results = check_claims_spec_reference(doc)
        assert results[0].status == "pass"

    def test_spec_ref_amend(self):
        doc = _cn_doc([
            _claim(1, "1. 一种装置，如说明书所述包括模块。"),
        ])
        results = check_claims_spec_reference(doc)
        assert results[0].status == "amend"

    def test_fig_ref_amend(self):
        doc = _cn_doc([
            _claim(1, "1. 一种装置，如图1所示包括模块。"),
        ])
        results = check_claims_spec_reference(doc)
        assert results[0].status == "amend"


# ── Check 19: Multi-multi dependency ──────────────────────────────────────


class TestMultiMultiDependency:
    def test_no_chain_pass(self):
        doc = _cn_doc([
            _claim(1, "A。"),
            _claim(2, "B。"),
            _claim(3, "C。", independent=False, dependencies=[1, 2],
                   multiple_dependent=True),
        ])
        results = check_multi_multi_dependency(doc)
        assert results[0].status == "pass"

    def test_chain_amend(self):
        doc = _cn_doc([
            _claim(1, "A。"),
            _claim(2, "B。"),
            _claim(3, "C。", independent=False, dependencies=[1, 2],
                   multiple_dependent=True),
            _claim(4, "D。", independent=False, dependencies=[2, 3],
                   multiple_dependent=True),
        ])
        results = check_multi_multi_dependency(doc)
        assert results[0].status == "amend"
        assert 4 in results[0].details_params["claims"]

    def test_single_dep_on_multi_pass(self):
        """Single-dependent on a multi-dependent is fine."""
        doc = _cn_doc([
            _claim(1, "A。"),
            _claim(2, "B。"),
            _claim(3, "C。", independent=False, dependencies=[1, 2],
                   multiple_dependent=True),
            _claim(4, "D。", independent=False, dependencies=[3]),
        ])
        results = check_multi_multi_dependency(doc)
        assert results[0].status == "pass"


# ── Check 20: Dependent ordering ─────────────────────────────────────────


class TestDependentOrdering:
    def test_correct_ordering_pass(self):
        doc = _cn_doc([
            _claim(1, "A。"),
            _claim(2, "B。", independent=False, dependencies=[1]),
            _claim(3, "C。", independent=False, dependencies=[1]),
            _claim(4, "D。"),
            _claim(5, "E。", independent=False, dependencies=[4]),
        ])
        results = check_dependent_ordering(doc)
        assert results[0].status == "pass"

    def test_out_of_order_amend(self):
        doc = _cn_doc([
            _claim(1, "A。"),
            _claim(2, "B。", independent=False, dependencies=[1]),
            _claim(3, "C。"),  # second independent
            _claim(4, "D。", independent=False, dependencies=[1]),  # dep of claim 1 after claim 3
        ])
        results = check_dependent_ordering(doc)
        assert results[0].status == "amend"

    def test_single_independent_pass(self):
        doc = _cn_doc([
            _claim(1, "A。"),
            _claim(2, "B。", independent=False, dependencies=[1]),
        ])
        results = check_dependent_ordering(doc)
        assert results[0].status == "pass"

    def test_empty_pass(self):
        doc = _cn_doc([])
        results = check_dependent_ordering(doc)
        assert results[0].status == "pass"
