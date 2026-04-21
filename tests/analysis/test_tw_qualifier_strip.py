# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Tests for the leading qualifier strip (ADR-095 addendum 2026-04-09)."""

from __future__ import annotations

from patentlint.analysis.tw_claims import (
    normalize_candidate_intro,
    normalize_reference_term,
    strip_leading_qualifier,
)


class TestRelationalQualifierStrip:
    """對應/相應/相對/相關 with optional 地/的 suffix."""

    def test_corresponding_strips(self):
        assert strip_leading_qualifier("對應第二定位構件") == "第二定位構件"

    def test_corresponding_with_de_strips(self):
        assert strip_leading_qualifier("對應的第二定位構件") == "第二定位構件"

    def test_corresponding_with_di_strips(self):
        assert strip_leading_qualifier("對應地第二定位構件") == "第二定位構件"

    def test_xiang_ying_strips(self):
        assert strip_leading_qualifier("相應齒輪") == "齒輪"

    def test_xiang_dui_strips(self):
        assert strip_leading_qualifier("相對位置") == "位置"

    def test_xiang_guan_strips(self):
        assert strip_leading_qualifier("相關資料") == "資料"


class TestPositionQualifierStrip:
    """前/後 + quantifier patterns."""

    def test_qian_yi_huo_duoge_strips(self):
        assert strip_leading_qualifier("前一或多個主題標籤") == "一或多個主題標籤"

    def test_hou_yi_strips(self):
        assert strip_leading_qualifier("後一電極") == "一電極"

    def test_qian_with_fushu_strips(self):
        assert strip_leading_qualifier("前複數齒輪") == "複數齒輪"

    def test_qian_with_arabic_strips(self):
        assert strip_leading_qualifier("前2個元件") == "2個元件"


class TestPositionQualifierPreservation:
    """前/後 in compound nouns must NOT strip."""

    def test_qian_duan_preserved(self):
        """前端 (front end) — 前 followed by 端, not a quantifier."""
        assert strip_leading_qualifier("前端") == "前端"

    def test_qian_shu_preserved(self):
        """前述 (aforementioned) — same."""
        assert strip_leading_qualifier("前述") == "前述"

    def test_qian_fang_preserved(self):
        """前方 (front direction) — same."""
        assert strip_leading_qualifier("前方") == "前方"

    def test_hou_lun_preserved(self):
        """後輪 (rear wheel) — 後 followed by 輪, not a quantifier."""
        assert strip_leading_qualifier("後輪") == "後輪"

    def test_hou_duan_preserved(self):
        """後端 (rear end) — same."""
        assert strip_leading_qualifier("後端") == "後端"


class TestStrictMode:
    """strict_qualifier_matching=True disables the strip entirely."""

    def test_corresponding_preserved_in_strict(self):
        assert strip_leading_qualifier(
            "對應第二定位構件",
            strict_qualifier_matching=True,
        ) == "對應第二定位構件"

    def test_qian_yi_preserved_in_strict(self):
        assert strip_leading_qualifier(
            "前一步驟",
            strict_qualifier_matching=True,
        ) == "前一步驟"


class TestNormalizationIntegration:
    """End-to-end: normalize_reference_term composes all strips."""

    def test_gai_dui_ying_ordinal_normalizes(self):
        """該 prefix + 對應 qualifier + ordinal + head noun."""
        # 該對應第二定位構件 → strip 該 → 對應第二定位構件
        # → strip 對應 → 第二定位構件 → clean → strip quantifier (no-op)
        # → 第二定位構件
        assert normalize_reference_term("該對應第二定位構件") == "第二定位構件"

    def test_gai_qian_yi_huo_duoge_normalizes(self):
        """該 prefix + 前 qualifier + 一或多個 quantifier + head noun."""
        # 該前一或多個主題標籤 → strip 該 → 前一或多個主題標籤
        # → strip 前 (followed by 一) → 一或多個主題標籤
        # → clean → strip leading quantifier 一 → 或多個主題標籤
        # NB: 一或多個 isn't in the multi-quantifier denylist; the
        # iterative strip removes 一 and leaves 或多個主題標籤. The 或
        # is filtered by _NOUN_CHARS at the regex layer in real walker
        # use, but normalize_reference_term operates on already-captured
        # text so 或多個主題標籤 is the documented intermediate form.
        # Walker test exists in test_tw_walker_qualifier.py for the
        # end-to-end claim flow.
        result = normalize_reference_term("該前一或多個主題標籤")
        # Accept either 或多個主題標籤 or 主題標籤 depending on whether
        # downstream cleaning collapses the 或 boundary. The contract is:
        # the qualifier 前 is consumed.
        assert "前" not in result
        assert "主題標籤" in result

    def test_gai_qian_duan_normalizes_to_qian_duan(self):
        """該前端 should normalize to 前端 (compound noun preserved)."""
        # 該前端 → strip 該 → 前端 → strip qualifier? No, 端 is not a
        # quantifier → 前端 → clean → strip quantifier (no-op) → 前端
        assert normalize_reference_term("該前端") == "前端"


class TestNormalizeCandidateIntroQualifier:
    """The intro side gets the same qualifier strip for symmetry."""

    def test_intro_dui_ying_strips(self):
        # An intro phrase like "對應齒輪" normalizes to "齒輪" so it
        # matches a 該齒輪 reference downstream.
        assert normalize_candidate_intro("對應齒輪") == "齒輪"

    def test_intro_strict_preserves(self):
        assert normalize_candidate_intro(
            "對應齒輪",
            strict_qualifier_matching=True,
        ) == "對應齒輪"
