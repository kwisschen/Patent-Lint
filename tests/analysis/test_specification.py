# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Tests for patentlint.analysis.specification."""

from patentlint.analysis.specification import (
    has_valid_ending,
    are_paragraphs_sequential,
    get_last_sequential_index,
    detect_restrictive_wording,
    has_sequence_listing_mismatch,
    check_required_sections,
    check_title,
)
from patentlint.models import AnalysisResult


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


class TestParagraphSequentialCheck:
    """Tests for the paragraph sequential check logic in AnalysisResult.to_report_data()."""

    def _get_paragraph_check(self, result):
        report = result.to_report_data()
        return next(
            (c for c in report.specification_checks
             if c.message_key and c.message_key.startswith("check.spec.paragraphSequential")),
            None,
        )

    def test_zero_paragraphs_patent_emits_amend(self):
        result = AnalysisResult(paragraph_count=0, likely_patent=True)
        check = self._get_paragraph_check(result)
        assert check is not None
        assert check.status == "amend"
        assert check.message_key == "check.spec.paragraphSequential.missing"

    def test_zero_paragraphs_non_patent_no_amend(self):
        result = AnalysisResult(paragraph_count=0, likely_patent=False)
        check = self._get_paragraph_check(result)
        assert check is not None
        assert check.status != "amend"

    def test_sequential_paragraphs_pass(self):
        result = AnalysisResult(
            paragraph_count=5, paragraphs_sequential=True, likely_patent=True,
        )
        check = self._get_paragraph_check(result)
        assert check is not None
        assert check.status == "pass"
        assert check.message_key == "check.spec.paragraphSequential.pass"

    def test_non_sequential_paragraphs_amend(self):
        result = AnalysisResult(
            paragraph_count=5, paragraphs_sequential=False,
            last_sequential_paragraph=3, likely_patent=True,
        )
        check = self._get_paragraph_check(result)
        assert check is not None
        assert check.status == "amend"
        assert check.message_key == "check.spec.paragraphSequential.amend"


class TestRestrictiveWording:
    def test_detected(self):
        result = detect_restrictive_wording("The device must always perform this step.", 5)
        assert 5 in result.flagged_paragraphs
        assert "must" in result.formatted_phrases
        assert "always" in result.formatted_phrases

    def test_mpep_narrowing_terms(self):
        """MPEP 2111.01(II) narrowing language: critical/essential/vital/necessary/imperative."""
        result = detect_restrictive_wording(
            "This feature is critical, essential, vital, and necessary.", 3
        )
        assert 3 in result.flagged_paragraphs
        for term in ("critical", "essential", "vital", "necessary"):
            assert term in result.formatted_phrases

    def test_absolute_quantifiers(self):
        result = detect_restrictive_wording(
            "The system must never fail, and solely operates in every mode.", 7
        )
        assert 7 in result.flagged_paragraphs
        for term in ("must", "never", "solely", "every"):
            assert term in result.formatted_phrases

    def test_phase_9_72b_tightened_terms_pass(self):
        """Removed in Phase 9 #72b: 'invention', 'particular', 'specific', 'key'
        are standard drafting words that were dominating verify noise with
        non-narrowing uses."""
        result = detect_restrictive_wording(
            "The present invention relates to a particular embodiment "
            "with a specific example illustrating the key feature.",
            4,
        )
        assert result.flagged_paragraphs == []

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


def _make_full_doc(**overrides):
    """Build a full patent document with all sections present by default.

    Uses DISCLOSURE variants (modern patent practice) as defaults.
    """
    sections = {
        "title": "WIDGET FOR PROCESSING DATA",
        "cross_ref": "CROSS-REFERENCE TO RELATED APPLICATIONS\nThis application claims priority to U.S. App 16/123,456.",
        "background": "BACKGROUND OF THE DISCLOSURE\nWidgets are well known in the art.",
        "summary": "SUMMARY OF THE DISCLOSURE\nA widget is disclosed.",
        "brief_drawings": "BRIEF DESCRIPTION OF THE DRAWINGS\nFIG. 1 shows the widget.",
        "detailed_desc": "DETAILED DESCRIPTION OF THE EXEMPLARY EMBODIMENTS\nThe widget 100 includes a base plate 102.",
        "claims": "CLAIMS\n1. A widget comprising a base plate.",
        "abstract": "ABSTRACT OF THE DISCLOSURE\nA widget for processing data is disclosed.",
    }
    sections.update(overrides)
    parts = [v for v in sections.values() if v]
    return "\n\n".join(parts)


