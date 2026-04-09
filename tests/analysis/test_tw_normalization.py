# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
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
)


class TestCleanNounPhraseTw:
    def test_strips_hai_bao(self):
        # 還包 is captured by the regex when the claim has
        # ``諧波減速模組還包含``. The clean function strips all trailing
        # verb fragments iteratively.
        assert clean_noun_phrase_tw("諧波減速模組還包") == "諧波減速模組"

    def test_strips_ji_nested(self):
        # 動力輸出系統包含 → 動力輸出系統
        assert clean_noun_phrase_tw("動力輸出系統包含") == "動力輸出系統"

    def test_strips_preposition_verb_leaves_stray_head(self):
        # 遊戲控制器通過第 — clean_noun_phrase_tw only strips TRAILING
        # tokens matching the denylist. The last character here is 第
        # (an ordinal prefix, not a verb), so the function stops
        # immediately and returns the input unchanged. This is the
        # observed behaviour, documented by the ADR-095 prompt:
        # "the walker MAY leave leading chars of the next clause if
        # they don't match any denylist entry." The leftover produces
        # a mismatch at comparison time, which is surfaced via the
        # did-you-mean hint if similarity is high enough.
        assert clean_noun_phrase_tw("遊戲控制器通過第") == "遊戲控制器通過第"

    def test_strips_preposition_verb_when_trailing(self):
        # When 通過 IS at the trailing edge, it strips cleanly.
        assert clean_noun_phrase_tw("遊戲控制器通過") == "遊戲控制器"

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

    def test_idempotent(self):
        for term in ["多個外齒狀結構", "一種樹脂組成物", "電極"]:
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
        claims describing temporal ordering. Edge cases — document
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
        # 前端/前述/前方 end in 端/述/方 — not in the trailing-strip
        # denylist, so the trailing-strip codepath doesn't touch them.
        assert clean_noun_phrase_tw("前端") == "前端"
        assert clean_noun_phrase_tw("前述") == "前述"
        assert clean_noun_phrase_tw("前方") == "前方"
        # 以前/之前 over-strip to 1 char — accepted as known limit
        # for rare grammatical adverbs in claim text.
        assert clean_noun_phrase_tw("以前") == "以"
        assert clean_noun_phrase_tw("之前") == "之"
        # Fragment case: 齒輪前 (front-of-the-gear, captured fragment)
        # strips to 齒輪 — the correct head noun for resolution.
        assert clean_noun_phrase_tw("齒輪前") == "齒輪"
