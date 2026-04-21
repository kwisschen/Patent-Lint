# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Adversarial tests for claims parsing — Phase 4 B6 audit."""

from patentlint.models import Claim
from patentlint.parser.claims import (
    parse_claims,
    detect_incorrect_wherein_commas,
    detect_improper_claim_wording,
)


class TestDependencyFormats:
    def test_according_to_claim(self):
        text = "1. A method.\n2. The method according to claim 1, further comprising step B.\n"
        claims = parse_claims(text)
        assert claims[1].independent is False
        assert 1 in claims[1].dependencies

    def test_as_recited_in_claim(self):
        text = "1. A device.\n2. The device as recited in claim 1, wherein the widget is blue.\n"
        claims = parse_claims(text)
        assert claims[1].independent is False

    def test_as_set_forth_in_claim(self):
        text = "1. A method.\n2. The method as set forth in claim 1, further comprising step C.\n"
        claims = parse_claims(text)
        assert claims[1].independent is False

    def test_as_defined_in_claim(self):
        text = "1. A system.\n2. The system as defined in claim 1, wherein the processor is fast.\n"
        claims = parse_claims(text)
        assert claims[1].independent is False

    def test_any_of_claims_multiple_dep(self):
        text = "1. A method.\n2. A device.\n3. The device of claims 1 or 2, with a widget.\n"
        claims = parse_claims(text)
        assert claims[2].multiple_dependent is True


class TestWhereinEdgeCases:
    def test_wherein_each_no_comma(self):
        """'wherein each' should NOT require a comma."""
        claims = [Claim(id=1, text="A device wherein each element is connected.", independent=True, method_claim=False)]
        assert detect_incorrect_wherein_commas(claims) == []

    def test_wherein_at_least_no_comma(self):
        claims = [Claim(id=1, text="A method wherein at least one processor executes.", independent=True, method_claim=True)]
        assert detect_incorrect_wherein_commas(claims) == []

    def test_wherein_when_needs_comma(self):
        claims = [Claim(id=1, text="A method wherein when the signal arrives, processing begins.", independent=True, method_claim=True)]
        assert 1 in detect_incorrect_wherein_commas(claims)


class TestWordingEdgeCases:
    def test_for_example_flagged(self):
        claims = [Claim(id=1, text="A device for example a widget.", independent=True, method_claim=False)]
        result = detect_improper_claim_wording(claims)
        assert 1 in result.improper_claims

    def test_such_as_flagged(self):
        claims = [Claim(id=1, text="A compound such as sodium chloride.", independent=True, method_claim=False)]
        result = detect_improper_claim_wording(claims)
        assert 1 in result.improper_claims

    def test_or_the_like_flagged(self):
        claims = [Claim(id=1, text="A fastener, rivet, or the like.", independent=True, method_claim=False)]
        result = detect_improper_claim_wording(claims)
        assert 1 in result.improper_claims

    def test_clean_claim_not_flagged(self):
        claims = [Claim(id=1, text="A semiconductor device comprising a substrate and a gate electrode disposed on the substrate.", independent=True, method_claim=False)]
        result = detect_improper_claim_wording(claims)
        assert 1 not in result.improper_claims
