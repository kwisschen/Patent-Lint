# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
"""Tests for patentlint.parser.claims."""

from patentlint.models import Claim
from patentlint.parser.claims import (
    parse_claims,
    is_method_claim,
    detect_incorrect_wherein_commas,
    detect_restrictive_absolutes_in_claims,
    detect_indefinite_wording_in_claims,
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

    def test_body_quoted_reference_populates_quoted_references(self):
        # 引用記載型式 / body cross-ref: `the X according to claim N` inside
        # an independent claim body should populate Claim.quoted_references.
        # The walker traverses both dependencies and quoted_references.
        text = (
            "1. A light-emitting packaging structure comprising a substrate.\n"
            "16. A light-emitting module, comprising:\n"
            "the light-emitting packaging structure according to claim 1; and\n"
            "an optical lens disposed over the light-emitting packaging structure.\n"
        )
        claims = parse_claims(text)
        c16 = next(c for c in claims if c.id == 16)
        # Body cross-ref to claim 1 must be picked up:
        assert 1 in c16.quoted_references, (
            f"expected 1 in quoted_references, got {c16.quoted_references}"
        )

    def test_body_quoted_reference_captures_all_body_form_refs(self):
        # Body cross-refs are recorded INDEPENDENTLY of the broad
        # dependencies extraction. For claim 2 (`The method of claim 1,
        # wherein the apparatus of claim 3 is used`), both `the method
        # of claim 1` (preamble form, also a body-shape match by the
        # regex) and `the apparatus of claim 3` (body cross-ref) match
        # _BODY_CROSS_REF. The walker's BFS dedups via `visited`.
        text = (
            "1. A method.\n"
            "2. The method of claim 1, wherein the apparatus of claim 3 is used.\n"
            "3. A separate apparatus.\n"
        )
        claims = parse_claims(text)
        c2 = next(c for c in claims if c.id == 2)
        # Both refs captured. (Self-ref 2 is dropped if present, which
        # it isn't here.)
        assert 1 in c2.quoted_references
        assert 3 in c2.quoted_references

    def test_body_quoted_reference_self_ref_dropped(self):
        # Pathological: claim 5 body has `the method of claim 5` - should
        # be dropped to prevent walker loops.
        text = (
            "1. A method.\n"
            "5. The method of claim 1, wherein the X of claim 5 is configured.\n"
        )
        claims = parse_claims(text)
        c5 = next(c for c in claims if c.id == 5)
        assert 5 not in c5.quoted_references

    def test_body_quoted_reference_np_cap_excludes_long_preambles(self):
        # The 5-word NP cap prevents an entire body sentence preceding
        # `claim N` from spuriously matching as a cross-ref. Here the
        # phrase before `according to claim 1` is a long preamble (>5
        # words between `the` and `according`), so it must NOT match.
        text = (
            "1. A method.\n"
            "16. A module having an exceedingly long preamble fragment "
            "comprising: the X. According to claim 1, the X is configured.\n"
        )
        claims = parse_claims(text)
        c16 = next(c for c in claims if c.id == 16)
        # The actual body cross-ref is malformed (the X with no connector),
        # so quoted_references should NOT spuriously contain 1.
        assert 1 not in c16.quoted_references

    def test_ofclaim_whitespace_collapse_normalized(self):
        # PDF→text whitespace collapse: "of claim" → "ofclaim"
        text = (
            "1. A method comprising step A.\n"
            "2. The method ofclaim 1, further comprising step B.\n"
            "3. The apparatus OfClaim 1 wherein X.\n"
            "4. The system ofclaims 1-2 wherein Y.\n"
        )
        claims = parse_claims(text)
        assert len(claims) == 4
        # canonical spacing restored
        assert "of claim 1" in claims[1].text
        assert "of Claim 1" in claims[2].text
        assert "of claims 1-2" in claims[3].text
        # dependency parsing now succeeds (was previously masked)
        assert 1 in claims[1].dependencies
        assert 1 in claims[2].dependencies
        assert claims[3].multiple_dependent is True


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

    def test_parenthetical_in_each(self):
        """'wherein, in each of the groups, the...' - parenthetical prep phrase, not a false positive."""
        claims = [Claim(id=1, text="A method wherein, in each of the groups, the elements are processed.", independent=True, method_claim=True)]
        assert detect_incorrect_wherein_commas(claims) == []

    def test_parenthetical_for_each(self):
        """'wherein, for each item in the list, a value is computed' - parenthetical."""
        claims = [Claim(id=1, text="A method wherein, for each item in the list, a value is computed.", independent=True, method_claim=True)]
        assert detect_incorrect_wherein_commas(claims) == []

    def test_parenthetical_during_operation(self):
        """'wherein, during the operation, the motor rotates' - parenthetical."""
        claims = [Claim(id=1, text="An apparatus wherein, during the operation, the motor rotates.", independent=True, method_claim=False)]
        assert detect_incorrect_wherein_commas(claims) == []

    def test_parenthetical_with_respect(self):
        """'wherein, with respect to the axis, the arm extends' - parenthetical."""
        claims = [Claim(id=1, text="A device wherein, with respect to the axis, the arm extends.", independent=True, method_claim=False)]
        assert detect_incorrect_wherein_commas(claims) == []

    def test_real_missing_comma_still_flagged(self):
        """'wherein when X' (no comma) should still be flagged."""
        claims = [Claim(id=1, text="A method wherein when the signal is received the output changes.", independent=True, method_claim=True)]
        assert 1 in detect_incorrect_wherein_commas(claims)

    def test_non_parenthetical_comma_still_flagged(self):
        """'wherein, the element is large' - comma before non-conditional should be flagged."""
        claims = [Claim(id=1, text="A method wherein, the element is large.", independent=True, method_claim=True)]
        assert 1 in detect_incorrect_wherein_commas(claims)


class TestRestrictiveAbsolutes:
    """MPEP § 2173.01: restrictive absolute terminology."""

    def test_flags_restrictive_absolutes(self):
        claims = [
            Claim(id=1, text="A method that must always process the widget.", independent=True, method_claim=True),
            Claim(id=2, text="An apparatus comprising a processor.", independent=True, method_claim=False),
        ]
        result = detect_restrictive_absolutes_in_claims(claims)
        assert 1 in result.improper_claims
        assert 2 not in result.improper_claims
        assert "must" in result.formatted_phrases
        assert "always" in result.formatted_phrases

    def test_does_not_flag_invention(self):
        # "invention" alone is not a § 2173.01 restrictive absolute; legitimate
        # antecedent references ("the invention") should not be flagged here.
        claims = [Claim(id=1, text="A method according to the invention.", independent=True, method_claim=True)]
        result = detect_restrictive_absolutes_in_claims(claims)
        assert result.improper_claims == []

    def test_does_not_flag_indefinite_modals(self):
        # Indefinite modals (may/might/can) are handled by the indefinite detector.
        claims = [Claim(id=1, text="A method that may process data.", independent=True, method_claim=True)]
        result = detect_restrictive_absolutes_in_claims(claims)
        assert result.improper_claims == []

    def test_does_not_flag_key_as_element_noun(self):
        # #286: "key" is overloaded as a physical element noun - flagging every
        # occurrence is an FP. Element-noun uses must NOT flag.
        claims = [
            Claim(id=1, text="A device comprising a key configured to actuate, wherein the key detects a pressed state of the key.", independent=True),
            Claim(id=2, text="The device, wherein the control circuit detects a key state of the key.", independent=True),
            Claim(id=3, text="A keyboard comprising a key 12 and a housing.", independent=True),
        ]
        result = detect_restrictive_absolutes_in_claims(claims)
        assert result.improper_claims == []

    def test_flags_key_only_adjectivally(self):
        # "key" IS a restrictive absolute when it adjectivally modifies an
        # importance-noun ("a key feature") - that use still flags.
        claims = [Claim(id=1, text="The invention is defined by a key feature of the housing.", independent=True)]
        result = detect_restrictive_absolutes_in_claims(claims)
        assert 1 in result.improper_claims
        assert "key" in result.formatted_phrases


class TestIndefiniteWording:
    """MPEP § 2173.05(b): relative / indefinite terminology."""

    def test_flags_indefinite_modals(self):
        claims = [Claim(id=1, text="A method that may substantially improve performance.", independent=True, method_claim=True)]
        result = detect_indefinite_wording_in_claims(claims)
        assert 1 in result.improper_claims
        assert "may" in result.formatted_phrases
        assert "substantially" in result.formatted_phrases

    def test_flags_relative_frequency(self):
        claims = [Claim(id=1, text="A method that generally typically processes data.", independent=True, method_claim=True)]
        result = detect_indefinite_wording_in_claims(claims)
        assert 1 in result.improper_claims
        assert "generally" in result.formatted_phrases
        assert "typically" in result.formatted_phrases

    def test_flags_degree_and_comparison(self):
        claims = [Claim(id=1, text="A device with a relatively similar structure.", independent=True, method_claim=False)]
        result = detect_indefinite_wording_in_claims(claims)
        assert 1 in result.improper_claims
        assert "relatively" in result.formatted_phrases
        assert "similar" in result.formatted_phrases

    def test_does_not_flag_restrictive_absolutes(self):
        # Restrictive absolutes (must/always/never) are handled by the restrictive detector.
        claims = [Claim(id=1, text="A method that must always process data.", independent=True, method_claim=True)]
        result = detect_indefinite_wording_in_claims(claims)
        assert result.improper_claims == []

    def test_does_not_flag_means_step(self):
        # § 112(f) MPF triggers are handled by detect_means_plus_function.
        claims = [Claim(id=1, text="A device comprising means for processing.", independent=True, method_claim=False)]
        result = detect_indefinite_wording_in_claims(claims)
        assert result.improper_claims == []


class TestClaimDetectorMutualExclusivity:
    """Invariant: a token caught by detect_restrictive_absolutes_in_claims
    must NOT also be caught by detect_indefinite_wording_in_claims (and vice
    versa). Same design as the abstract split - clean MPEP subcategorization."""

    def test_disjoint_coverage(self):
        text = (
            "A method that must always process substantially every element, "
            "with a generally similar output that may be preferably narrow."
        )
        claims = [Claim(id=1, text=text, independent=True, method_claim=True)]
        restrictive = detect_restrictive_absolutes_in_claims(claims)
        indefinite = detect_indefinite_wording_in_claims(claims)
        # Both fire (there are both kinds of terms in the sentence)...
        assert restrictive.improper_claims == [1]
        assert indefinite.improper_claims == [1]
        # ...but their formatted_phrases must not share any matched token.
        import re
        r_tokens = set(re.findall(r'"([^"]+)"', restrictive.formatted_phrases))
        i_tokens = set(re.findall(r'"([^"]+)"', indefinite.formatted_phrases))
        assert r_tokens & i_tokens == set(), (
            f"Overlap between restrictive and indefinite detectors: {r_tokens & i_tokens}"
        )
