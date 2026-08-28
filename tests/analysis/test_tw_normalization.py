# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
"""Tests for TW reference-term normalization helpers (ADR-095)."""

from __future__ import annotations

import pytest

from patentlint.analysis.tw_claims import (
    clean_noun_phrase_tw,
    detect_plural_reference,
    normalize_candidate_intro,
    normalize_reference_term,
    strip_leading_quantifier,
    strip_reference_form_prefix,
    _extend_neng_compound_tw,
)


class TestExtendNengCompoundTw:
    """能量 / 能源 follow-gate - issue #75. 能 is excluded from the
    _NOUN_CHARS class, so `<noun>能量` is cut at 能; the follow-gate
    re-extends when 能 is followed by the noun-forming 量 / 源."""

    def test_energy_compound_reextended(self):
        # 靜電能量 - cut to 靜電 by the 能 exclusion; 電 is not a classic
        # 能-precursor, so only the 能量 follow-gate recovers it.
        assert _extend_neng_compound_tw("靜電", 2, "靜電能量大於一值") == ("靜電能量", 4)

    def test_energy_source_compound_reextended(self):
        assert _extend_neng_compound_tw("靜電", 2, "靜電能源為主") == ("靜電能源", 4)

    def test_follow_gate_stops_before_comparison_verb(self):
        # No greedy continuation - must not swallow the trailing 大 of 大於.
        noun, _ = _extend_neng_compound_tw("放電", 2, "放電能量大於一門檻值")
        assert noun == "放電能量"

    def test_modal_neng_not_extended(self):
        # 模組能控制 - 能 here is the modal "can"; not followed by 量/源
        # and 組 is not a precursor → no extension.
        assert _extend_neng_compound_tw("模組", 2, "模組能控制電流") == ("模組", 2)


class TestCleanNounPhraseTw:
    def test_strips_hai_bao(self):
        # 還包 is captured by the regex when the claim has
        # ``諧波減速模組還包含``. The clean function strips all trailing
        # verb fragments iteratively.
        assert clean_noun_phrase_tw("諧波減速模組還包") == "諧波減速模組"

    def test_strips_ji_nested(self):
        # 動力輸出系統包含 → 動力輸出系統
        assert clean_noun_phrase_tw("動力輸出系統包含") == "動力輸出系統"

    def test_strips_preposition_verb_at_interior_boundary(self):
        # 遊戲控制器通過第 - pre-2026-04-09 round 2, this returned
        # unchanged because clean_noun_phrase_tw only stripped trailing
        # tokens, and the trailing 第 didn't match any denylist entry.
        # Round 2 (Bug A1/C1 fix) added 通過 to _INTERIOR_VERB_BOUNDARIES
        # so the interior-cut pass now correctly truncates at 通過 and
        # returns the head noun cleanly.
        assert clean_noun_phrase_tw("遊戲控制器通過第") == "遊戲控制器"

    def test_strips_preposition_verb_when_trailing(self):
        # When 通過 IS at the trailing edge, it strips cleanly.
        assert clean_noun_phrase_tw("遊戲控制器通過") == "遊戲控制器"

    def test_strips_trailing_coverb_cong(self):
        # Issue #75: `控制電流從所述控制節點流經` - walker over-captured
        # `控制電流從`; 從 ("from") is a coverb in suffix position and
        # strips to the clean head noun `控制電流`.
        assert clean_noun_phrase_tw("控制電流從") == "控制電流"

    def test_strips_still_includes_variant(self):
        # 還包含 strips as a single token (listed longest-first).
        assert clean_noun_phrase_tw("齒輪還包含") == "齒輪"

    def test_no_trailing_verb_unchanged(self):
        assert clean_noun_phrase_tw("諧波減速模組") == "諧波減速模組"

    def test_empty_unchanged(self):
        assert clean_noun_phrase_tw("") == ""

    def test_single_char_unchanged(self):
        # Guard: stripping must leave at least one character.
        assert clean_noun_phrase_tw("包") == "包"


class TestStripLeadingQuantifier:
    def test_strips_fu_shu(self):
        assert strip_leading_quantifier("複數外齒狀結構") == "外齒狀結構"

    def test_strips_duo_ge(self):
        assert strip_leading_quantifier("多個外齒狀結構") == "外齒狀結構"

    def test_strips_yi_zhong(self):
        assert strip_leading_quantifier("一種樹脂組成物") == "樹脂組成物"

    def test_strips_at_least_one(self):
        assert strip_leading_quantifier("至少一個電極") == "電極"

    def test_no_quantifier_unchanged(self):
        assert strip_leading_quantifier("外齒狀結構") == "外齒狀結構"

    def test_single_quantifier_not_stripped_when_only_match(self):
        # Guard: stripping must leave at least one character behind.
        assert strip_leading_quantifier("一") == "一"


