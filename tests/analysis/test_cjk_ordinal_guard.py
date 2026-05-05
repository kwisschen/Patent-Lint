# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Tests for src/patentlint/analysis/cjk_ordinal_guard.py."""

from __future__ import annotations

import pytest

from patentlint.analysis.cjk_ordinal_guard import (
    normalize_arabic_ordinal_to_cjk,
    ordinal_guard,
)


class TestNumericOrdinal:
    def test_first_vs_second_electrode_fires(self):
        assert ordinal_guard("第一電極", "第二電極") is True

    def test_arabic_numeric_ordinal_fires(self):
        assert ordinal_guard("第1電極", "第2電極") is True

    def test_same_ordinal_does_not_fire(self):
        # 第一電極 vs 該第一電極 — same ordinal, different (optional) prefix.
        # Guard must NOT fire; the prefix is a reference marker, not an
        # ordinal difference. (Note: 該 is stripped by the walker before
        # the guard sees the pair, so this tests the raw inputs anyway.)
        assert ordinal_guard("第一電極", "第一電極") is False

    def test_ordinal_prefix_on_one_side_only(self):
        # 透明電極 (no ordinal) / 第一透明電極 (ordinal) — guard must not fire
        assert ordinal_guard("透明電極", "第一透明電極") is False

    def test_ordinal_differs_but_suffix_differs_does_not_fire(self):
        # Not a legitimate ordinal pair
        assert ordinal_guard("第一電極", "第二齒輪") is False


class TestPolarity:
    def test_yang_yin_fires(self):
        assert ordinal_guard("陽極", "陰極") is True

    def test_tu_ao_lens_fires(self):
        assert ordinal_guard("凸透鏡", "凹透鏡") is True

    def test_zheng_fu_fires(self):
        assert ordinal_guard("正極", "負極") is True

    def test_polarity_prefix_on_one_side_only(self):
        assert ordinal_guard("陽極", "電極") is False

    def test_same_polarity_different_suffix_does_not_fire(self):
        # 陽極 / 陽極層 — same polarity, different suffix (not an ordinal pair)
        assert ordinal_guard("陽極", "陽極層") is False


class TestLatinLetterType:
    def test_p_type_vs_n_type_semiconductor_fires(self):
        assert ordinal_guard("P型半導體", "N型半導體") is True

    def test_type_prefix_on_one_side_only(self):
        assert ordinal_guard("半導體", "P型半導體") is False

    def test_same_letter_different_suffix_does_not_fire(self):
        # P型半導體 / P型矽半導體 — same letter type, different noun
        assert ordinal_guard("P型半導體", "P型矽半導體") is False


class TestDigitG:
    def test_5g_vs_4g_fires(self):
        assert ordinal_guard("5G網路", "4G網路") is True

    def test_different_digit_different_suffix_does_not_fire(self):
        assert ordinal_guard("5G網路", "4G電極") is False


class TestBareReferenceFormsDoNotFire:
    def test_guang_vs_guangxian_does_not_fire(self):
        # 光 / 光線 — not an ordinal pair
        assert ordinal_guard("光", "光線") is False

    def test_identical_terms_do_not_fire(self):
        assert ordinal_guard("電極", "電極") is False

    def test_empty_strings_do_not_fire(self):
        assert ordinal_guard("", "") is False
        assert ordinal_guard("", "電極") is False
        assert ordinal_guard("電極", "") is False


class TestSymmetry:
    """Guard must be symmetric: ``guard(a, b) == guard(b, a)``."""

    @pytest.mark.parametrize("a,b", [
        ("第一電極", "第二電極"),
        ("陽極", "陰極"),
        ("凸透鏡", "凹透鏡"),
        ("P型半導體", "N型半導體"),
        ("5G網路", "4G網路"),
        ("第一電極", "該第一電極"),
        ("透明電極", "第一透明電極"),
        ("半導體", "P型半導體"),
        ("光", "光線"),
        ("陽極", "陽極層"),
        ("P型半導體", "P型矽半導體"),
    ])
    def test_symmetric(self, a, b):
        assert ordinal_guard(a, b) == ordinal_guard(b, a)


