# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Tests for patentlint.parser.language — CJK script detection helpers."""

from __future__ import annotations

from patentlint.parser.language import (
    cjk_ratio,
    contains_hangul,
    contains_hiragana_or_katakana,
    count_cjk_chars,
    east_asian_ratio,
    hangul_ratio,
    is_cjk_char,
    is_east_asian_char,
    is_hangul_char,
    is_hiragana_or_katakana,
    jp_kana_count,
    jp_kana_ratio,
)


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


class TestIsHangulChar:
    def test_korean_syllable(self):
        assert is_hangul_char("청") is True
        assert is_hangul_char("구") is True
        assert is_hangul_char("항") is True

    def test_ascii_letter(self):
        assert is_hangul_char("A") is False

    def test_cjk_kanji_excluded(self):
        """Hangul check is strict — CJK kanji must not match."""
        assert is_hangul_char("漢") is False

    def test_empty(self):
        assert is_hangul_char("") is False


class TestIsHiraganaOrKatakana:
    def test_hiragana(self):
        assert is_hiragana_or_katakana("あ") is True
        assert is_hiragana_or_katakana("の") is True

    def test_katakana(self):
        assert is_hiragana_or_katakana("ア") is True
        assert is_hiragana_or_katakana("ネ") is True

    def test_kanji_excluded(self):
        """Kanji is shared with CN/TW, so not a Japanese-specific signal."""
        assert is_hiragana_or_katakana("特") is False
        assert is_hiragana_or_katakana("許") is False

    def test_hangul_excluded(self):
        assert is_hiragana_or_katakana("청") is False

    def test_middle_dot_excluded(self):
        """U+30FB (KATAKANA MIDDLE DOT) is script=Common per Unicode —
        used in Traditional Chinese typography (保溫・保冷). Rejecting a
        TW draft on a single middle dot is the ADR-150 bug."""
        assert is_hiragana_or_katakana("・") is False

    def test_prolonged_sound_mark_excluded(self):
        """U+30FC (KATAKANA-HIRAGANA PROLONGED SOUND MARK) is script=Common."""
        assert is_hiragana_or_katakana("ー") is False

    def test_double_hyphen_excluded(self):
        """U+30A0 (KATAKANA-HIRAGANA DOUBLE HYPHEN) is script=Common."""
        assert is_hiragana_or_katakana("゠") is False

    def test_voicing_marks_excluded(self):
        """U+3099..U+309C voicing marks are script-Common/Inherited, not JP."""
        assert is_hiragana_or_katakana("゙") is False
        assert is_hiragana_or_katakana("゛") is False

    def test_katakana_iteration_marks_included(self):
        """U+30FD..U+30FF are script=Katakana — legitimate JP signal."""
        assert is_hiragana_or_katakana("ヽ") is True
        assert is_hiragana_or_katakana("ヾ") is True


class TestIsEastAsianChar:
    def test_union_of_cjk_and_hangul(self):
        assert is_east_asian_char("漢") is True
        assert is_east_asian_char("あ") is True
        assert is_east_asian_char("청") is True

    def test_latin_excluded(self):
        assert is_east_asian_char("A") is False
        assert is_east_asian_char("ü") is False


class TestContainsHangul:
    def test_korean_sentence(self):
        assert contains_hangul("본 발명은 신호 처리에 관한 것이다.") is True

    def test_pure_ascii(self):
        assert contains_hangul("A method comprising step A.") is False

    def test_pure_cjk(self):
        """Chinese/Japanese kanji-only text should not trip Hangul check."""
        assert contains_hangul("本发明涉及一种方法。") is False
        assert contains_hangul("本発明は方法に関する。") is False

    def test_empty(self):
        assert contains_hangul("") is False

    def test_single_hangul_is_enough(self):
        """Presence check — a single Hangul char is sufficient."""
        assert contains_hangul("Hello 한") is True


class TestContainsHiraganaOrKatakana:
    def test_hiragana_sentence(self):
        assert contains_hiragana_or_katakana("本発明は信号処理に関する。") is True

    def test_katakana_sentence(self):
        assert contains_hiragana_or_katakana("プロセッサを含む装置。") is True

    def test_pure_kanji_is_false(self):
        """Kanji-only is shared across CN/TW/JP — not Japanese-specific."""
        assert contains_hiragana_or_katakana("本发明涉及装置。") is False

    def test_korean_is_false(self):
        assert contains_hiragana_or_katakana("본 발명은 장치이다.") is False

    def test_empty(self):
        assert contains_hiragana_or_katakana("") is False


class TestEastAsianRatio:
    def test_korean_patent_high_ratio(self):
        text = "본 발명은 신호 처리 장치에 관한 것이다."
        assert east_asian_ratio(text) > 0.5

    def test_japanese_patent_high_ratio(self):
        text = "本発明は信号処理装置に関するものである。"
        assert east_asian_ratio(text) > 0.5

    def test_us_patent_low_ratio(self):
        text = "The invention relates to a signal processing apparatus."
        assert east_asian_ratio(text) == 0.0


class TestJpKanaCount:
    def test_kana_characters_counted(self):
        assert jp_kana_count("本発明は信号処理") == 1  # は
        assert jp_kana_count("プロセッサ") == 5

    def test_middle_dot_not_counted(self):
        """ADR-150: middle dot U+30FB is script=Common, not JP kana."""
        assert jp_kana_count("保溫・保冷") == 0

    def test_empty(self):
        assert jp_kana_count("") == 0

    def test_none_tolerant(self):
        assert jp_kana_count(None) == 0  # type: ignore[arg-type]


class TestJpKanaRatio:
    def test_pure_jp_high_ratio(self):
        text = "本発明は信号処理装置に関するものである。"
        assert jp_kana_ratio(text) > 0.2

    def test_tw_with_single_middle_dot_below_threshold(self):
        """ADR-150 regression: the user-reported TW fixture had a single
        ・ in 20k chars → 0.005%, well below the 0.5% rejection ratio."""
        # 40 Chinese chars + 1 middle dot. The middle dot is excluded
        # from kana count, so ratio should be 0.0.
        text = "本發明提供一種蓋組件及帶蓋容器，能更穩定地抑制容器本體保溫・保冷機能"
        assert jp_kana_ratio(text) == 0.0

    def test_us_patent_zero(self):
        assert jp_kana_ratio("The invention relates to apparatus.") == 0.0

    def test_empty(self):
        assert jp_kana_ratio("") == 0.0


class TestHangulRatio:
    def test_pure_ko_high_ratio(self):
        text = "본 발명은 신호 처리 장치에 관한 것이다."
        assert hangul_ratio(text) > 0.5

    def test_cn_zero(self):
        text = "本发明涉及一种信号处理装置。"
        assert hangul_ratio(text) == 0.0

    def test_empty(self):
        assert hangul_ratio("") == 0.0

    def test_cjk_ratio_excludes_hangul(self):
        """cjk_ratio preserves its TIPO-abstract semantic; east_asian_ratio
        is the jurisdiction-detection superset."""
        korean_text = "본 발명은 장치이다."
        assert cjk_ratio(korean_text) == 0.0
        assert east_asian_ratio(korean_text) > 0.5
