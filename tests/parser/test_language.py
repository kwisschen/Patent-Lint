# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Tests for patentlint.parser.language — CJK script detection helpers."""

from __future__ import annotations

from patentlint.parser.language import cjk_ratio, count_cjk_chars, is_cjk_char


class TestIsCjkChar:
    def test_simplified_chinese(self):
        assert is_cjk_char("发") is True
        assert is_cjk_char("明") is True

    def test_traditional_chinese(self):
        assert is_cjk_char("發") is True
        assert is_cjk_char("請") is True

    def test_hiragana(self):
        assert is_cjk_char("あ") is True

    def test_katakana(self):
        assert is_cjk_char("ア") is True

    def test_fullwidth_ascii(self):
        assert is_cjk_char("．") is True  # fullwidth period U+FF0E

    def test_ascii_letter(self):
        assert is_cjk_char("A") is False

    def test_ascii_digit(self):
        assert is_cjk_char("1") is False

    def test_ascii_punct(self):
        assert is_cjk_char(".") is False

    def test_empty(self):
        assert is_cjk_char("") is False

    def test_cjk_symbol_punct_block_excluded(self):
        """U+3000-0x303F (CJK Symbols and Punctuation) block is out of range.

        Notable: the halfwidth ideographic full stop U+3002 (。) is NOT
        counted. Fullwidth variants in the 0xFF00-0xFFEF block (e.g., the
        fullwidth comma U+FF0C 「，」 or fullwidth period U+FF0E 「．」) ARE
        counted, because drafters use them interchangeably with CJK text.
        """
        assert is_cjk_char("。") is False  # U+3002 CJK Symbols block
        assert is_cjk_char("　") is False  # U+3000 ideographic space


class TestCountCjkChars:
    def test_pure_ascii(self):
        assert count_cjk_chars("hello world") == 0

    def test_pure_chinese(self):
        assert count_cjk_chars("发明") == 2

    def test_mixed(self):
        assert count_cjk_chars("The 发明 relates to X.") == 2

    def test_empty(self):
        assert count_cjk_chars("") == 0

    def test_none(self):
        assert count_cjk_chars(None) == 0  # type: ignore[arg-type]


class TestCjkRatio:
    def test_pure_ascii(self):
        assert cjk_ratio("hello world") == 0.0

    def test_pure_chinese(self):
        assert cjk_ratio("发明专利") == 1.0

    def test_mixed_50_50(self):
        # 4 CJK + 4 ASCII letters = 0.5 (whitespace excluded)
        assert cjk_ratio("abcd 发明专利") == 0.5

    def test_empty(self):
        assert cjk_ratio("") == 0.0

    def test_whitespace_only(self):
        assert cjk_ratio("   \n\t  ") == 0.0

    def test_whitespace_excluded_from_denominator(self):
        """Lots of whitespace shouldn't dilute the CJK signal."""
        ratio_no_ws = cjk_ratio("abcd发明")
        ratio_with_ws = cjk_ratio("a b c d\n发  明")
        assert abs(ratio_no_ws - ratio_with_ws) < 1e-9

    def test_us_patent_with_minor_cjk_citation(self):
        """US patent text with a foreign-application CJK citation stays below 5%."""
        text = (
            "DETAILED DESCRIPTION OF THE INVENTION\n"
            "The invention is described herein. It claims priority to "
            "Japanese Patent Application No. 2023-123456 (特許), which "
            "is incorporated by reference in its entirety.\n"
        )
        assert cjk_ratio(text) < 0.05

    def test_cn_patent_above_50_percent(self):
        text = (
            "用于调整神经网络的方法和装置\n"
            "[0001] 本申请涉及通信技术领域。\n"
            "[0002] 具体地，本申请涉及一种用于调整神经网络的方法和装置。\n"
        )
        assert cjk_ratio(text) > 0.5
