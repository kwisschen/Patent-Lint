# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Tests for TW abstract checks (#27-30)."""

from __future__ import annotations

from patentlint.analysis.tw_abstract import (
    check_abstract_char_count,
    check_abstract_title_match,
    check_commercial_language,
    check_representative_drawing,
)
from patentlint.models import TwPatentDocument


class TestCheckAbstractCharCount:
    """Check #27: Abstract character count (250-char soft limit)."""

    def test_exactly_250_chars_pass(self):
        doc = TwPatentDocument(abstract_char_count=250)
        result = check_abstract_char_count(doc)
        assert len(result) == 1
        assert result[0].status == "pass"
        assert result[0].details_params == {"count": "250"}

    def test_251_chars_verify(self):
        doc = TwPatentDocument(abstract_char_count=251)
        result = check_abstract_char_count(doc)
        assert len(result) == 1
        assert result[0].status == "verify"
        assert result[0].details_params == {"count": "251"}
        assert result[0].reference == "專利法施行細則 §21"

    def test_empty_abstract_pass(self):
        doc = TwPatentDocument(abstract_char_count=0)
        result = check_abstract_char_count(doc)
        assert result[0].status == "pass"
        assert result[0].details_params == {"count": "0"}

    def test_under_limit_pass(self):
        doc = TwPatentDocument(abstract_char_count=100)
        result = check_abstract_char_count(doc)
        assert result[0].status == "pass"

    def test_well_over_limit_verify(self):
        doc = TwPatentDocument(abstract_char_count=500)
        result = check_abstract_char_count(doc)
        assert result[0].status == "verify"

    def test_severity_is_verify_not_amend(self):
        """TIPO won't reject on length alone — must be VERIFY."""
        doc = TwPatentDocument(abstract_char_count=300)
        result = check_abstract_char_count(doc)
        assert result[0].status == "verify"
        assert result[0].status != "amend"

    def test_message_key(self):
        doc = TwPatentDocument(abstract_char_count=251)
        result = check_abstract_char_count(doc)
        assert result[0].message_key == "check.tw.abstract.charCount.verify"

    def test_pass_message_key(self):
        doc = TwPatentDocument(abstract_char_count=200)
        result = check_abstract_char_count(doc)
        assert result[0].message_key == "check.tw.abstract.charCount.pass"


class TestCheckAbstractTitleMatch:
    """Check #28: Title appears in abstract."""

    def test_title_found_pass(self):
        doc = TwPatentDocument(
            title="光學感測裝置",
            abstract_text="本發明提供一種光學感測裝置，包括感測元件。",
        )
        result = check_abstract_title_match(doc)
        assert result[0].status == "pass"

    def test_title_not_found_verify(self):
        doc = TwPatentDocument(
            title="光學感測裝置",
            abstract_text="本發明提供一種電子元件，包括處理器。",
        )
        result = check_abstract_title_match(doc)
        assert result[0].status == "verify"
        assert result[0].details_params == {"detail": "光學感測裝置"}

    def test_empty_abstract_pass(self):
        doc = TwPatentDocument(title="光學感測裝置", abstract_text="")
        result = check_abstract_title_match(doc)
        assert result[0].status == "pass"

    def test_empty_title_pass(self):
        doc = TwPatentDocument(title="", abstract_text="本發明提供一種裝置。")
        result = check_abstract_title_match(doc)
        assert result[0].status == "pass"

    def test_both_empty_pass(self):
        doc = TwPatentDocument(title="", abstract_text="")
        result = check_abstract_title_match(doc)
        assert result[0].status == "pass"

    def test_whitespace_only_title_pass(self):
        doc = TwPatentDocument(title="  ", abstract_text="本發明提供一種裝置。")
        result = check_abstract_title_match(doc)
        assert result[0].status == "pass"

    def test_message_key_verify(self):
        doc = TwPatentDocument(title="X", abstract_text="Y")
        result = check_abstract_title_match(doc)
        assert result[0].message_key == "check.tw.abstract.titleMatch.verify"


class TestCheckCommercialLanguage:
    """Check #29: Commercial language in abstract."""

    def test_single_term_amend(self):
        doc = TwPatentDocument(abstract_text="本發明為最優之解決方案。")
        result = check_commercial_language(doc)
        assert result[0].status == "amend"
        assert "最優" in result[0].details_params["terms"]

    def test_multiple_terms_amend(self):
        doc = TwPatentDocument(abstract_text="本發明為最優且最佳之世界領先技術。")
        result = check_commercial_language(doc)
        assert result[0].status == "amend"
        terms = result[0].details_params["terms"]
        assert "最優" in terms
        assert "最佳" in terms
        assert "世界領先" in terms

    def test_clean_abstract_pass(self):
        doc = TwPatentDocument(abstract_text="本發明提供一種光學感測裝置。")
        result = check_commercial_language(doc)
        assert result[0].status == "pass"

    def test_empty_abstract_pass(self):
        doc = TwPatentDocument(abstract_text="")
        result = check_commercial_language(doc)
        assert result[0].status == "pass"

    def test_all_commercial_terms(self):
        """All 6 TW commercial terms should be detected."""
        terms = ["最優", "最佳", "世界領先", "國際領先", "國內首創", "填補空白"]
        for term in terms:
            doc = TwPatentDocument(abstract_text=f"本發明{term}技術。")
            result = check_commercial_language(doc)
            assert result[0].status == "amend", f"Failed for {term}"

    def test_traditional_chinese_terms(self):
        """Verify terms are Traditional Chinese, not Simplified."""
        doc = TwPatentDocument(abstract_text="本發明為國內首創技術。")
        result = check_commercial_language(doc)
        assert result[0].status == "amend"

    def test_reference(self):
        doc = TwPatentDocument(abstract_text="最佳方案。")
        result = check_commercial_language(doc)
        assert result[0].reference == "專利法施行細則 §21"


class TestCheckRepresentativeDrawing:
    """Check #30: Representative drawing designation."""

    def test_drawings_exist_no_rep_drawing_verify(self):
        doc = TwPatentDocument(
            figure_refs=["1", "2"],
            representative_drawing=None,
        )
        result = check_representative_drawing(doc)
        assert result[0].status == "verify"

    def test_drawings_exist_rep_drawing_present_pass(self):
        doc = TwPatentDocument(
            figure_refs=["1", "2"],
            representative_drawing="第1圖",
        )
        result = check_representative_drawing(doc)
        assert result[0].status == "pass"

    def test_no_drawings_pass(self):
        doc = TwPatentDocument(figure_refs=[], representative_drawing=None)
        result = check_representative_drawing(doc)
        assert result[0].status == "pass"

    def test_empty_rep_drawing_string_verify(self):
        doc = TwPatentDocument(
            figure_refs=["1"],
            representative_drawing="",
        )
        result = check_representative_drawing(doc)
        assert result[0].status == "verify"

    def test_message_key(self):
        doc = TwPatentDocument(figure_refs=["1"], representative_drawing=None)
        result = check_representative_drawing(doc)
        assert result[0].message_key == "check.tw.abstract.representativeDrawing.verify"

    def test_reference(self):
        doc = TwPatentDocument(figure_refs=["1"], representative_drawing=None)
        result = check_representative_drawing(doc)
        assert result[0].reference == "專利法施行細則 §21"
