# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Tests for TW claim parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from patentlint.parser.claims_tw import parse_tw_claims
from patentlint.parser.docx_loader import load_docx
from patentlint.parser.sections_tw import extract_tw_sections

FIXTURES = Path(__file__).parent.parent / "fixtures" / "tw"


def _load_claims(name: str):
    loaded = load_docx(str(FIXTURES / name))
    paragraphs = [line for line in loaded.full_text.split("\n") if line.strip()]
    doc = extract_tw_sections(paragraphs)
    return doc.claims


class TestClaimDependencyFixture:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.claims = _load_claims("claim_dependencies.docx")

    def test_claim_count(self):
        assert len(self.claims) == 9

    def test_claim_1_independent(self):
        c = self.claims[0]
        assert c.id == 1
        assert c.independent is True
        assert c.dependencies == []

    def test_claim_2_simple_dep(self):
        """如請求項1所述之 -> depends on [1]."""
        c = self.claims[1]
        assert c.id == 2
        assert c.independent is False
        assert c.dependencies == [1]

    def test_claim_3_short_form_dep(self):
        """如請求項1之 -> depends on [1]."""
        c = self.claims[2]
        assert c.id == 3
        assert c.independent is False
        assert c.dependencies == [1]

    def test_claim_4_multi_dep_or(self):
        """如請求項1或2之 -> depends on [1, 2]."""
        c = self.claims[3]
        assert c.id == 4
        assert c.independent is False
        assert sorted(c.dependencies) == [1, 2]
        assert c.multiple_dependent is True

    def test_claim_5_range_dep(self):
        """如請求項1~3中任一項所述之 -> depends on [1, 2, 3]."""
        c = self.claims[4]
        assert c.id == 5
        assert c.independent is False
        assert sorted(c.dependencies) == [1, 2, 3]
        assert c.multiple_dependent is True

    def test_claim_6_independent(self):
        c = self.claims[5]
        assert c.id == 6
        assert c.independent is True

    def test_claim_7_self_ref(self):
        """Self-referencing claim — deps include self."""
        c = self.claims[6]
        assert c.id == 7
        assert 7 in c.dependencies

    def test_claim_8_forward_ref(self):
        """Forward-referencing claim — deps include higher number."""
        c = self.claims[7]
        assert c.id == 8
        assert 9 in c.dependencies

    def test_claim_9_normal_dep(self):
        c = self.claims[8]
        assert c.id == 9
        assert c.dependencies == [6]


class TestParseTwClaimsUnit:
    def test_empty_input(self):
        assert parse_tw_claims([]) == []

    def test_empty_string(self):
        assert parse_tw_claims([""]) == []

    def test_single_independent(self):
        claims = parse_tw_claims(["1. 一種裝置，包含一元件。"])
        assert len(claims) == 1
        assert claims[0].id == 1
        assert claims[0].independent is True

    def test_two_claims(self):
        claims = parse_tw_claims([
            "1. 一種裝置，包含一元件A。",
            "2. 如請求項1所述之裝置，更包含一元件B。",
        ])
        assert len(claims) == 2
        assert claims[1].dependencies == [1]

    def test_fullwidth_period(self):
        """Fullwidth period ．as claim number separator."""
        claims = parse_tw_claims(["1．一種裝置。"])
        assert len(claims) == 1
        assert claims[0].id == 1

    def test_range_with_至(self):
        claims = parse_tw_claims([
            "1. 一種裝置。",
            "2. 如請求項1所述之裝置。",
            "3. 如請求項1至2中任一項所述之裝置。",
        ])
        assert sorted(claims[2].dependencies) == [1, 2]

    def test_dep_with_or_and_comma(self):
        claims = parse_tw_claims([
            "1. 一種裝置。",
            "2. 一種方法。",
            "3. 一種系統。",
            "4. 如請求項1或2、3之裝置。",
        ])
        assert sorted(claims[3].dependencies) == [1, 2, 3]
        assert claims[3].multiple_dependent is True

    def test_no_claim_number_pattern(self):
        """Text without claim number pattern returns empty."""
        claims = parse_tw_claims(["這不是請求項。"])
        assert claims == []
