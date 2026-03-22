"""Tests for patentlint.parser.claims."""

from patentlint.models import Claim
from patentlint.parser.claims import (
    parse_claims,
    is_method_claim,
    detect_incorrect_wherein_commas,
    detect_improper_claim_wording,
)


class TestParseClaims:
    def test_basic(self):
        text = "CLAIMS\n1. A method comprising step A.\n2. The method of claim 1, further comprising step B.\n3. A system comprising a processor.\n"
        claims = parse_claims(text)
        assert len(claims) == 3
        assert claims[0].id == 1
        assert claims[0].independent is True
        assert claims[1].id == 2
        assert claims[1].independent is False
        assert 1 in claims[1].dependencies
        assert claims[2].id == 3
        assert claims[2].independent is True

    def test_multiple_dependency(self):
        text = "1. A method.\n2. The method of claim 1, with step B.\n3. The method of claims 1 to 2, with step C.\n"
        claims = parse_claims(text)
        assert claims[2].multiple_dependent is True

    def test_method_claim(self):
        text = "1. A method of processing data, comprising: receiving input.\n2. An apparatus comprising a processor.\n"
        claims = parse_claims(text)
        assert claims[0].method_claim is True
        assert claims[1].method_claim is False

    def test_what_is_claimed(self):
        text = "What is claimed is:\n1. A device for processing.\n"
        claims = parse_claims(text)
        assert len(claims) == 1
        assert "device for processing" in claims[0].text

    def test_empty(self):
        assert parse_claims("") == []
        assert parse_claims("   ") == []


class TestIsMethodClaim:
    def test_method_before_comma(self):
        assert is_method_claim("A method of manufacturing, comprising:") is True

    def test_method_after_comma(self):
        assert is_method_claim("An apparatus, wherein a method is applied") is False

    def test_no_method(self):
        assert is_method_claim("An apparatus comprising a widget") is False


class TestWhereinComma:
    def test_missing_comma(self):
        claims = [Claim(id=1, text="A method wherein when the input is received, processing occurs.", independent=True, method_claim=True)]
        assert 1 in detect_incorrect_wherein_commas(claims)

    def test_at_least_ok(self):
        claims = [Claim(id=1, text="A method wherein at least one element is present.", independent=True, method_claim=True)]
        assert detect_incorrect_wherein_commas(claims) == []


class TestImproperWording:
    def test_flags_restrictive(self):
        claims = [
            Claim(id=1, text="A method that must always process the invention.", independent=True, method_claim=True),
            Claim(id=2, text="An apparatus comprising a processor.", independent=True, method_claim=False),
        ]
        result = detect_improper_claim_wording(claims)
        assert 1 in result.improper_claims
        assert 2 not in result.improper_claims
        assert "must" in result.formatted_phrases
        assert "always" in result.formatted_phrases
        assert "invention" in result.formatted_phrases

    def test_flags_indefinite(self):
        claims = [Claim(id=1, text="A method that may substantially improve performance.", independent=True, method_claim=True)]
        result = detect_improper_claim_wording(claims)
        assert 1 in result.improper_claims
        assert "may" in result.formatted_phrases
        assert "substantially" in result.formatted_phrases

    def test_flags_relative_frequency(self):
        claims = [Claim(id=1, text="A method that generally typically processes data.", independent=True, method_claim=True)]
        result = detect_improper_claim_wording(claims)
        assert 1 in result.improper_claims
        assert "generally" in result.formatted_phrases
        assert "typically" in result.formatted_phrases

    def test_flags_degree_and_comparison(self):
        claims = [Claim(id=1, text="A device with a relatively similar structure.", independent=True, method_claim=False)]
        result = detect_improper_claim_wording(claims)
        assert 1 in result.improper_claims
        assert "relatively" in result.formatted_phrases
        assert "similar" in result.formatted_phrases
