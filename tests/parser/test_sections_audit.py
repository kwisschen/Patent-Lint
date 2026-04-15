# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Adversarial tests for section extraction — Phase 4 B6 audit."""

import pytest
from pathlib import Path

from patentlint.parser.sections import (
    extract_claims_section,
    extract_abstract_section,
    extract_background_section,
    extract_description_of_drawings_section,
    extract_detailed_description_section,
    extract_summary_section,
)

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"
TESTSPEC1 = FIXTURE_DIR / "TestSpec1.docx"


class TestBackgroundAudit:
    def test_plain_background_header(self):
        """Plain 'BACKGROUND' header (common in modern filings)."""
        doc = "BACKGROUND\nWidgets are old.\n\nSUMMARY OF THE INVENTION\nWe improve."
        result = extract_background_section(doc)
        assert "Widgets are old." in result

    def test_background_of_disclosure(self):
        doc = "BACKGROUND OF THE DISCLOSURE\nPrior work.\n\nSUMMARY\nWe do better."
        assert "Prior work." in extract_background_section(doc)

    def test_background_falls_through_to_end(self):
        """If no end boundary, capture to end of document."""
        doc = "BACKGROUND OF THE INVENTION\nWidgets existed."
        result = extract_background_section(doc)
        assert "Widgets existed." in result


class TestDrawingsAudit:
    def test_several_views_variant(self):
        """USPTO standard: BRIEF DESCRIPTION OF THE SEVERAL VIEWS OF THE DRAWINGS."""
        doc = (
            "BRIEF DESCRIPTION OF THE SEVERAL VIEWS OF THE DRAWINGS\n"
            "FIG. 1 shows a widget.\n\n"
            "DETAILED DESCRIPTION\nThe widget is described."
        )
        result = extract_description_of_drawings_section(doc)
        assert "FIG. 1 shows a widget." in result
        assert "The widget is described." not in result

    def test_description_of_figures(self):
        doc = "BRIEF DESCRIPTION OF THE FIGURES\nFIG. 1 is a view.\n\nDETAILED DESCRIPTION\nText."
        result = extract_description_of_drawings_section(doc)
        assert "FIG. 1 is a view." in result


class TestDetailedDescriptionAudit:
    def test_standard_header(self):
        doc = "DETAILED DESCRIPTION\nThe widget has a base plate 102.\n\nCLAIMS\n1. A widget."
        result = extract_detailed_description_section(doc)
        assert "base plate 102" in result
        assert "1. A widget" not in result

    def test_of_the_invention(self):
        doc = "DETAILED DESCRIPTION OF THE INVENTION\nDescription text.\n\nCLAIMS\n1. A method."
        result = extract_detailed_description_section(doc)
        assert "Description text." in result

    def test_preferred_embodiment(self):
        doc = "DETAILED DESCRIPTION OF THE PREFERRED EMBODIMENT\nSingle embodiment.\n\nWhat is claimed is:\n1. A device."
        result = extract_detailed_description_section(doc)
        assert "Single embodiment." in result

    def test_preferred_embodiments_plural(self):
        doc = "DETAILED DESCRIPTION OF THE PREFERRED EMBODIMENTS\nMultiple embodiments.\n\nCLAIMS\n1. A system."
        result = extract_detailed_description_section(doc)
        assert "Multiple embodiments." in result

    def test_falls_through_to_end(self):
        """If no CLAIMS section follows, capture to end."""
        doc = "DETAILED DESCRIPTION\nContent goes to the end."
        result = extract_detailed_description_section(doc)
        assert "Content goes to the end." in result


class TestSummarySection:
    def test_summary_of_invention(self):
        doc = "SUMMARY OF THE INVENTION\nA widget is provided.\n\nBRIEF DESCRIPTION OF THE DRAWINGS\nFIG. 1"
        result = extract_summary_section(doc)
        assert "A widget is provided." in result

    def test_brief_summary(self):
        doc = "BRIEF SUMMARY\nAn improved widget.\n\nDETAILED DESCRIPTION\nDetails here."
        result = extract_summary_section(doc)
        assert "An improved widget." in result

    def test_plain_summary(self):
        doc = "SUMMARY\nThe invention relates to widgets.\n\nDETAILED DESCRIPTION\nMore text."
        result = extract_summary_section(doc)
        assert "The invention relates to widgets." in result


