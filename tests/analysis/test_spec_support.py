# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""Tests for check_spec_support — Phase 4 B3."""

from patentlint.models import Claim
from patentlint.analysis.claims import check_spec_support


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

    def test_already_flagged_by_antecedent_not_double_flagged(self):
        """Phrase already flagged by antecedent basis -> not double-flagged."""
        claims = [_make_claim(1, "A device comprising: a widget, wherein the connector is attached.")]
        spec = "No mention of connectors."
        ab = [{"claim_id": 1, "term": "connector"}]
        unsupported = check_spec_support(claims, spec, antecedent_flagged=ab)
        phrases = [u.phrase for u in unsupported]
        assert "connector" not in phrases

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
