# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""Tests for check_spec_support — Phase 4 B3."""

from pathlib import Path

import pytest

from patentlint.models import Claim
from patentlint.analysis.claims import (
    attach_cross_references,
    check_antecedent_basis,
    check_spec_support,
)


def _make_claim(cid, text, indep=True, method=False, deps=None):
    return Claim(id=cid, text=text, independent=indep, method_claim=method, dependencies=deps or [])


class TestSpecSupport:
    def test_exact_match_supported(self):
        """Claim says 'base plate', spec contains 'base plate' -> supported."""
        claims = [_make_claim(1, "A device comprising: a base plate connected to a frame.")]
        spec = "The base plate is mounted on the frame for support."
        unsupported = check_spec_support(claims, spec)
        phrases = [u.phrase for u in unsupported]
        assert "base plate" not in phrases

    def test_stemmed_match_supported(self):
        """Claim says 'fastening mechanism', spec says 'fastened mechanism' -> supported."""
        claims = [_make_claim(1, "A device comprising: a fastening mechanism.")]
        spec = "The fastened mechanism holds the parts together."
        unsupported = check_spec_support(claims, spec)
        phrases = [u.phrase for u in unsupported]
        assert "fastening mechanism" not in phrases

    def test_word_window_match(self):
        """Claim says 'thermal unit', spec says 'a unit for thermal management' -> supported."""
        claims = [_make_claim(1, "A device comprising: a thermal unit.")]
        spec = "A unit for thermal management is provided in the device."
        unsupported = check_spec_support(claims, spec)
        phrases = [u.phrase for u in unsupported]
        assert "thermal unit" not in phrases

    def test_unsupported_term_flagged(self):
        """Claim says 'quantum entanglement module', spec never mentions it -> flagged."""
        claims = [_make_claim(1, "A device comprising: a quantum entanglement module.")]
        spec = "The device has a processor and a memory."
        unsupported = check_spec_support(claims, spec)
        phrases = [u.phrase for u in unsupported]
        assert any("quantum" in p for p in phrases)

    def test_generic_word_excluded(self):
        """Generic word 'device' -> excluded, not checked."""
        claims = [_make_claim(1, "A system comprising: a device.")]
        spec = "No mention of anything."
        unsupported = check_spec_support(claims, spec)
        phrases = [u.phrase for u in unsupported]
        assert "device" not in phrases

    def test_option_y_no_suppression_cross_ref_attached(self):
        """ADR-091: spec_support no longer suppresses antecedent-flagged terms.

        Both checks emit independently; ``attach_cross_references`` then
        annotates each side with a ``cross_ref`` pointing at its sibling so
        the frontend can render hint lines.
        """
        claims = [_make_claim(
            1,
            "A device comprising: a widget, wherein the quantum resonator is attached."
        )]
        spec = "The widget is described in detail and various parts are present."
        unsupported = check_spec_support(claims, spec)
        phrases = [u.phrase for u in unsupported]
        # Option Y: 'quantum resonator' IS flagged by spec support now (no suppression).
        assert "quantum resonator" in phrases
        # And after cross-ref attachment, the spec-support finding is
        # annotated with cross_ref="antecedent"
        ab = check_antecedent_basis(claims)
        attach_cross_references(ab, unsupported)
        target_term = next(u for u in unsupported if u.phrase == "quantum resonator")
        assert target_term.cross_ref == "antecedent"
        # And the antecedent finding is annotated with cross_ref="spec_support"
        target_ab = next(i for i in ab if i["term"] == "quantum resonator")
        assert target_ab["cross_ref"] == "spec_support"

    def test_dependent_claim_new_term(self):
        """Dependent claim introduces new term not in spec -> flagged."""
        claims = [
            _make_claim(1, "A device comprising: a base.", True),
            _make_claim(2, "The device of claim 1, further comprising a quantum resonator.", False, deps=[1]),
        ]
        spec = "The device has a base for support."
        unsupported = check_spec_support(claims, spec)
        phrases = [u.phrase for u in unsupported]
        assert any("quantum" in p for p in phrases)

    def test_plural_variant_stemmed(self):
        """Claim 'plates', spec 'plate' -> supported (stemmed)."""
        claims = [_make_claim(1, "A device comprising: plates mounted on a frame.")]
        spec = "The plate is mounted on the frame."
        unsupported = check_spec_support(claims, spec)
        phrases = [u.phrase for u in unsupported]
        assert "plates" not in phrases

    def test_term_in_summary_supported(self):
        """Term present in Summary text -> supported."""
        claims = [_make_claim(1, "A device comprising: a heat sink assembly.")]
        spec = "The heat sink assembly dissipates thermal energy from the processor."
        unsupported = check_spec_support(claims, spec)
        phrases = [u.phrase for u in unsupported]
        assert "heat sink assembly" not in phrases

    def test_boilerplate_excluded(self):
        """Boilerplate terms like 'plurality' excluded."""
        claims = [_make_claim(1, "A device comprising: a plurality of widgets.")]
        spec = "No mention."
        unsupported = check_spec_support(claims, spec)
        phrases = [u.phrase for u in unsupported]
        assert "plurality" not in phrases

    def test_empty_spec(self):
        """Empty spec text should not crash."""
        claims = [_make_claim(1, "A device comprising: a widget.")]
        unsupported = check_spec_support(claims, "")
        # Should flag everything since spec is empty
        assert isinstance(unsupported, list)

    def test_no_claims(self):
        """No claims should return empty."""
        unsupported = check_spec_support([], "Some spec text.")
        assert unsupported == []


