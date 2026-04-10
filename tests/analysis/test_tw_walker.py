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
    _INTRO_PATTERN,
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


# ─────────────────────────────────────────────────────────────────────────
# Regex invariants — pattern-level isolation tests
# ─────────────────────────────────────────────────────────────────────────


class TestRegexInvariants:
    def test_bare_yi_does_not_match_after_ordinal(self):
        """ADR-095 Commit 4 fix: ``_INTRO_PATTERN``'s bare 一 alternative
        must not match after 第 (would cause 第一剛輪 to parse as
        quantifier 一 + noun 剛輪, breaking the cross-category dependent
        fixture).

        This test isolates the regex behavior at the pattern level so a
        failure is diagnostic ('you broke the 第一 negative lookbehind')
        rather than mysterious ('cross-category dependent fixture
        started failing').
        """
        # Should NOT match 一 as an intro inside 第一剛輪
        matches = list(_INTRO_PATTERN.finditer("第一剛輪"))
        bare_yi_matches = [
            m for m in matches
            if m.group(0).startswith("一")
            and not m.group(0).startswith("一種")
            and not m.group(0).startswith("一個")
            and not m.group(0).startswith("一對")
        ]
        assert len(bare_yi_matches) == 0, (
            f"Bare 一 matched after 第 in '第一剛輪': {bare_yi_matches}. "
            f"The (?<!第) negative lookbehind on bare 一 is broken."
        )

        # Should still match bare 一 when NOT preceded by 第
        matches = list(_INTRO_PATTERN.finditer("一剛輪"))
        assert len(matches) >= 1, (
            "Bare 一 should still match when not preceded by 第"
        )


# ─────────────────────────────────────────────────────────────────────────
# 110P000633 determinism canary scar-tissue test
# ─────────────────────────────────────────────────────────────────────────


class Test110P000633DeterminismCanary:
    """Scar-tissue test: the 110P000633 fixture exists as two files
    (..._FV.DOCX and ..._FV_1.DOCX) that have different .docx
    container metadata but character-identical claim text. The walker
    MUST produce byte-identical findings when run against both files —
    any divergence is a walker non-determinism bug, not a fixture
    difference.

    This test is SKIPPED in CI because the fixtures are gitignored
    (real patents). It runs locally whenever the fixtures are present.
    See docs/phase8b-baseline.md for the observation that originated
    this invariant.
    """

    def test_determinism_canary(self):
        import pytest
        from pathlib import Path

        fixture_a = Path(
            "tests/fixtures/tw/local/110P000633US.JP派譯版-FV.DOCX"
        )
        fixture_b = Path(
            "tests/fixtures/tw/local/110P000633US.JP派譯版-FV_1.DOCX"
        )

        if not fixture_a.exists() or not fixture_b.exists():
            pytest.skip("110P000633 fixture pair not present (local-only)")

        from patentlint.parser.docx_loader import load_docx_tw
        from patentlint.parser.sections_tw import extract_tw_sections

        doc_a = extract_tw_sections(load_docx_tw(str(fixture_a)).paragraphs)
        doc_b = extract_tw_sections(load_docx_tw(str(fixture_b)).paragraphs)

        findings_a = check_antecedent_basis(doc_a)
        findings_b = check_antecedent_basis(doc_b)

        # Assertion 1: same count
        assert len(findings_a) == len(findings_b), (
            f"Determinism canary failed: {len(findings_a)} findings in A, "
            f"{len(findings_b)} in B. Walker is non-deterministic on "
            f"character-identical claim text."
        )

        # Assertion 2: sorted tuples byte-identical. Findings are dicts
        # (not dataclasses) so use dict-key access. ``suggested_match``
        # is itself a dict|None — convert to a tuple for hashable
        # ordering.
        def _key(f: dict) -> tuple:
            sm = f["suggested_match"]
            sm_tuple = (
                (sm["term"], sm["claim_id"]) if sm is not None else None
            )
            return (
                f["claim_id"],
                f["term"],
                f["reference_form"],
                sm_tuple,
            )

        sorted_a = sorted(_key(f) for f in findings_a)
        sorted_b = sorted(_key(f) for f in findings_b)
        assert sorted_a == sorted_b, (
            "Determinism canary failed: sorted findings differ between "
            "A and B. This is a walker non-determinism bug."
        )


# ─────────────────────────────────────────────────────────────────────────
# F1: Weight-composition intro pattern
# ─────────────────────────────────────────────────────────────────────────


