# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""Tests for src/patentlint/analysis/cjk_ordinal_guard.py."""

from __future__ import annotations

import pytest

from patentlint.analysis.cjk_ordinal_guard import ordinal_guard


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
