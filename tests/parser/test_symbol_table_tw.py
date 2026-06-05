# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
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
        """Range notation 10~12 expands to discrete entries (issues #61/#63).

        Pre-fix behaviour was to store '10~12' as a single key, which caused
        symbolVsRepDrawing FPs when drafter wrote the range in one section
        and the enumerated form in the other. Range expansion mirrors the
        CN refnum-range convention and is bounded to <=30 spans.
        """
        result = parse_tw_symbol_table(["10~12‧‧‧散熱鰭片"])
        assert [(e.numeral, e.name) for e in result] == [
            ("10", "散熱鰭片"),
            ("11", "散熱鰭片"),
            ("12", "散熱鰭片"),
        ]

    def test_range_numeral_oversized_falls_back(self):
        """Spans > 30 fall back to the raw token (anti-runaway guard)."""
        result = parse_tw_symbol_table(["10~100‧‧‧保留"])
        assert len(result) == 1
        assert result[0].numeral == "10~100"

    def test_range_numeral_fullwidth_tilde(self):
        """Full-width tilde 10～12 expands the same as ASCII 10~12."""
        result = parse_tw_symbol_table(["10～12‧‧‧散熱鰭片"])
        assert [e.numeral for e in result] == ["10", "11", "12"]

    def test_hyphen_numeral(self):
        """Numeral with hyphen: 10-1."""
        result = parse_tw_symbol_table(["10-1‧‧‧子組件"])
        assert len(result) == 1
        assert result[0].numeral == "10-1"

    # Issue #159 — letter-prefixed range coverage. TIPO 符號說明 drafters
    # write `PHA1~PHAn`, `PR1~PRn`, `L1~Ln`, `C1~Cn` to mean "enumerated
    # family up to n" without committing to a specific upper bound. Spec
    # then uses `PR2`, `PR5`, etc. Pre-fix, the walker rejected these as
    # not covered. Post-fix, open `<prefix>n` ranges expand to the safe
    # cap (20), enumerated `<prefix>k~<prefix>m` ranges expand to the
    # literal range.

    def test_letter_prefix_open_range(self):
        """PR1~PRn → PR1, PR2, ..., PR20 (capped)."""
        result = parse_tw_symbol_table(["PR1~PRn‧‧‧光阻"])
        nums = [e.numeral for e in result]
        assert "PR1" in nums
        assert "PR2" in nums
        assert "PR20" in nums
        assert "PR21" not in nums

    def test_letter_prefix_open_range_fullwidth_tilde(self):
        """Full-width tilde variant: PR1～PRn → same expansion."""
        result = parse_tw_symbol_table(["PR1～PRn‧‧‧光阻"])
        nums = [e.numeral for e in result]
        assert "PR2" in nums

    def test_letter_prefix_enumerated_range(self):
        """LD1~LD5 → enumerated 5-item range (not open-ended)."""
        result = parse_tw_symbol_table(["LD1~LD5‧‧‧雷射二極體"])
        nums = [e.numeral for e in result]
        assert nums == ["LD1", "LD2", "LD3", "LD4", "LD5"]

    def test_letter_prefix_multichar(self):
        """Multi-char prefix: PHA1~PHAn."""
        result = parse_tw_symbol_table(["PHA1~PHAn‧‧‧相位"])
        nums = [e.numeral for e in result]
        assert "PHA1" in nums and "PHA5" in nums and "PHA20" in nums

    def test_letter_prefix_oversized_falls_back(self):
        """Enumerated range > 30 falls back to raw token."""
        result = parse_tw_symbol_table(["P1~P100‧‧‧大量"])
        assert len(result) == 1
        assert result[0].numeral == "P1~P100"

    def test_letter_prefix_mismatched_prefix_no_expand(self):
        """Mismatched prefixes (LD1~PR5) don't match the letter-range
        regex — fall through to raw token."""
        result = parse_tw_symbol_table(["LD1~PR5‧‧‧誤"])
        assert len(result) == 1
        assert result[0].numeral == "LD1~PR5"

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

    def test_comma_space_separated_numerals(self):
        """Issue #184 — enumerated numerals separated by comma-and-space
        (`210, 220, 230`) must parse identically to the tight `210,220,230`.
        The interior space previously broke the numeral group, so every
        numeral in the row was reported undeclared."""
        result = parse_tw_symbol_table(["210, 220, 230：欄位說明"])
        assert [e.numeral for e in result] == ["210", "220", "230"]
        assert all(e.name == "欄位說明" for e in result)

    def test_comma_space_letter_prefix_numerals(self):
        """#184 — same comma-and-space form with letter-prefixed numerals."""
        result = parse_tw_symbol_table(["RS11, RS14：訊號"])
        assert [e.numeral for e in result] == ["RS11", "RS14"]

    def test_comma_space_two_space_separator(self):
        """#184 — comma-and-space list with a 2-space gap before the name
        (no colon) still parses; the list continuation requires a literal
        separator so the trailing gap is unambiguous."""
        result = parse_tw_symbol_table(["210, 220, 230  欄位"])
        assert [e.numeral for e in result] == ["210", "220", "230"]

    def test_space_before_and_after_separator(self):
        """#184 — whitespace on both sides of the separator is tolerated."""
        result = parse_tw_symbol_table(["100、 101 、102：隨身碟"])
        assert [e.numeral for e in result] == ["100", "101", "102"]

    def test_tight_comma_list_unchanged(self):
        """#184 regression guard — the pre-existing tight comma form keeps
        parsing exactly as before."""
        result = parse_tw_symbol_table(["100、100a：容器本體"])
        assert [e.numeral for e in result] == ["100", "100a"]
