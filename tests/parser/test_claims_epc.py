# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""EPC claim parser tests.

Covers EPC-specific dependency phrasings:
  - "claim N"
  - "claims N to M" / "claims N-M"
  - "any of claims N to M"
  - "any one of claims N to M"
  - "any preceding claim"  (uniquely EPC)
  - "claim N and M" / "claim N or M"
"""

from __future__ import annotations

from patentlint.parser.claims_epc import (
    is_method_claim_epc,
    parse_claims_epc,
    parse_dependencies_epc,
)


CLAIMS_BLOCK_BASIC = """
1. An apparatus comprising a processor and a memory.

2. The apparatus according to claim 1, wherein the memory stores
   convergence parameters.

3. The apparatus according to any preceding claim, further comprising
   a communication interface.

4. The apparatus according to any one of claims 1 to 3, wherein the
   communication interface is wireless.

5. The apparatus of claim 2 or 3, wherein the processor is a microcontroller.

6. A method of operating the apparatus of claim 1, comprising:
   receiving a signal; and
   processing the signal.
"""


def test_parses_six_claims():
    claims = parse_claims_epc(CLAIMS_BLOCK_BASIC)
    assert len(claims) == 6
    assert [c.id for c in claims] == [1, 2, 3, 4, 5, 6]


def test_claim_1_independent():
    claims = parse_claims_epc(CLAIMS_BLOCK_BASIC)
    assert claims[0].independent is True
    assert claims[0].dependencies == []


def test_claim_2_simple_dependency():
    claims = parse_claims_epc(CLAIMS_BLOCK_BASIC)
    assert claims[1].independent is False
    assert claims[1].dependencies == [1]


def test_claim_3_any_preceding_claim_expands():
    """'any preceding claim' on claim 3 should expand to [1, 2]."""
    claims = parse_claims_epc(CLAIMS_BLOCK_BASIC)
    assert claims[2].independent is False
    assert claims[2].dependencies == [1, 2]
    assert claims[2].multiple_dependent is True


def test_claim_4_any_one_of_range_expands():
    """'any one of claims 1 to 3' should expand to [1, 2, 3]."""
    claims = parse_claims_epc(CLAIMS_BLOCK_BASIC)
    assert claims[3].independent is False
    assert claims[3].dependencies == [1, 2, 3]
    assert claims[3].multiple_dependent is True


def test_claim_5_alternative_dependency():
    """'claim 2 or 3' should resolve to [2, 3]."""
    claims = parse_claims_epc(CLAIMS_BLOCK_BASIC)
    assert claims[4].independent is False
    assert claims[4].dependencies == [2, 3]
    assert claims[4].multiple_dependent is True


def test_claim_6_method_claim_flagged():
    """'A method of operating ...' is a method claim."""
    claims = parse_claims_epc(CLAIMS_BLOCK_BASIC)
    assert claims[5].method_claim is True
    assert claims[5].independent is False
    assert claims[5].dependencies == [1]


def test_strips_claims_header():
    text = "CLAIMS\n\n1. An apparatus.\n\n2. The apparatus of claim 1."
    claims = parse_claims_epc(text)
    assert len(claims) == 2
    assert claims[0].text.startswith("An apparatus")


def test_strips_what_is_claimed_is_header():
    text = "What is claimed is:\n\n1. An apparatus.\n\n2. The apparatus of claim 1."
    claims = parse_claims_epc(text)
    assert len(claims) == 2


def test_empty_returns_empty():
    assert parse_claims_epc("") == []
    assert parse_claims_epc("CLAIMS\n\n") == []


def test_self_reference_dropped():
    """Claim 5 listing itself as a parent shouldn't leak through."""
    text = "1. A widget.\n\n5. The widget of claim 5, wherein x."
    claims = parse_claims_epc(text)
    assert claims[1].dependencies == []


def test_range_expansion():
    deps = parse_dependencies_epc("according to claims 1 to 4", False, 5)
    assert deps == [1, 2, 3, 4]


def test_hyphen_range_expansion():
    deps = parse_dependencies_epc("according to claims 2-5", False, 6)
    assert deps == [2, 3, 4, 5]


def test_is_method_claim_epc():
    assert is_method_claim_epc("A method of doing X, comprising:") is True
    assert is_method_claim_epc("A process for forming Y, comprising:") is True
    assert is_method_claim_epc("An apparatus comprising X") is False


# ---------------------------------------------------------------------------
# Edge cases — dependency parsing
# ---------------------------------------------------------------------------


def test_dep_with_capitalised_claim():
    """'Claim N' (capital C, common in EPC drafts) should parse as a dep."""
    deps = parse_dependencies_epc("The apparatus of Claim 1", False, 2)
    assert deps == [1]


def test_dep_inverted_range_does_not_crash():
    """A backward range like 'claims 5 to 2' is malformed input; parser must
    not crash. Specific behavior: range expansion is skipped (start > end);
    the simple "claim N" fallback only catches "claim 5" — "2" remains an
    isolated number without a "claim" prefix, so it's not captured. This is
    acceptable for malformed input; the test guards against crashes."""
    deps = parse_dependencies_epc("according to claims 5 to 2", False, 6)
    assert 5 in deps


def test_any_preceding_on_claim_2():
    """'any preceding claim' on claim 2 → only [1]."""
    deps = parse_dependencies_epc("according to any preceding claim", False, 2)
    assert deps == [1]


def test_any_preceding_on_claim_1_yields_empty():
    """'any preceding claim' on claim 1 → empty (no prior claims)."""
    deps = parse_dependencies_epc("according to any preceding claim", False, 1)
    assert deps == []


def test_three_way_alternation():
    """'claim 1, 2 or 3' — common EPC alternation form."""
    # The current parser matches "claim N and/or M" as a pair, so three-way
    # alternation may collapse to the first pair. Verify the actual behaviour
    # so future parser improvements have a baseline to compare against.
    deps = parse_dependencies_epc("according to claim 1, 2 or 3", False, 4)
    # At minimum, every numeric reference is captured by the simple "claim N"
    # fallback; the multi-dep flag may or may not fire depending on the
    # primary regex.
    assert 1 in deps
    assert 2 in deps
    assert 3 in deps


def test_parens_in_claim_body_not_dep():
    """Reference signs like '(10)' in a claim body must not be parsed as deps."""
    text = "An apparatus (10) comprising a processor (12)"
    deps = parse_dependencies_epc(text, True, 1)
    # Independent → empty regardless
    assert deps == []
    # And the independent classifier shouldn't flip on parenthesized refs
    claims = parse_claims_epc("1. An apparatus (10) comprising a processor (12).")
    assert claims[0].independent is True


def test_claim_block_with_blank_lines():
    """Claim blocks separated by blank lines parse correctly."""
    text = """1. An apparatus.


2. The apparatus of claim 1, wherein X.


3. The apparatus of claim 2, wherein Y."""
    claims = parse_claims_epc(text)
    assert len(claims) == 3
    assert claims[1].dependencies == [1]
    assert claims[2].dependencies == [2]


def test_multiple_dep_with_and_or_in_chain():
    """'claim 1, 2, and 3' or 'claims 1, 2 and 3' patterns."""
    deps = parse_dependencies_epc("according to claims 1 and 2", False, 3)
    assert deps == [1, 2]


def test_dep_with_long_prepositional_phrase():
    """Long preamble shouldn't break dep parsing."""
    text = "The signal-processing apparatus for use in a communication device according to claim 5, wherein"
    deps = parse_dependencies_epc(text, False, 6)
    assert deps == [5]
