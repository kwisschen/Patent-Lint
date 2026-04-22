# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
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

    def test_compound_title_ji_both_halves_pass_compound(self):
        """Real spec1 case: 蓋組件及帶蓋容器 — both halves appear in abstract."""
        doc = TwPatentDocument(
            title="蓋組件及帶蓋容器",
            abstract_text="本發明提供一種蓋組件，適用於帶蓋容器的密封結構。",
        )
        result = check_abstract_title_match(doc)
        assert result[0].status == "pass"
        assert result[0].message_key == "check.tw.abstract.titleMatch.passCompound"
        assert result[0].details_params == {"halves": "蓋組件、帶蓋容器"}

    def test_compound_title_he_both_halves_pass_compound(self):
        doc = TwPatentDocument(
            title="感測元件和控制電路",
            abstract_text="本發明揭示一種感測元件及與其耦接之控制電路。",
        )
        result = check_abstract_title_match(doc)
        assert result[0].status == "pass"
        assert result[0].message_key == "check.tw.abstract.titleMatch.passCompound"

    def test_compound_title_yu_both_halves_pass_compound(self):
        doc = TwPatentDocument(
            title="發光二極體與驅動電路",
            abstract_text="本發明提供一種發光二極體及驅動電路。",
        )
        result = check_abstract_title_match(doc)
        assert result[0].status == "pass"
        assert result[0].message_key == "check.tw.abstract.titleMatch.passCompound"

    def test_compound_title_yiji_preferred_over_ji(self):
        """以及 must match first so split does not fire on trailing 及."""
        doc = TwPatentDocument(
            title="記憶體模組以及存取裝置",
            abstract_text="本發明揭示記憶體模組及存取裝置。",
        )
        result = check_abstract_title_match(doc)
        assert result[0].status == "pass"
        assert result[0].details_params == {"halves": "記憶體模組、存取裝置"}

    def test_compound_title_one_half_missing_verify(self):
        doc = TwPatentDocument(
            title="蓋組件及帶蓋容器",
            abstract_text="本發明提供一種蓋組件。",
        )
        result = check_abstract_title_match(doc)
        assert result[0].status == "verify"
        assert result[0].message_key == "check.tw.abstract.titleMatch.verify"

    def test_compound_title_single_char_half_verify(self):
        """Single-CJK-char halves do not trigger compound match."""
        doc = TwPatentDocument(
            title="A及蓋組件",
            abstract_text="本發明揭示A與蓋組件。",
        )
        result = check_abstract_title_match(doc)
        assert result[0].status == "verify"


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

    def test_flagged_phrases_items_surfaced(self):
        """FlaggedTermList chip payload is emitted alongside the legacy
        `terms` string so the UI can render detected commercial terms as chips."""
        doc = TwPatentDocument(abstract_text="本發明為最優且最佳之世界領先技術。")
        result = check_commercial_language(doc)
        items = result[0].details_params.get("flagged_phrases", {}).get("items", [])
        tokens = [i["token"] for i in items]
        assert "最優" in tokens
        assert "最佳" in tokens
        assert "世界領先" in tokens
        for item in items:
            assert item["kind"] == "phrase"


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
