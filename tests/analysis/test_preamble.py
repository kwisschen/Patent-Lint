# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""Tests for check_preamble_consistency — Phase 4 B1."""

from pathlib import Path

import pytest

from patentlint.models import Claim
from patentlint.analysis.claims import (
    _extract_head_noun,
    _find_all_immediate_parents,
    _find_immediate_parent,
    _find_root_independent,
    _preamble_head_info,
    check_preamble_consistency,
)


def _make_claims(*specs):
    """Helper: specs are (id, text, independent, method, deps)."""
    return [
        Claim(id=s[0], text=s[1], independent=s[2], method_claim=s[3], dependencies=s[4])
        for s in specs
    ]


class TestPreambleConsistency:
    def test_product_matching(self):
        """Standard product claim + matching dependent -> PASS."""
        claims = _make_claims(
            (1, "A device comprising: a widget; and a gadget.", True, False, []),
            (2, "The device of claim 1, wherein the widget is metal.", False, False, [1]),
        )
        results = check_preamble_consistency(claims)
        assert all(r.status == "pass" for r in results)

    def test_method_matching(self):
        """Standard method claim + matching dependent -> PASS."""
        claims = _make_claims(
            (1, "A method comprising: step A; and step B.", True, True, []),
            (2, "The method of claim 1, further comprising step C.", False, True, [1]),
        )
        results = check_preamble_consistency(claims)
        assert all(r.status == "pass" for r in results)

    def test_cross_category_method_on_product(self):
        """Method dependent on product independent -> AMEND."""
        claims = _make_claims(
            (1, "A device comprising: a widget.", True, False, []),
            (2, "The method of claim 1, further comprising step B.", False, True, [1]),
        )
        results = check_preamble_consistency(claims)
        amends = [r for r in results if r.status == "amend"]
        assert len(amends) >= 1
        assert "cross-category" in amends[0].message

    def test_cross_category_product_on_method(self):
        """Product dependent on method independent -> AMEND."""
        claims = _make_claims(
            (1, "A method comprising: step A.", True, True, []),
            (2, "The apparatus of claim 1, further comprising a widget.", False, False, [1]),
        )
        results = check_preamble_consistency(claims)
        amends = [r for r in results if r.status == "amend"]
        assert len(amends) >= 1

    def test_noun_mismatch_same_category(self):
        """'apparatus' independent, 'device' dependent -> VERIFY."""
        claims = _make_claims(
            (1, "An apparatus comprising: a widget.", True, False, []),
            (2, "The device of claim 1, wherein the widget is red.", False, False, [1]),
        )
        results = check_preamble_consistency(claims)
        verifies = [r for r in results if r.status == "verify"]
        assert len(verifies) >= 1
        assert "differs" in verifies[0].message

    def test_exact_noun_match(self):
        """'system' independent, 'system' dependent -> PASS."""
        claims = _make_claims(
            (1, "A system comprising: a processor; and a memory.", True, False, []),
            (2, "The system of claim 1, wherein the processor is fast.", False, False, [1]),
        )
        results = check_preamble_consistency(claims)
        assert all(r.status == "pass" for r in results)

    def test_indefinite_article_in_dependent(self):
        """'A device of claim 1' -> AMEND (should be 'The')."""
        claims = _make_claims(
            (1, "A device comprising: a base.", True, False, []),
            (2, "A device of claim 1, further comprising a cover.", False, False, [1]),
        )
        results = check_preamble_consistency(claims)
        amends = [r for r in results if r.status == "amend"]
        assert len(amends) >= 1
        assert "indefinite" in amends[0].message

    def test_crm_claim(self):
        """CRM independent + matching dependent -> PASS."""
        claims = _make_claims(
            (1, "A non-transitory computer-readable medium storing instructions comprising: code.", True, False, []),
            (2, "The non-transitory computer-readable medium of claim 1, further storing data.", False, False, [1]),
        )
        results = check_preamble_consistency(claims)
        # Should not flag cross-category
        amends = [r for r in results if r.status == "amend"]
        assert len(amends) == 0

    def test_dependent_on_dependent_chain(self):
        """Dependent-on-dependent chain with root mismatch -> AMEND."""
        claims = _make_claims(
            (1, "A device comprising: a widget.", True, False, []),
            (2, "The device of claim 1, further comprising a gadget.", False, False, [1]),
            (3, "The method of claim 2, further comprising step A.", False, True, [2]),
        )
        results = check_preamble_consistency(claims)
        amends = [r for r in results if r.status == "amend"]
        assert any("cross-category" in r.message for r in amends)

    def test_no_transitional_phrase(self):
        """No transition found -> skip, no false positive."""
        claims = _make_claims(
            (1, "A widget that processes data.", True, False, []),
            (2, "The widget of claim 1, further processing more data.", False, False, [1]),
        )
        results = check_preamble_consistency(claims)
        # Should pass (independent not parsed, so no comparison)
        assert all(r.status == "pass" for r in results)

    def test_according_to_variant(self):
        """'according to claim N' should be correctly parsed."""
        claims = _make_claims(
            (1, "A system comprising: a processor.", True, False, []),
            (2, "The system according to claim 1, wherein the processor is fast.", False, False, [1]),
        )
        results = check_preamble_consistency(claims)
        assert all(r.status == "pass" for r in results)

    def test_multiple_independent_different_entities(self):
        """Multiple independent claims with different entity types — normal and expected."""
        claims = _make_claims(
            (1, "A device comprising: a widget.", True, False, []),
            (2, "The device of claim 1, further comprising a gadget.", False, False, [1]),
            (3, "A method comprising: step A.", True, True, []),
            (4, "The method of claim 3, further comprising step B.", False, True, [3]),
        )
        results = check_preamble_consistency(claims)
        assert all(r.status == "pass" for r in results)


