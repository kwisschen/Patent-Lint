# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""Tests for patentlint.analysis.specification."""

from patentlint.analysis.specification import (
    has_valid_ending,
    are_paragraphs_sequential,
    get_last_sequential_index,
    detect_restrictive_wording,
    has_sequence_listing_mismatch,
)


class TestValidEnding:
    def test_period(self):
        assert has_valid_ending("Some text.") is True

    def test_colon(self):
        assert has_valid_ending("Some text:") is True

    def test_semicolon_drawings(self):
        assert has_valid_ending("Some text;", is_description_of_drawings=True) is True
        assert has_valid_ending("Some text;", is_description_of_drawings=False) is False

    def test_semicolon_and_drawings(self):
        assert has_valid_ending("Some text; and", is_description_of_drawings=True) is True
        assert has_valid_ending("Some text; and", is_description_of_drawings=False) is False

    def test_no_punctuation(self):
        assert has_valid_ending("Some text") is False

    def test_quoted(self):
        assert has_valid_ending('He said "done."') is True
        assert has_valid_ending("He said \u201Cdone.\u201D") is True


class TestParagraphSequentiality:
    def test_sequential(self):
        assert are_paragraphs_sequential([1, 2, 3, 4, 5]) is True

    def test_gap(self):
        assert are_paragraphs_sequential([1, 2, 4, 5]) is False

    def test_last_index(self):
        assert get_last_sequential_index([1, 2, 3, 5, 6]) == 3


class TestRestrictiveWording:
    def test_detected(self):
        result = detect_restrictive_wording("The invention must always perform this step.", 5)
        assert 5 in result.flagged_paragraphs
        assert "invention" in result.formatted_phrases
        assert "must" in result.formatted_phrases
        assert "always" in result.formatted_phrases

    def test_new_mpep_terms(self):
        result = detect_restrictive_wording("This is necessary and imperative for this specific implementation.", 3)
        assert 3 in result.flagged_paragraphs
        assert "necessary" in result.formatted_phrases
        assert "imperative" in result.formatted_phrases
        assert "specific" in result.formatted_phrases

    def test_clean(self):
        result = detect_restrictive_wording("The device processes data according to the configuration.", 1)
        assert result.flagged_paragraphs == []


class TestSequenceListing:
    def test_mismatch(self):
        assert has_sequence_listing_mismatch("The protein has SEQ ID NO 1 and performs a function.") is True

    def test_no_mismatch(self):
        text = "STATEMENT REGARDING SEQUENCE LISTING\nSee attached.\nThe protein has SEQ ID NO 1."
        assert has_sequence_listing_mismatch(text) is False

    def test_no_seq_id(self):
        assert has_sequence_listing_mismatch("Normal patent text.") is False
