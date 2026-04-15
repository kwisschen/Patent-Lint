# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Tests for patentlint.parser.sections — direct port of Java characterization tests."""

from patentlint.parser.sections import (
    extract_claims_section,
    extract_abstract_section,
    extract_cross_reference_section,
    extract_background_section,
    extract_description_of_drawings_section,
    detect_prior_art_citations,
    detect_patent_document,
)


class TestExtractClaimsSection:
    def test_standard_header(self):
        doc = "BACKGROUND\nSome background text.\n\nCLAIMS\n1. A method comprising step A.\n2. The method of claim 1, further comprising step B.\n\nABSTRACT\nThis is the abstract."
        result = extract_claims_section(doc)
        assert "1. A method comprising step A." in result
        assert "2. The method of claim 1" in result
        assert "ABSTRACT" not in result
        assert "background" not in result

    def test_what_is_claimed(self):
        doc = "SUMMARY\nSome summary.\n\nWhat is claimed is:\n1. An apparatus comprising a widget.\n\nABSTRACT\nAbstract text."
        assert "1. An apparatus comprising a widget." in extract_claims_section(doc)

    def test_no_claims(self):
        assert extract_claims_section("BACKGROUND\nSome text.\nABSTRACT\nAbstract.") == ""

    def test_combined_header(self):
        doc = "CLAIMS\nWhat is claimed is:\n1. A device for processing data.\n\nABSTRACT\nText."
        assert "1. A device for processing data." in extract_claims_section(doc)


class TestExtractAbstractSection:
    def test_standard(self):
        doc = "CLAIMS\n1. A method.\n\nABSTRACT\nA method for doing things is disclosed."
        result = extract_abstract_section(doc)
        assert result.startswith("ABSTRACT")
        assert "A method for doing things is disclosed." in result

    def test_stops_at_reference_numerals(self):
        doc = "ABSTRACT\nA device is shown.\nreference numerals\n100 widget\n200 gadget"
        result = extract_abstract_section(doc)
        assert "A device is shown." in result
        assert "100 widget" not in result

    def test_none(self):
        assert extract_abstract_section("CLAIMS\n1. A method.\n") == ""


class TestExtractCrossReference:
    def test_standard(self):
        doc = "CROSS-REFERENCE TO RELATED APPLICATIONS\nThis application claims priority to 16/123,456.\n\nFIELD OF THE DISCLOSURE\nThis relates to widgets."
        assert "16/123,456" in extract_cross_reference_section(doc)

    def test_absent(self):
        assert extract_cross_reference_section("FIELD OF THE INVENTION\nWidgets.\nBACKGROUND\nStuff.") == ""


class TestExtractBackground:
    def test_standard(self):
        doc = "BACKGROUND OF THE INVENTION\nWidgets have been known for years.\n\nSUMMARY OF THE INVENTION\nWe improve widgets."
        assert "Widgets have been known for years." in extract_background_section(doc)

    def test_disclosure_variant(self):
        doc = "BACKGROUND OF THE DISCLOSURE\nPrior approaches failed.\n\nSUMMARY OF THE DISCLOSURE\nWe succeed."
        assert "Prior approaches failed." in extract_background_section(doc)


class TestExtractDrawings:
    def test_standard(self):
        doc = "BRIEF DESCRIPTION OF THE DRAWINGS\nFIG. 1 shows a widget.\nFIG. 2 shows a gadget.\n\nDETAILED DESCRIPTION OF THE EMBODIMENTS\nThe widget is described."
        result = extract_description_of_drawings_section(doc)
        assert "FIG. 1 shows a widget." in result
        assert "FIG. 2 shows a gadget." in result


class TestDetectPatentDocument:
    def test_claims_header(self):
        """Text with CLAIMS section header → True."""
        assert detect_patent_document("Some text.\nCLAIMS\n1. A method.") is True

    def test_abstract_header(self):
        """Text with ABSTRACT OF THE DISCLOSURE header → True."""
        assert detect_patent_document("ABSTRACT OF THE DISCLOSURE\nA method is disclosed.") is True

    def test_detailed_description_header(self):
        """Text with DETAILED DESCRIPTION header → True."""
        assert detect_patent_document("DETAILED DESCRIPTION\nThe widget includes a base.") is True

    def test_numbered_claims_pattern(self):
        """Text with numbered claims pattern → True."""
        assert detect_patent_document("Preamble text.\n1. A method comprising step A.\n2. The method of claim 1.") is True

    def test_bracketed_paragraph_numbers(self):
        """Text with 3+ bracketed paragraph numbers [0001] → True."""
        text = "[0001] First paragraph.\n[0002] Second paragraph.\n[0003] Third paragraph."
        assert detect_patent_document(text) is True

    def test_plain_essay(self):
        """Plain essay text with no patent indicators → False."""
        text = "This is an essay about technology. It discusses various topics. The conclusion follows."
        assert detect_patent_document(text) is False

    def test_business_letter(self):
        """Business letter text → False."""
        text = "Dear Mr. Smith,\nPlease find attached the requested documents.\nBest regards,\nJane Doe"
        assert detect_patent_document(text) is False

    def test_single_bracket_not_four_digit(self):
        """Text with only 1 bracketed number (not 4-digit format) → False."""
        text = "See reference [1] for details. Also [2] is relevant."
        assert detect_patent_document(text) is False


class TestDetectPriorArtCitations:
    def test_found(self):
        text = "U.S. Patent No. 7,654,321 discloses a widget. Also see 10,123,456."
        result = detect_prior_art_citations(text)
        assert "7,654,321" in result
        assert "10,123,456" in result

    def test_none(self):
        assert detect_prior_art_citations("Widgets have been known for a long time.") == ""
