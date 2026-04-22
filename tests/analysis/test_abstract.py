# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Tests for patentlint.analysis.abstract."""

from patentlint.analysis.abstract import (
    count_words,
    is_single_paragraph_and_final,
    has_implied_phrase,
    detect_implied_phrases,
    detect_improper_wording,
)


class TestCountWords:
    def test_standard(self):
        assert count_words("ABSTRACT\nA method for doing things with widgets.") == 8

    def test_empty(self):
        assert count_words("") == 0
        assert count_words(None) == 0

    def test_boundary_150(self):
        text = " ".join(["word"] * 150)
        assert count_words(text) == 150


class TestSingleParagraphAndFinal:
    def test_valid(self):
        abstract = "ABSTRACT\nA method for processing data is disclosed."
        doc = "Some content.\n" + abstract
        assert is_single_paragraph_and_final(doc, abstract) is True

    def test_multi_paragraph(self):
        abstract = "ABSTRACT\nFirst paragraph.\nSecond paragraph."
        doc = "Some content.\n" + abstract
        assert is_single_paragraph_and_final(doc, abstract) is False

    def test_no_period(self):
        abstract = "ABSTRACT\nA method for processing data"
        doc = "Some content.\n" + abstract
        assert is_single_paragraph_and_final(doc, abstract) is False


class TestImpliedPhrase:
    def test_is_provided(self):
        assert has_implied_phrase("A method is provided for processing.") is True

    def test_disclosure(self):
        assert has_implied_phrase("This disclosure relates to widgets.") is True

    def test_clean(self):
        assert has_implied_phrase("A method for processing data includes steps A and B.") is False


class TestDetectImpliedPhrases:
    """detect_implied_phrases surfaces the actual matched tokens so the
    UI can show users WHICH phrase triggered the finding."""

    def test_is_provided(self):
        assert detect_implied_phrases("A method is provided for processing.") == ["is provided"]

    def test_are_provided(self):
        assert detect_implied_phrases("Several improvements are provided herein.") == ["are provided"]

    def test_disclosure(self):
        assert detect_implied_phrases("This disclosure relates to widgets.") == ["disclosure"]

    def test_multiple(self):
        # "A disclosure is provided for..." → both trigger
        phrases = detect_implied_phrases("A disclosure is provided for processing.")
        assert "is provided" in phrases
        assert "disclosure" in phrases

    def test_clean(self):
        assert detect_implied_phrases("A method for processing data includes steps A and B.") == []

    def test_empty_input(self):
        assert detect_implied_phrases("") == []


class TestImproperWording:
    def test_legal_phraseology(self):
        result = detect_improper_wording("A method comprising means for said processing thereof.")
        assert "comprising" in result
        assert "means" in result
        assert "said" in result
        assert "thereof" in result

    def test_self_praising(self):
        result = detect_improper_wording("A novel and innovative method for unique processing.")
        assert "novel" in result
        assert "innovative" in result
        assert "unique" in result

    def test_evaluative(self):
        result = detect_improper_wording("An important and significant method.")
        assert "important" in result
        assert "significant" in result

    def test_present_invention(self):
        result = detect_improper_wording("The present invention relates to widgets.")
        assert "present invention" in result

    def test_clean(self):
        assert detect_improper_wording("A method for processing data.") == ""
