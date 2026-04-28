# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Per-script context-window sanity for the report-modal preview.

These values are a privacy-facing contract: the modal preview shows the
user every fragment that will be sent. Changing the window size silently
would change what users see, so the per-script values are pinned here.
"""

from patentlint.diagnostic_extractors import (
    CONTEXT_WINDOW_HAN,
    CONTEXT_WINDOW_HANGUL,
    CONTEXT_WINDOW_JA,
    CONTEXT_WINDOW_LATIN,
    _context_window_for,
    _excerpt_around,
)


class TestContextWindowForScript:
    def test_latin_english(self):
        assert _context_window_for("A user interface comprising the user device.") == CONTEXT_WINDOW_LATIN

    def test_latin_german_with_umlauts(self):
        assert _context_window_for("Eine Benutzeroberfläche umfassend das Gerät.") == CONTEXT_WINDOW_LATIN

    def test_han_traditional_chinese(self):
        assert _context_window_for("一種使用者介面，包括該使用者裝置。") == CONTEXT_WINDOW_HAN

    def test_han_simplified_chinese(self):
        assert _context_window_for("一种用户界面装置，包括所述用户装置。") == CONTEXT_WINDOW_HAN

    def test_japanese_kana_presence_wins(self):
        # Mixed Han + kana — kana presence routes to JA window
        assert _context_window_for("ユーザインターフェースであって、前記ユーザ装置を備える。") == CONTEXT_WINDOW_JA

    def test_japanese_kanji_heavy_with_some_kana(self):
        # Predominantly kanji but with hiragana particles — still JA
        assert _context_window_for("前記ユーザ装置を備えることを特徴とする。") == CONTEXT_WINDOW_JA

    def test_hangul_korean(self):
        assert _context_window_for("사용자 인터페이스로서, 상기 사용자 장치가 표시되는 것을 특징으로 한다.") == CONTEXT_WINDOW_HANGUL

    def test_empty(self):
        assert _context_window_for("") == CONTEXT_WINDOW_LATIN

    def test_stray_cjk_in_latin_falls_back_to_latin(self):
        assert _context_window_for("user interface 裝置 displayed on browser") == CONTEXT_WINDOW_LATIN

    def test_chinese_with_one_stray_kana_does_not_misroute(self):
        # Edge case: CN claim that quotes a single Japanese product
        # name. Threshold of 3 kana chars protects against misrouting.
        assert _context_window_for("一种装置，引用ソ产品的设计。") == CONTEXT_WINDOW_HAN


class TestExcerptHonorsPerScriptWindow:
    def test_han_window_is_smaller(self):
        zh = "一種使用者介面，包括該使用者裝置顯示於該瀏覽程式上。"
        before, after, _ = _excerpt_around(zh, "該使用者裝置")
        assert before is not None and len(before) <= CONTEXT_WINDOW_HAN
        assert after is not None and len(after) <= CONTEXT_WINDOW_HAN

    def test_japanese_window_is_18(self):
        ja = "本発明はユーザインターフェースであって、前記ユーザ装置を備えることを特徴とする発明である。"
        before, after, _ = _excerpt_around(ja, "前記ユーザ装置")
        assert before is not None and len(before) <= CONTEXT_WINDOW_JA
        assert after is not None and len(after) <= CONTEXT_WINDOW_JA

    def test_latin_window_keeps_full_30(self):
        en = "A user interface comprising the user device displayed on the browser opening the page above."
        before, after, _ = _excerpt_around(en, "user device")
        assert before is not None and len(before) <= CONTEXT_WINDOW_LATIN
        assert after is not None and len(after) <= CONTEXT_WINDOW_LATIN

    def test_explicit_override_wins(self):
        en = "A" * 100 + "TARGET" + "B" * 100
        before, after, _ = _excerpt_around(en, "TARGET", before=5, after=5)
        assert before == "AAAAA"
        assert after == "BBBBB"
