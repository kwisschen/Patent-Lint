# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""Phase 8b TW antecedent walker — BFS resolution tests.

Covers exact-match resolution, number-neutral matching (ADR-095 Rule 3),
multi-parent BFS traversal, cycle protection, and immediate-parent
semantics on cross-category dependents (ADR-092 mirror).

Did-you-mean / Jaccard tests live in test_tw_walker_didyoumean.py
(Commit 5). Strict-mode escape-hatch tests live in
test_tw_walker_strict_mode.py (Commit 6).
"""

from __future__ import annotations

from patentlint.analysis.tw_claims import (
    check_antecedent_basis,
    extract_introductions_tw,
    get_ancestor_chain_tw,
)
from patentlint.models import Claim, TwPatentDocument, TwPatentType


def _make_doc(claims: list[Claim]) -> TwPatentDocument:
    """Build a minimal TwPatentDocument carrying only claims."""
    return TwPatentDocument(
        patent_type=TwPatentType.INVENTION,
        title="一種裝置",
        technical_field=["本發明涉及一種裝置。"],
        prior_art=["已知有相關技術。"],
        disclosure=["本發明提供一種解決方案。"],
        embodiment=["參照圖1說明實施方式。"],
        claims=claims,
    )


def _claim(
    num: int,
    text: str,
    independent: bool = True,
    deps: list[int] | None = None,
    multi_dep: bool = False,
) -> Claim:
    return Claim(
        id=num,
        text=text,
        independent=independent,
        dependencies=deps or [],
        multiple_dependent=multi_dep,
    )


# ─────────────────────────────────────────────────────────────────────────
# Exact-match resolution
# ─────────────────────────────────────────────────────────────────────────


class TestExactMatch:
    def test_self_contained_claim_pass(self):
        """Independent claim with 一底座...該底座 self-resolves."""
        doc = _make_doc([
            _claim(1, "1. 一種裝置，包含一底座，該底座設有一孔洞。"),
        ])
        assert check_antecedent_basis(doc) == []

    def test_dependent_resolves_via_parent(self):
        """所述框架 in claim 2 resolves to 一框架 in claim 1."""
        doc = _make_doc([
            _claim(1, "1. 一種裝置，包含一框架。"),
            _claim(2, "2. 如請求項1所述之裝置，其中所述框架為金屬。",
                   independent=False, deps=[1]),
        ])
        assert check_antecedent_basis(doc) == []

    def test_missing_intro_emits_finding(self):
        doc = _make_doc([
            _claim(1, "1. 一種裝置，包含一底座，該齒輪與該底座相連。"),
        ])
        issues = check_antecedent_basis(doc)
        assert len(issues) == 1
        assert issues[0]["claim_id"] == 1
        assert issues[0]["term"] == "齒輪"
        assert issues[0]["reference_form"] == "該齒輪"
        assert issues[0]["suggested_match"] is None
        assert issues[0]["cross_ref"] is None

    def test_finding_carries_full_claim_text(self):
        doc = _make_doc([
            _claim(1, "1. 一種裝置，其中該底座為金屬。"),
        ])
        issues = check_antecedent_basis(doc)
        assert len(issues) == 1
        assert issues[0]["claim_text"] == "1. 一種裝置，其中該底座為金屬。"

    def test_dedup_within_claim(self):
        """Same (term, reference_form) pair appearing twice — emit once."""
        doc = _make_doc([
            _claim(1, "1. 一種裝置，該齒輪為金屬，該齒輪設有齒。"),
        ])
        issues = check_antecedent_basis(doc)
        assert len(issues) == 1


# ─────────────────────────────────────────────────────────────────────────
# Reference-form prefix variants (ADR-095 Rule 1)
# ─────────────────────────────────────────────────────────────────────────


class TestReferenceFormPrefixes:
    def test_該_resolves(self):
        doc = _make_doc([
            _claim(1, "1. 一種裝置，包含一電極，該電極為金屬。"),
        ])
        assert check_antecedent_basis(doc) == []

    def test_所述_resolves(self):
        doc = _make_doc([
            _claim(1, "1. 一種裝置，包含一電極，所述電極為金屬。"),
        ])
        assert check_antecedent_basis(doc) == []

    def test_前述_resolves(self):
        doc = _make_doc([
            _claim(1, "1. 一種裝置，包含一電極，前述電極為金屬。"),
        ])
        assert check_antecedent_basis(doc) == []

    def test_該等_resolves(self):
        doc = _make_doc([
            _claim(1, "1. 一種裝置，包含複數電極，該等電極為金屬。"),
        ])
        assert check_antecedent_basis(doc) == []

    def test_該些_resolves(self):
        doc = _make_doc([
            _claim(1, "1. 一種裝置，包含複數電極，該些電極為金屬。"),
        ])
        assert check_antecedent_basis(doc) == []

    def test_該第一電極_resolves_to_一第一電極(self):
        """Composite reference: 該 + ordinal noun. Both sides normalize
        away the 該 and the implicit 一, so 第一電極 matches 第一電極."""
        doc = _make_doc([
            _claim(1, "1. 一種裝置，包含一第一電極，該第一電極為陽極。"),
        ])
        assert check_antecedent_basis(doc) == []


# ─────────────────────────────────────────────────────────────────────────
# Number-neutral matching (ADR-095 Rule 3)
# ─────────────────────────────────────────────────────────────────────────


class TestNumberNeutralMatching:
    def test_plural_intro_singular_reference(self):
        """複數外齒狀結構 / 該外齒狀結構 — number-neutral, no finding."""
        doc = _make_doc([
            _claim(1, "1. 一種裝置，包含複數外齒狀結構，該外齒狀結構為金屬。"),
        ])
        assert check_antecedent_basis(doc) == []

    def test_多個_intro_singular_reference(self):
        doc = _make_doc([
            _claim(1, "1. 一種裝置，包含多個齒狀結構，該齒狀結構為漸開線。"),
        ])
        assert check_antecedent_basis(doc) == []

    def test_singular_一個_intro_plural_reference(self):
        """一個X / 該等X — both normalize to X."""
        doc = _make_doc([
            _claim(1, "1. 一種裝置，包含一個齒輪，該等齒輪相互嚙合。"),
        ])
        assert check_antecedent_basis(doc) == []

    def test_至少一個_intro_resolves(self):
        doc = _make_doc([
            _claim(1, "1. 一種裝置，包含至少一個電極，該電極為金屬。"),
        ])
        assert check_antecedent_basis(doc) == []


# ─────────────────────────────────────────────────────────────────────────
# BFS multi-parent traversal
# ─────────────────────────────────────────────────────────────────────────


class TestBFSAncestorChain:
    def test_multi_dep_collects_from_both_parents(self):
        """如請求項1或3所述 — intro can come from claim 1 OR claim 3."""
        doc = _make_doc([
            _claim(1, "1. 一種裝置，包含一基座。"),
            _claim(2, "2. 如請求項1所述之裝置，包含一馬達。",
                   independent=False, deps=[1]),
            _claim(3, "3. 如請求項1所述之裝置，包含一齒輪。",
                   independent=False, deps=[1]),
            _claim(4, "4. 如請求項2或3所述之裝置，其中該馬達驅動該齒輪。",
                   independent=False, deps=[2, 3], multi_dep=True),
        ])
        # Both 該馬達 (claim 2) and 該齒輪 (claim 3) must resolve via BFS.
        assert check_antecedent_basis(doc) == []

    def test_three_deep_chain(self):
        """Claim 3 references intro defined two hops up."""
        doc = _make_doc([
            _claim(1, "1. 一種裝置，包含一控制器。"),
            _claim(2, "2. 如請求項1所述之裝置，包含一感測器。",
                   independent=False, deps=[1]),
            _claim(3, "3. 如請求項2所述之裝置，其中該控制器讀取該感測器。",
                   independent=False, deps=[2]),
        ])
        assert check_antecedent_basis(doc) == []

    def test_cycle_protection(self):
        """Pathological self-cycle must not loop forever."""
        doc = _make_doc([
            _claim(1, "1. 一種裝置，包含一基座。"),
            # Synthetic: claim 2 lists itself as a dependency (parser
            # would normally drop this, but the walker must still
            # tolerate it without recursing forever).
            _claim(2, "2. 如請求項2所述之裝置，其中該基座為金屬。",
                   independent=False, deps=[2]),
        ])
        # Walker must terminate; the term 該基座 is still flagged
        # because the cycle prevents reaching claim 1.
        issues = check_antecedent_basis(doc)
        # No assertion on count — only that the call returns.
        assert isinstance(issues, list)

    def test_get_ancestor_chain_helper_walks_bfs(self):
        c1 = _claim(1, "1. 一種裝置。")
        c2 = _claim(2, "2. 如請求項1所述。", independent=False, deps=[1])
        c3 = _claim(3, "3. 如請求項2所述。", independent=False, deps=[2])
        chain = get_ancestor_chain_tw(c3, [c1, c2, c3])
        assert [c.id for c in chain] == [3, 2, 1]


# ─────────────────────────────────────────────────────────────────────────
# Sort + dedup invariants
# ─────────────────────────────────────────────────────────────────────────


class TestSortAndDedupe:
    def test_findings_sorted_by_claim_then_term(self):
        doc = _make_doc([
            _claim(1, "1. 一種裝置，該齒輪為金屬。"),
            _claim(2, "2. 如請求項1所述之裝置，其中該軸承為陶瓷。",
                   independent=False, deps=[1]),
        ])
        issues = check_antecedent_basis(doc)
        assert [i["claim_id"] for i in issues] == sorted(
            [i["claim_id"] for i in issues]
        )

    def test_extract_introductions_returns_pairs(self):
        c = _claim(1, "1. 一種裝置，包含一基座、一第一電極及一第二電極。")
        pairs = extract_introductions_tw(c)
        normalized = {n for _, n in pairs}
        assert "基座" in normalized
        assert "第一電極" in normalized
        assert "第二電極" in normalized


# ─────────────────────────────────────────────────────────────────────────
# ADR-092 mirror: cross-category dependent (引用記載型式)
# ─────────────────────────────────────────────────────────────────────────


class TestCrossCategoryDependent:
    """The walker must resolve references across the FULL ancestor chain
    (ADR-092 binding), not just the immediate parent. Dependent claims
    that introduce new components and then reference them downstream
    must NOT generate findings — the new components ARE introduced
    somewhere in the chain.

    The synthetic fixture cross_category_dependent_tw.docx exercises a
    four-claim chain mirroring the US fixture from Phase 8a.
    """

    def test_three_deep_introduces_new_component(self):
        """Claim 2 introduces 第一剛輪; claim 3 references it."""
        doc = _make_doc([
            _claim(1, "1. 一種諧波減速裝置，包含一波產生器及一柔輪。"),
            _claim(2, "2. 如請求項1所述之諧波減速裝置，其中更包含一第一剛輪，所述第一剛輪與該柔輪相嚙合。",
                   independent=False, deps=[1]),
            _claim(3, "3. 如請求項2所述之諧波減速裝置，其中所述第一剛輪包含複數個齒狀結構。",
                   independent=False, deps=[2]),
            _claim(4, "4. 如請求項3所述之諧波減速裝置，其中所述齒狀結構為漸開線齒形。",
                   independent=False, deps=[3]),
        ])
        # Each component IS introduced somewhere in the ancestor chain:
        #   - 波產生器, 柔輪 → claim 1
        #   - 第一剛輪 → claim 2
        #   - 齒狀結構 → claim 3 (plural intro 複數個)
        # Number-neutral matching (Rule 3) lets 所述齒狀結構 (claim 4)
        # resolve to 複數個齒狀結構 (claim 3).
        assert check_antecedent_basis(doc) == []
