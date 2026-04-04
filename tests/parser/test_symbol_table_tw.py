# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""Tests for TW symbol table parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from patentlint.parser.symbol_table_tw import parse_tw_symbol_table
from patentlint.parser.docx_loader import load_docx
from patentlint.parser.sections_tw import extract_tw_sections

FIXTURES = Path(__file__).parent.parent / "fixtures" / "tw"


class TestSymbolTableVariantsFixture:
    @pytest.fixture(autouse=True)
    def setup(self):
        loaded = load_docx(str(FIXTURES / "symbol_table_variants.docx"))
        paragraphs = [line for line in loaded.full_text.split("\n") if line.strip()]
        self.doc = extract_tw_sections(paragraphs)

    def test_all_five_parsed(self):
        assert len(self.doc.symbol_table) == 5

    def test_middle_dot_separator(self):
        """‧‧‧ (U+2027) separator."""
        entry = self.doc.symbol_table[0]
        assert entry.numeral == "10"
        assert entry.name == "本體"

    def test_ascii_dot_separator(self):
        """... (ASCII dots) separator."""
        entry = self.doc.symbol_table[1]
        assert entry.numeral == "20"
        assert entry.name == "端子"

    def test_tab_separator(self):
        entry = self.doc.symbol_table[2]
        assert entry.numeral == "30"
        assert entry.name == "外殼"

    def test_colon_separator(self):
        """Fullwidth colon ： separator."""
        entry = self.doc.symbol_table[3]
        assert entry.numeral == "40"
        assert entry.name == "彈片"

    def test_middle_dot_single(self):
        """Middle dot · (U+00B7) separator."""
        entry = self.doc.symbol_table[4]
        assert entry.numeral == "50"
        assert entry.name == "接觸面"


class TestParseTwSymbolTableUnit:
    def test_empty_input(self):
        assert parse_tw_symbol_table([]) == []

    def test_blank_lines_skipped(self):
        result = parse_tw_symbol_table(["", "  ", "\t"])
        assert result == []

    def test_single_entry(self):
        result = parse_tw_symbol_table(["10‧‧‧基板"])
        assert len(result) == 1
        assert result[0].numeral == "10"
        assert result[0].name == "基板"

    def test_non_matching_line_skipped(self):
        result = parse_tw_symbol_table([
            "10‧‧‧基板",
            "這不是符號說明",
            "20‧‧‧晶片",
        ])
        assert len(result) == 2

    def test_alphanumeric_numeral(self):
        result = parse_tw_symbol_table(["S1‧‧‧步驟一"])
        assert len(result) == 1
        assert result[0].numeral == "S1"

    def test_range_numeral(self):
        """Numeral with tilde: 10~12."""
        result = parse_tw_symbol_table(["10~12‧‧‧散熱鰭片"])
        assert len(result) == 1
        assert result[0].numeral == "10~12"

    def test_hyphen_numeral(self):
        """Numeral with hyphen: 10-1."""
        result = parse_tw_symbol_table(["10-1‧‧‧子組件"])
        assert len(result) == 1
        assert result[0].numeral == "10-1"

    def test_ellipsis_separator(self):
        """… (single ellipsis character) separator."""
        result = parse_tw_symbol_table(["10…基板"])
        assert len(result) == 1
        assert result[0].name == "基板"

    def test_whitespace_trimmed(self):
        result = parse_tw_symbol_table(["  10 ‧‧‧ 基板  "])
        assert result[0].numeral == "10"
        assert result[0].name == "基板"

    def test_ascii_colon_separator(self):
        result = parse_tw_symbol_table(["10:基板"])
        assert len(result) == 1
        assert result[0].name == "基板"
