# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Tests for patentlint.analysis.cn_claims."""

from patentlint.analysis.cn_claims import (
    check_claims_sequential,
    check_claims_spec_reference,
    check_dependency_format,
    check_dependent_ordering,
    check_forward_dependency,
    check_markush_open_transition,
    check_multi_multi_dependency,
    check_omnibus_claims,
    check_reference_numeral_parentheses,
    check_self_dependent,
    check_single_sentence,
    check_subject_name_consistency,
    check_transition_phrase,
    check_tw_terminology,
    detect_markush_open_transition_cn,
    detect_omnibus_claims_cn,
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

    def test_genju_verb_accepted(self):
        # CNIPA 审查指南 §3.3.1 canonical example uses 根据, which is the most
        # common verb in real CN drafts. Previously the regex required 如,
        # false-positiving on every 根据-using claim (user-reported on
        # CN114357105B, CN213655447U, CN117427144B fixtures).
        doc = _cn_doc([
            _claim(1, "1. 一种方法。"),
            _claim(2, "2. 根据权利要求1所述的方法，其特征在于，包括步骤A。",
                   independent=False, dependencies=[1]),
        ])
        results = check_dependency_format(doc)
        assert results[0].status == "pass"

    def test_anzhao_verb_accepted(self):
        doc = _cn_doc([
            _claim(1, "1. 一种方法。"),
            _claim(2, "2. 按照权利要求1所述的方法，其特征在于，包括步骤A。",
                   independent=False, dependencies=[1]),
        ])
        results = check_dependency_format(doc)
        assert results[0].status == "pass"

    def test_multi_dep_huo_form_pass(self):
        # 或 (or) alternative — common multi-dep form.
        doc = _cn_doc([
            _claim(1, "1. 一种装置。"),
            _claim(2, "2. 一种方法。"),
            _claim(3, "3. 根据权利要求1或2所述的系统，其特征在于，包括部件。",
                   independent=False, dependencies=[1, 2], multiple_dependent=True),
        ])
        results = check_dependency_format(doc)
        assert results[0].status == "pass"

    def test_multi_dep_range_renyi_yi_xiang_pass(self):
        # 根据权利要求X至Y中任意一项所述的 — range + 中任意一项
        doc = _cn_doc([
            _claim(1, "1. 一种装置。"),
            _claim(2, "2. 装置2。"),
            _claim(3, "3. 装置3。"),
            _claim(4, "4. 根据权利要求1至3中任意一项所述的装置，其特征在于部件A。",
                   independent=False, dependencies=[1, 2, 3], multiple_dependent=True),
        ])
        results = check_dependency_format(doc)
        assert results[0].status == "pass"

    def test_multi_dep_endash_range_pass(self):
        # 根据权利要求1‑5任一项所述的 — non-breaking hyphen range, no 中
        doc = _cn_doc([
            _claim(1, "1. 一种方法。"),
            _claim(2, "2. 方法2。"),
            _claim(3, "3. 根据权利要求1‑5任一项所述的方法，其特征在于步骤A。",
                   independent=False, dependencies=[1, 2], multiple_dependent=True),
        ])
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


# ── Check 15: Subject matter consistency ──────────────────────────────────


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

    def test_descriptive_preamble_suffix_pass(self):
        # Parent preamble carries a qualifier phrase the dependent drops; the
        # dep subject matter is still a suffix of the parent's, so the claim
        # pair is consistent under 审查指南 一致 semantics. Regression guard
        # against the FP where ~100% of real-corpus deps fired before the
        # symmetric extractor + suffix-containment fix.
        doc = _cn_doc([
            _claim(1, "1. 一种基于深度学习模型的数据生成方法，其特征在于包括步骤。"),
            _claim(2, "2. 如权利要求1所述的数据生成方法，其特征在于还包括其他步骤。",
                   independent=False, dependencies=[1]),
        ])
        results = check_subject_name_consistency(doc)
        assert results[0].status == "pass"

    def test_duplicate_claim_ids_deduped_in_emit(self):
        # A malformed docx can print two distinct claims under the same
        # printed number (e.g., two "44."s in CN115952274B). The parser
        # keeps both so claims_sequential can flag the duplication, but
        # the subject-matter emit must not show "44, 44".
        doc = _cn_doc([
            _claim(1, "1. 一种数据处理装置，其特征在于包括模块。"),
            _claim(44, "44. 如权利要求1所述的信号处理系统，其特征在于还包括部件。",
                   independent=False, dependencies=[1]),
            _claim(44, "44. 如权利要求1所述的信号处理系统，其特征在于还包括另一部件。",
                   independent=False, dependencies=[1]),
        ])
        results = check_subject_name_consistency(doc)
        assert results[0].status == "verify"
        assert results[0].details_params["claims"] == [44]
        assert results[0].details_params["count"] == 1
        assert "44, 44" not in results[0].message

    def test_ji_zai_connective_pass(self):
        """如权利要求1所记载的 — JP-translation form, mirrors TW bug fix."""
        doc = _cn_doc([
            _claim(1, "1. 一种盖组件，其特征在于包括本体。"),
            _claim(2, "2. 如权利要求1所记载的盖组件，其特征在于还包括嵌合部。",
                   independent=False, dependencies=[1]),
        ])
        results = check_subject_name_consistency(doc)
        assert results[0].status == "pass"

    def test_gen_ju_ji_zai_de_pass(self):
        """根据权利要求1所记载的 — JP-translation formal."""
        doc = _cn_doc([
            _claim(1, "1. 一种盖组件，其特征在于包括本体。"),
            _claim(2, "2. 根据权利要求1所记载的盖组件，其特征在于还包括嵌合部。",
                   independent=False, dependencies=[1]),
        ])
        results = check_subject_name_consistency(doc)
        assert results[0].status == "pass"

    def test_jie_shi_de_pass(self):
        """根据权利要求1所揭示的 — formal alternative."""
        doc = _cn_doc([
            _claim(1, "1. 一种盖组件，其特征在于包括本体。"),
            _claim(2, "2. 根据权利要求1所揭示的盖组件，其特征在于还包括嵌合部。",
                   independent=False, dependencies=[1]),
        ])
        results = check_subject_name_consistency(doc)
        assert results[0].status == "pass"

    def test_parse_fallthrough_emits_parseUnclear_not_verify(self):
        """ADR-145: parse fallthrough (unrecognized preamble form) → parseUnclear."""
        doc = _cn_doc([
            _claim(1, "1. 一种盖组件，其特征在于包括本体。"),
            _claim(2, "2. 基于权利要求1的组件，其特征在于还包括Z。",
                   independent=False, dependencies=[1]),
        ])
        results = check_subject_name_consistency(doc)
        unclear = [
            r for r in results
            if r.message_key == "check.cn.claims.subjectConsistencyParseUnclear"
        ]
        mismatch = [
            r for r in results
            if r.message_key == "check.cn.claims.subjectConsistency.verify"
        ]
        assert len(unclear) == 1
        assert len(mismatch) == 0
        assert unclear[0].diagnostics is not None
        assert unclear[0].diagnostics["dep_path"] == "fallthrough"

    def test_diagnostics_attached_on_verify(self):
        """Mismatch finding carries structural fingerprint."""
        doc = _cn_doc([
            _claim(1, "1. 一种盖组件，其特征在于包括本体。"),
            _claim(2, "2. 如权利要求1所述的信号处理系统，其特征在于还包括部件。",
                   independent=False, dependencies=[1]),
        ])
        results = check_subject_name_consistency(doc)
        mismatch = [
            r for r in results
            if r.message_key == "check.cn.claims.subjectConsistency.verify"
        ]
        assert len(mismatch) == 1
        dx = mismatch[0].diagnostics
        assert dx is not None
        assert dx["dep_path"] == "dep_prefix"
        assert dx["parent_path"] == "indep_prefix"
        assert dx["parent_subject_charlen"] > 0
        assert dx["dep_subject_charlen"] > 0


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

    def test_tw_simplified_amend(self):
        doc = _cn_doc([_claim(1, "1. 根据请求项1所述的装置。")])
        results = check_tw_terminology(doc)
        assert results[0].status == "amend"

    def test_tw_traditional_amend(self):
        doc = _cn_doc([_claim(1, "1. 根據請求項1所述的裝置。")])
        results = check_tw_terminology(doc)
        assert results[0].status == "amend"

    def test_flagged_phrases_items_surfaced(self):
        """FlaggedTermList chips surface the actual detected TW terms and
        the claims they were found in — previously the walker emitted only
        a boolean-ish finding with no token content."""
        doc = _cn_doc([
            _claim(1, "1. 一种装置。"),
            _claim(2, "2. 根据请求项1所述的装置。"),
            _claim(3, "3. 根據請求項1所述的裝置。"),
        ])
        results = check_tw_terminology(doc)
        items = results[0].details_params.get("flagged_phrases", {}).get("items", [])
        tokens = [i["token"] for i in items]
        locations = [i["location"] for i in items]
        assert "请求项" in tokens
        assert "請求項" in tokens
        assert 2 in locations
        assert 3 in locations


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

    def test_flagged_phrases_items_surfaced(self):
        """FlaggedTermList chips surface the actual matched spec/drawing
        reference tokens, not just claim IDs. Previously the walker only
        emitted `count` and `claims`, losing the matched phrase content."""
        doc = _cn_doc([
            _claim(1, "1. 一种装置，如说明书所述包括模块。"),
            _claim(2, "2. 根据权利要求1所述的装置，如图1所示。"),
        ])
        results = check_claims_spec_reference(doc)
        items = results[0].details_params.get("flagged_phrases", {}).get("items", [])
        tokens = [i["token"] for i in items]
        assert "如说明书" in tokens
        assert "如图" in tokens
        for item in items:
            assert item["kind"] == "reference"
            assert isinstance(item["location"], int)


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


class TestDymQualityGate:
    """R21 — `_dym_quality_reject_cn` filters out over-captured DYMs."""

    def _reject(self, ref: str, dym: str) -> bool:
        from patentlint.analysis.cn_claims import _dym_quality_reject_cn
        return _dym_quality_reject_cn(ref, dym)

    def test_length_ratio_rejects_disproportionate(self):
        assert self._reject("IPC引擎硬件", "处理器核在IPC引擎硬件初始化时")

    def test_leading_particle_rejects_locative(self):
        assert self._reject("客户端进程", "在所述客户端进程")

    def test_leading_particle_rejects_preposition(self):
        assert self._reject("输入数据", "对历史输入数据项")

    def test_substring_wrap_rejects_trailing_conjunction(self):
        assert self._reject("第一训练信号", "第一训练信号与")
        assert self._reject("信息", "信息和")

    def test_legitimate_typo_dym_kept(self):
        assert not self._reject("第一预设", "第一预测")

    def test_legitimate_base_suffix_kept(self):
        assert not self._reject("初始地理预训练模型", "地理预训练模型")

    def test_same_length_kept(self):
        assert not self._reject("数据组", "数据集")

# ── Check 22: Omnibus claims (CN) ────────────────────────────────────────


class TestOmnibusClaimsCn:
    def test_pass_no_omnibus(self):
        doc = _cn_doc([
            _claim(1, '一种装置，包括基座（10）和盖（20），所述盖通过铰链与基座连接。')
        ])
        assert detect_omnibus_claims_cn(doc) == []
        results = check_omnibus_claims(doc)
        assert results[0].status == 'pass'

    def test_amend_shuomingshu_ref(self):
        doc = _cn_doc([
            _claim(1, '一种装置，如说明书所述。')
        ])
        assert detect_omnibus_claims_cn(doc) == [1]
        results = check_omnibus_claims(doc)
        assert results[0].status == 'amend'

    def test_amend_fig_ref(self):
        doc = _cn_doc([
            _claim(1, '一种装置，如附图所示。')
        ])
        assert detect_omnibus_claims_cn(doc) == [1]

    def test_long_claim_with_incidental_mention_not_flagged(self):
        # >40 CJK chars, so length guard kicks in.
        doc = _cn_doc([
            _claim(1,
                '一种装置，包括基座（10）、盖（20）、铰链（30）、弹簧（40）、'
                '开关（50）、显示器（60）和控制电路（70），其中所述控制电路的'
                '具体实施方式如说明书所述。')
        ])
        assert detect_omnibus_claims_cn(doc) == []


# ── Check 23: Markush open transition (CN) ───────────────────────────────


class TestMarkushOpenTransitionCn:
    def test_pass_closed_transition(self):
        doc = _cn_doc([
            _claim(1, '选自由铜、铁、铝组成的群组。')
        ])
        assert detect_markush_open_transition_cn(doc) == []
        results = check_markush_open_transition(doc)
        assert results[0].status == 'pass'

    def test_amend_open_transition_baokuo(self):
        doc = _cn_doc([
            _claim(1, '选自由包括铜、铁、铝。')
        ])
        pairs = detect_markush_open_transition_cn(doc)
        assert pairs == [(1, '包括')]
        results = check_markush_open_transition(doc)
        assert results[0].status == 'amend'

    def test_verify_open_transition_juyou(self):
        doc = _cn_doc([
            _claim(1, '选自由具有铜、铁、铝的基团。')
        ])
        pairs = detect_markush_open_transition_cn(doc)
        assert pairs == [(1, '具有')]



# ── check.cn.claims.independentPreamble ─────────────────────────────────


class TestCnIndependentPreamble:
    """审查指南 第二部分第二章 §3.1.1: advisory — indep claims conventionally
    open with 一种 (statute requires 主题名称, not literal 一种). Status is
    VERIFY (advisory), not AMEND (hard rule).
    """

    def test_independent_with_yizhong_passes(self):
        from patentlint.analysis.cn_claims import check_independent_preamble
        doc = _cn_doc([
            _claim(1, "1. 一种装置，其特征在于包括A。"),
        ])
        results = check_independent_preamble(doc)
        assert results[0].status == "pass"

    def test_independent_missing_yizhong_flags_verify(self):
        from patentlint.analysis.cn_claims import check_independent_preamble
        doc = _cn_doc([
            _claim(1, "1. 装置，其特征在于包括A。"),
        ])
        results = check_independent_preamble(doc)
        assert results[0].status == "verify"
        assert 1 in results[0].details_params["claims"]

    def test_dependent_claim_ignored(self):
        from patentlint.analysis.cn_claims import check_independent_preamble
        doc = _cn_doc([
            _claim(1, "1. 一种装置。"),
            _claim(2, "2. 根据权利要求1所述的装置，其特征在于包括B。",
                   independent=False, dependencies=[1]),
        ])
        results = check_independent_preamble(doc)
        assert results[0].status == "pass"


class TestParenAbbrevR34Cn:
    """R34 (2026-05-04) widening of CN R30 mechanism #6 paren-abbrev bridge.

    Mirror of TW R34: accept full-width 全角 parens + lowercase-full-form-
    comma-uppercase-abbrev shape. Cross-jurisdiction parity with TW.
    """

    def _intros(self, text: str) -> list[str]:
        from patentlint.analysis.cn_claims import extract_introductions_cn
        from patentlint.models import Claim
        c = Claim(id=1, text=text, independent=True, multiple_dependent=False, method_claim=False, dependencies=[])
        return [norm for _orig, norm in extract_introductions_cn(c)]

    def test_ascii_paren_simple_unchanged(self):
        intros = self._intros("一种用户设备(UE)，包括一处理器。")
        assert "UE" in intros, f"UE missing from {intros}"

    def test_full_width_paren_registers_abbrev(self):
        intros = self._intros("一种用户设备（UE），包括一处理器。")
        assert "UE" in intros, f"UE missing from {intros}"

    def test_lowercase_ff_comma_uppercase_abbrev(self):
        intros = self._intros("一种用户设备(user equipment, UE)，包括一处理器。")
        assert "UE" in intros, f"UE missing from {intros}"