class TestFindRootIndependent:
    """Tests for _find_root_independent BFS multi-parent walking."""

    def test_single_parent_chain(self):
        """Standard linear chain: 3 → 2 → 1 (independent)."""
        claims = _make_claims(
            (1, "A device.", True, False, []),
            (2, "The device of claim 1.", False, False, [1]),
            (3, "The device of claim 2.", False, False, [2]),
        )
        root = _find_root_independent(claims[2], claims)
        assert root is not None
        assert root.id == 1

    def test_multi_parent_first_is_independent(self):
        """Claim depends on [1, 3]; claim 1 is independent → returns 1."""
        claims = _make_claims(
            (1, "A device.", True, False, []),
            (3, "A method.", True, True, []),
            (5, "The device of claims 1 and 3.", False, False, [1, 3]),
        )
        root = _find_root_independent(claims[2], claims)
        assert root is not None
        assert root.id == 1

    def test_multi_parent_second_leads_to_root(self):
        """Claim depends on [2, 3]; claim 2 is dependent with missing parent,
        claim 3 is independent → BFS finds 3."""
        claims = _make_claims(
            (2, "The widget of claim 99.", False, False, [99]),
            (3, "A method.", True, True, []),
            (5, "The device of claims 2 and 3.", False, False, [2, 3]),
        )
        root = _find_root_independent(claims[2], claims)
        assert root is not None
        assert root.id == 3

    def test_cycle_protection(self):
        """Circular dependency: 2 → 3 → 2.  Should not hang."""
        claims = _make_claims(
            (2, "The device of claim 3.", False, False, [3]),
            (3, "The device of claim 2.", False, False, [2]),
        )
        root = _find_root_independent(claims[0], claims)
        assert root is None

    def test_nonexistent_parent(self):
        """Parent ID doesn't exist in the claim list."""
        claims = _make_claims(
            (5, "The device of claim 99.", False, False, [99]),
        )
        root = _find_root_independent(claims[0], claims)
        assert root is None

    def test_independent_claim_returns_self(self):
        """An independent claim is its own root."""
        claims = _make_claims(
            (1, "A device.", True, False, []),
        )
        root = _find_root_independent(claims[0], claims)
        assert root is not None
        assert root.id == 1


class TestExtractHeadNoun:
    """Commit 9a: head noun extraction stops at the first qualifier."""

    def test_stops_at_for(self):
        """'A motor driver for adjusting power' → 'motor driver'."""
        assert _extract_head_noun("A motor driver for adjusting power") == "motor driver"

    def test_stops_at_with(self):
        """'A device with a sensor' → 'device'."""
        assert _extract_head_noun("A device with a sensor") == "device"

    def test_stops_at_having(self):
        """'A circuit having multiple inputs' → 'circuit'."""
        assert _extract_head_noun("A circuit having multiple inputs") == "circuit"

    def test_stops_at_comprising(self):
        """'A device comprising a base' → 'device'."""
        assert _extract_head_noun("A device comprising a base") == "device"

    def test_stops_at_including(self):
        """'A device including a frame' → 'device'."""
        assert _extract_head_noun("A device including a frame") == "device"

    def test_stops_at_based_on(self):
        """'A driver based on common voltage' → 'driver'."""
        assert _extract_head_noun("A driver based on common voltage") == "driver"

    def test_long_qualifier_chain(self):
        """The fixture-shaped case: 'motor driver for adjusting power based on
        common voltage' should still extract just 'motor driver'.
        """
        assert _extract_head_noun(
            "A motor driver for adjusting power based on common voltage"
        ) == "motor driver"

    def test_simple_unchanged(self):
        """Bare preamble with no qualifier still returns the whole noun phrase."""
        assert _extract_head_noun("A device") == "device"

    def test_relative_clause_head_extracted(self):
        """'An inkjet recording method that records an image...' → 'inkjet recording method'.

        ADR-092: _PREAMBLE_STOP was extended with `that|which` so relative-clause
        heads extract cleanly. Test6 claim 9 is the real-fixture trigger.
        """
        assert _extract_head_noun(
            "An inkjet recording method that records an image on a recording surface, comprising"
        ) == "inkjet recording method"


