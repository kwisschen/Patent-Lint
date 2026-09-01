# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
"""US R48 - antecedent basis must PRECEDE the reference.

Report kwisschen/patentlint-reports#677 (a reporter-flagged FALSE NEGATIVE).
"""
from __future__ import annotations


def _us(claims: list[str]) -> list[dict]:
    from patentlint.analysis.claims import check_antecedent_basis
    from patentlint.parser.claims import parse_claims
    return check_antecedent_basis(parse_claims("\n".join(claims)))


def _terms(findings: list[dict]) -> list[str]:
    return [f["term"] for f in findings]


# --- the reported false negative -----------------------------------------

def test_later_same_claim_intro_does_not_satisfy_earlier_reference() -> None:
    """#677: claim 9's own later `a volume` was resolving its earlier `the volume`."""
    findings = _us([
        "1. An earphone device, comprising: a body having a first chamber; and a "
        "tuning channel connected to the first chamber.",
        "8. The earphone device according to claim 1, wherein the tuning channel "
        "has a volume ranging from 5 cm3 and 9 cm3.",
        "9. The earphone device according to claim 1, wherein a ratio of the volume "
        "of the tuning channel to a volume of the first chamber ranges from 1:2 to 1:3.",
    ])
    assert "volume" in _terms(findings)


def test_sibling_claim_was_never_the_cause() -> None:
    """The FN reproduces with claim 8 deleted - the sibling never contributed."""
    findings = _us([
        "1. An earphone device, comprising: a body having a first chamber; and a "
        "tuning channel connected to the first chamber.",
        "9. The earphone device according to claim 1, wherein a ratio of the volume "
        "of the tuning channel to a volume of the first chamber ranges from 1:2 to 1:3.",
    ])
    assert "volume" in _terms(findings)


# --- controls: the veto must not fire ------------------------------------

def test_intro_preceding_reference_in_same_claim_is_still_basis() -> None:
    findings = _us([
        "1. A device, comprising: a body.",
        "2. The device according to claim 1, further comprising a heat sink, "
        "wherein the heat sink is coupled to the body.",
    ])
    assert "heat sink" not in _terms(findings)


def test_ancestor_basis_is_positionally_unconditional() -> None:
    """An ancestor's intro covers the whole child claim regardless of position."""
    findings = _us([
        "1. A device comprising: a housing; and a lid.",
        "2. The device of claim 1, wherein the housing is metal and a housing cover "
        "is attached.",
    ])
    assert "housing" not in _terms(findings)


def test_plural_intro_singular_reference_across_claims() -> None:
    findings = _us([
        "1. A device comprising a plurality of electrodes.",
        "2. The device of claim 1, wherein the electrode is copper.",
    ])
    assert "electrode" not in _terms(findings)


# --- the two designs the corpus REJECTED, pinned so they cannot return ----

def test_phrase_must_not_match_as_a_prefix_of_a_different_element() -> None:
    """A hand-written determiner regex read `an electrolyte salt` as introducing
    `electrolyte`. It also missed the `andan` PDF whitespace collapse. Both are
    why coverage is read from real match offsets, not re-derived by regex."""
    findings = _us([
        "1. A battery comprising:a positive electrode;a negative electrode; andan "
        "electrolyte,wherein:the electrolyte comprises a water-containing solvent, "
        "an electrolyte salt and a compound.",
    ])
    assert "electrolyte" not in _terms(findings)


def test_list_context_is_not_destroyed_by_truncation() -> None:
    """Re-running the extractor over the truncated prefix broke `comprising:`
    list context and added 1,577 findings, 228 on known walker FPs."""
    findings = _us([
        "1. A system comprising: a memory to store data; anda processor coupled to "
        "the memory, wherein the processor is to execute instructions.",
    ])
    assert "processor" not in _terms(findings)


def test_dependent_claim_preamble_is_never_vetoed() -> None:
    """`The antibody ... of claim 1` is a back-reference by construction.

    US12060411B2 c4 fails the preamble head-noun match, so without the guard the
    veto manufactured a finding on an ordinary dependent preamble.
    """
    findings = _us([
        "1. An anti-target antibody or antigen-binding fragment thereof.",
        "4. The antibody or antigen-binding fragment thereof of claim 1, wherein "
        "the anti-target antibody or antigen-binding fragment thereof comprises a "
        "heavy chain.",
    ])
    assert "antibody" not in _terms(findings)


def test_pattern_a_offsets_agree_with_the_extractor_they_mirror() -> None:
    """The offset twin must never drift from extract_pattern_a_intros."""
    from patentlint.analysis.utils import (
        extract_pattern_a_intros,
        pattern_a_intro_offsets,
    )
    text = (
        "The earphone device according to claim 1, wherein a ratio of the volume "
        "of the tuning channel to a volume of the first chamber ranges."
    )
    assert sorted(pattern_a_intro_offsets(text)) == sorted(
        set(extract_pattern_a_intros(text))
    )