class TestSpecSupportTier2SlidingWindow:
    """Tier 2 must enforce stem proximity within a sliding window.

    Before this fix, Tier 2 used ``set.issubset()`` over a bag of stems
    spanning the entire spec — any multi-word claim term whose individual
    stems each appeared somewhere passed silently, regardless of distance.
    """

    def test_scattered_stems_no_longer_match(self):
        """Stems for 'circulating line head' scattered across the spec must NOT match."""
        # 'circul' (from circulating), 'line', 'head' each appear unrelatedly
        # in different sentences. The bag-of-stems issubset would have passed
        # this; the sliding window must reject it.
        claims = [_make_claim(1, "A device comprising: a circulating line head.")]
        spec = (
            "The water is circulating through the cooling jacket. "
            "Connect the power line to the inlet valve. "
            "The pressure head must remain below threshold during operation. "
            "Monitor the gauge for safety."
        )
        unsupported = check_spec_support(claims, spec)
        phrases = [u.phrase for u in unsupported]
        assert any("circulating line head" in p for p in phrases)

    def test_far_apart_stems_no_match(self):
        """Two stems separated by more than WINDOW_SIZE words must not match."""
        claims = [_make_claim(1, "A device comprising: a thermal coupling.")]
        # 'thermal' at the start, 'coupling' (or 'couple') 30+ words later.
        spec = (
            "The thermal management subsystem regulates heat in the assembly. "
            + " ".join(["filler"] * 40)
            + " A coupling between the inlet and outlet provides flow control."
        )
        unsupported = check_spec_support(claims, spec)
        phrases = [u.phrase for u in unsupported]
        assert any("thermal coupling" in p for p in phrases)

    def test_adjacent_stems_match(self):
        """Stems within a contiguous window must still match."""
        claims = [_make_claim(1, "A device comprising: a fastening mechanism.")]
        spec = "The fastened mechanism holds the parts together securely."
        unsupported = check_spec_support(claims, spec)
        phrases = [u.phrase for u in unsupported]
        assert "fastening mechanism" not in phrases

    def test_stems_within_window_match(self):
        """Stems separated by a few words but within the window must match."""
        claims = [_make_claim(1, "A device comprising: a heat exchanger.")]
        # 'heat' and 'exchang' (from exchanger) within WINDOW_SIZE words.
        spec = "The heat is dissipated by the exchanger over time."
        unsupported = check_spec_support(claims, spec)
        phrases = [u.phrase for u in unsupported]
        assert "heat exchanger" not in phrases

    def test_test6_chemistry_circulating_line_head_flagged(self):
        """Real fixture: deliberately stripped 'circulating line head' must be flagged."""
        from patentlint.parser import sections
        from patentlint.parser.claims import parse_claims
        from patentlint.parser.docx_loader import load_docx

        fixture = Path(__file__).parent.parent / "fixtures" / "us" / "local" / "test6_chemistry_bare_noun_list.docx"
        if not fixture.exists():
            pytest.skip(f"Real US patent fixture not present: {fixture}")

        loaded = load_docx(fixture)
        full_text = loaded.full_text

        # Mirror pipeline.py: spec_text is summary + detailed description.
        summary = sections.extract_summary_section(full_text) or ""
        detailed = sections.extract_detailed_description_section(full_text) or ""
        spec_text = summary + "\n" + detailed

        claims_section = sections.extract_claims_section(full_text)
        claims = parse_claims(claims_section) if claims_section else []
        if not claims:
            pytest.skip("Fixture loaded but no claims parsed")

        unsupported = check_spec_support(claims, spec_text)
        phrases_lower = [u.phrase.lower() for u in unsupported]
        # The deliberately stripped phrase must surface as unsupported.
        assert any("circulating line head" in p for p in phrases_lower), (
            f"Expected 'circulating line head' to be flagged after Tier 2 fix; "
            f"got phrases: {phrases_lower[:30]}"
        )