class TestImmediateParentComparison:
    """ADR-092: check_preamble_consistency compares dep head against the
    immediate parent's head noun, not the transitive root independent.
    """

    def test_cross_category_dep_with_new_entity_not_flagged(self):
        """'An ink set, comprising the pretreatment liquid of claim 1' →
        new entity under MPEP 608.01(n)(III), indefinite article is correct.
        """
        claims = _make_claims(
            (1, "A pretreatment liquid for an impermeable medium, comprising a polar compound.", True, False, []),
            (2, "An ink set, comprising the pretreatment liquid of claim 1, wherein the ink set includes a pigment.", False, False, [1]),
        )
        results = check_preamble_consistency(claims)
        assert not any(
            r.message_key == "checks.preamble_indefinite_article" for r in results
        )

    def test_same_entity_dep_with_wrong_article_still_flagged(self):
        """'A widget of claim 1' where parent is also a widget → still AMEND.

        The unflag rule must not silence genuine article errors.
        """
        claims = _make_claims(
            (1, "A widget comprising: a base.", True, False, []),
            (2, "A widget of claim 1, wherein the base is metal.", False, False, [1]),
        )
        results = check_preamble_consistency(claims)
        assert any(
            r.message_key == "checks.preamble_indefinite_article" for r in results
        )

    def test_multi_dep_cross_category_new_entity_not_flagged(self):
        """Multi-dep claim introducing a new entity under MPEP 608.01(n)(III).

        'A joint of claims 1 and 2' introduces a new entity ('joint') that
        incorporates both parents but matches neither parent's head noun.
        The indefinite article is mandatory, so the check must unflag.

        Exercises both (a) multi-dep parent enumeration via
        _find_all_immediate_parents and (b) the cross-category unflag path.
        """
        claims = _make_claims(
            (1, "A base comprising: a frame.", True, False, []),
            (2, "A platform comprising: a surface.", True, False, []),
            (3, "A joint of claims 1 and 2, wherein the joint connects the frame to the surface.", False, False, [1, 2]),
        )
        results = check_preamble_consistency(claims)
        assert not any(
            r.message_key == "checks.preamble_indefinite_article" and "Claim 3:" in r.message
            for r in results
        )

    def test_multi_dep_same_entity_still_flagged(self):
        """Multi-dep where dep head matches one parent ⟹ same-entity ⟹ FLAG.

        Guard against the inverse error: if any parent head matches, the
        user is referring to the same entity and "A/An" is wrong.
        """
        claims = _make_claims(
            (1, "A widget comprising: a base.", True, False, []),
            (2, "A gadget comprising: a cover.", True, False, []),
            (3, "A widget of claims 1 and 2, wherein the widget is metal.", False, False, [1, 2]),
        )
        results = check_preamble_consistency(claims)
        assert any(
            r.message_key == "checks.preamble_indefinite_article" and "Claim 3:" in r.message
            for r in results
        )

    def test_chain_through_new_entity(self):
        """claim 3 = 'The ink set of claim 2' must not flag against root claim 1."""
        claims = _make_claims(
            (1, "A liquid comprising: a polar compound.", True, False, []),
            (2, "An ink set comprising the liquid of claim 1, wherein the liquid is dispersed.", False, False, [1]),
            (3, "The ink set of claim 2, wherein the ink set includes a pigment.", False, False, [2]),
        )
        results = check_preamble_consistency(claims)
        assert not any(
            r.status != "pass" and "3" in r.message for r in results
        )

    def test_noun_mismatch_uses_immediate_parent(self):
        """Noun-mismatch branch must also compare against the immediate parent."""
        claims = _make_claims(
            (1, "A pretreatment liquid comprising: a polar compound.", True, False, []),
            (2, "An ink set comprising the liquid of claim 1, wherein the liquid is dispersed.", False, False, [1]),
            (3, "The ink set of claim 2, wherein the ink set is aqueous.", False, False, [2]),
        )
        results = check_preamble_consistency(claims)
        # Claim 3 must not be flagged as noun_mismatch against "pretreatment liquid"
        assert not any(
            r.message_key == "checks.preamble_noun_mismatch" and "3" in r.message
            for r in results
        )

    def test_dep_preamble_comma_stops_extraction(self):
        """Dep head extraction must stop at the first comma.

        For 'The ink set, comprising the pretreatment liquid according to
        claim 1, ...', the extracted head must be 'ink set', not the full
        greedy capture.
        """
        claim = Claim(
            id=2,
            text="The ink set, comprising the pretreatment liquid according to claim 1, wherein the ink set includes a pigment.",
            independent=False,
            dependencies=[1],
        )
        info = _preamble_head_info(claim)
        assert info is not None
        assert info[0] == "ink set"

    def test_find_immediate_parent_single_hop(self):
        """_find_immediate_parent walks exactly one hop, unlike _find_root_independent."""
        claims = _make_claims(
            (1, "A device comprising: a widget.", True, False, []),
            (2, "The device of claim 1, wherein the widget is red.", False, False, [1]),
            (3, "The device of claim 2, wherein the widget is metal.", False, False, [2]),
        )
        immediate = _find_immediate_parent(claims[2], claims)
        assert immediate is not None
        assert immediate.id == 2  # one hop, not transitive root
        root = _find_root_independent(claims[2], claims)
        assert root is not None and root.id == 1  # walker contract intact

    def test_find_all_immediate_parents_multi_dep(self):
        """Multi-dep claim returns all existing parents."""
        claims = _make_claims(
            (1, "A base.", True, False, []),
            (2, "A platform.", True, False, []),
            (3, "A platform of claims 1 and 2.", False, False, [1, 2]),
        )
        parents = _find_all_immediate_parents(claims[2], claims)
        assert [p.id for p in parents] == [1, 2]

    def test_synthetic_fixture_parses_clean(self):
        """The committed synthetic fixture exercises the full Test6 pattern
        (pretreatment liquid → ink set → ink set) and must produce zero
        AMEND/VERIFY findings from check_preamble_consistency.
        """
        from patentlint.parser import sections
        from patentlint.parser.claims import parse_claims
        from patentlint.parser.docx_loader import load_docx

        fixture = (
            Path(__file__).parent.parent
            / "fixtures"
            / "us"
            / "cross_category_dependent.docx"
        )
        assert fixture.exists(), f"committed synthetic fixture missing: {fixture}"
        loaded = load_docx(fixture)
        claims_text = sections.extract_claims_section(loaded.full_text)
        claims = parse_claims(claims_text)
        assert len(claims) == 3
        results = check_preamble_consistency(claims)
        non_pass = [r for r in results if r.status != "pass"]
        assert non_pass == [], f"unexpected findings: {[(r.status, r.message) for r in non_pass]}"

    def test_test6_cross_category_no_false_positives(self):
        """Real fixture: test6_chemistry_bare_noun_list.docx must produce zero
        §608.01(m) or noun_mismatch findings on its cross-category dependents.
        Skipped if the gitignored real fixture is absent.
        """
        from patentlint.parser import sections
        from patentlint.parser.claims import parse_claims
        from patentlint.parser.docx_loader import load_docx

        fixture = (
            Path(__file__).parent.parent
            / "fixtures"
            / "us"
            / "local"
            / "test6_chemistry_bare_noun_list.docx"
        )
        if not fixture.exists():
            pytest.skip(f"Real US patent fixture not present: {fixture}")

        loaded = load_docx(fixture)
        claims_text = sections.extract_claims_section(loaded.full_text)
        claims = parse_claims(claims_text) if claims_text else []
        if not claims:
            pytest.skip("Fixture loaded but no claims parsed")

        results = check_preamble_consistency(claims)
        false_positive_claims = {2, 3, 4, 6, 7, 8, 9}
        flagged_keys = {"checks.preamble_indefinite_article", "checks.preamble_noun_mismatch"}
        hits = [
            r for r in results
            if r.message_key in flagged_keys
            and any(f"Claim {cid}:" in r.message for cid in false_positive_claims)
        ]
        assert hits == [], (
            f"expected zero false positives on claims {sorted(false_positive_claims)}, "
            f"got: {[(r.status, r.message) for r in hits]}"
        )