class TestRequiredSections:
    def test_all_sections_present(self):
        doc = _make_full_doc()
        results = check_required_sections(doc)
        statuses = [r.status for r in results]
        assert "amend" not in statuses
        assert any(r.message_key == "checks.required_sections_pass" for r in results)

    def test_missing_background_and_summary(self):
        doc = _make_full_doc(background="", summary="")
        results = check_required_sections(doc)
        amend = [r for r in results if r.status == "amend"]
        assert len(amend) == 1
        assert "Background of the Invention" in amend[0].message
        assert "Brief Summary of the Invention" in amend[0].message

    def test_missing_only_cross_reference_is_verify(self):
        doc = _make_full_doc(cross_ref="")
        results = check_required_sections(doc)
        assert not any(r.status == "amend" for r in results)
        verify = [r for r in results if r.status == "verify"]
        assert len(verify) == 1
        assert verify[0].message_key == "checks.optional_section_missing"

    def test_minimal_doc_claims_and_abstract_only(self):
        # No figure references in the body → BDoD is conditionally
        # not required (37 CFR 1.74). Other required sections still
        # missing should be flagged.
        doc = (
            "CLAIMS\n1. A widget comprising a base plate.\n\n"
            "ABSTRACT OF THE DISCLOSURE\nA widget is disclosed."
        )
        results = check_required_sections(doc)
        amend = [r for r in results if r.status == "amend"]
        assert len(amend) == 1
        assert "Background" in amend[0].message
        assert "Summary" in amend[0].message
        assert "Detailed Description" in amend[0].message
        # BDoD NOT required when no figures are mentioned anywhere in body.
        assert "Brief Description of the Drawings" not in amend[0].message

    def test_bdod_required_when_figures_referenced(self):
        # Body mentions FIG. 1 but the BDoD heading is removed —
        # BDoD must surface as missing per 37 CFR 1.74.
        doc = (
            "TITLE OF THE INVENTION\nWidget With Base Plate\n\n"
            "BACKGROUND OF THE INVENTION\nWidgets are known.\n\n"
            "BRIEF SUMMARY OF THE INVENTION\nA widget is disclosed.\n\n"
            "DETAILED DESCRIPTION OF THE INVENTION\nFIG. 1 shows the widget.\n\n"
            "CLAIMS\n1. A widget comprising a base plate.\n\n"
            "ABSTRACT OF THE DISCLOSURE\nA widget is disclosed."
        )
        results = check_required_sections(doc)
        amend = [r for r in results if r.status == "amend"]
        assert len(amend) == 1
        assert "Brief Description of the Drawings" in amend[0].message

    def test_variant_header_spellings(self):
        doc = "\n\n".join([
            "METHOD FOR DATA PROCESSING",
            "BACKGROUND",
            "Widgets are known.",
            "SUMMARY",
            "A method is disclosed.",
            "DESCRIPTION OF THE DRAWINGS",
            "FIG. 1 shows the method.",
            "DETAILED DESCRIPTION OF THE PREFERRED EMBODIMENTS",
            "The method includes steps.",
            "CLAIMS",
            "1. A method for processing data.",
            "ABSTRACT",
            "A method for data processing.",
        ])
        results = check_required_sections(doc)
        assert not any(r.status == "amend" for r in results)
        assert any(r.message_key == "checks.required_sections_pass" for r in results)

    def test_invention_variants(self):
        """INVENTION family headers should also be recognized."""
        doc = "\n\n".join([
            "APPARATUS FOR SIGNAL PROCESSING",
            "CROSS-REFERENCE TO RELATED APPLICATIONS",
            "This claims priority.",
            "BACKGROUND OF THE INVENTION",
            "Signal processing is known.",
            "BRIEF SUMMARY OF THE INVENTION",
            "An apparatus is disclosed.",
            "BRIEF DESCRIPTION OF THE DRAWINGS",
            "FIG. 1 shows the apparatus.",
            "DETAILED DESCRIPTION OF THE INVENTION",
            "The apparatus includes a processor.",
            "CLAIMS",
            "1. An apparatus for signal processing.",
            "ABSTRACT OF THE INVENTION",
            "An apparatus for signal processing is disclosed.",
        ])
        results = check_required_sections(doc)
        assert not any(r.status == "amend" for r in results)
        assert any(r.message_key == "checks.required_sections_pass" for r in results)

    def test_bare_summary_detected(self):
        """Plain 'SUMMARY' without qualifier should be detected."""
        doc = _make_full_doc(summary="SUMMARY\nA widget is disclosed.")
        results = check_required_sections(doc)
        assert not any(r.status == "amend" for r in results)

    def test_disclosure_variants(self):
        """DISCLOSURE family headers (modern practice) should be recognized."""
        doc = "\n\n".join([
            "SURGE PROTECTION CIRCUIT",
            "CROSS-REFERENCE TO RELATED PATENT APPLICATION",
            "This claims priority to U.S. App 17/456,789.",
            "BACKGROUND OF THE DISCLOSURE",
            "Surge protection is known.",
            "SUMMARY OF THE DISCLOSURE",
            "A circuit is disclosed.",
            "BRIEF DESCRIPTION OF THE DRAWINGS",
            "FIG. 1 shows the circuit.",
            "DETAILED DESCRIPTION OF THE DISCLOSURE",
            "The circuit includes a varistor.",
            "CLAIMS",
            "1. A surge protection circuit.",
            "ABSTRACT OF THE DISCLOSURE",
            "A surge protection circuit is disclosed.",
        ])
        results = check_required_sections(doc)
        assert not any(r.status == "amend" for r in results)
        assert any(r.message_key == "checks.required_sections_pass" for r in results)

    def test_brief_summary_of_disclosure(self):
        """'BRIEF SUMMARY OF THE DISCLOSURE' should be detected."""
        doc = _make_full_doc(summary="BRIEF SUMMARY OF THE DISCLOSURE\nA widget is disclosed.")
        results = check_required_sections(doc)
        assert not any(r.status == "amend" for r in results)

    def test_no_recognizable_headers(self):
        doc = "This is just some random text with no patent structure at all."
        results = check_required_sections(doc)
        amend = [r for r in results if r.status == "amend"]
        assert len(amend) == 1
        assert amend[0].message_key == "checks.required_sections_missing"


