# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""Tests for check_preamble_consistency — Phase 4 B1."""

from patentlint.models import Claim
from patentlint.analysis.claims import check_preamble_consistency, _find_root_independent


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
