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

    def test_至少三個_intro_resolves(self):
        """F4: generalized 至少N個 pattern — 至少三個軸承."""
        doc = _make_doc([
            _claim(1, "1. 一種裝置，包含至少三個軸承，所述軸承為密封式。"),
        ])
        assert check_antecedent_basis(doc) == []

    def test_至少四個_intro_resolves(self):
        """F4: generalized 至少N個 pattern — 至少四個軸承."""
        doc = _make_doc([
            _claim(1, "1. 一種裝置，包含至少四個軸承，所述軸承為密封式。"),
        ])
        assert check_antecedent_basis(doc) == []

    def test_兩_bare_intro_resolves(self):
        """F4: 兩X (bare two without counter) introduces noun."""
        doc = _make_doc([
            _claim(1, "1. 一種裝置，包含兩曲柄，其連接於所述曲柄。"),
        ])
        assert check_antecedent_basis(doc) == []

    def test_兩個_intro_resolves(self):
        """F4: 兩個X (two with counter) introduces noun."""
        doc = _make_doc([
            _claim(1, "1. 一種裝置，包含兩個電極，分別設置於所述電極上。"),
        ])
        assert check_antecedent_basis(doc) == []

    def test_bare_N個_intro_resolves(self):
        """F4b: 四個X (bare CJK numeral+個) introduces noun."""
        doc = _make_doc([
            _claim(1, "1. 一種結構，包含四個第一連接面，四個所述第一連接面與頂面連接。"),
        ])
        # 四個第一連接面 → intro; 四個所述第一連接面 → F3 Rule 1a discards
        assert check_antecedent_basis(doc) == []

    def test_bare_N個_三個_intro(self):
        """F4b: 三個X introduces noun; 三個所述X is reference (discarded)."""
        doc = _make_doc([
            _claim(1, "1. 一種裝置，包含三個軸承，三個所述軸承分別安裝。"),
        ])
        assert check_antecedent_basis(doc) == []

    def test_bare_N個_至少_takes_priority(self):
        """Regression: 至少三個軸承 still resolved by 至少 branch."""
        doc = _make_doc([
            _claim(1, "1. 一種裝置，包含至少三個軸承，該軸承為滾珠軸承。"),
        ])
        assert check_antecedent_basis(doc) == []

    def test_至少一_no_counter_regression(self):
        """F4 regression: 至少一焊墊 (no counter) must still introduce."""
        doc = _make_doc([
            _claim(1, "1. 一種裝置，包含至少一焊墊，該焊墊為金屬。"),
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


# ─────────────────────────────────────────────────────────────────────────
# Trailing verb 介 (F2)
# ─────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────
# F3: Post-processing — 一 splitting, ref-marker truncation, paren variant
# ─────────────────────────────────────────────────────────────────────────


class TestPostProcessYiSplitting:
    """Embedded 一 in greedy captures is split into separate intro sites."""

    def test_yi_splitting_染色墨水(self):
        """電子組件通過浸泡一染色墨水 → split at 一 → 染色墨水 introduced."""
        c = _claim(1, "1. 一種方法，包括將一電子組件通過浸泡一染色墨水的步驟。")
        pairs = extract_introductions_tw(c)
        normalized = {n for _, n in pairs}
        assert "染色墨水" in normalized
        assert "電子組件" in normalized

    def test_yi_splitting_second_fragment(self):
        """Longer synthetic: two nouns separated by verb + 一."""
        c = _claim(1, "1. 一種裝置，包含一感測模組偵測一目標物體。")
        pairs = extract_introductions_tw(c)
        normalized = {n for _, n in pairs}
        assert "目標物體" in normalized


class TestPostProcessRefMarkerDiscard:
    """Reference-marker discard + re-scan recovers 一 intro sites."""

    def test_ref_marker_discard_rescan(self):
        """一個所述感測器為一旋轉編碼器 → discard 所述感測器, recover 旋轉編碼器."""
        c = _claim(10, "10. 如請求項9所述之裝置，其中一個所述感測器為一旋轉編碼器。")
        pairs = extract_introductions_tw(c)
        normalized = {n for _, n in pairs}
        assert "旋轉編碼器" in normalized
        # 所述感測器 should NOT appear as an intro
        assert "感測器" not in normalized or "所述感測器" not in normalized


class TestPostProcessRefMarkerTruncation:
    """Reference-marker truncation at embedded 所述."""

    def test_ref_marker_truncation(self):
        """一影像擷取裝置擷取所述基板 → truncate at 所述 → 影像擷取裝置擷取.
        After commit 3 adds 擷取 to denylist, this will normalize to
        影像擷取裝置. For now, check 所述基板 is NOT in intros."""
        c = _claim(3, "3. 方法，利用一影像擷取裝置擷取所述基板的影像。")
        pairs = extract_introductions_tw(c)
        normalized = {n for _, n in pairs}
        # The 所述基板 portion must not be captured as an intro
        assert "基板" not in normalized
        # Some form of 影像擷取裝置 should be present
        assert any("影像擷取裝置" in n for n in normalized)


class TestPostProcessParenVariant:
    """Paren-numeral asymmetry resolution (F3 Rule 4)."""

    def test_paren_numeral_intro_registered(self):
        """容置杯體(420) is registered as an intro with the paren numeral."""
        c = _claim(6, "6. 裝置，所述蓋體配件為一容置杯體(420)設置有多數孔隙。")
        pairs = extract_introductions_tw(c)
        normalized = {n for _, n in pairs}
        assert "容置杯體(420)" in normalized

    def test_paren_numeral_resolves_reference_without_numeral(self):
        """所述容置杯體 (no numeral) resolves against intro 容置杯體(420)."""
        doc = _make_doc([
            _claim(6, "6. 一種裝置，包含一蓋體配件，該蓋體配件為一容置杯體(420)。"),
            _claim(7, "7. 如請求項6所述之裝置，其中所述容置杯體為金屬。",
                   independent=False, deps=[6]),
        ])
        findings = check_antecedent_basis(doc)
        assert findings == [], (
            f"Expected 0 findings but got {len(findings)}: "
            + ", ".join(f["term"] for f in findings)
        )

    def test_paren_numeral_mismatch_not_resolved(self):
        """第二長度(L2) reference must NOT resolve against intro 第二長度(L1).
        Protects the L1/L2 typo detection (protect:true gate)."""
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


class TestPostProcessWordInternalYi:
    """Word-internal 一 (after 第/另/任/某/唯/同/單/統) is NOT split."""

    def test_另一端部_not_split(self):
        """另一端部 — 一 after 另 is word-internal, no split."""
        c = _claim(1, "1. 一種裝置，包含另一端部及一連接件。")
        pairs = extract_introductions_tw(c)
        normalized = {n for _, n in pairs}
        assert "連接件" in normalized
        assert "端部" in normalized


# ─────────────────────────────────────────────────────────────────────────
# F3: Trailing verbs — 至, 依序, 擷取
# ─────────────────────────────────────────────────────────────────────────


class TestTrailingVerb至:
    """Tests for 至 in _TRAILING_VERB_DENYLIST."""

    def test_至_stripped_from_intro(self):
        """一解鎖指令至 → introduces 解鎖指令 (至 stripped)."""
        pairs = extract_introductions_tw(
            _claim(8, "8. 裝置，該模組輸出一解鎖指令至該通訊模組。"),
        )
        nouns = [n for _, n in pairs]
        assert "解鎖指令" in nouns, f"Expected 解鎖指令 in {nouns}"


class TestTrailingVerb依序:
    """Tests for 依序 in _TRAILING_VERB_DENYLIST."""

    def test_依序_stripped_from_intro(self):
        """一第二方向依序 → introduces 第二方向 (依序 stripped)."""
        pairs = extract_introductions_tw(
            _claim(10, "10. 方法，依據一第二方向依序，將元件排列。"),
        )
        nouns = [n for _, n in pairs]
        assert "第二方向" in nouns, f"Expected 第二方向 in {nouns}"


class TestTrailingVerb擷取:
    """Tests for 擷取 in _TRAILING_VERB_DENYLIST."""

    def test_擷取_stripped_from_long_noun(self):
        """影像擷取裝置擷取 → 影像擷取裝置 (residual 6 ≥ 3, strip)."""
        pairs = extract_introductions_tw(
            _claim(3, "3. 方法，利用一影像擷取裝置擷取所述基板的影像。"),
        )
        nouns = [n for _, n in pairs]
        assert "影像擷取裝置" in nouns, f"Expected 影像擷取裝置 in {nouns}"

    def test_影像擷取_preserved(self):
        """影像擷取 (4 chars) — residual 2 < 3, guard protects."""
        pairs = extract_introductions_tw(
            _claim(1, "1. 一種系統，包含一影像擷取。"),
        )
        nouns = [n for _, n in pairs]
        assert "影像擷取" in nouns, f"Expected 影像擷取 in {nouns}"


class TestTrailingVerb介:
    """Tests for 介 in _TRAILING_VERB_DENYLIST."""

    def test_介_stripped_from_intro(self):
        """一第一夾角介於 → introduces 第一夾角 (介 stripped)."""
        pairs = extract_introductions_tw(
            _claim(1, "1. 一種裝置，其與一水平線的一第一夾角介於0.1至5度之間。"),
        )
        nouns = [n for _, n in pairs]
        assert "第一夾角" in nouns, f"Expected 第一夾角 in {nouns}"

    def test_中介_not_stripped(self):
        """中介裝置 — residual guard protects: 中 is 1 char < 3."""
        pairs = extract_introductions_tw(
            _claim(1, "1. 一種系統，包含一中介裝置。"),
        )
        nouns = [n for _, n in pairs]
        assert "中介裝置" in nouns, f"Expected 中介裝置 in {nouns}"

    def test_antecedent_resolved_via_介_strip(self):
        """Claim 1 一第一夾角介於...; claim 2 所述第一夾角 — 0 findings."""
        doc = _make_doc([
            _claim(
                1,
                "1. 一種裝置，其與一水平線的一第一夾角介於0.1至5度之間。",
            ),
            _claim(
                2,
                "2. 如請求項1所述之裝置，其中所述第一夾角為2度。",
                independent=False,
                deps=[1],
            ),
        ])
        findings = check_antecedent_basis(doc)
        assert findings == [], (
            f"Expected 0 findings but got {len(findings)}: "
            + ", ".join(f["term"] for f in findings)
        )


# ── F9: 透過Y連接 instrumental pattern ──────────────────────────────────


class TestSupplementaryIntrosF9:
    """F9: 透過Y連接 instrumental pattern."""

    def test_instrumental_basic(self):
        """透過樞軸(2221)連接 → introduces 樞軸."""
        text = "所述連接臂(222)相對於所述柱塞構件(221)的一端透過樞軸(2221)連接於所述樞接部(216)"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "樞軸" in norms

    def test_instrumental_no_numeral(self):
        """透過螺栓連結 → introduces 螺栓."""
        text = "所述蓋體透過螺栓連結於所述本體"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "螺栓" in norms

    def test_instrumental_no_duplicate(self):
        """If 一螺栓 already captured by _INTRO_PATTERN, supplementary doesn't duplicate."""
        text = "設置一螺栓，透過螺栓連接於所述本體"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert norms.count("螺栓") == 1

    def test_instrumental_with_lian_jie(self):
        """透過Y連結 (variant verb) also works."""
        text = "透過卡扣(30)連結於所述框架"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "卡扣" in norms