class TestWeightCompositionIntro:
    """N重量份(至M重量份)的X should introduce noun X."""

    def test_range_form_introduces_noun(self):
        """20重量份至70重量份的聚苯醚樹脂 → introduces 聚苯醚樹脂."""
        c = _claim(1, "1. 一種組成物，包括20重量份至70重量份的聚苯醚樹脂。")
        pairs = extract_introductions_tw(c)
        normalized = {n for _, n in pairs}
        assert "聚苯醚樹脂" in normalized

    def test_single_value_introduces_noun(self):
        """5重量份的聚丁二烯樹脂 → introduces 聚丁二烯樹脂."""
        c = _claim(1, "1. 一種組成物，包括5重量份的聚丁二烯樹脂。")
        pairs = extract_introductions_tw(c)
        normalized = {n for _, n in pairs}
        assert "聚丁二烯樹脂" in normalized

    def test_measurement_no_intro(self):
        """100重量百分比 without 的+noun does NOT introduce anything."""
        c = _claim(2, "2. 如請求項1所述之組成物，其中以所述聚丁二烯樹脂的總含量為100重量百分比。")
        pairs = extract_introductions_tw(c)
        # The only possible intro here is from the quantifier pattern,
        # not from weight-composition.  重量百分比 ends the clause.
        normalized = {n for _, n in pairs}
        assert "重量百分比" not in normalized

    def test_antecedent_resolved_via_weight_intro(self):
        """Claim 2 references 所述聚苯醚樹脂; claim 1 introduces it via
        weight-composition.  Should produce 0 findings."""
        doc = _make_doc([
            _claim(
                1,
                "1. 一種組成物，其包括：20重量份至70重量份的聚苯醚樹脂。",
            ),
            _claim(
                2,
                "2. 如請求項1所述的組成物，其中，所述聚苯醚樹脂的重均分子量為1000。",
                independent=False,
                deps=[1],
            ),
        ])
        findings = check_antecedent_basis(doc)
        assert findings == [], (
            f"Expected 0 findings but got {len(findings)}: "
            + ", ".join(f["term"] for f in findings)
        )

    def test_multiple_weight_intros_all_resolved(self):
        """Multiple weight-composition nouns in claim 1, all referenced
        in claim 2 — should produce 0 findings."""
        doc = _make_doc([
            _claim(
                1,
                "1. 一種組成物，其包括："
                "20重量份至70重量份的聚苯醚樹脂；"
                "5重量份至40重量份的聚丁二烯樹脂；以及"
                "5重量份至30重量份的雙馬來醯亞胺。",
            ),
            _claim(
                2,
                "2. 如請求項1所述的組成物，其中，"
                "所述聚苯醚樹脂的重均分子量為1000，"
                "所述聚丁二烯樹脂的含量小於25，"
                "所述雙馬來醯亞胺為改性雙馬來醯亞胺。",
                independent=False,
                deps=[1],
            ),
        ])
        findings = check_antecedent_basis(doc)
        assert findings == [], (
            f"Expected 0 findings but got {len(findings)}: "
            + ", ".join(f["term"] for f in findings)
        )


# ─────────────────────────────────────────────────────────────────────────
# Definitional intro pattern (F2)
# ─────────────────────────────────────────────────────────────────────────


class TestDefinitionalIntro:
    """Tests for 定義為/稱為/記為/表示為 intro prefix recognition."""

    def test_定義為_introduces_noun(self):
        """距離定義為第一長度(L1) → introduces 第一長度(L1)."""
        pairs = extract_introductions_tw(
            _claim(1, "1. 一種裝置，其距離定義為第一長度(L1)。"),
        )
        nouns = [n for _, n in pairs]
        assert "第一長度(L1)" in nouns or "第一長度" in nouns

    def test_定義為一_introduces_noun(self):
        """分別定義為一第一剛輪及一第二剛輪 → introduces 第一剛輪
        (一 consumed by 一?, 及 stops capture)."""
        pairs = extract_introductions_tw(
            _claim(1, "1. 一種裝置，其分別定義為一第一剛輪及一第二剛輪。"),
        )
        nouns = [n for _, n in pairs]
        assert "第一剛輪" in nouns

    def test_稱為_introduces_noun(self):
        """稱為 variant — forward-compat."""
        pairs = extract_introductions_tw(
            _claim(1, "1. 一種裝置，其元件稱為第一接頭。"),
        )
        nouns = [n for _, n in pairs]
        assert "第一接頭" in nouns

    def test_表示為_introduces_noun(self):
        """表示為 variant — forward-compat."""
        pairs = extract_introductions_tw(
            _claim(1, "1. 一種裝置，其長度表示為第一距離。"),
        )
        nouns = [n for _, n in pairs]
        assert "第一距離" in nouns

    def test_antecedent_resolved_via_definitional_intro(self):
        """Claim 1 defines 第一長度(L1) via 定義為; claim 2 references
        所述第一長度(L1) — 0 findings."""
        doc = _make_doc([
            _claim(
                1,
                "1. 一種裝置，其距離定義為第一長度(L1)，"
                "所述第一長度(L1)和底面之間。",
            ),
            _claim(
                2,
                "2. 如請求項1所述之裝置，其中所述第一長度(L1)大於10mm。",
                independent=False,
                deps=[1],
            ),
        ])
        findings = check_antecedent_basis(doc)
        assert findings == [], (
            f"Expected 0 findings but got {len(findings)}: "
            + ", ".join(f["term"] for f in findings)
        )

    def test_protect_true_typo_persists(self):
        """Protect:true gate — 定義為第二長度(L1) intro does NOT resolve
        所述第二長度(L2) reference because (L1) ≠ (L2)."""
        doc = _make_doc([
            _claim(
                1,
                "1. 一種裝置，其距離定義為第一長度(L1)，"
                "其距離定義為第二長度(L1)，"
                "所述第一長度(L1)和所述第二長度(L2)之間。",
            ),
        ])
        findings = check_antecedent_basis(doc)
        terms = [f["term"] for f in findings]
        assert any("第二長度" in t for t in terms), (
            "Expected finding for 第二長度(L2) but got: " + str(terms)
        )