class TestNormalizeArabicOrdinalToCjk:
    """R33 walker-mine M2: half-width Arabic ordinals fold to CJK form."""

    def test_single_digit(self):
        assert normalize_arabic_ordinal_to_cjk("第1電極") == "第一電極"
        assert normalize_arabic_ordinal_to_cjk("第2電極") == "第二電極"
        assert normalize_arabic_ordinal_to_cjk("第9電極") == "第九電極"

    def test_two_digit_teens(self):
        assert normalize_arabic_ordinal_to_cjk("第10端子") == "第十端子"
        assert normalize_arabic_ordinal_to_cjk("第11端子") == "第十一端子"
        assert normalize_arabic_ordinal_to_cjk("第19端子") == "第十九端子"

    def test_two_digit_round_tens(self):
        assert normalize_arabic_ordinal_to_cjk("第20部") == "第二十部"
        assert normalize_arabic_ordinal_to_cjk("第90部") == "第九十部"

    def test_two_digit_compound(self):
        assert normalize_arabic_ordinal_to_cjk("第25層") == "第二十五層"
        assert normalize_arabic_ordinal_to_cjk("第99層") == "第九十九層"

    def test_already_cjk_unchanged(self):
        # Idempotent on already-CJK form (no 第N+digit pattern present)
        assert normalize_arabic_ordinal_to_cjk("第一電極") == "第一電極"
        assert normalize_arabic_ordinal_to_cjk("第二十五層") == "第二十五層"

    def test_three_or_more_digits_unchanged(self):
        # Element-label range; not normalized to avoid mis-handling
        # rare large ordinals or label numbers like 第100段
        assert normalize_arabic_ordinal_to_cjk("第123段") == "第123段"
        assert normalize_arabic_ordinal_to_cjk("第1000部") == "第1000部"

    def test_paren_label_untouched(self):
        # Element labels in parens (101) lack a leading 第, so they
        # must NOT be normalized — only the ordinal prefix is.
        assert normalize_arabic_ordinal_to_cjk("第1電極(101)") == "第一電極(101)"
        assert normalize_arabic_ordinal_to_cjk("第2端子（202）") == "第二端子（202）"

    def test_no_di_unchanged(self):
        # Fast path: no 第 in text → return as-is
        assert normalize_arabic_ordinal_to_cjk("電極") == "電極"
        assert normalize_arabic_ordinal_to_cjk("123") == "123"
        assert normalize_arabic_ordinal_to_cjk("") == ""

    def test_multiple_ordinals(self):
        assert normalize_arabic_ordinal_to_cjk("第1電極與第2電極") == "第一電極與第二電極"

    def test_di_without_digit_unchanged(self):
        # 第 followed by CJK numeral or non-digit → no transformation
        assert normalize_arabic_ordinal_to_cjk("第十電極") == "第十電極"
        assert normalize_arabic_ordinal_to_cjk("第A型") == "第A型"


class TestNormalizeIntegration:
    """End-to-end: TW + CN normalize_reference_term*/normalize_candidate_intro*
    fold 第1/第2 with 第一/第二 for matching purposes (round-1 cluster T1 + CN parity).
    """

    def test_tw_reference_normalize_folds_arabic_ordinal(self):
        from patentlint.analysis.tw_claims import (
            normalize_candidate_intro,
            normalize_reference_term,
        )
        # Same component — JP-translated style vs canonical TW style
        ref_arabic = normalize_reference_term("該第1電極")
        ref_cjk = normalize_reference_term("該第一電極")
        assert ref_arabic == ref_cjk
        intro_arabic = normalize_candidate_intro("一第1電極")
        intro_cjk = normalize_candidate_intro("一第一電極")
        assert intro_arabic == intro_cjk

    def test_cn_reference_normalize_folds_arabic_ordinal(self):
        from patentlint.analysis.cn_claims import (
            normalize_candidate_intro_cn,
            normalize_reference_term_cn,
        )
        ref_arabic = normalize_reference_term_cn("所述第1电极")
        ref_cjk = normalize_reference_term_cn("所述第一电极")
        assert ref_arabic == ref_cjk
        intro_arabic = normalize_candidate_intro_cn("一第1电极")
        intro_cjk = normalize_candidate_intro_cn("一第一电极")
        assert intro_arabic == intro_cjk