class TestStripReferenceFormPrefix:
    def test_strips_suo_shu(self):
        assert strip_reference_form_prefix("所述外齒狀結構") == "外齒狀結構"

    def test_strips_gai(self):
        assert strip_reference_form_prefix("該第一電極") == "第一電極"

    def test_strips_qian_shu(self):
        assert strip_reference_form_prefix("前述樹脂組成物") == "樹脂組成物"

    def test_strips_gai_deng(self):
        assert strip_reference_form_prefix("該等齒輪") == "齒輪"

    def test_strips_gai_xie(self):
        assert strip_reference_form_prefix("該些電極") == "電極"

    def test_no_prefix_unchanged(self):
        assert strip_reference_form_prefix("電極") == "電極"


class TestNormalizeReferenceTerm:
    def test_composite_gai_di_yi_dian_ji(self):
        # 該第一電極 → strip 該 → 第一電極 → no quantifier → 第一電極
        assert normalize_reference_term("該第一電極") == "第一電極"

    def test_composite_suo_shu_wai_chi(self):
        assert normalize_reference_term("所述外齒狀結構") == "外齒狀結構"

    def test_composite_gai_deng_chi_lun(self):
        assert normalize_reference_term("該等齒輪") == "齒輪"

    def test_idempotent(self):
        """normalize(normalize(x)) == normalize(x) for all x."""
        for term in [
            "該第一電極",
            "所述外齒狀結構",
            "該等齒輪",
            "電極",
            "一種樹脂組成物",
        ]:
            once = normalize_reference_term(term)
            assert normalize_reference_term(once) == once


class TestNormalizeCandidateIntro:
    def test_strips_duo_ge(self):
        assert normalize_candidate_intro("多個外齒狀結構") == "外齒狀結構"

    def test_strips_fu_shu(self):
        assert normalize_candidate_intro("複數外齒狀結構") == "外齒狀結構"

    def test_strips_leaked_reference_form_prefix(self):
        # Round 3 fix: when ``_INTRO_PATTERN`` greedily matches a
        # quantifier (e.g. ``一個`` in ``一個所述第一弧面``), the bare
        # noun group still carries the ``所述`` prefix. Without
        # symmetric stripping, the intro is keyed under
        # ``所述第一弧面`` while the reference normalizes to
        # ``第一弧面``, the exact-match path fails, and did-you-mean
        # surfaces a self-suggestion (110P000641 c15/c19 弧面).
        assert normalize_candidate_intro("所述第一弧面") == "第一弧面"
        assert normalize_candidate_intro("該齒輪") == "齒輪"
        assert normalize_candidate_intro("前述樹脂組成物") == "樹脂組成物"

    def test_idempotent(self):
        for term in [
            "多個外齒狀結構",
            "一種樹脂組成物",
            "電極",
            "所述第一弧面",
            "該齒輪",
        ]:
            once = normalize_candidate_intro(term)
            assert normalize_candidate_intro(once) == once


class TestNumberNeutralMatchProperty:
    """ADR-095 Rule 3: after normalization, 所述外齒狀結構 (reference)
    and 多個外齒狀結構 (intro) must be equal, so the walker's equality
    check treats them as matching."""

    def test_plural_intro_singular_ref(self):
        assert (
            normalize_reference_term("所述外齒狀結構")
            == normalize_candidate_intro("多個外齒狀結構")
        )

    def test_general_intro_singular_ref(self):
        assert (
            normalize_reference_term("該樹脂組成物")
            == normalize_candidate_intro("一種樹脂組成物")
        )

    def test_plural_variant_intro_matches(self):
        assert (
            normalize_reference_term("所述外齒狀結構")
            == normalize_candidate_intro("複數外齒狀結構")
        )


class TestDetectPluralReference:
    @pytest.mark.parametrize("term,expected", [
        ("該等齒輪", True),
        ("該些電極", True),
        ("所述多個結構", True),
        ("該齒輪", False),
        ("所述電極", False),
        ("前述樹脂", False),
        ("電極", False),
    ])
    def test_detect_plural_reference(self, term, expected):
        assert detect_plural_reference(term) is expected


