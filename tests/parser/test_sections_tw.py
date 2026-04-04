# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""Tests for TW section extraction from bracket-header .docx files."""

from __future__ import annotations

from pathlib import Path

import pytest

from patentlint.models import TwPatentType
from patentlint.parser.docx_loader import load_docx
from patentlint.parser.sections_tw import extract_tw_sections, _count_cjk_chars

FIXTURES = Path(__file__).parent.parent / "fixtures" / "tw"


def _load_fixture(name: str):
    """Load a .docx fixture and return TwPatentDocument."""
    loaded = load_docx(str(FIXTURES / name))
    paragraphs = [line for line in loaded.full_text.split("\n") if line.strip()]
    return extract_tw_sections(paragraphs)


class TestInventionComplete:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.doc = _load_fixture("invention_complete.docx")

    def test_patent_type(self):
        assert self.doc.patent_type == TwPatentType.INVENTION

    def test_title(self):
        assert self.doc.title == "半導體封裝結構及其製造方法"

    def test_technical_field(self):
        assert len(self.doc.technical_field) == 2
        assert "半導體封裝" in self.doc.technical_field[0]

    def test_prior_art(self):
        assert len(self.doc.prior_art) == 2

    def test_disclosure(self):
        assert len(self.doc.disclosure) == 2

    def test_drawings_description(self):
        assert len(self.doc.drawings_description) == 3

    def test_embodiment(self):
        assert len(self.doc.embodiment) == 3

    def test_symbol_table(self):
        assert len(self.doc.symbol_table) == 4
        numerals = [e.numeral for e in self.doc.symbol_table]
        assert "10" in numerals
        assert "100" in numerals

    def test_claims_count(self):
        assert len(self.doc.claims) == 6

    def test_independent_claims(self):
        indep = [c for c in self.doc.claims if c.independent]
        assert len(indep) == 2
        assert indep[0].id == 1
        assert indep[1].id == 5

    def test_dependent_claims(self):
        dep = [c for c in self.doc.claims if not c.independent]
        assert len(dep) == 4

    def test_abstract(self):
        assert "半導體封裝結構" in self.doc.abstract_text
        assert self.doc.abstract_char_count > 0

    def test_representative_drawing(self):
        assert self.doc.representative_drawing == "圖1"

    def test_representative_drawing_symbols(self):
        assert len(self.doc.representative_drawing_symbols) == 2
        assert self.doc.representative_drawing_symbols[0].numeral == "10"

    def test_figure_refs(self):
        # 圖1, 圖2, 圖3 from drawings desc + 圖1, 圖2 from embodiment
        assert len(self.doc.figure_refs) == 5
        ref_texts = [r for r in self.doc.figure_refs]
        assert any("圖1" in r for r in ref_texts)
        assert any("圖3" in r for r in ref_texts)

    def test_paragraph_numbering(self):
        assert self.doc.has_paragraph_numbering is True
        assert len(self.doc.paragraph_numbers) == 12
        assert self.doc.paragraph_numbers[0] == "0001"
        assert self.doc.paragraph_numbers[-1] == "0012"


class TestUtilityModel:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.doc = _load_fixture("utility_model_complete.docx")

    def test_patent_type(self):
        assert self.doc.patent_type == TwPatentType.UTILITY_MODEL

    def test_title(self):
        assert self.doc.title == "散熱裝置"

    def test_disclosure_populated(self):
        """新型內容 maps to disclosure field."""
        assert len(self.doc.disclosure) >= 1

    def test_claims(self):
        assert len(self.doc.claims) == 2


class TestMissingSections:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.doc = _load_fixture("missing_sections.docx")

    def test_no_drawings_description(self):
        assert len(self.doc.drawings_description) == 0

    def test_no_symbol_table(self):
        assert len(self.doc.symbol_table) == 0

    def test_no_paragraph_numbering(self):
        assert self.doc.has_paragraph_numbering is False
        assert len(self.doc.paragraph_numbers) == 0

    def test_other_sections_populated(self):
        assert len(self.doc.technical_field) >= 1
        assert len(self.doc.prior_art) >= 1
        assert len(self.doc.disclosure) >= 1
        assert len(self.doc.embodiment) >= 1

    def test_representative_drawing_none(self):
        assert self.doc.representative_drawing is None


class TestCountCjkChars:
    def test_pure_cjk(self):
        assert _count_cjk_chars("本發明") == 3

    def test_mixed_with_punctuation(self):
        # Punctuation should not be counted
        assert _count_cjk_chars("本發明。") == 3

    def test_mixed_with_spaces(self):
        assert _count_cjk_chars("本 發 明") == 3

    def test_empty(self):
        assert _count_cjk_chars("") == 0

    def test_with_numbers(self):
        # ASCII digits are not CJK — only 元件 counted
        assert _count_cjk_chars("元件10") == 2


class TestExtractTwSectionsFromRawParagraphs:
    def test_empty_input(self):
        doc = extract_tw_sections([])
        assert doc.title == ""
        assert len(doc.claims) == 0

    def test_minimal_invention(self):
        doc = extract_tw_sections([
            "【發明名稱】",
            "測試裝置",
            "【申請專利範圍】",
            "1. 一種測試裝置。",
            "【摘要】",
            "本發明提供測試裝置。",
        ])
        assert doc.title == "測試裝置"
        assert len(doc.claims) == 1
        assert doc.patent_type == TwPatentType.INVENTION

    def test_utility_model_detection(self):
        doc = extract_tw_sections([
            "【新型名稱】",
            "散熱器",
        ])
        assert doc.patent_type == TwPatentType.UTILITY_MODEL

    def test_utility_model_content_header(self):
        """新型內容 also triggers utility model detection."""
        doc = extract_tw_sections([
            "【發明名稱】",
            "某裝置",
            "【新型內容】",
            "本新型提供某裝置。",
        ])
        assert doc.patent_type == TwPatentType.UTILITY_MODEL
