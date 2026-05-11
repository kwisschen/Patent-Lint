# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""Tests for CN specification-support analysis (专利法 §26 第4款).

Mirrors tests/analysis/test_tw_spec_support.py with CN-specific cases:
  - Bare-numeral strip (CN-specific; TIPO universally parenthesizes)
  - Disjunctive-conjunction split (X或Y → X, Y — CN-specific)
  - Existential-verb leading rejects (设有/装有/配置有)
  - tw_contamination skip (该等/该些 parser artifacts not double-reported)
  - 3-tier matcher (no Tier 0 symbol-table whitelist)
  - 背景技术 excluded from spec_text per 审查指南 §2.2.3
"""

from __future__ import annotations

from patentlint.analysis.cn_spec_support import (
    _build_inventory_cn,
    _collect_spec_text_cn,
    _has_interior_reject_cn,
    _has_leading_conjunction_cn,
    _has_leading_reject_cn,
    _is_boilerplate_cn,
    _normalize_for_spec_support_cn,
    _recover_from_midphrase_prefix_cn,
    _split_on_conjunction_cn,
    _strip_spec_support_trailing_tokens_cn,
    _strip_trailing_conjunction_cn,
    _tier3_char_window,
    attach_cross_references_cn,
    check_spec_support_cn,
)
from patentlint.models import Claim, CnPatentDocument, UnsupportedTerm


def _make_claim(cid: int, text: str, independent: bool = True, deps=None) -> Claim:
    return Claim(
        id=cid,
        text=text,
        independent=independent,
        method_claim=False,
        dependencies=deps or [],
    )


def _make_doc(
    *,
    claims: list[Claim] | None = None,
    technical_field: list[str] | None = None,
    background: list[str] | None = None,
    summary: list[str] | None = None,
    detailed_description: list[str] | None = None,
    drawings_description: list[str] | None = None,
) -> CnPatentDocument:
    return CnPatentDocument(
        claims=claims or [],
        technical_field=technical_field or [],
        background=background or [],
        summary=summary or [],
        detailed_description=detailed_description or [],
        drawings_description=drawings_description or [],
    )


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------


class TestNormalizeForSpecSupportCn:
    """_normalize_for_spec_support_cn: claim-side normalization."""

    def test_reference_form_prefix_stripped(self):
        assert _normalize_for_spec_support_cn("该基板") == "基板"
        assert _normalize_for_spec_support_cn("所述基板") == "基板"
        assert _normalize_for_spec_support_cn("前述基板") == "基板"

    def test_leading_preposition_stripped(self):
        assert _normalize_for_spec_support_cn("于所述基板") == "基板"
        assert _normalize_for_spec_support_cn("在所述容器本体") == "容器本体"
        # CN-specific prepositions (从/向/对 not in TW list). Use simple
        # 2-char nouns that the walker's normalization passes through
        # cleanly — preposition strip is this helper's own concern; walker
        # aggressiveness on compound nouns is tested separately.
        assert _normalize_for_spec_support_cn("从所述底座") == "底座"
        assert _normalize_for_spec_support_cn("向所述基板") == "基板"
        assert _normalize_for_spec_support_cn("对所述基板") == "基板"

    def test_paren_reference_numeral_stripped(self):
        assert _normalize_for_spec_support_cn("底座(10)") == "底座"
        assert _normalize_for_spec_support_cn("容器本体（100）") == "容器本体"
        assert _normalize_for_spec_support_cn("第一壳体(1a)") == "第一壳体"

    def test_paren_reference_numeral_unbalanced(self):
        """Walker captures may have unbalanced parens (CN213655447U BYD)."""
        assert _normalize_for_spec_support_cn("屏幕支撑组件(100") == "屏幕支撑组件"
        assert _normalize_for_spec_support_cn("底座(10") == "底座"

    def test_paren_reference_numeral_interior(self):
        """Non-anchored regex strips parens anywhere in the term, including
        interior position when walker capture has trailing text."""
        # Even if walker leaves `(100)的` mid-term, the paren strip removes it
        # (the walker normalize will then handle 的-terminated suffix)
        assert "(100)" not in _normalize_for_spec_support_cn("底座(100)")

    def test_bare_reference_numeral_stripped(self):
        """CN-specific: drafters often write bare numerals without parens."""
        assert _normalize_for_spec_support_cn("底座10") == "底座"
        assert _normalize_for_spec_support_cn("壳体10a") == "壳体"
        # Ordinal 第一 must NOT be misread as trailing digit of a preceding char
        assert _normalize_for_spec_support_cn("第一壳体") == "第一壳体"

    def test_midphrase_reference_prefix_recovered(self):
        assert _normalize_for_spec_support_cn("有所述高亮度区域") == "高亮度区域"
        assert _normalize_for_spec_support_cn("个所述电子元件") == "电子元件"

    def test_trailing_conjunction_stripped(self):
        assert _normalize_for_spec_support_cn("颜色与") == "颜色"
        assert _normalize_for_spec_support_cn("内环结构及") == "内环结构"
        assert _normalize_for_spec_support_cn("基板或") == "基板"

    def test_trailing_clause_token_stripped(self):
        assert _normalize_for_spec_support_cn("间距位于") == "间距"
        assert _normalize_for_spec_support_cn("第一部件之间") == "第一部件"
        assert _normalize_for_spec_support_cn("元件相连") == "元件"


class TestStripTrailingTokensCn:
    """_strip_spec_support_trailing_tokens_cn iterative strip."""

    def test_iterative_strip(self):
        # 元件位于之间 → 元件位于 → 元件
        assert _strip_spec_support_trailing_tokens_cn("元件位于之间") == "元件"

    def test_longest_first_priority(self):
        # 之间 (2 chars) preferred over 之 (not in list anyway)
        assert _strip_spec_support_trailing_tokens_cn("连接器之间") == "连接器"

    def test_no_strip_when_core_too_short(self):
        # Short core (after strip would leave <1 char) → no strip
        assert _strip_spec_support_trailing_tokens_cn("位于") == "位于"


class TestSplitOnConjunctionCn:
    """_split_on_conjunction_cn: splits including CN-specific 或."""

    def test_split_on_and(self):
        assert _split_on_conjunction_cn("基板及壳体") == ["基板", "壳体"]
        assert _split_on_conjunction_cn("基板和壳体") == ["基板", "壳体"]
        assert _split_on_conjunction_cn("基板与壳体") == ["基板", "壳体"]

    def test_split_on_or_cn_specific(self):
        """或 is CN-load-bearing: `包括A或B` means both A and B must be supported."""
        assert _split_on_conjunction_cn("电阻器或电容器") == ["电阻器", "电容器"]

    def test_no_split_if_right_side_too_short(self):
        # Right side would be only 1 char → protect compound
        result = _split_on_conjunction_cn("基板及A")
        assert result == ["基板及A"]


class TestLeadingRejectCn:
    """_has_leading_reject_cn: CN existential-verb + suffix-only leads."""

    def test_existential_verb_prefixes_rejected(self):
        assert _has_leading_reject_cn("设有底座") is True
        assert _has_leading_reject_cn("装有第一元件") is True
        assert _has_leading_reject_cn("配置有连接器") is True
        assert _has_leading_reject_cn("设置有第一凹槽") is True

    def test_suffix_only_leads_rejected(self):
        # 部/端 appear only as noun suffixes — if at position 0, capture mid-compound
        assert _has_leading_reject_cn("部底座") is True
        assert _has_leading_reject_cn("端元件") is True

    def test_legitimate_terms_pass(self):
        assert _has_leading_reject_cn("底座") is False
        assert _has_leading_reject_cn("第一连接器") is False
        assert _has_leading_reject_cn("开口部") is False  # 部 as suffix is fine


class TestInteriorRejectCn:
    """_has_interior_reject_cn: comprehensive structural markers."""

    def test_comparison_marker_rejected(self):
        assert _has_interior_reject_cn("X超过Y") is True
        assert _has_interior_reject_cn("A超出B") is True

    def test_relational_marker_rejected(self):
        assert _has_interior_reject_cn("X彼此Y") is True

    def test_claim_reference_anywhere_rejected(self):
        """权利要求 anywhere in term = walker meta-reference leakage."""
        assert _has_interior_reject_cn("权利要求") is True  # bare
        assert _has_interior_reject_cn("通信设备执行如权利要求") is True
        assert _has_interior_reject_cn("采用如权利要求1中任") is True

    def test_modal_auxiliary_rejected(self):
        assert _has_interior_reject_cn("单元能够") is True

    def test_adverb_markers_rejected(self):
        assert _has_interior_reject_cn("单元被进一步") is True
        assert _has_interior_reject_cn("方向依次") is True
        assert _has_interior_reject_cn("第一轴线相背地") is True
        assert _has_interior_reject_cn("相向地转动以使") is True

    def test_purposive_phrases_rejected(self):
        assert _has_interior_reject_cn("单元用于向第二设备") is True
        assert _has_interior_reject_cn("X以使Y") is True

    def test_locative_ordinal_rejected(self):
        assert _has_interior_reject_cn("单元在第二起始时刻") is True

    def test_preposition_phrase_rejected(self):
        assert _has_interior_reject_cn("沿远离") is True

    def test_passive_marker_rejected(self):
        assert _has_interior_reject_cn("X被进一步") is True
        assert _has_interior_reject_cn("X被执行") is True

    def test_clean_term_passes(self):
        assert _has_interior_reject_cn("基板") is False
        assert _has_interior_reject_cn("第一壳体") is False
        assert _has_interior_reject_cn("电子元件") is False

    def test_bare_被_in_compound_noun_NOT_rejected(self):
        """`被` alone is too common in legitimate compounds (被覆层,
        被加热部) to blanket-reject. Only multi-char patterns flagged."""
        assert _has_interior_reject_cn("被覆层") is False
        assert _has_interior_reject_cn("被加热部") is False


class TestLeadingConjunctionCn:
    """_has_leading_conjunction_cn: walker stranded conjunction prefix."""

    def test_or_stranded(self):
        assert _has_leading_conjunction_cn("或所述") is True

    def test_and_stranded(self):
        assert _has_leading_conjunction_cn("与所述") is True
        assert _has_leading_conjunction_cn("及X") is True
        assert _has_leading_conjunction_cn("和Y") is True

    def test_compound_conjunction_stranded(self):
        assert _has_leading_conjunction_cn("以及组件") is True

    def test_clean_terms_pass(self):
        assert _has_leading_conjunction_cn("基板") is False
        assert _has_leading_conjunction_cn("第一壳体") is False


class TestBoilerplateCn:
    """_is_boilerplate_cn: anaphoric markers + CN-only quantifiers."""

    def test_cn_only_quantifiers_rejected(self):
        assert _is_boilerplate_cn("多个") is True
        assert _is_boilerplate_cn("若干") is True  # CN-only
        assert _is_boilerplate_cn("一些") is True  # CN-only
        assert _is_boilerplate_cn("数个") is True
        assert _is_boilerplate_cn("两个") is True  # numeric-quantifier
        assert _is_boilerplate_cn("三个") is True

    def test_anaphoric_markers_rejected(self):
        assert _is_boilerplate_cn("前述") is True
        assert _is_boilerplate_cn("上述") is True

    def test_claim_reference_prefix_rejected(self):
        assert _is_boilerplate_cn("如权利要求4至权利要求10") is True
        assert _is_boilerplate_cn("根据权利要求1") is True
        # Bare 权利要求 (walker leakage when 如/根据 stripped upstream)
        assert _is_boilerplate_cn("权利要求") is True

    def test_legitimate_terms_pass(self):
        assert _is_boilerplate_cn("底座") is False
        assert _is_boilerplate_cn("第一连接器") is False

    def test_reference_particles_NOT_in_stoplist(self):
        """所述/其中 are reference particles; walker should never emit bare.
        Including them in boilerplate would mask walker bugs."""
        assert _is_boilerplate_cn("所述") is False
        assert _is_boilerplate_cn("其中") is False


class TestRecoverFromMidphrasePrefixCn:
    """_recover_from_midphrase_prefix_cn: 前述/所述/该 stranded at interior."""

    def test_recover_from_所述(self):
        assert _recover_from_midphrase_prefix_cn("有所述高亮度区域") == "高亮度区域"

    def test_recover_from_该(self):
        assert _recover_from_midphrase_prefix_cn("至该通讯模块") == "通讯模块"

    def test_position_0_ignored(self):
        # Position 0 handled upstream by strip_reference_form_prefix_cn
        assert _recover_from_midphrase_prefix_cn("所述基板") == "所述基板"


class TestStripTrailingConjunctionCn:
    """_strip_trailing_conjunction_cn including 或."""

    def test_strip_trailing_and(self):
        assert _strip_trailing_conjunction_cn("基板及") == "基板"
        assert _strip_trailing_conjunction_cn("壳体与") == "壳体"

    def test_strip_trailing_or_cn_specific(self):
        assert _strip_trailing_conjunction_cn("基板或") == "基板"


# ---------------------------------------------------------------------------
# Spec text collection
# ---------------------------------------------------------------------------


class TestCollectSpecTextCn:
    """_collect_spec_text_cn excludes 背景技术 per §26 第4款 strict reading."""

    def test_includes_technical_field_summary_detailed(self):
        doc = _make_doc(
            technical_field=["本发明涉及电子领域。"],
            summary=["所述基板用于支撑。"],
            detailed_description=["第一连接器连接至所述基板。"],
        )
        text = _collect_spec_text_cn(doc)
        assert "电子领域" in text
        assert "基板" in text
        assert "第一连接器" in text

    def test_excludes_background(self):
        """审查指南 §2.2.3: 背景技术 is prior-art context, not disclosure.
        A claim term supported only by 背景技术 is itself a §26 第4款 violation."""
        doc = _make_doc(
            background=["现有技术中，专利A公开了一种特殊底座。"],
            summary=["本发明的目的是改进。"],
        )
        text = _collect_spec_text_cn(doc)
        assert "特殊底座" not in text
        assert "改进" in text

    def test_excludes_drawings_description(self):
        doc = _make_doc(
            drawings_description=["图1示出了底座。"],
            detailed_description=["主要结构如下。"],
        )
        text = _collect_spec_text_cn(doc)
        assert "图1" not in text
        assert "主要结构" in text


# ---------------------------------------------------------------------------
# Inventory building
# ---------------------------------------------------------------------------


class TestBuildInventoryCn:
    """_build_inventory_cn: extraction + hygiene filtering + tw_contamination skip."""

    def test_basic_intro_extracted(self):
        claim = _make_claim(1, "一种装置，包括第一壳体。")
        inv = _build_inventory_cn(
            [claim],
            contamination_terms=frozenset(),
        )
        # At minimum the intro should surface (normalized)
        terms = [t for _, t in inv]
        assert any("壳体" in t for t in terms)

    def test_tw_contamination_skipped(self):
        """Terms flagged as tw_contamination (该等/该些 residue from 繁转简)
        should not enter the spec_support inventory."""
        claim = _make_claim(1, "一种装置，包括该等壳体。")
        # Simulate antecedent walker flagging 壳体 as tw_contamination
        inv = _build_inventory_cn(
            [claim],
            contamination_terms=frozenset({"壳体"}),
        )
        terms = [t for _, t in inv]
        assert "壳体" not in terms

    def test_generic_terms_rejected(self):
        # Bare genus terms like 方法, 装置 should not enter inventory
        claim = _make_claim(1, "一种方法，包括步骤一。")
        inv = _build_inventory_cn(
            [claim],
            contamination_terms=frozenset(),
        )
        terms = [t for _, t in inv]
        assert "方法" not in terms
        assert "装置" not in terms
        assert "技术方案" not in terms


# ---------------------------------------------------------------------------
# Tier 3 char window matcher
# ---------------------------------------------------------------------------


class TestTier3CharWindow:
    """Bigram Jaccard window fallback for compound-assembly patterns."""

    def test_all_bigrams_present_in_window(self):
        norm_term = "第一壳体"  # bigrams: {第一, 一壳, 壳体}
        spec = "本发明提供一种装置，包括第一壳体以及其他元件。"
        assert _tier3_char_window(norm_term, spec) is True

    def test_bigrams_missing_returns_false(self):
        norm_term = "第一壳体"
        spec = "完全无关的文本，没有关键字。"
        assert _tier3_char_window(norm_term, spec) is False


# ---------------------------------------------------------------------------
# End-to-end spec_support
# ---------------------------------------------------------------------------


class TestCheckSpecSupportCn:
    """check_spec_support_cn: end-to-end matcher over realistic docs."""

    def test_empty_doc_returns_empty(self):
        doc = _make_doc()
        assert check_spec_support_cn(doc) == []

    def test_supported_term_passes(self):
        """Claim term present verbatim in 具体实施方式 → no finding."""
        claim = _make_claim(1, "一种装置，包括第一壳体。")
        doc = _make_doc(
            claims=[claim],
            detailed_description=["所述第一壳体设置于基板上。"],
        )
        unsupported = check_spec_support_cn(doc)
        phrases = [ut.phrase for ut in unsupported]
        assert "第一壳体" not in phrases

    def test_unsupported_term_flagged(self):
        """Claim term absent from spec → flagged."""
        claim = _make_claim(1, "一种装置，包括完全未披露的新奇组件。")
        doc = _make_doc(
            claims=[claim],
            detailed_description=["本发明描述了其他结构。"],
        )
        unsupported = check_spec_support_cn(doc)
        phrases = [ut.phrase for ut in unsupported]
        # At least one capture from the claim that isn't in spec should flag
        assert len(phrases) > 0

    def test_term_supported_only_by_background_is_flagged(self):
        """审查指南 §2.2.3: term supported only by 背景技术 is §26 第4款
        violation — 背景技术 is prior-art context, not disclosure."""
        claim = _make_claim(1, "一种装置，包括第一特殊组件。")
        doc = _make_doc(
            claims=[claim],
            # Term appears ONLY in 背景技术 — should still be flagged
            background=["现有技术中已知第一特殊组件的功能。"],
            detailed_description=["本发明的改进如下。"],
        )
        unsupported = check_spec_support_cn(doc)
        phrases = [ut.phrase for ut in unsupported]
        # 特殊组件 should be flagged because background is excluded
        assert any("特殊组件" in p for p in phrases)


# ---------------------------------------------------------------------------
# Cross-reference attachment
# ---------------------------------------------------------------------------


class TestAttachCrossReferencesCn:
    """attach_cross_references_cn: links same-term findings across walkers."""

    def test_overlapping_term_gets_cross_ref(self):
        antecedent_findings = [
            {"claim_id": 1, "term": "基板", "reference_form": "所述",
             "claim_text": "", "suggested_match": None, "cross_ref": None},
        ]
        unsupported = [
            UnsupportedTerm(claim_number=1, phrase="基板", tiers_checked=[]),
        ]
        attach_cross_references_cn(antecedent_findings, unsupported)
        assert antecedent_findings[0]["cross_ref"] == "spec_support"
        assert unsupported[0].cross_ref == "antecedent"

    def test_non_overlapping_term_not_crossed(self):
        antecedent_findings = [
            {"claim_id": 1, "term": "基板", "reference_form": "所述",
             "claim_text": "", "suggested_match": None, "cross_ref": None},
        ]
        unsupported = [
            UnsupportedTerm(claim_number=1, phrase="不同的词", tiers_checked=[]),
        ]
        attach_cross_references_cn(antecedent_findings, unsupported)
        assert antecedent_findings[0]["cross_ref"] is None
        assert unsupported[0].cross_ref is None

    def test_different_claim_same_term_not_crossed(self):
        """Claim ID must match for cross-ref."""
        antecedent_findings = [
            {"claim_id": 1, "term": "基板", "reference_form": "所述",
             "claim_text": "", "suggested_match": None, "cross_ref": None},
        ]
        unsupported = [
            UnsupportedTerm(claim_number=2, phrase="基板", tiers_checked=[]),
        ]
        attach_cross_references_cn(antecedent_findings, unsupported)
        assert antecedent_findings[0]["cross_ref"] is None
        assert unsupported[0].cross_ref is None
