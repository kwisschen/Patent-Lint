# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
"""US R60 - distributive ordinals and an ordinal before an inline acronym.

Report kwisschen/patentlint-reports#968. Both shapes introduce one element per
ordinal; the walker registered only the last one (or a name cut at the paren).
"""
from __future__ import annotations


def _us(claims: list[str]) -> list[dict]:
    from patentlint.analysis.claims import check_antecedent_basis
    from patentlint.parser.claims import parse_claims
    return check_antecedent_basis(parse_claims("\n".join(claims)))


def _terms(findings: list[dict]) -> list[str]:
    return [f["term"] for f in findings]


# --- distributive ordinals ---------------------------------------------------

def test_first_and_a_second_introduces_both() -> None:
    findings = _us([
        "1. A meter comprising a first and a second probe, wherein the first probe "
        "is spaced from the second probe.",
    ])
    assert "first probe" not in _terms(findings)


def test_bare_plural_first_and_second_introduces_both() -> None:
    findings = _us([
        "1. A meter comprising first and second probes, wherein the first probe "
        "is spaced from the second probe.",
    ])
    terms = _terms(findings)
    assert "first probe" not in terms
    assert "second probe" not in terms


def test_last_ordinal_is_registered_outside_a_list() -> None:
    """No article precedes the last ordinal, and no list arm reaches it here."""
    findings = _us([
        "1. A method comprising: determining, by a first server, a score; "
        "obtaining, by the first server, a record from second and third servers; and "
        "storing the record, wherein the third server is remote.",
    ])
    assert "third server" not in _terms(findings)


def test_three_way_list_introduces_every_ordinal() -> None:
    findings = _us([
        "1. A meter comprising a first, second, and third probe, wherein the first "
        "probe and the second probe flank the third probe.",
    ])
    terms = _terms(findings)
    assert "first probe" not in terms
    assert "second probe" not in terms


def test_ordinal_outside_the_run_still_flags() -> None:
    findings = _us([
        "1. A meter comprising a first and a second probe, wherein the third probe "
        "is grounded.",
    ])
    assert "third probe" in _terms(findings)


def test_definite_run_is_a_reference_not_an_introduction() -> None:
    findings = _us([
        "1. A meter comprising a housing, wherein the first and second probes "
        "extend from the housing, and the first probe is grounded.",
    ])
    assert "first probe" in _terms(findings)


def test_or_does_not_introduce() -> None:
    findings = _us([
        "1. A meter comprising a housing configured to hold first or second probes, "
        "wherein the first probe is grounded.",
    ])
    assert "first probe" in _terms(findings)


def test_distributive_intro_after_the_reference_does_not_count() -> None:
    """The R48 ordering rule applies to the new intros too."""
    findings = _us([
        "1. A meter comprising a housing, wherein the first probe is grounded and "
        "the housing holds a first and a second probe.",
    ])
    assert "first probe" in _terms(findings)


# --- ordinal before an inline acronym ------------------------------------------

def test_ordinal_carries_over_to_the_acronym_form() -> None:
    findings = _us([
        "1. A receiver comprising a first low-noise amplifier (LNA) stage and a "
        "second LNA stage, wherein an input of the first LNA stage is coupled to a "
        "filter.",
    ])
    assert "first lna stage" not in _terms(findings)


def test_ordinal_inside_the_expansion_is_not_carried() -> None:
    """In `a first in first out (FIFO) buffer` the ordinal is part of the name."""
    findings = _us([
        "1. A controller comprising a first in first out (FIFO) buffer, wherein the "
        "first FIFO buffer is cleared.",
    ])
    assert "first fifo buffer" in _terms(findings)


def test_acronym_form_without_ordinal_still_resolves() -> None:
    findings = _us([
        "1. A receiver comprising a first low-noise amplifier (LNA) stage, wherein "
        "the LNA stage is biased.",
    ])
    assert "lna stage" not in _terms(findings)
