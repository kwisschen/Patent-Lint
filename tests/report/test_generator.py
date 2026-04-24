# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Tests for PDF report generation."""

import pytest

from patentlint.i18n import supported_locales
from patentlint.models import (
    AnalysisResult,
    CheckItem,
    Claim,
    Jurisdiction,
    UnsupportedTerm,
)
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
        restrictive_absolute_claims=[1],
        restrictive_absolute_phrases_formatted='[1] -> "must"\n              ',
        indefinite_wording_claims=[],
        indefinite_wording_phrases_formatted="",
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
        abstract_legal_phraseology_formatted="",
        abstract_merit_language_formatted="",
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
        assert "REVIEW" in html
        assert "FIX" in html

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
        # 9 after the restrictiveWording split: restrictiveAbsolutes +
        # indefiniteWording now emit independently. punctuation_checks empty
        # by default.
        assert len(data.claims_checks) == 9

    def test_abstract_checks_count(self, sample_result):
        data = sample_result.to_report_data()
        # 5 after the restrictiveWording split: legalPhraseology +
        # meritLanguage now emit independently.
        assert len(data.abstract_checks) == 5

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


# ---------------------------------------------------------------------------
# Locale sweep — verify every supported locale renders without raising and
# produces jurisdiction-appropriate copy.
# ---------------------------------------------------------------------------


@pytest.fixture
def tw_sample_result():
    """TW-jurisdiction AnalysisResult with antecedent + spec-support payloads
    populated so both cards render in the PDF, plus a spec-section
    check so the jurisdictional section heading surfaces.
    """
    claims = [
        Claim(
            id=1,
            text="一種裝置，包含一元件。",
            independent=True,
            method_claim=False,
        ),
        Claim(
            id=2,
            text="如請求項1之裝置，其中該元件為金屬。",
            independent=False,
            method_claim=False,
            dependencies=[1],
        ),
    ]
    return AnalysisResult(
        jurisdiction=Jurisdiction.TW,
        patent_type="INVENTION",
        paragraph_count=10,
        claims=claims,
        independent_claims_count=1,
        dependent_claims_count=1,
        abstract_word_count=120,
        tw_specification_checks=[
            CheckItem(
                status="amend",
                message="Paragraph ending amend",
                message_key="check.tw.spec.paragraphEnding.amend",
            ),
        ],
        antecedent_basis_issues=[
            {
                "claim_id": 2,
                "term": "第二元件",
                "reference_form": "該第二元件",
                "claim_text": "如請求項1之裝置，其中該第二元件為金屬。",
                "suggested_match": None,
                "cross_ref": None,
            }
        ],
        unsupported_terms=[
            UnsupportedTerm(claim_number=2, phrase="第二元件", cross_ref=None),
        ],
    )


@pytest.fixture
def cn_sample_result():
    """CN-jurisdiction AnalysisResult for locale sweep."""
    claims = [
        Claim(id=1, text="一种装置。", independent=True, method_claim=False),
    ]
    return AnalysisResult(
        jurisdiction=Jurisdiction.CN,
        patent_type="INVENTION",
        paragraph_count=5,
        claims=claims,
        independent_claims_count=1,
        abstract_word_count=200,
    )


SUPPORTED_LOCALES = list(supported_locales())


class TestLocaleSweepUs:

    @pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
    def test_render_html_no_raise(self, sample_result, locale):
        """Every supported locale renders a US AnalysisResult without error."""
        html = render_html(sample_result, locale=locale)
        assert html
        assert "<html" in html
        assert "<body>" in html
        assert "</html>" in html

    @pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
    def test_header_translated(self, sample_result, locale):
        html = render_html(sample_result, locale=locale)
        if locale == "en":
            assert "PatentLint Analysis Report" in html
        else:
            # Every non-en bundle localizes pdf.header; we expect the
            # English fallback NOT to appear as the h1 text.
            assert "<h1>PatentLint Analysis Report</h1>" not in html

    def test_zh_tw_section_labels(self, sample_result):
        # US AnalysisResult + zh-TW locale renders the US section
        # labels (section.specification, section.claims, etc.) in
        # Traditional Chinese.
        html = render_html(sample_result, locale="zh-TW")
        assert "說明書" in html or "規格" in html
        assert "請求項" in html


