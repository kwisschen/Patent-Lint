# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""EPC G4 claims-structure check tests.

Eight checks:
  - claimsSequential
  - dependencyFormat
  - selfDependent
  - forwardDependency
  - singleSentencePerClaim
  - refSignsInParens
  - subjectConsistency
  - transitionPhrase
"""

from __future__ import annotations

from patentlint.analysis.epc_claims import (
    check_claims_sequential_epc,
    check_dependency_format_epc,
    check_forward_dependency_epc,
    check_reference_signs_in_parens_epc,
    check_self_dependent_epc,
    check_single_sentence_per_claim_epc,
    check_subject_consistency_epc,
    check_transition_phrase_epc,
    run_g4_claims_structure_checks,
)
from patentlint.models import Claim


def _make(id, text, independent=True, deps=None, multi=False, method=False):
    return Claim(
        id=id, text=text, independent=independent,
        dependencies=deps or [], multiple_dependent=multi, method_claim=method,
    )


CANONICAL_CLAIMS = [
    _make(1, "An apparatus (10) comprising a processor (12) and a memory (14)."),
    _make(2, "The apparatus (10) according to claim 1, wherein the memory (14) is volatile.",
          independent=False, deps=[1]),
    _make(3, "The apparatus (10) according to any preceding claim, further comprising a transceiver (16).",
          independent=False, deps=[1, 2], multi=True),
]


# --- claimsSequential ---------------------------------------------------------


def test_sequential_canonical_passes():
    results = check_claims_sequential_epc(CANONICAL_CLAIMS)
    assert len(results) == 1
    assert results[0].status == "pass"


def test_sequential_gap_amends():
    claims = [_make(1, "An apparatus comprising X."), _make(3, "The apparatus of claim 1.", independent=False, deps=[1])]
    results = check_claims_sequential_epc(claims)
    assert len(results) == 1
    assert results[0].status == "amend"
    assert "2" in (results[0].details or "")


def test_sequential_empty_passes():
    results = check_claims_sequential_epc([])
    assert results[0].status == "pass"


# --- dependencyFormat ---------------------------------------------------------


def test_dependency_format_canonical_passes():
    results = check_dependency_format_epc(CANONICAL_CLAIMS)
    assert results[0].status == "pass"


def test_dependency_format_dependent_without_parent_amends():
    """A claim classified as dependent but with an empty dependency list."""
    bad = _make(2, "Some text without a real parent.", independent=False, deps=[])
    results = check_dependency_format_epc([_make(1, "An apparatus comprising X."), bad])
    assert results[0].status == "amend"


# --- selfDependent ------------------------------------------------------------


def test_self_dependent_canonical_passes():
    results = check_self_dependent_epc(CANONICAL_CLAIMS)
    assert results[0].status == "pass"


def test_self_dependent_amends():
    bad = _make(2, "The apparatus of claim 2.", independent=False, deps=[2])
    results = check_self_dependent_epc([_make(1, "An apparatus."), bad])
    assert results[0].status == "amend"


# --- forwardDependency --------------------------------------------------------


def test_forward_dependency_canonical_passes():
    results = check_forward_dependency_epc(CANONICAL_CLAIMS)
    assert results[0].status == "pass"


def test_forward_dependency_amends():
    """Claim 2 depends on claim 5 (forward reference)."""
    claims = [
        _make(1, "An apparatus comprising X."),
        _make(2, "The apparatus of claim 5.", independent=False, deps=[5]),
        _make(5, "The apparatus of claim 1.", independent=False, deps=[1]),
    ]
    results = check_forward_dependency_epc(claims)
    assert results[0].status == "amend"


# --- singleSentencePerClaim ---------------------------------------------------


def test_single_sentence_canonical_passes():
    results = check_single_sentence_per_claim_epc(CANONICAL_CLAIMS)
    assert results[0].status == "pass"


def test_single_sentence_multi_amends():
    """Claim with two sentences should fire."""
    claim = _make(1, "An apparatus comprising X. The apparatus also has Y.")
    results = check_single_sentence_per_claim_epc([claim])
    assert results[0].status == "verify"


def test_single_sentence_eg_abbreviation_tolerated():
    """'e.g.' is an abbreviation, not a sentence boundary."""
    claim = _make(1, "An apparatus, e.g., a smartphone, comprising X.")
    results = check_single_sentence_per_claim_epc([claim])
    assert results[0].status == "pass"


# --- refSignsInParens ---------------------------------------------------------


def test_ref_signs_canonical_passes():
    """All numerals in canonical fixture are parenthesised."""
    results = check_reference_signs_in_parens_epc(CANONICAL_CLAIMS)
    assert results[0].status == "pass"


def test_ref_signs_bare_numeral_verifies():
    """Bare numeral in claim body (not in parentheses, not a claim ref) fires."""
    claim = _make(1, "An apparatus comprising a processor 12 and a memory 14.")
    results = check_reference_signs_in_parens_epc([claim])
    assert results[0].status == "verify"


def test_ref_signs_year_excluded():
    """4-digit years 1900-2099 are not flagged."""
    claim = _make(1, "An apparatus comprising a processor (12) and updated in 2025.")
    results = check_reference_signs_in_parens_epc([claim])
    assert results[0].status == "pass"


def test_ref_signs_claim_n_reference_excluded():
    """The 'claim 1' reference in a dependent claim is not a ref sign."""
    claim = _make(2, "The apparatus of claim 1, wherein the processor (12) is a microcontroller.",
                  independent=False, deps=[1])
    results = check_reference_signs_in_parens_epc([claim])
    assert results[0].status == "pass"


# --- subjectConsistency -------------------------------------------------------


def test_subject_consistency_canonical_passes():
    results = check_subject_consistency_epc(CANONICAL_CLAIMS)
    assert results[0].status == "pass"


def test_subject_consistency_mismatch_verifies():
    """Dep 'A method' pointing to parent 'An apparatus' should fire."""
    claims = [
        _make(1, "An apparatus comprising a processor (12)."),
        _make(2, "The method of claim 1, wherein the method comprises filtering.",
              independent=False, deps=[1]),
    ]
    results = check_subject_consistency_epc(claims)
    assert results[0].status == "verify"


# --- transitionPhrase ---------------------------------------------------------


def test_transition_phrase_canonical_passes():
    results = check_transition_phrase_epc(CANONICAL_CLAIMS)
    assert results[0].status == "pass"


def test_transition_phrase_missing_verifies():
    """Independent claim without 'comprising' / 'consisting' / 'characterised'."""
    claim = _make(1, "An apparatus with a processor.")
    results = check_transition_phrase_epc([claim])
    assert results[0].status == "verify"


def test_transition_phrase_characterised_passes():
    """'characterised in that' is a valid EPC transitional phrase."""
    claim = _make(1, "An apparatus, characterised in that the processor is dual-core.")
    results = check_transition_phrase_epc([claim])
    assert results[0].status == "pass"


# --- Aggregator ---------------------------------------------------------------


def test_g4_runner_emits_all_eight_checks():
    results = run_g4_claims_structure_checks(CANONICAL_CLAIMS)
    assert len(results) == 8
    for r in results:
        assert r.status == "pass", f"Expected pass but got {r.status}: {r.message}"
