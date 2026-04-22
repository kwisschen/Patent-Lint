# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Regression tests grounded in TestSpec123.docx (user-supplied US fixture).

The fixture lives in the user's iCloud Test Cases folder and is not
committed. Tests skip gracefully when the file is absent so CI on other
machines stays green. The test cases encode specific bug reports from
the user's TIPO-attorney dog-fooder — keep these tests as targeted
regression gates when the fixture is available."""

from pathlib import Path

import pytest

from patentlint.analysis.claims import check_antecedent_basis, check_spec_support
from patentlint.parser import sections
from patentlint.parser.claims import parse_claims
from patentlint.parser.docx_loader import load_docx


TESTSPEC123_PATH = Path(
    "/Users/chrischen/Library/Mobile Documents/com~apple~CloudDocs/"
    "Documents/Test Cases/us/TestSpec123.docx"
)


def _load_testspec123():
    if not TESTSPEC123_PATH.exists():
        pytest.skip(f"TestSpec123.docx not available at {TESTSPEC123_PATH}")
    loaded = load_docx(TESTSPEC123_PATH)
    full_text = loaded.full_text
    summary = sections.extract_summary_section(full_text) or ""
    detailed = sections.extract_detailed_description_section(full_text) or ""
    spec_text = summary + "\n" + detailed
    claims_section = sections.extract_claims_section(full_text)
    claims = parse_claims(claims_section) if claims_section else []
    if not claims:
        pytest.skip("TestSpec123 loaded but no claims parsed")
    return claims, spec_text


class TestRelationalAdjectiveBleedFix:
    """The phrase 'the lower cover surface opposite to the upper cover surface'
    was being captured as 'lower cover surface opposite' in both
    extract_noun_phrases (spec-support) and the antecedent-basis walker
    (did-you-mean suggestions). After the trailing-relational-adjective
    strip lands, 'opposite' never leaks into any captured term."""

    def test_spec_support_no_opposite_bleed(self):
        """Spec-support must not surface 'lower cover surface opposite' for any claim."""
        claims, spec_text = _load_testspec123()
        unsupported = check_spec_support(claims, spec_text)
        bad_phrases = [
            u.phrase.lower() for u in unsupported
            if u.phrase.lower().endswith(" opposite")
        ]
        assert not bad_phrases, (
            f"Expected zero spec-support findings ending in 'opposite'; got {bad_phrases}. "
            f"Root cause: clean_noun_phrase not stripping trailing relational adjectives."
        )

    def test_antecedent_dym_no_opposite_bleed(self):
        """Antecedent-basis DYM suggestions must not point at 'X opposite'
        as the did-you-mean target — the trailing adjective should be
        stripped before the suggestion is formed."""
        claims, _ = _load_testspec123()
        findings = check_antecedent_basis(claims)
        bleeding_suggestions = []
        for f in findings:
            suggested = f.get("suggested_match")
            if suggested and suggested.get("term", "").endswith(" opposite"):
                bleeding_suggestions.append(suggested["term"])
        assert not bleeding_suggestions, (
            f"Expected zero DYM suggestions ending in 'opposite'; got {bleeding_suggestions}."
        )

    def test_antecedent_finding_term_no_opposite_bleed(self):
        """The reference term captured by the walker (what the user sees
        as the missing-antecedent phrase) must never end in 'opposite'."""
        claims, _ = _load_testspec123()
        findings = check_antecedent_basis(claims)
        bleeding_terms = [
            f["term"] for f in findings
            if f.get("term", "").endswith(" opposite")
        ]
        assert not bleeding_terms, (
            f"Expected zero antecedent findings with term ending in 'opposite'; "
            f"got {bleeding_terms}."
        )