class TestLocaleSweepTw:

    @pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
    def test_render_html_no_raise(self, tw_sample_result, locale):
        html = render_html(tw_sample_result, locale=locale)
        assert html
        assert "</html>" in html

    def test_tw_header_uses_tw_variant(self, tw_sample_result):
        """TW jurisdiction → pdf.headerTw key, not pdf.header."""
        html = render_html(tw_sample_result, locale="zh-TW")
        # Should contain the TW-specific header text
        assert "台灣" in html or "Taiwan" in html

    def test_tw_section_labels_tw_locale(self, tw_sample_result):
        html = render_html(tw_sample_result, locale="zh-TW")
        assert "說明書" in html  # section.tw.specification
        assert "請求項" in html  # section.tw.claims

    def test_tw_section_labels_en_locale(self, tw_sample_result):
        """TW jurisdiction + en locale renders TW section labels in English."""
        html = render_html(tw_sample_result, locale="en")
        # section.tw.specification = "Description" (English TW label)
        assert "Description" in html

    def test_tw_antecedent_card_renders_tw_copy(self, tw_sample_result):
        html = render_html(tw_sample_result, locale="zh-TW")
        assert "先行詞基礎檢視" in html

    def test_tw_spec_support_card_renders_tw_copy(self, tw_sample_result):
        html = render_html(tw_sample_result, locale="zh-TW")
        assert "說明書支持檢視" in html

    def test_tw_antecedent_card_en_fallback(self, tw_sample_result):
        """TW jurisdiction + en locale uses the English antecedent heading."""
        html = render_html(tw_sample_result, locale="en")
        assert "Antecedent Basis Review" in html
        assert "Specification Support Review" in html


class TestLocaleSweepCn:

    @pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
    def test_render_html_no_raise(self, cn_sample_result, locale):
        html = render_html(cn_sample_result, locale=locale)
        assert html
        assert "</html>" in html

    def test_cn_section_labels_cn_locale(self, cn_sample_result):
        html = render_html(cn_sample_result, locale="zh-CN")
        assert "说明书" in html
        assert "权利要求" in html

    def test_cn_abstract_counter_is_chars(self, cn_sample_result):
        """CN jurisdiction uses pdf.abstractCharCount, not wordCount."""
        html = render_html(cn_sample_result, locale="zh-CN")
        assert "摘要字数" in html


class TestLocaleFallback:
    """Unknown / unsupported locales fall through to English."""

    def test_unknown_locale_renders_english(self, sample_result):
        html_fr = render_html(sample_result, locale="fr-FR")
        html_en = render_html(sample_result, locale="en")
        # Bit-equivalence isn't guaranteed (timestamps, etc.), but the
        # triage heading should match.
        assert "Priority Actions" in html_fr
        assert "Priority Actions" in html_en

    def test_bcp47_regional_variant_normalization(self, tw_sample_result):
        """zh-Hant-TW and zh-TW should render identically."""
        html_bcp47 = render_html(tw_sample_result, locale="zh-Hant-TW")
        html_canonical = render_html(tw_sample_result, locale="zh-TW")
        assert html_bcp47 == html_canonical


class TestLocalePdfBinary:
    """A single PDF render per locale to catch font/encoding issues.

    Cheaper than doing the full cartesian product for HTML + PDF; HTML
    rendering is the pressure-test, PDF is the smoke test.
    """

    @pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
    def test_pdf_renders(self, tw_sample_result, locale):
        pdf = render_pdf(tw_sample_result, locale=locale)
        assert pdf[:4] == b"%PDF"
        assert len(pdf) > 2000


class TestNoRawKeyLeaks:
    """Any ``key.not.found`` literal in rendered HTML means the template
    referenced a locale key that doesn't exist in the bundle — surfaces
    via the i18n helper's raw-key fallback.
    """

    @pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
    def test_us_no_raw_keys(self, sample_result, locale):
        html = render_html(sample_result, locale=locale)
        # If the template references ``pdf.foo`` and the locale has no
        # ``pdf.foo`` key, the i18n helper returns the raw key literal.
        # Check for a few representative prefixes.
        for prefix in ("pdf.", "section.", "tree.", "status.", "punct.", "term."):
            # The prefix may legitimately appear inside interpolated
            # values (not as a bare rendered key). Raw-key leaks look
            # like ``pdf.header`` standalone, no <tag> wrapping.
            leaked = f">{prefix}"  # bare render attempt, not markup
            assert leaked not in html, (
                f"{locale}: raw key leak containing {prefix!r} — check "
                "template references + locale coverage."
            )

    @pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
    def test_tw_no_raw_keys(self, tw_sample_result, locale):
        html = render_html(tw_sample_result, locale=locale)
        for prefix in ("pdf.", "section.", "tree.", "status.", "punct.", "term."):
            leaked = f">{prefix}"
            assert leaked not in html, (
                f"{locale}: raw key leak containing {prefix!r}"
            )
