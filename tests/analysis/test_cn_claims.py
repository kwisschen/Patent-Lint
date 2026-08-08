# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
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
    _extend_neng_compound_cn,
)
from patentlint.models import Claim, CnPatentDocument


class TestExtendNengCompoundCn:
    """能量 / 能源 follow-gate - parity mirror of TW issue #75."""

    def test_energy_compound_reextended(self):
        assert _extend_neng_compound_cn("静电", 2, "静电能量大于一值") == ("静电能量", 4)

    def test_follow_gate_stops_before_comparison_verb(self):
        noun, _ = _extend_neng_compound_cn("放电", 2, "放电能量大于一阈值")
        assert noun == "放电能量"

    def test_modal_neng_not_extended(self):
        assert _extend_neng_compound_cn("模块", 2, "模块能控制电流") == ("模块", 2)


class TestExtendShiCompoundCn:
    """R47 时-compound follow-gate - timer/clock/period nouns truncated by
    the _NOUN_CHARS_CN 时-exclusion (定时器→定, 录入时间项→录入)."""

    def test_timer_compound_reextended(self):
        # 配置第一定时器，… - comma bounds the compound (real drafting shape).
        from patentlint.analysis.cn_claims import _extend_shi_compound_cn
        assert _extend_shi_compound_cn("第一定", 3, "第一定时器，所述第一定时器") == (
            "第一定时器", 5
        )

    def test_time_period_compound_reextended(self):
        from patentlint.analysis.cn_claims import _extend_shi_compound_cn
        noun, _ = _extend_shi_compound_cn("录入", 2, "录入时间项，从外部库")
        assert noun == "录入时间项"

    def test_when_clause_shi_not_extended(self):
        # 在X时， - 时 is followed by a comma/connective, never a noun
        # suffix → the follow-gate leaves the when-clause boundary intact.
        from patentlint.analysis.cn_claims import _extend_shi_compound_cn
        assert _extend_shi_compound_cn("监听", 2, "监听时，触发启动") == ("监听", 2)


class TestExtendYingCompoundCn:
    """R48 应-compound precursor-gate - reaction/effect/sense nouns truncated
    by the _NOUN_CHARS_CN 应-exclusion (反应器→反, 晶化反应→晶化反)."""

    def test_reaction_compound_reextended(self):
        from patentlint.analysis.cn_claims import _extend_ying_compound_cn
        assert _extend_ying_compound_cn("晶化反", 3, "晶化反应，压力为") == (
            "晶化反应", 4
        )

    def test_reactor_compound_reextended(self):
        from patentlint.analysis.cn_claims import _extend_ying_compound_cn
        noun, _ = _extend_ying_compound_cn("第一反", 3, "第一反应器，用于")
        assert noun == "第一反应器"

    def test_gray_adverb_not_extended(self):
        # 执行相应 - 相 is NOT in the precursor whitelist (相应 = adverb).
        from patentlint.analysis.cn_claims import _extend_ying_compound_cn
        assert _extend_ying_compound_cn("执行相", 3, "执行相应的操作") == ("执行相", 3)

    def test_modal_ying_not_extended(self):
        # 系统应该 - 统 is not a reaction precursor → modal guard preserved.
        from patentlint.analysis.cn_claims import _extend_ying_compound_cn
        assert _extend_ying_compound_cn("系统", 2, "系统应该启动") == ("系统", 2)


