# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Tests for PDF report generation."""

import pytest

from patentlint.models import AnalysisResult, Claim
from patentlint.report.generator import render_html, render_pdf


@pytest.fixture
def sample_result():
    """Build a minimal but complete AnalysisResult with mixed pass/verify/amend states."""
    claims = [
        Claim(id=1, text="A device comprising a widget.", independent=True, method_claim=False),
        Claim(
            id=2,
            text="The device of claim 1, wherein the widget is metal.",
            independent=False,
            method_claim=False,
            dependencies=[1],
        ),
        Claim(
            id=3,
            text="A method of making a widget, comprising forming the widget.",
            independent=True,
            method_claim=True,
        ),
    ]
    return AnalysisResult(
        # Specification — some issues to trigger amend/verify
        paragraph_count=15,
        improper_spec_paragraphs=[3, 7],
        improper_spec_phrases_formatted='[3] -> "invention"\n              [7] -> "must"\n              ',
        paragraphs_sequential=True,
        last_sequential_paragraph=15,
        missing_ending_paragraphs=[5],
        sequence_listing_mismatch=False,
        cross_reference_text="CROSS-REFERENCE TO RELATED APPLICATIONS\nU.S. App 16/123,456",
        cross_reference_citations="16/123,456",
        prior_art_citations="",
        # Drawings
        figures_count=3,
        figures_sequential=True,
        contains_prior_art_in_drawings=False,
        single_figure=False,
        wrong_label_for_single_figure=False,
        # Claims
        claims=claims,
        improper_claims=[1],
        improper_claim_phrases_formatted='[1] -> "comprising"\n              ',
        independent_claims_count=2,
        dependent_claims_count=1,
        claims_sequential=True,
        last_sequential_claim=3,
        multiple_dependent_claims=[],
        self_dependent_claims=[],
        # Abstract
        abstract_word_count=85,
        abstract_structure_good=True,
        abstract_has_implied_phrase=False,
        improper_abstract_phrases_formatted="",
    )


class TestRenderHtml:

    def test_contains_structure(self, sample_result):
        html = render_html(sample_result)
        assert "PatentLint Analysis Report" in html
        assert "Specification" in html
        assert "Claims" in html
        assert "Abstract" in html
        assert "Brief Description of Drawings" in html

    def test_contains_status_tags(self, sample_result):
        html = render_html(sample_result)
        assert "Passed Checks" in html  # PASS summary section
        assert "VERIFY" in html
        assert "AMEND" in html

    def test_contains_summary_stats(self, sample_result):
        html = render_html(sample_result)
        assert "15" in html  # paragraph count
        assert "3" in html  # total claims or figure count
        assert "85" in html  # abstract word count

    def test_contains_claim_trees(self, sample_result):
        html = render_html(sample_result)
        assert "Apparatus Claims" in html
        assert "Method Claims" in html
        assert "Independent" in html
        assert "Dependent" in html

    def test_contains_disclaimer(self, sample_result):
        html = render_html(sample_result)
        assert "does not constitute legal advice" in html


class TestRenderPdf:

    def test_returns_valid_pdf(self, sample_result):
        pdf = render_pdf(sample_result)
        assert isinstance(pdf, bytes)
        assert pdf[:4] == b"%PDF"
        assert len(pdf) > 1000

    def test_pdf_has_substantial_content(self, sample_result):
        """PDF should have substantial content (compressed streams contain the text)."""
        pdf = render_pdf(sample_result)
        # PDF text is compressed in FlateDecode streams, so we check size
        # rather than searching for literal strings
        assert len(pdf) > 5000


class TestToReportData:

    def test_report_data_structure(self, sample_result):
        data = sample_result.to_report_data()
        assert data.paragraph_count == 15
        assert data.total_claims == 3
        assert data.independent_count == 2
        assert data.dependent_count == 1
        assert data.figure_count == 3
        assert data.abstract_word_count == 85

    def test_specification_checks_count(self, sample_result):
        data = sample_result.to_report_data()
        assert len(data.specification_checks) == 7

    def test_claims_checks_count(self, sample_result):
        data = sample_result.to_report_data()
        assert len(data.claims_checks) == 8  # punctuation_checks empty by default

    def test_abstract_checks_count(self, sample_result):
        data = sample_result.to_report_data()
        assert len(data.abstract_checks) == 4

    def test_drawings_checks_present(self, sample_result):
        data = sample_result.to_report_data()
        assert len(data.drawings_checks) >= 3

    def test_claim_trees_groups(self, sample_result):
        data = sample_result.to_report_data()
        labels = [g.label for g in data.claim_trees]
        assert "Apparatus Claims" in labels
        assert "Method Claims" in labels

    def test_claim_tree_chain_format(self, sample_result):
        data = sample_result.to_report_data()
        product_group = next(g for g in data.claim_trees if g.label == "Apparatus Claims")
        dep_row = next(r for r in product_group.rows if r.claim_id == 2)
        # Chain should use ← arrows
        assert "\u2190" in dep_row.chain

    def test_empty_result(self):
        """An empty AnalysisResult should produce valid ReportData without errors."""
        result = AnalysisResult()
        data = result.to_report_data()
        assert data.total_claims == 0
        assert data.claim_trees == []

    def test_tracked_changes_adds_amend(self):
        """When has_tracked_changes=True, spec checks include an AMEND item."""
        result = AnalysisResult(has_tracked_changes=True)
        data = result.to_report_data()
        tc_checks = [c for c in data.specification_checks if "tracked changes" in c.message.lower()]
        assert len(tc_checks) == 1
        assert tc_checks[0].status == "amend"
        assert tc_checks[0].message_key == "check.spec.trackedChanges.amend"

    def test_no_tracked_changes_no_amend(self):
        """When has_tracked_changes=False, no tracked changes check in spec."""
        result = AnalysisResult(has_tracked_changes=False)
        data = result.to_report_data()
        tc_checks = [c for c in data.specification_checks if "tracked changes" in c.message.lower()]
        assert len(tc_checks) == 0