class TestCheckTitle:
    def test_missing_title(self):
        results = check_title("")
        assert len(results) == 1
        assert results[0].status == "amend"
        assert results[0].message_key == "check.spec.title.amendMissing"

    def test_pass(self):
        results = check_title("Method and Apparatus for Widget Assembly")
        assert len(results) == 1
        assert results[0].status == "pass"
        assert results[0].message_key == "check.spec.title.pass"

    def test_too_long(self):
        # 501 characters
        long_title = "A " + ("very " * 100) + "title"
        assert len(long_title) >= 500
        results = check_title(long_title)
        assert any(
            r.message_key == "check.spec.title.amendLength" for r in results
        )

    def test_trademark_rejected(self):
        results = check_title("Coca-Cola® Bottling Method")
        assert any(
            r.message_key == "check.spec.title.amendContent" for r in results
        )

    def test_model_number_rejected(self):
        results = check_title("Widget XJ-9000 Assembly System")
        assert any(
            r.message_key == "check.spec.title.amendContent" for r in results
        )

    def test_wordy_title_verify(self):
        # 18 words
        wordy = " ".join(["word"] * 18)
        results = check_title(wordy)
        assert any(
            r.message_key == "check.spec.title.verify" for r in results
        )

    def test_short_title_no_verify(self):
        # Five words — no warning.
        results = check_title("Method for Assembling a Widget")
        assert all(
            r.message_key != "check.spec.title.verify" for r in results
        )
