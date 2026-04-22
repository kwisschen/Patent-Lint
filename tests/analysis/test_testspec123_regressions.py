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


class TestFlaggedPhrasesSurfacing:
    """End-to-end: running the US pipeline on TestSpec123.docx must
    populate details_params.flagged_phrases.items on the spec + claims
    restrictive-wording emit sites so FlaggedTermList renders chips.
    Without chips, the user sees hardcoded placeholder examples in the
    template and has no way to know WHICH tokens were actually flagged."""

    def _run_us_pipeline(self):
        from patentlint.models import Jurisdiction
        from patentlint.pipeline import analyze_file
        if not TESTSPEC123_PATH.exists():
            pytest.skip(f"TestSpec123.docx not available at {TESTSPEC123_PATH}")
        return analyze_file(str(TESTSPEC123_PATH), jurisdiction=Jurisdiction.US)

    def test_spec_restrictive_wording_surfaces_flagged_phrases(self):
        result = self._run_us_pipeline()
        report = result.to_report_data()
        spec_checks = [
            c for c in report.specification_checks
            if c.message_key == "check.spec.restrictiveWording.verify"
        ]
        assert spec_checks, "Expected at least one spec restrictive-wording verify finding"
        check = spec_checks[0]
        assert check.details_params is not None
        phrases = check.details_params.get("flagged_phrases")
        assert phrases is not None, (
            "details_params.flagged_phrases missing on spec restrictiveWording — "
            "FlaggedTermList chips won't render."
        )
        items = phrases.get("items")
        assert items, "flagged_phrases.items empty"
        # Each item has token + location + kind; tokens are actual detected words
        for item in items:
            assert "token" in item and item["token"]
            assert "location" in item and isinstance(item["location"], int)

    def test_claims_restrictive_wording_surfaces_flagged_phrases(self):
        result = self._run_us_pipeline()
        report = result.to_report_data()
        claims_checks = [
            c for c in report.claims_checks
            if c.message_key == "check.claims.restrictiveWording.verify"
        ]
        assert claims_checks, "Expected at least one claims restrictive-wording verify finding"
        check = claims_checks[0]
        assert check.details_params is not None
        phrases = check.details_params.get("flagged_phrases")
        assert phrases is not None, (
            "details_params.flagged_phrases missing on claims restrictiveWording — "
            "FlaggedTermList chips won't render."
        )
        items = phrases.get("items")
        assert items, "flagged_phrases.items empty"
        for item in items:
            assert "token" in item and item["token"]
            assert "location" in item and isinstance(item["location"], int)

    def test_abstract_restrictive_wording_surfaces_flagged_phrases(self):
        result = self._run_us_pipeline()
        report = result.to_report_data()
        abstract_checks = [
            c for c in report.abstract_checks
            if c.message_key == "check.abstract.restrictiveWording.verify"
        ]
        assert abstract_checks, "Expected at least one abstract restrictive-wording finding"
        check = abstract_checks[0]
        assert check.details_params is not None
        phrases = check.details_params.get("flagged_phrases")
        assert phrases is not None, (
            "details_params.flagged_phrases missing on abstract restrictiveWording"
        )
        items = phrases.get("items")
        assert items, "flagged_phrases.items empty"

    def test_preamble_noun_mismatch_surfaces_claim_ids(self):
        """Each individual preamble_noun_mismatch CheckItem must carry the
        dependent claim ID in details_params so the frontend consolidation
        in AnalysisReport.jsx can list specific dep claims ('附屬項 5') rather
        than the previous generic '1 個附屬項' summary."""
        result = self._run_us_pipeline()
        report = result.to_report_data()
        mismatches = [
            c for c in report.claims_checks
            if c.message_key == "checks.preamble_noun_mismatch"
        ]
        if not mismatches:
            pytest.skip("This fixture doesn't trigger preamble_noun_mismatch")
        for c in mismatches:
            assert c.details_params is not None
            assert c.details_params.get("claim"), f"Missing claim id: {c.details_params}"
            assert c.details_params.get("parent"), f"Missing parent id: {c.details_params}"
            assert c.details_params.get("dependent"), "Missing dependent noun"
            assert c.details_params.get("independent"), "Missing independent noun"


class TestParseFormattedPhrases:
    """Unit tests for _parse_formatted_phrases — the shim that converts the
    legacy '[N] → \"word\"\\n' formatted string into structured chip items."""

    def _parser(self):
        from patentlint.models import _parse_formatted_phrases
        return _parse_formatted_phrases

    def test_single_match(self):
        f = self._parser()
        result = f('[4] → "must"\n              ')
        assert result == [{"location": 4, "token": "must", "kind": "phrase"}]

    def test_multiple_matches(self):
        f = self._parser()
        result = f('[4] → "must"\n              [4] → "always"\n              [47] → "invention"\n              ')
        assert result == [
            {"location": 4, "token": "must", "kind": "phrase"},
            {"location": 4, "token": "always", "kind": "phrase"},
            {"location": 47, "token": "invention", "kind": "phrase"},
        ]

    def test_dedupe_same_token_same_location(self):
        f = self._parser()
        result = f('[4] → "must"\n              [4] → "must"\n              ')
        assert result == [{"location": 4, "token": "must", "kind": "phrase"}]

    def test_dedupe_case_insensitive(self):
        f = self._parser()
        result = f('[4] → "Must"\n              [4] → "must"\n              ')
        # Preserves first-seen casing ("Must"), skips case-duplicate
        assert result == [{"location": 4, "token": "Must", "kind": "phrase"}]

    def test_empty_input(self):
        f = self._parser()
        assert f("") == []
        assert f(None or "") == []

    def test_kind_override(self):
        f = self._parser()
        result = f('[4] → "must"', kind="custom")
        assert result == [{"location": 4, "token": "must", "kind": "custom"}]