class TestTrailingStripPreservesLegitimate所Suffixes:
    """ADR-095 Rule 1 trailing-verb strip includes 所 to handle
    reference-prefix fragments like 電子組件所包含 → 電子組件. This
    class locks in the tradeoff that 所-terminated compound nouns
    (研究所, 場所, 事務所) must not be over-stripped when they appear
    as standalone reference terms.

    If any of these tests start failing, the trailing-strip rule has
    become too aggressive and needs a compound-noun allowlist or
    minimum-length guard.
    """

    def test_research_institute_preserved(self):
        """研究所 must not strip to 研究."""
        assert clean_noun_phrase_tw("研究所") == "研究所"

    def test_location_preserved(self):
        """場所 must not strip to 場."""
        assert clean_noun_phrase_tw("場所") == "場所"

    def test_law_firm_preserved(self):
        """事務所 must not strip to 事務."""
        assert clean_noun_phrase_tw("事務所") == "事務所"

    def test_fragment_still_stripped(self):
        """電子組件所 (reference-prefix fragment) should still strip to 電子組件."""
        assert clean_noun_phrase_tw("電子組件所") == "電子組件"

    def test_before_as_compound_suffix_preserved(self):
        """以前 (before) and 之前 (prior) must not over-strip to empty.

        These are rare in claim language but possible in method
        claims describing temporal ordering. Edge cases - document
        current behavior with the weaker assertion (len > 0) so the
        observed value goes in the writeup for review rather than
        forcing a specific output. Post-2026-04-09: 前 was removed
        from _NOUNLIKE_SINGLE_CHAR_SUFFIXES (see
        test_qian_strips_as_verb_fragment below), so these now strip
        to 1 char (以/之), still satisfying the > 0 floor.
        """
        result_yi = clean_noun_phrase_tw("以前")
        result_zhi = clean_noun_phrase_tw("之前")
        assert len(result_yi) > 0, "以前 stripped to empty string"
        assert len(result_zhi) > 0, "之前 stripped to empty string"

    def test_qian_strips_as_verb_fragment(self):
        """前 is NOT in _NOUNLIKE_SINGLE_CHAR_SUFFIXES because it is
        overwhelmingly a prefix in patent Chinese (前端, 前述, 前方,
        前蓋, 前緣), not a suffix. 以前/之前 are grammatical adverbs
        rare in claims; if they appear they over-strip to 1 char,
        accepted as known behavior. Compound prefixes like 前端 are
        unaffected because they don't end in 前.
        """
        # 前端/前述/前方 end in 端/述/方 - not in the trailing-strip
        # denylist, so the trailing-strip codepath doesn't touch them.
        assert clean_noun_phrase_tw("前端") == "前端"
        assert clean_noun_phrase_tw("前述") == "前述"
        assert clean_noun_phrase_tw("前方") == "前方"
        # 以前/之前 over-strip to 1 char - accepted as known limit
        # for rare grammatical adverbs in claim text.
        assert clean_noun_phrase_tw("以前") == "以"
        assert clean_noun_phrase_tw("之前") == "之"
        # Fragment case: 齒輪前 (front-of-the-gear, captured fragment)
        # strips to 齒輪 - the correct head noun for resolution.
        assert clean_noun_phrase_tw("齒輪前") == "齒輪"

    def test_連接面_compound_preserved(self):
        """F4 fix: 連接面 (connecting surface) is a compound noun, not
        a verb+residual. Interior verb 連接 must not truncate 第一連接面
        to bare ordinal 第一. Root cause of walker_bug.regex_noun_class_narrow.
        """
        assert clean_noun_phrase_tw("第一連接面") == "第一連接面"
        assert clean_noun_phrase_tw("第二連接面") == "第二連接面"
        assert clean_noun_phrase_tw("連接面") == "連接面"
        # Regression: 連接 as a verb should still cut
        assert clean_noun_phrase_tw("焊墊連接") == "焊墊"