class TestClaimsAudit:
    def test_i_claim_header(self):
        doc = "I claim:\n1. A method of making widgets.\n\nABSTRACT\nText."
        result = extract_claims_section(doc)
        assert "1. A method of making widgets." in result

    def test_we_hereby_claim(self):
        doc = "We hereby claim:\n1. A device.\n\nABSTRACT\nText."
        result = extract_claims_section(doc)
        assert "1. A device." in result

    def test_many_claims(self):
        """Claims section with many claims should be fully captured."""
        doc = "CLAIMS\n1. A method.\n2. The method of claim 1.\n3. A device.\n\nABSTRACT\nText."
        result = extract_claims_section(doc)
        assert "1. A method." in result
        assert "3. A device." in result
        assert "ABSTRACT" not in result


class TestAbstractAudit:
    def test_abstract_of_disclosure(self):
        doc = "CLAIMS\n1. A method.\n\nABSTRACT OF THE DISCLOSURE\nA widget is disclosed."
        result = extract_abstract_section(doc)
        assert "A widget is disclosed." in result

    def test_abstract_at_very_end(self):
        doc = "ABSTRACT\nFinal abstract text with no trailing content."
        result = extract_abstract_section(doc)
        assert "Final abstract text" in result


class TestStandaloneHeaderBoundary:
    """Bug 1: Section extractors must match standalone headers, not body text."""

    def test_claims_in_body_text_not_matched(self):
        """'This application claims the benefit...' must not be matched as CLAIMS header."""
        body = "The widget has a base plate 102 and a cover body 104.\n" * 50
        doc = (
            "CROSS-REFERENCE TO RELATED APPLICATIONS\n"
            "This application claims the benefit of priority to Japanese Patent App.\n\n"
            "DETAILED DESCRIPTION\n"
            + body +
            "CLAIMS\n"
            "1. A fuse carrying mechanism.\n"
        )
        result = extract_detailed_description_section(doc)
        assert len(result) > 1000, f"DD too short ({len(result)} chars), likely matched body text 'claims'"
        assert "base plate 102" in result

    def test_summary_in_body_text_not_matched(self):
        """'a summary of the results' in Background must not end Background early."""
        doc = (
            "BACKGROUND\n"
            "Prior work includes a summary of the results from earlier experiments.\n"
            "This was insufficient for the intended purpose.\n\n"
            "SUMMARY\n"
            "We provide a widget."
        )
        result = extract_background_section(doc)
        assert "insufficient" in result

    def test_detailed_description_in_body_text_not_matched(self):
        """'see the detailed description below' in Summary must not end Summary early."""
        doc = (
            "SUMMARY\n"
            "The reader should see the detailed description below for full context.\n"
            "In brief, a widget is provided.\n\n"
            "DETAILED DESCRIPTION\n"
            "The widget is described fully here."
        )
        result = extract_summary_section(doc)
        assert "In brief" in result

    def test_standalone_claims_header_identified(self):
        """Standalone 'CLAIMS' on its own line is correctly identified."""
        doc = (
            "DETAILED DESCRIPTION\n"
            "Throughout the claims that follow, the terms are defined.\n"
            "The device includes a housing 10.\n\n"
            "CLAIMS\n"
            "1. A device comprising a housing.\n"
        )
        result = extract_detailed_description_section(doc)
        assert "Throughout the claims that follow" in result
        assert "1. A device" not in result

    def test_abstract_before_claims(self):
        """Non-standard ordering: Abstract before Claims."""
        doc = (
            "DETAILED DESCRIPTION\n"
            "The widget is complex.\n\n"
            "ABSTRACT\n"
            "A widget is disclosed.\n\n"
            "CLAIMS\n"
            "1. A widget.\n"
        )
        dd = extract_detailed_description_section(doc)
        assert "The widget is complex." in dd
        assert "A widget is disclosed." not in dd

        abstract = extract_abstract_section(doc)
        assert "A widget is disclosed." in abstract

    @pytest.mark.skipif(not TESTSPEC1.exists(), reason="TestSpec1.docx not in fixtures")
    def test_testspec1_detailed_description_length(self):
        """Integration: DD from TestSpec1.docx should be >10,000 chars."""
        from patentlint.parser.docx_loader import load_docx
        loaded = load_docx(str(TESTSPEC1))
        dd = extract_detailed_description_section(loaded.full_text)
        assert len(dd) > 10000, f"DD only {len(dd)} chars — boundary likely wrong"