class TestLeadingQuantifierCapTruncationCn:
    """R49 - _NOUN_CHARS_CN {2,12} cap truncates a long compound when a leading
    quantifier eats the budget (一个或更多个便携式手持控制器→…控)."""

    def test_quantifier_inflated_compound_resolves(self):
        # End-to-end: the reference now matches its bare intro, no FP.
        from patentlint.models import Claim, CnPatentDocument
        from patentlint.analysis.cn_claims import check_antecedent_basis_cn
        text = (
            "1.一种系统，包括：一个或更多个便携式手持控制器，"
            "其中所述一个或更多个便携式手持控制器用于操作。"
        )
        doc = CnPatentDocument(
            title="系统", claims=[Claim(id=1, text=text, independent=True)]
        )
        flagged = [
            f["term"] for f in check_antecedent_basis_cn(doc)
            if "便携式手持控" in f["term"]
        ]
        # The mid-compound truncation (…控) must not be emitted as a missing
        # antecedent; the reference resolves against the bare intro.
        assert all(t.endswith("控制器") for t in flagged), flagged


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
        # 或 (or) alternative - common multi-dep form.
        doc = _cn_doc([
            _claim(1, "1. 一种装置。"),
            _claim(2, "2. 一种方法。"),
            _claim(3, "3. 根据权利要求1或2所述的系统，其特征在于，包括部件。",
                   independent=False, dependencies=[1, 2], multiple_dependent=True),
        ])
        results = check_dependency_format(doc)
        assert results[0].status == "pass"

    def test_multi_dep_range_renyi_yi_xiang_pass(self):
        # 根据权利要求X至Y中任意一项所述的 - range + 中任意一项
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
        # 根据权利要求1‑5任一项所述的 - non-breaking hyphen range, no 中
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

    def test_latin_prefix_unbracketed_verify(self):
        """R1 / IC2 unbracketed Latin-prefix designators are 符号 under
        实施细则 §22 - must be flagged in CN claims too."""
        doc = _cn_doc([
            _claim(1, "1. 一种电路，包括一电阻R1和一晶体管Q2。"),
        ])
        results = check_reference_numeral_parentheses(doc)
        assert results[0].status == "verify"
        assert results[0].details_params["claims"] == [1]

    def test_latin_prefix_in_parens_pass(self):
        doc = _cn_doc([
            _claim(1, "1. 一种电路，包括一电阻(R1)和一晶体管(Q2)。"),
        ])
        results = check_reference_numeral_parentheses(doc)
        assert results[0].status == "pass"


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
        """如权利要求1所记载的 - JP-translation form, mirrors TW bug fix."""
        doc = _cn_doc([
            _claim(1, "1. 一种盖组件，其特征在于包括本体。"),
            _claim(2, "2. 如权利要求1所记载的盖组件，其特征在于还包括嵌合部。",
                   independent=False, dependencies=[1]),
        ])
        results = check_subject_name_consistency(doc)
        assert results[0].status == "pass"

    def test_gen_ju_ji_zai_de_pass(self):
        """根据权利要求1所记载的 - JP-translation formal."""
        doc = _cn_doc([
            _claim(1, "1. 一种盖组件，其特征在于包括本体。"),
            _claim(2, "2. 根据权利要求1所记载的盖组件，其特征在于还包括嵌合部。",
                   independent=False, dependencies=[1]),
        ])
        results = check_subject_name_consistency(doc)
        assert results[0].status == "pass"

    def test_jie_shi_de_pass(self):
        """根据权利要求1所揭示的 - formal alternative."""
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
            if r.message_key == "check.cn.claims.subjectConsistencyParseUnclear.verify"
        ]
        mismatch = [
            r for r in results
            if r.message_key == "check.cn.claims.subjectConsistency.verify"
        ]
        assert len(unclear) == 1
        assert len(mismatch) == 0
        assert unclear[0].diagnostics is not None
        assert unclear[0].diagnostics["dep_path"] == "fallthrough"

    def test_yiju_and_bare_openers_route_to_dep_prefix(self):
        """#328 CN parity: 依据 and the opener-less bare form route to
        dep_prefix (agreeing with the _CN_DEPENDENCY parser), not fallthrough.
        The wider 基于 opener stays unrecognized (see parseUnclear test)."""
        from patentlint.analysis.cn_claims import _extract_subject_with_path
        assert _extract_subject_with_path(
            "依据权利要求1所述的装置，其特征在于还包括Z。"
        )[1] == "dep_prefix"
        assert _extract_subject_with_path(
            "权利要求1所述的装置，其特征在于还包括Z。"
        )[1] == "dep_prefix"

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
        the claims they were found in - previously the walker emitted only
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
    """R21 - `_dym_quality_reject_cn` filters out over-captured DYMs."""

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
    """审查指南 第二部分第二章 §3.1.1: advisory - indep claims conventionally
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


class TestGarbageCaptureSweepR67:
    """R67 (2026-05-05) garbage-capture sweep on CN walker.

    Two safe fixes:
    1. 具有 added to _LEADING_VERB_PREFIXES_CN - strips possession verb
       prefix so `所述具有酸解离性基的结构单元` resolves on the head
       noun instead of emitting `具有酸解离性基` as a meaningless term.
    2. 由 added to _NOUN_CHARS_CN regex boundary - prevents over-capture
       across `X由Y` ("X composed of Y") relational frames. CN112271269B
       previously emitted `交联网状结构由可交联配体` (the bare relational
       句); now emits `交联网状结构` (the actual antecedent term).
    """

    def test_jou_strip_silences_meaningless_term(self):
        """所述具有X的Y → walker no longer emits the meaningless `具有X`."""
        from patentlint.analysis.cn_claims import check_antecedent_basis_cn
        doc = _cn_doc([
            _claim(
                1,
                "1. 一种组合物，所述具有酸解离性基的结构单元由下述式表示。",
            ),
        ])
        issues = check_antecedent_basis_cn(doc)
        # Walker should not surface `具有酸解离性基` as a reference term -
        # 具有 is a verb, not part of an element name.
        assert not any("具有" in i["term"] for i in issues), issues

    def test_you_boundary_truncates_capture(self):
        """所述<noun>由<another_noun> - capture stops before 由."""
        from patentlint.analysis.cn_claims import check_antecedent_basis_cn
        doc = _cn_doc([
            _claim(
                1,
                "1. 一种结构，包含一可交联配体，"
                "所述交联网状结构由可交联配体形成。",
            ),
        ])
        issues = check_antecedent_basis_cn(doc)
        # If walker emits, term should NOT span across 由.
        for i in issues:
            assert "由" not in i["term"], i


class TestVerbOnlySuppressionR68:
    """R68 (2026-05-06) - verb-only walker degenerate fragments.

    `所述确定` / `所述获得` / `所述进行` etc. surface when the walker
    regex stops at 的 or other boundary and the leading verb is left
    bare. These bare verbs are NEVER drafter-intended antecedent
    references; suppress at emit time.
    """

    def test_quoque_che_ding_suppressed(self):
        from patentlint.analysis.cn_claims import check_antecedent_basis_cn
        doc = _cn_doc([
            _claim(
                1,
                "1. 一种方法，包含一参数，根据所述参数确定的结果输出至显示屏。",
            ),
        ])
        issues = check_antecedent_basis_cn(doc)
        assert not any(i["term"] == "确定" for i in issues), issues

    def test_jin_xing_suppressed(self):
        from patentlint.analysis.cn_claims import check_antecedent_basis_cn
        doc = _cn_doc([
            _claim(
                1,
                "1. 一种方法，用于进行的步骤包含数据采集和处理。",
            ),
        ])
        issues = check_antecedent_basis_cn(doc)
        assert not any(i["term"] == "进行" for i in issues), issues

    def test_huo_de_suppressed(self):
        from patentlint.analysis.cn_claims import check_antecedent_basis_cn
        doc = _cn_doc([
            _claim(
                1,
                "1. 一种方法，所述获得的数据存储在存储模块中。",
            ),
        ])
        issues = check_antecedent_basis_cn(doc)
        assert not any(i["term"] == "获得" for i in issues), issues


class TestTrailingLaiSuppressionR68:
    """R68 (2026-05-06) - trailing 来 verb-particle strip.

    `所述<noun>来自X` constructions leave `<noun>来` as the term after
    walker captures past the regex boundary. 来 is a verb tail particle
    ("come"); strip it as a single-char trailing suffix.
    """

    def test_trailing_lai_stripped_cn(self):
        from patentlint.analysis.cn_claims import check_antecedent_basis_cn
        doc = _cn_doc([
            _claim(
                1,
                "1. 一种装置，包含一信号源，所述测量值来自所述信号源。",
            ),
        ])
        issues = check_antecedent_basis_cn(doc)
        # No emit with bare `测量值来` - strip 来 → 测量值, then test
        # against intros (not introduced as `一测量值` so emits as
        # `测量值` cleanly OR is silent if drafter introduces it elsewhere).
        for i in issues:
            assert not i["term"].endswith("来"), i

    def test_3char_trailing_lai_stripped_cn(self):
        """3-char term ending in 来 - relaxed-guard set allows residual ≥ 2."""
        from patentlint.analysis.cn_claims import check_antecedent_basis_cn
        doc = _cn_doc([
            _claim(
                1,
                "1. 一种装置，所述行为来自传感器输出。",
            ),
        ])
        issues = check_antecedent_basis_cn(doc)
        # `行为来` (3 chars) - strip 来 → `行为` (2 chars residual).
        # Either silenced or emitted as bare `行为`, never `行为来`.
        for i in issues:
            assert not i["term"].endswith("来"), i

    def test_direction_noun_xiang_not_stripped_cn(self):
        """WS-B1: 向 is a bound noun suffix in direction nouns (方向/轴向/…) -
        must NOT be stripped (was truncating 所述圆周方向 → 圆周方, a corpus FP)."""
        from patentlint.analysis.cn_claims import clean_noun_phrase_cn
        for noun in ("圆周方向", "第一方向", "第一取向", "轴向", "径向"):
            assert clean_noun_phrase_cn(noun) == noun, noun

    def test_non_direction_xiang_still_stripped_cn(self):
        """The 向 guard is narrow: a non-direction stem before 向 still strips
        (preposition 'toward'), residual ≥ 3 retained."""
        from patentlint.analysis.cn_claims import clean_noun_phrase_cn
        # 器 is not a direction stem → 向 strips; residual 传感器 (3) ≥ 3.
        assert clean_noun_phrase_cn("传感器向") == "传感器"


# ─────────────────────────────────────────────────────────────────────────
# R35 - CN bare-noun-introduction rescue (mirror of TW R7)
# ─────────────────────────────────────────────────────────────────────────


class TestBareNounIntroductionCn:
    """End-to-end: the rescue resolves verb-object intros, guards hold."""

    def test_verb_object_intro_resolves(self):
        """接收输入信号 (verb-object) resolves 所述输入信号."""
        from patentlint.analysis.cn_claims import check_antecedent_basis_cn
        doc = _cn_doc([
            _claim(1, "1. 一种方法，包括接收输入信号，并处理所述输入信号。"),
        ])
        assert check_antecedent_basis_cn(doc) == []

    def test_存在_X_in_conditional_clause_resolves(self):
        """在存在已知不良时…所述已知不良 - verb-object in 在…时 clause
        (the CN110276410B BOE case that motivated R20 reversal)."""
        from patentlint.analysis.cn_claims import check_antecedent_basis_cn
        doc = _cn_doc([
            _claim(1, "1. 一种方法，在检测对象存在已知不良时，"
                      "抽取与所述已知不良有关的生产数据。"),
        ])
        assert check_antecedent_basis_cn(doc) == []

    def test_ancestor_verb_object_resolves_dependent(self):
        """ancestor 接收输入信号 resolves 所述输入信号 in dep claim."""
        from patentlint.analysis.cn_claims import check_antecedent_basis_cn
        doc = _cn_doc([
            _claim(1, "1. 一种方法，包括接收输入信号。"),
            _claim(2, "2. 根据权利要求1所述的方法，其中所述输入信号被放大。",
                   independent=False, dependencies=[1]),
        ])
        assert check_antecedent_basis_cn(doc) == []

    def test_compound_tail_still_flagged(self):
        """使用者介面-style: 接口 as tail of 图形接口 is NOT a bare intro
        (guard a - whole-compound-boundary)."""
        from patentlint.analysis.cn_claims import check_antecedent_basis_cn
        doc = _cn_doc([
            _claim(1, "1. 一种方法，包括一程序。"),
            _claim(2, "2. 根据权利要求1所述的方法，其中所述程序形成一图形界面，"
                      "并显示在该界面上。",
                   independent=False, dependencies=[1]),
        ])
        issues = check_antecedent_basis_cn(doc)
        assert any(i["term"] == "界面" for i in issues), issues

    def test_possessive_de_resolves_via_r37_possessive_arm(self):
        """`所述U盘的标识数据` is now correctly resolved as a possessive
        intro of 标识数据 (U盘's identification data) via the R37
        has_possessive_introduction_cn arm. Pre-R37 this was flagged
        under the stricter doctrine where 的-headed was blanket-rejected
        as ambiguous relative-clause; R37's narrowed scope (requires
        definite-reference 所述/前述/该 prefix + non-ordinal term)
        correctly identifies this as pure possessive (U盘 is a noun,
        not a verb/adjective phrase). Guard (b) on has_bare_noun_introduction_cn
        is preserved separately for the bare-noun arm - see
        test_r36_possessive_de_still_rejected (which tests the bare-noun
        function directly)."""
        from patentlint.analysis.cn_claims import check_antecedent_basis_cn
        doc = _cn_doc([
            _claim(1, "1. 一种装置，包括一U盘，所述U盘的标识数据被存储，"
                      "并读取所述标识数据。"),
        ])
        issues = check_antecedent_basis_cn(doc)
        assert not any(i["term"] == "标识数据" for i in issues), issues

    # R37 (2026-06-01) - TW R9 parity. has_possessive_introduction_cn
    # closes the (所述|前述|该)<X>(的|之)<term> coverage gap for short
    # locative-attribute possessive intros (顶面/底面/侧面/端面).
    # Ordinal-led terms (第一X etc.) excluded to preserve R20 protect
    # calls on CN115485995B c82/c124.

    def test_r37_possessive_de_intro_short_locative(self):
        from patentlint.analysis.cn_claims import has_possessive_introduction_cn
        text = "所述第二波长发光元件的顶面外露于所述反射层，且所述顶面被覆盖。"
        ref = text.find("所述顶面被")
        assert has_possessive_introduction_cn(text, [], "顶面", ref) is True

    def test_r37_possessive_zhi_intro_classical_variant(self):
        # 之 (classical / JP-translation variant) also accepted in CN.
        from patentlint.analysis.cn_claims import has_possessive_introduction_cn
        text = "所述支架之底面接触基板，且所述底面被覆盖。"
        ref = text.find("所述底面被")
        assert has_possessive_introduction_cn(text, [], "底面", ref) is True

    def test_r37_requires_definite_reference_marker(self):
        # Negative control: 的 without 所述/前述/该 prefix - must reject.
        from patentlint.analysis.cn_claims import has_possessive_introduction_cn
        text = "具有第一晶体管的外观，且所述外观为平整。"
        ref = text.find("所述外观")
        assert has_possessive_introduction_cn(text, [], "外观", ref) is False

    def test_r37_ordinal_led_term_excluded(self):
        # Critical narrowing: 第一X / 第二X / ... excluded. Preserves R20
        # protect labels on CN115485995B c82/c124's `所述第三信号相关的
        # 第一训练信号` shape.
        from patentlint.analysis.cn_claims import has_possessive_introduction_cn
        text = "所述第三信号相关的第一训练信号与所述第一训练信号为相关。"
        ref = text.find("所述第一训练信号为")
        assert has_possessive_introduction_cn(
            text, [], "第一训练信号", ref) is False

    def test_pure_missing_antecedent_still_flagged(self):
        """该外壳 with no intro anywhere stays flagged."""
        from patentlint.analysis.cn_claims import check_antecedent_basis_cn
        doc = _cn_doc([
            _claim(1, "1. 一种装置，包括一基板。"),
            _claim(2, "2. 根据权利要求1所述的装置，其中该外壳围绕所述基板。",
                   independent=False, dependencies=[1]),
        ])
        issues = check_antecedent_basis_cn(doc)
        assert any("外壳" in i["term"] for i in issues), issues


class TestBareNounHelperCn:
    """Direct unit coverage of has_bare_noun_introduction_cn boundaries."""

    def test_verb_object_accepted(self):
        from patentlint.analysis.cn_claims import has_bare_noun_introduction_cn
        txt = "一种方法，包括接收输入信号，并处理所述输入信号。"
        ro = txt.find("所述输入信号")
        assert has_bare_noun_introduction_cn(txt, [_claim(1, txt)], "输入信号", ro)

    def test_存在_in_conditional_clause_accepted(self):
        """在检测对象存在X时 - verb-object regardless of conditional wrapper."""
        from patentlint.analysis.cn_claims import has_bare_noun_introduction_cn
        txt = "在检测对象存在已知不良时，抽取所述已知不良。"
        ro = txt.find("所述已知不良")
        assert has_bare_noun_introduction_cn(txt, [_claim(1, txt)], "已知不良", ro)

    def test_compound_tail_rejected(self):
        from patentlint.analysis.cn_claims import has_bare_noun_introduction_cn
        txt = "其中所述程序形成一图形界面，并显示在该界面上。"
        ro = txt.find("该界面")
        assert not has_bare_noun_introduction_cn(
            txt, [_claim(1, txt)], "界面", ro)

    def test_possessive_de_rejected(self):
        from patentlint.analysis.cn_claims import has_bare_noun_introduction_cn
        txt = "所述U盘的标识数据被存储，并读取所述标识数据。"
        ro = txt.find("所述标识数据")
        assert not has_bare_noun_introduction_cn(
            txt, [_claim(1, txt)], "标识数据", ro)

    def test_short_term_below_gate(self):
        from patentlint.analysis.cn_claims import has_bare_noun_introduction_cn
        txt = "包括轴承，所述轴承转动。"
        ro = txt.find("所述轴承")
        assert not has_bare_noun_introduction_cn(txt, [_claim(1, txt)], "轴承", ro)

    # R36 (2026-05-29) - issues #141 / #142. Drafter wrote
    # `限位于第三位置或第四位置二者之一` then referenced both `该第三位置`
    # and `该第四位置`. Three mechanisms cover the case: (a) locative verb
    # `位于` accepted as bare-intro context; (b) Markush enumerator `或`
    # accepted as left clause boundary; (c) Markush closer `二者` accepted
    # as right clause boundary.

    def test_r36_locative_verb_intro(self):
        from patentlint.analysis.cn_claims import has_bare_noun_introduction_cn
        txt = "该弹性件用于将该延伸部限位于第三位置，并允许在该第三位置切换。"
        ro = txt.find("该第三位置")
        assert has_bare_noun_introduction_cn(txt, [_claim(1, txt)], "第三位置", ro)

    def test_r36_markush_enumerator_left_boundary(self):
        from patentlint.analysis.cn_claims import has_bare_noun_introduction_cn
        txt = "该弹性件用于将该延伸部限位于第三位置或第四位置二者之一，并在该第四位置切换。"
        ro = txt.find("该第四位置")
        assert has_bare_noun_introduction_cn(txt, [_claim(1, txt)], "第四位置", ro)

    def test_r36_markush_closer_right_boundary(self):
        from patentlint.analysis.cn_claims import has_bare_noun_introduction_cn
        # Even with the `或` left-boundary acceptance, the right side of
        # `第四位置` here is `二` - the Markush-closer carve-out lets it pass.
        txt = "限位于第三位置或第四位置二者之一，并在该第四位置切换。"
        ro = txt.find("该第四位置")
        assert has_bare_noun_introduction_cn(txt, [_claim(1, txt)], "第四位置", ro)

    def test_r36_possessive_de_still_rejected(self):
        # Critical negative control: `所述X相关的Y` must still reject Y as
        # a bare intro, even though `的` is in _BARE_NOUN_BOUNDARY_CN.
        # If this assertion fails, R36 over-broadened the left set and
        # would silence real §112(b) defects per CN115485995B c82/c124.
        from patentlint.analysis.cn_claims import has_bare_noun_introduction_cn
        txt = "所述第三信号相关的第一训练信号与所述第六信号相关的第二训练信号。"
        # Use end-of-text as ref_offset so the _scan looks at every occurrence
        assert not has_bare_noun_introduction_cn(
            txt, [_claim(1, txt)], "第一训练信号", len(txt))


# ─────────────────────────────────────────────────────────────────────────
# CN CRM non-transitory check (gap-fill: 专利法 §25 + 审查指南)
# ─────────────────────────────────────────────────────────────────────────


class TestCnCrmNonTransitory:
    def test_计算机可读介质_missing_amend(self):
        from patentlint.analysis.cn_claims import check_crm_non_transitory_cn
        doc = _cn_doc([_claim(1, "1. 一种计算机可读介质，其存储有指令用于执行方法。")])
        assert check_crm_non_transitory_cn(doc)[0].status == "amend"

    def test_存储介质_missing_amend(self):
        from patentlint.analysis.cn_claims import check_crm_non_transitory_cn
        doc = _cn_doc([_claim(1, "1. 一种存储介质，存储有数据。")])
        assert check_crm_non_transitory_cn(doc)[0].status == "amend"

    def test_with_非暂态_pass(self):
        from patentlint.analysis.cn_claims import check_crm_non_transitory_cn
        doc = _cn_doc([_claim(1, "1. 一种非暂态计算机可读介质，其存储有指令。")])
        assert check_crm_non_transitory_cn(doc)[0].status == "pass"

    def test_with_非暂时性_pass(self):
        from patentlint.analysis.cn_claims import check_crm_non_transitory_cn
        doc = _cn_doc([_claim(1, "1. 一种非暂时性计算机可读存储介质，存储指令。")])
        assert check_crm_non_transitory_cn(doc)[0].status == "pass"

    def test_machine_readable_media_amend(self):
        """机器可读介质 also a recognised CRM target."""
        from patentlint.analysis.cn_claims import check_crm_non_transitory_cn
        doc = _cn_doc([_claim(1, "1. 一种机器可读介质，存储指令。")])
        assert check_crm_non_transitory_cn(doc)[0].status == "amend"

    def test_media_alternative_媒体_amend(self):
        """计算机可读媒体 (less common but accepted) - recognised."""
        from patentlint.analysis.cn_claims import check_crm_non_transitory_cn
        doc = _cn_doc([_claim(1, "1. 一种计算机可读媒体，存储指令。")])
        assert check_crm_non_transitory_cn(doc)[0].status == "amend"


# --- indefiniteWording (审查指南 §3.2.2, conservative exemplary list) ---------


class TestCnIndefiniteWording:
    def _doc(self, *texts):
        claims = [
            Claim(id=i + 1, text=t, independent=(i == 0), dependencies=[] if i == 0 else [1])
            for i, t in enumerate(texts)
        ]
        return CnPatentDocument(claims=claims, input_format="google_patents_html")

    def test_clean_claim_passes(self):
        from patentlint.analysis.cn_claims import check_indefinite_wording_cn
        doc = self._doc("1. 一种装置，包括一壳体、一控制电路及一光源组。")
        res = check_indefinite_wording_cn(doc)
        assert res[0].status == "pass"
        assert res[0].message_key == "check.cn.claims.indefiniteWording.pass"

    def test_exemplary_verifies(self):
        from patentlint.analysis.cn_claims import check_indefinite_wording_cn
        doc = self._doc("1. 一种装置，包括一传感器，例如温度传感器。")
        res = check_indefinite_wording_cn(doc)
        assert res[0].status == "verify"
        assert res[0].message_key == "check.cn.claims.indefiniteWording.verify"
        assert res[0].diagnostics["flagged_claim_count"] == 1

    def test_deng_and_yue_excluded(self):
        """等 / 约 deliberately NOT flagged (corpus-noise; legit senses)."""
        from patentlint.analysis.cn_claims import check_indefinite_wording_cn
        doc = self._doc("1. 一种装置，其中第一齿轮等于第二齿轮，直径约为5毫米。")
        res = check_indefinite_wording_cn(doc)
        assert res[0].status == "pass"


class TestR54TrailingAndInteriorVerbParity:
    """R54 (2026-07-18) - TW R29 parity, verified latent on CN before mirroring."""

    def test_trailing_and_interior_verbs(self):
        from patentlint.analysis.cn_claims import clean_noun_phrase_cn as C
        assert C("预定输入电流值划分为多个级距") == "预定输入电流值"
        assert C("柱镜焦度随着一方位角变化") == "柱镜焦度"
        assert C("等效球面焦度满足下式") == "等效球面焦度"

    def test_satisfy_narrowed_to_formula_idiom(self):
        """FN-guard: a bare 满足 strip would truncate 'meets or exceeds'."""
        from patentlint.analysis.cn_claims import clean_noun_phrase_cn as C
        assert C("运行长度满足或超过所述阈值") == "运行长度满足或超过"


class TestR59MarkushConjunctionAndIntegration:
    """R59 (2026-08-01) - reports #448/#449/#451/#454 from one CNIPA
    drafter's on-chip integrated WDM draft. Each fix is paired with the
    FN control that decides its width.
    """

    def test_huozhe_markush_conjunction_stripped(self):
        # Report #451: 连接所述刻蚀衍射光栅结构、所述阵列波导光栅结构或者所述...
        from patentlint.analysis.cn_claims import clean_noun_phrase_cn as C
        assert C("阵列波导光栅结构或者") == "阵列波导光栅结构"

    def test_huozhe_reaches_spec_support(self):
        # Report #454: 所述第一输入波导的数量或者所述第二输入波导的数量.
        # The CN spec-support normalizer delegates to clean_noun_phrase_cn,
        # so Engine 2 inherits the fix.
        from patentlint.analysis.cn_spec_support import (
            _normalize_for_spec_support_cn as N,
        )
        assert N("数量或者") == "数量"

    def test_bare_huo_alone_could_not_reach_it(self):
        # Bare 或 has been a member since R36; the capture ends in 者, which
        # is why the two-character form was the whole gap.
        from patentlint.analysis.cn_claims import clean_noun_phrase_cn as C
        assert C("阵列波导光栅结构或") == "阵列波导光栅结构"

    def test_or_gate_noun_preserved(self):
        from patentlint.analysis.cn_claims import clean_noun_phrase_cn as C
        assert C("或门") == "或门"

    def test_integration_verb_stripped(self):
        # Reports #448 / #449: 所述波分复用器集成于一光子集成电路芯片上.
        # 于 is excluded from the CN noun chars, so the capture always ends
        # exactly at the verb.
        from patentlint.analysis.cn_claims import clean_noun_phrase_cn as C
        assert C("波分复用器集成") == "波分复用器"

    def test_integration_noun_modifier_preserved(self):
        # 集成 is a noun-modifier in these compounds - followed by its head
        # noun, never at the tail - so an endswith strip cannot reach them.
        from patentlint.analysis.cn_claims import clean_noun_phrase_cn as C
        assert C("集成电路") == "集成电路"
        assert C("大规模集成电路") == "大规模集成电路"
        assert C("片上集成波分复用器") == "片上集成波分复用器"
