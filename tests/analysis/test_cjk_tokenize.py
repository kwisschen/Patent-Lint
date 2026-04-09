# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""Tests for src/patentlint/analysis/cjk_tokenize.py (ADR-094)."""

from __future__ import annotations

import pytest

from patentlint.analysis.cjk_tokenize import jaccard, tokenize_cn, tokenize_tw


class TestBigramContract:
    def test_empty_string(self):
        assert tokenize_tw("") == []
        assert tokenize_cn("") == []

    def test_single_char_unigram_fallback(self):
        assert tokenize_tw("光") == ["光"]
        assert tokenize_cn("光") == ["光"]

    def test_two_chars_single_bigram(self):
        assert tokenize_tw("電極") == ["電極"]

    def test_three_chars_two_sorted_bigrams(self):
        # "組成物" → {"組成", "成物"}, sorted
        result = tokenize_tw("組成物")
        assert result == sorted(result)
        assert set(result) == {"組成", "成物"}

    def test_four_chars_three_overlapping_bigrams(self):
        result = tokenize_tw("電子裝置")
        assert set(result) == {"電子", "子裝", "裝置"}
        assert result == sorted(result)

    def test_dedupe_bigrams(self):
        # "AAA" should produce only one bigram ["AA"], not ["AA", "AA"]
        result = tokenize_tw("電電電")
        assert result == ["電電"]


class TestPunctuationStripping:
    def test_cjk_comma_stripped(self):
        assert tokenize_tw("組成，物") == tokenize_tw("組成物")

    def test_mixed_cjk_punctuation_stripped(self):
        # All the listed CJK punctuation should be removed before bigrams
        for punct in "。！？，、；：「」『』（）《》【】":
            with_punct = f"組{punct}成物"
            assert tokenize_tw(with_punct) == tokenize_tw("組成物"), (
                f"punctuation {punct!r} was not stripped"
            )


class TestLatinAndDigits:
    def test_latin_characters_preserved(self):
        # "USB接口" → strip nothing, bigrams: {"US","SB","B接","接口"}
        result = tokenize_tw("USB接口")
        assert set(result) == {"US", "SB", "B接", "接口"}
        assert result == sorted(result)

    def test_arabic_digits_preserved(self):
        # "5G網路" → {"5G","G網","網路"}
        result = tokenize_tw("5G網路")
        assert set(result) == {"5G", "G網", "網路"}


class TestSelfComparisonInvariant:
    """Jaccard of tokenize(X) vs tokenize(X) is 1.0 for every non-empty X."""

    @pytest.mark.parametrize("text", [
        "電極",
        "組成物",
        "高頻基板用樹脂組成物",
        "USB接口",
        "5G網路",
        "第一齒輪",
        "諧波減速模組",
    ])
    def test_self_jaccard_is_one(self, text):
        tokens = tokenize_tw(text)
        assert tokens  # sanity: token set not empty
        assert jaccard(tokens, tokens) == 1.0


class TestJaccardHelper:
    def test_empty_returns_zero(self):
        assert jaccard([], []) == 0.0
        assert jaccard(["電極"], []) == 0.0

    def test_disjoint_returns_zero(self):
        assert jaccard(["電極"], ["齒輪"]) == 0.0

    def test_partial_overlap(self):
        a = tokenize_tw("含浸液")  # {"含浸", "浸液"}
        b = tokenize_tw("含浸")    # {"含浸"}
        # |A ∩ B| / |A ∪ B| = 1 / 2 = 0.5
        assert jaccard(a, b) == pytest.approx(0.5)


class TestKnownLimitsDocumented:
    """Per ADR-094, the following failure modes are inherent to
    character-bigram tokenization on Chinese patent terminology and are
    NOT fixable by threshold tuning. These tests pin the observed
    behaviour so any change is deliberate rather than accidental.
    """

    def test_verb_noun_distinction_limit_hanjinye(self):
        """含浸液 / 含浸 — Jaccard 0.5 despite being a verb/noun pair."""
        a = tokenize_tw("含浸液")
        b = tokenize_tw("含浸")
        assert jaccard(a, b) == pytest.approx(0.5)

    def test_component_assembly_distinction_limit_chilunxiang(self):
        """齒輪 / 齒輪箱 — Jaccard 0.5 despite being a component/assembly pair."""
        a = tokenize_tw("齒輪")
        b = tokenize_tw("齒輪箱")
        # {"齒輪"} vs {"齒輪", "輪箱"} → 1/2
        assert jaccard(a, b) == pytest.approx(0.5)

    def test_lexically_disjoint_synonyms_limit(self):
        """聚合物 / 共聚物 — Jaccard 0.0 despite being valid shared head."""
        a = tokenize_tw("聚合物")  # {"聚合", "合物"}
        b = tokenize_tw("共聚物")  # {"共聚", "聚物"}
        # No overlap
        assert jaccard(a, b) == 0.0

    def test_unigram_fallback_disjoint(self):
        """光 / 光線 — unigram fallback means 0.0 Jaccard."""
        a = tokenize_tw("光")      # ["光"]
        b = tokenize_tw("光線")    # ["光線"]
        # {"光"} vs {"光線"} — disjoint as sets of strings
        assert jaccard(a, b) == 0.0
