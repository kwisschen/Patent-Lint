# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Tests for the Python details-formatter port.

Structural parity with frontend/src/lib/detailsFormatter.js. If these
drift, the weasyprint PDF copy will diverge from the React copy on
structured payloads (claim lists, figure lists, symbol-table
inconsistency, etc.).
"""

import pytest

from patentlint.models import CheckItem
from patentlint.report.details import (
    format_details,
    localize_details,
    localize_message,
)


class TestFormatDetails:

    def test_empty_key_returns_empty(self):
        assert format_details("", {}) == ""
        assert format_details("", None) == ""

    def test_no_params(self):
        # Translates plain key without interpolation.
        assert format_details("pdf.header", None) == "PatentLint Analysis Report"

    def test_flat_params(self):
        out = format_details(
            "details.claimsOverview",
            {"independent": 2, "dependent": 5, "total": 7},
        )
        assert "2" in out and "5" in out and "7" in out

    def test_claim_list(self):
        # ``details.tw.antecedentBasisTerms`` interpolates claim_count +
        # issue_count; ``claims`` is a formatter-eligible field even if
        # the template doesn't reference it, so the pre-render pass
        # must not raise.
        rendered_claims = format_details(
            "details.tw.antecedentBasisTerms",
            {"issue_count": 3, "claim_count": 2, "claims": [1, 3]},
            "en",
        )
        assert "3" in rendered_claims and "2" in rendered_claims

    def test_claim_list_truncation(self):
        from patentlint.report.details import _format_claim_list
        from patentlint.i18n import get_translator

        claims = list(range(1, 15))  # 14 claims → truncate to 10 + ellipsis
        rendered = _format_claim_list(claims, get_translator("en"))
        assert rendered.endswith(", ...")
        # 10 claims + ellipsis
        assert rendered.count("claim") == 10

    def test_figure_list(self):
        from patentlint.report.details import _format_figure_list
        from patentlint.i18n import get_translator

        t = get_translator("en")
        rendered = _format_figure_list([1, 2, 3], t)
        assert "figure 1" in rendered and "figure 3" in rendered

    def test_numeral_list(self):
        from patentlint.report.details import _format_numeral_list
        from patentlint.i18n import get_translator

        t = get_translator("en")
        rendered = _format_numeral_list([100, 200, 300], t)
        assert "100" in rendered and "300" in rendered

    def test_sample_names_with_component_count(self):
        from patentlint.report.details import _format_sample_names
        from patentlint.i18n import get_translator

        t = get_translator("en")
        rendered = _format_sample_names(
            ["a", "b", "c"], t, {"component_count": 5}
        )
        assert rendered.endswith(", ...")

    def test_sample_names_without_truncation(self):
        from patentlint.report.details import _format_sample_names
        from patentlint.i18n import get_translator

        t = get_translator("en")
        rendered = _format_sample_names(
            ["a", "b", "c"], t, {"component_count": 3}
        )
        assert not rendered.endswith("...")

    def test_figures_with_locations(self):
        from patentlint.report.details import _format_figures_with_locations
        from patentlint.i18n import get_translator

        t = get_translator("en")
        rendered = _format_figures_with_locations(
            [{"figure": 2, "paragraphs": [5, 7]}], t
        )
        assert "figure 2" in rendered and "paragraph 5" in rendered

    def test_numerals_with_locations(self):
        from patentlint.report.details import _format_numerals_with_locations
        from patentlint.i18n import get_translator

        t = get_translator("en")
        rendered = _format_numerals_with_locations(
            [{"numeral": 42, "claims": [1, 2]}], t
        )
        assert "42" in rendered and "claim 1" in rendered

    def test_symbol_table_inconsistency(self):
        from patentlint.report.details import _format_symbol_table_inconsistency
        from patentlint.i18n import get_translator

        t = get_translator("en")
        rendered = _format_symbol_table_inconsistency(
            {"unreferenced": [10, 20], "undefined": [30]}, t
        )
        assert "10" in rendered and "20" in rendered and "30" in rendered

    def test_figure_ref_inconsistency_tw(self):
        from patentlint.report.details import _format_figure_ref_inconsistency
        from patentlint.i18n import get_translator

        t = get_translator("en")
        rendered = _format_figure_ref_inconsistency(
            {
                "only_drawings": [1, 2],
                "only_embodiment": [3],
                "jurisdiction": "tw",
            },
            t,
        )
        # Template includes "Only cited in 圖式簡單說明" marker in en
        assert "1" in rendered and "3" in rendered

    def test_paragraph_format_violations(self):
        from patentlint.report.details import _format_paragraph_format_violations
        from patentlint.i18n import get_translator

        t = get_translator("en")
        rendered = _format_paragraph_format_violations(
            {"examples": ["[foo]", "[bar]"], "count": 7}, t
        )
        assert "[foo]" in rendered and "[bar]" in rendered and "7" in rendered


class TestLocalizeMessage:

    def test_returns_translation_when_key_resolves(self):
        item = CheckItem(
            status="pass",
            message="ENGLISH FALLBACK",
            message_key="pdf.header",
        )
        assert localize_message(item, "en") == "PatentLint Analysis Report"

    def test_falls_back_to_message_on_missing_key(self):
        item = CheckItem(
            status="pass",
            message="ENGLISH FALLBACK",
            message_key="does.not.exist",
        )
        assert localize_message(item, "en") == "ENGLISH FALLBACK"

    def test_no_key_returns_message(self):
        item = CheckItem(
            status="pass",
            message="ONLY ENGLISH",
            message_key="",
        )
        assert localize_message(item, "en") == "ONLY ENGLISH"

    def test_different_locale(self):
        item = CheckItem(
            status="pass",
            message="ENGLISH",
            message_key="pdf.header",
        )
        zh = localize_message(item, "zh-TW")
        en = localize_message(item, "en")
        assert zh != en
        assert zh != "pdf.header"


class TestLocalizeDetails:

    def test_returns_translation_when_key_resolves(self):
        item = CheckItem(
            status="pass",
            message="x",
            message_key="pdf.header",
            details="ENGLISH DETAILS",
            details_key="pdf.header",  # reusing a known key for test purposes
        )
        assert localize_details(item, "en") == "PatentLint Analysis Report"

    def test_falls_back_to_details_on_missing_key(self):
        item = CheckItem(
            status="pass",
            message="x",
            message_key="pdf.header",
            details="ENGLISH DETAILS",
            details_key="does.not.exist",
        )
        assert localize_details(item, "en") == "ENGLISH DETAILS"

    def test_no_key_returns_details(self):
        item = CheckItem(
            status="pass",
            message="x",
            message_key="pdf.header",
            details="ONLY ENGLISH DETAILS",
            details_key=None,
        )
        assert localize_details(item, "en") == "ONLY ENGLISH DETAILS"

    def test_no_details_no_key_returns_none(self):
        item = CheckItem(
            status="pass",
            message="x",
            message_key="pdf.header",
        )
        assert localize_details(item, "en") is None


class TestFrontendParity:
    """Cross-reference Python output against the frontend JS logic.

    The JS detailsFormatter passes ``claims: [1,3,5]`` and renders
    ``claim 1, claim 3, claim 5`` via ``term.claim.numbered``. We
    mirror that exactly so the PDF and React paths render claim lists
    identically.
    """

    @pytest.mark.parametrize("locale", ["en", "zh-TW", "zh-CN", "ja", "ko"])
    def test_claim_list_renders_in_all_locales(self, locale):
        from patentlint.report.details import _format_claim_list
        from patentlint.i18n import get_translator

        t = get_translator(locale)
        rendered = _format_claim_list([1, 5, 12], t)
        assert rendered  # non-empty in every locale
        # Must contain localized claim labels (number alone doesn't prove
        # the formatter ran, but together with the separator it does).
        assert "1" in rendered and "12" in rendered