class TestR35TrailingVerbsAndComparatives:
    """R35 (2026-08-01) - trailing verbs, comparatives, and stranded verb
    heads drained from the 2026-07-28/31 report batch. Each pair below is
    (the reported over-capture, an FN control that must stay intact).
    """

    def test_markush_selected_from_stripped(self):
        # Report #473: 所述苯乙烯單體選自於由...所組成的群組
        assert clean_noun_phrase_tw("苯乙烯單體選自") == "苯乙烯單體"

    def test_load_verb_stripped(self):
        # Report #479: 經由一可攜式電子裝置載入並執行 (intro side)
        assert clean_noun_phrase_tw("可攜式電子裝置載入") == "可攜式電子裝置"

    def test_assign_verb_stripped(self):
        # Report #466: 依照該班表指派中執行該照護指令的人員
        assert clean_noun_phrase_tw("班表指派") == "班表"

    def test_auxiliary_establish_collocation_stripped(self):
        # Reports #466 / #469: 依據該場域的一班表輔助建立該工作流程
        assert clean_noun_phrase_tw("班表輔助建立") == "班表"

    def test_bare_auxiliary_preserved(self):
        # 輔助建立 ships as a collocation precisely so bare 輔助 stays a
        # legal noun tail - 駕駛輔助 ("driving assistance") is a real element.
        assert clean_noun_phrase_tw("駕駛輔助") == "駕駛輔助"

    def test_disconnect_collocation_stripped(self):
        # Report #481: 與...所述可攜式電子裝置斷開連線時
        assert clean_noun_phrase_tw("可攜式電子裝置斷開連線") == "可攜式電子裝置"

    def test_bare_connection_noun_preserved(self):
        # 斷開連線 ships as a collocation so bare 連線 is never stripped -
        # 網路連線 ("network connection") is a real element name, and a bare
        # strip would be an invisible false negative.
        assert clean_noun_phrase_tw("網路連線") == "網路連線"

    def test_press_verb_stripped(self):
        # Report #485: 多個所述按鈕用以提供使用者按壓
        assert clean_noun_phrase_tw("使用者按壓") == "使用者"

    def test_stranded_suo_chuan_head_stripped(self):
        # Reports #483 / #484: 多個所述比賽資訊顯示裝置所傳遞的所述連接資訊.
        # 遞 is excluded from _NOUN_CHARS so the scan halts mid-傳遞 and
        # leaves 所+傳 glued to the noun - the R32 所對 shape.
        assert clean_noun_phrase_tw("比賽資訊顯示裝置所傳") == "比賽資訊顯示裝置"

    def test_trailing_comparatives_stripped(self):
        # Reports #478 / #479: the intro captured as 比分總數較大.
        assert clean_noun_phrase_tw("比分總數較大") == "比分總數"
        for comparative in ("較小", "較高", "較低", "較長", "較短"):
            assert clean_noun_phrase_tw(f"比分總數{comparative}") == "比分總數"

    def test_transmit_cardinal_gated_interior_cut(self):
        # Report #480: 通過所述可攜式電子裝置傳遞一訓練資訊至... - the capture
        # ends in the verb's OBJECT, so only an interior cut can reach it.
        assert clean_noun_phrase_tw("可攜式電子裝置傳遞一訓練") == "可攜式電子裝置"

    def test_transmit_noun_compound_preserved(self):
        # The cardinal gate is what keeps bare 傳遞 usable as a noun modifier.
        assert clean_noun_phrase_tw("訊號傳遞路徑") == "訊號傳遞路徑"
        assert clean_noun_phrase_tw("傳遞機構") == "傳遞機構"

    def test_r46_trailing_predicates_stripped(self):
        # Reports #630-#638 (nine, one drafter), #645/#646/#647.
        # 即 is the adverb of 即時 ("real-time") bleeding into the noun.
        assert clean_noun_phrase_tw("影音內容即") == "影音內容"
        assert clean_noun_phrase_tw("高度差佔") == "高度差"
        assert clean_noun_phrase_tw("鋰源反應得") == "鋰源反應"

    def test_r46_de_greedy_trim_siblings_ship_together(self):
        # Bare 得 alone strands the head of 使得 / 所得 / 求得, which is DIRTIER
        # than the bug it fixes (指令使得 -> 指令使). The denylist is a
        # length-sorted tuple with break-on-first-match, so the longer members
        # must be present AND must sort first. Measured, not reasoned.
        assert clean_noun_phrase_tw("指令使得") == "指令"
        assert clean_noun_phrase_tw("指令進一步使得") == "指令"
        assert clean_noun_phrase_tw("發行端求得") == "發行端"
        assert clean_noun_phrase_tw("壓粉體所得") == "壓粉體"

    def test_r46_withheld_zhi_does_not_strip_noun_heads(self):
        # #662 is WITHHELD. Pins BOTH failure modes so a later round cannot
        # ship either quietly. Bare 製 would destroy real noun heads:
        assert clean_noun_phrase_tw("脈衝寬度調製") == "脈衝寬度調製"  # modulation
        assert clean_noun_phrase_tw("複製") == "複製"
        # ...and the collocation 材料製 OVER-STRIPS, because an endswith member
        # removes the whole matched suffix. The drafter's element is
        # 透明導電材料 (the US twin #659 captures exactly that), so the correct
        # fix drops only the single 製 before 成 and is not a denylist member.
        assert clean_noun_phrase_tw("透明導電材料製") != "透明導電"

    def test_r46_withheld_da_comparison_stays_unstripped(self):
        # 大 of 高度差大 (#645/#646/#647) stays WITHHELD: reaching it needs the
        # comparison gate on a following 於, not a bare trailing strip, which
        # would shatter compounds like 增大. Pinned so the withhold is visible.
        assert clean_noun_phrase_tw("高度差大") == "高度差大"
        assert clean_noun_phrase_tw("訊號增大") == "訊號增大"
