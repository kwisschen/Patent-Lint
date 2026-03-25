# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""Tests for reference numeral inventory extraction (Bugs 7 & 8)."""

import pytest
from pathlib import Path

from patentlint.analysis.specification import extract_reference_numeral_inventory

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"
TESTSPEC1 = FIXTURE_DIR / "TestSpec1.docx"


class TestRefNumExtraction:
    def test_noun_followed_by_number(self):
        """'base plate 102' -> numeral 102."""
        text = "The base plate 102 is mounted on the base plate 102."
        nums = extract_reference_numeral_inventory(text)
        found = {rn.number: rn for rn in nums}
        assert 102 in found
        assert "base plate" in found[102].element_name

    def test_unit_excluded(self):
        """'100°C' should NOT be extracted."""
        text = "The temperature is 100°C and the temperature is 100°C again."
        nums = extract_reference_numeral_inventory(text)
        found = {rn.number for rn in nums}
        assert 100 not in found

    def test_unit_mm_excluded(self):
        """'100 mm' should NOT be extracted."""
        text = "The width is 100 mm and the width is 100 mm."
        nums = extract_reference_numeral_inventory(text)
        found = {rn.number for rn in nums}
        assert 100 not in found

    def test_claim_excluded(self):
        """'claim 1' should NOT be extracted."""
        text = "As described in claim 1, the device of claim 1 operates."
        nums = extract_reference_numeral_inventory(text)
        found = {rn.number for rn in nums}
        assert 1 not in found

    def test_fig_excluded(self):
        """'FIG. 3' should NOT be extracted."""
        text = "Referring to FIG. 3 and FIG. 3 again."
        nums = extract_reference_numeral_inventory(text)
        found = {rn.number for rn in nums}
        assert 3 not in found

    def test_year_excluded(self):
        """'2024' should NOT be extracted."""
        text = "In the year 2024, the widget in 2024 was designed."
        nums = extract_reference_numeral_inventory(text)
        found = {rn.number for rn in nums}
        assert 2024 not in found

    def test_parenthetical_format(self):
        """'widget (102)' extracted correctly."""
        text = "The widget (102) connects to the widget (102) above."
        nums = extract_reference_numeral_inventory(text)
        found = {rn.number for rn in nums}
        assert 102 in found

    def test_single_occurrence_not_promoted(self):
        """Numeral appearing only once -> not promoted (below confidence)."""
        text = "The processor 300 is fast."
        nums = extract_reference_numeral_inventory(text)
        found = {rn.number for rn in nums}
        assert 300 not in found

    def test_occurrence_count(self):
        """Occurrence count reflects actual mentions."""
        text = "The housing 10 is sturdy. The housing 10 protects. The housing 10 encloses."
        nums = extract_reference_numeral_inventory(text)
        found = {rn.number: rn for rn in nums}
        assert 10 in found
        assert found[10].occurrences == 3

    def test_insufficient_data(self):
        """No numerals -> empty list."""
        text = "Some text without reference numerals."
        nums = extract_reference_numeral_inventory(text)
        assert len(nums) == 0


class TestElementNameQuality:
    """Bug 7: Element names should be 1-4 clean words, not sentence fragments."""

    def test_clean_element_name(self):
        """'insulating shell 11' → element_name = 'insulating shell'."""
        text = "The insulating shell 11 includes a cavity. The insulating shell 11 is formed."
        nums = extract_reference_numeral_inventory(text)
        found = {rn.number: rn for rn in nums}
        assert 11 in found
        assert found[11].element_name == "insulating shell"

    def test_connector_assembly(self):
        """'connector assembly 100' → element_name = 'connector assembly'."""
        text = "The connector assembly 100 includes parts. The connector assembly 100 is durable."
        nums = extract_reference_numeral_inventory(text)
        found = {rn.number: rn for rn in nums}
        assert 100 in found
        assert found[100].element_name == "connector assembly"

    def test_cover_body(self):
        """'cover body 112' → element_name = 'cover body'."""
        text = "A cover body 112 is movably connected. The cover body 112 slides."
        nums = extract_reference_numeral_inventory(text)
        found = {rn.number: rn for rn in nums}
        assert 112 in found
        assert found[112].element_name == "cover body"

    def test_no_sentence_fragments(self):
        """Element names should not contain sentence fragments > 4 words."""
        text = "The first engaging structure 121 is rigid. The first engaging structure 121 locks."
        nums = extract_reference_numeral_inventory(text)
        for rn in nums:
            words = rn.element_name.split()
            assert len(words) <= 4, f"Element name too long: '{rn.element_name}'"

    @pytest.mark.skipif(not TESTSPEC1.exists(), reason="TestSpec1.docx not in fixtures")
    def test_testspec1_element_names(self):
        """Integration: all element names from TestSpec1 should be 1-4 words."""
        from patentlint.parser.docx_loader import load_docx
        from patentlint.parser import sections
        loaded = load_docx(str(TESTSPEC1))
        dd = sections.extract_detailed_description_section(loaded.full_text)
        summary = sections.extract_summary_section(loaded.full_text)
        drawings = sections.extract_description_of_drawings_section(loaded.full_text)
        spec_text = (dd or "") + "\n" + (summary or "") + "\n" + (drawings or "")
        nums = extract_reference_numeral_inventory(spec_text)
        assert len(nums) > 5, f"Expected >5 numerals, got {len(nums)}"
        for rn in nums:
            words = rn.element_name.split()
            assert len(words) <= 4, f"Numeral {rn.number}: '{rn.element_name}' too long"
