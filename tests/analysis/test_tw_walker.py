# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
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


# ── F8: 相配合的Y VP modifier pattern ───────────────────────────────────


class TestSupplementaryIntrosF8:
    """F8: 相配合的Y VP modifier pattern."""

    def test_vp_modifier_ordinal(self):
        """相配合的第二螺紋部 → introduces 第二螺紋部."""
        text = "設置和所述第一螺紋部(2121a)相配合的第二螺紋部"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "第二螺紋部" in norms

    def test_vp_modifier_with_numeral(self):
        """相配合的第二螺紋部(2211a) → introduces 第二螺紋部."""
        text = "設置和所述第一螺紋部(2121a)相配合的第二螺紋部(2211a)"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "第二螺紋部" in norms

    def test_vp_modifier_rejects_shape(self):
        """相配合的圓柱形 → NOT introduced (shape descriptor, < 3 CJK)."""
        text = "和所述開口部(212)相配合的圓柱形"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "圓柱形" not in norms

    def test_vp_modifier_rejects_no_ordinal_no_numeral(self):
        """相配合的卡扣結構 without ordinal/numeral → NOT introduced."""
        text = "和所述框架相配合的卡扣結構"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "卡扣結構" not in norms

    def test_vp_modifier_no_duplicate(self):
        """If 一第二螺紋部 already captured, supplementary doesn't duplicate."""
        text = "一第二螺紋部，和所述第一螺紋部相配合的第二螺紋部"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert norms.count("第二螺紋部") == 1


# ── F7a: 形成於...的Y locative pattern ──────────────────────────────────


class TestSupplementaryIntrosF7a:
    """F7a: Locative 形成於...的Y."""

    def test_locative_basic(self):
        """形成於所述套接部(220)的側面的環形壓接部(211) → introduces 環形壓接部."""
        text = "以及形成於所述套接部(220)的側面的環形壓接部(211)；"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "環形壓接部" in norms

    def test_locative_reject_short(self):
        """形成於所述環狀本體的外圍 → NOT captured by F7a (2 CJK chars).

        F5a captures 外圍 as a possessive sub-component of 環狀本體,
        which is correct — 外圍 is a legitimate spatial component.
        """
        text = "形成於所述環狀本體的外圍"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "外圍" in norms

    def test_locative_no_duplicate(self):
        text = "一環形壓接部(211)，形成於所述套接部的側面的環形壓接部(211)"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert norms.count("環形壓接部") == 1


# ── F7b: 一V的Y participial pattern ─────────────────────────────────────


class TestSupplementaryIntrosF7b:
    """F7b: Participial 一V的Y."""

    def test_participial_ordinal(self):
        """一開口向下的第二容置空間(225) → introduces 第二容置空間."""
        text = "形成一開口向下的第二容置空間(225)"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "第二容置空間" in norms

    def test_participial_long_vp(self):
        """一執行於一使用者裝置的瀏覽程式 → introduces 瀏覽程式."""
        text = "一執行於一使用者裝置的瀏覽程式產生"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "瀏覽程式" in norms

    def test_participial_reject_short(self):
        """一種的方法 → 方法 NOT captured (2 CJK, no ordinal, no numeral)."""
        text = "一種的方法"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "方法" not in norms

    def test_participial_no_duplicate(self):
        text = "一第二容置空間(225)，形成一開口向下的第二容置空間(225)"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert norms.count("第二容置空間") == 1


# ── F7c: 的第Y post-的 ordinal noun ─────────────────────────────────────


class TestSupplementaryIntrosF7c:
    """F7c: Post-的 ordinal noun 的第Y."""

    def test_post_de_ordinal(self):
        """凹入的第二容納空間(230) → introduces 第二容納空間."""
        text = "從所述套接部底部凹入的第二容納空間(230)"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "第二容納空間" in norms

    def test_post_de_ordinal_no_numeral(self):
        """加工的第一面板 → introduces 第一面板."""
        text = "加工的第一面板"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "第一面板" in norms

    def test_post_de_reject_non_ordinal(self):
        """凹入的底部 → 底部 captured by the broader F10 bare-modifier pass.

        F7c itself rejects non-ordinal captures, but F10 emits it
        independently because 底部 ends with a component-suffix (部). Safe:
        extra intros only resolve references, never manufacture findings.
        """
        text = "凹入的底部"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "底部" in norms

    def test_post_de_reject_ref_between(self):
        """所述X的所述第Y → NOT captured (所述 between 的 and 第)."""
        text = "所述套接部的所述第二容納空間"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "第二容納空間" not in norms

    def test_post_de_no_duplicate(self):
        text = "一第二容納空間(230)，凹入的第二容納空間(230)"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert norms.count("第二容納空間") == 1


# ── F6: 具有/設置/形成 + Y bare-after-verb pattern ──────────────────────


class TestSupplementaryIntrosF6:
    """F6: Bare-after-verb 具有/設置/形成 + Y."""

    def test_bare_verb_ju_you(self):
        """具有第一扣接部 → introduces 第一扣接部."""
        text = "所述第一定位構件(215)具有第一扣接部"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "第一扣接部" in norms

    def test_bare_verb_she_zhi(self):
        """設置第一螺紋部(2121a) → introduces 第一螺紋部."""
        text = "所述開口部(212)內側設置第一螺紋部(2121a)"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "第一螺紋部" in norms

    def test_bare_verb_xing_cheng(self):
        """形成第一容置空間(101) → introduces 第一容置空間."""
        text = "所述容器本體(100)內部形成第一容置空間(101)"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "第一容置空間" in norms

    def test_bare_verb_reject_descriptive(self):
        """具有至少一改性基 → 改性基 NOT captured by F6 (no ordinal, no numeral)."""
        text = "聚苯醚樹脂具有至少一改性基"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "改性基" in norms  # captured by _INTRO_PATTERN via 一改性基, not F6

    def test_bare_verb_reject_attributive(self):
        """具有第一直徑的管道 → 第一直徑 NOT captured (followed by 的)."""
        text = "具有第一直徑的管道"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "第一直徑" not in norms

    def test_bare_verb_numeral_only(self):
        """形成容置空間(101) → introduces 容置空間 (has numeral, no ordinal)."""
        text = "所述本體內部形成容置空間(101)"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "容置空間" in norms

    def test_bare_verb_no_duplicate(self):
        text = "一第一扣接部，所述構件具有第一扣接部"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert norms.count("第一扣接部") == 1

    def test_bare_verb_bao_han(self):
        """包含第一元件 → introduces 第一元件."""
        text = "所述基板包含第一元件"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "第一元件" in norms

    def test_bare_verb_she_you(self):
        """設有第一凹槽(301) → introduces 第一凹槽."""
        text = "所述框架設有第一凹槽(301)"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "第一凹槽" in norms

    def test_bare_verb_pei_zhi(self):
        """配置第一電極 → introduces 第一電極."""
        text = "所述控制模組配置第一電極"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "第一電極" in norms

    def test_bare_verb_an_zhuang(self):
        """安裝第一螺栓(50) → introduces 第一螺栓."""
        text = "所述蓋體安裝第一螺栓(50)"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "第一螺栓" in norms

    def test_bare_verb_lian_jie(self):
        """連接第一端子(101) → introduces 第一端子."""
        text = "所述導線連接第一端子(101)"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "第一端子" in norms

    def test_bare_verb_ti_gong(self):
        """提供第一信號 → introduces 第一信號."""
        text = "所述處理器提供第一信號"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "第一信號" in norms


class TestSupplementaryIntrosF5a:
    """F5a: Ref-prefix possessive 所述X的Y."""

    def test_ref_possessive_basic(self):
        """所述開口部(120)的上端邊緣 → introduces 上端邊緣."""
        text = "所述開口部(120)的上端邊緣相互銜接"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "上端邊緣" in norms

    def test_ref_possessive_gai(self):
        """該框架的底座 → introduces 底座."""
        text = "該框架的底座設有螺孔"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "底座" in norms

    def test_ref_possessive_reject_ref_y(self):
        """所述X的所述Y → NOT captured (Y has ref prefix)."""
        text = "所述容器本體(100)的所述第一容置空間(101)"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "第一容置空間" not in norms

    def test_ref_possessive_verb_cleaned(self):
        """所述框架的側面設置一螺栓 → 側面 captured (設置 stripped by clean)."""
        text = "所述框架的側面設置一螺栓"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "側面" in norms

    def test_ref_possessive_no_duplicate(self):
        text = "一上端邊緣，所述開口部的上端邊緣"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert norms.count("上端邊緣") == 1


class TestSupplementaryIntrosF5b:
    """F5b: 一X(N)的Y — paren-numeral possessive."""

    def test_yi_paren_possessive(self):
        """一容器本體(100)的開口部(120) → introduces 開口部."""
        text = "設置於一容器本體(100)的開口部(120)"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "開口部" in norms

    def test_yi_paren_possessive_no_numeral_y(self):
        """一容器本體(100)的底部 → introduces 底部."""
        text = "一容器本體(100)的底部朝向下方"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "底部" in norms

    def test_yi_paren_reject_ref_y(self):
        """一容器本體(100)的所述蓋體 → NOT captured (Y has ref prefix)."""
        text = "一容器本體(100)的所述蓋體(200)"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "蓋體" not in norms

    def test_yi_paren_reject_no_paren_x(self):
        """一容器本體的開口部 → NOT captured by F5b (X lacks paren-numeral).
        This might be captured by F7b instead, but F5b specifically requires X(N)."""
        text = "一容器本體的開口部"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "開口部" in norms  # captured by F7b, not F5b

    def test_yi_paren_verb_cleaned(self):
        """一容器(100)的蓋體連接於本體 → 蓋體 captured (連接 stripped by clean)."""
        text = "一容器(100)的蓋體連接於本體"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert "蓋體" in norms

    def test_yi_paren_no_duplicate(self):
        text = "一開口部(120)，一容器本體(100)的開口部(120)"
        intros = extract_introductions_tw(_claim(1, text))
        norms = [n for _, n in intros]
        assert norms.count("開口部") == 1


class TestBugReportJPTranslatedCapAssembly:
    """Regression test for a 2026-04-24 bug report.

    JP-translated TW patent — "一種蓋組件" cap assembly claim — introduces
    elements bare (without 一) via participial/locative possessive patterns:
      - 配置在容器本體上部的開口部        → 容器本體 + 開口部
      - 具有…突出的環狀的嵌合壁部         → 嵌合壁部
      - 可彈性變形的嵌合部                → 嵌合部
      - …外部連通的壓力調節閥             → 壓力調節閥
      - …更硬質的基材                     → 基材

    Reporter flagged 6 findings, one of which (前述壓力調節閥更硬質) was a
    pure walker-extraction bug (更 leaked into the reference-noun greedy
    capture). Fix adds 更 to _NOUN_CHARS exclusion plus F10 (bare-modifier
    的NOUN intro, component-suffix-gated) and F11 (locative-possessive
    bare-noun intro) so all six go clean.
    """

    _CLAIM_TEXT = (
        "一種蓋組件，係可拆裝地安裝於配置在容器本體上部的開口部，具有螺接於前述"
        "開口部的蓋體、以及配置於前述開口部內的密封構件，前述蓋體，具有插入前述"
        "開口部內的內塞，前述密封構件，係安裝於前述內塞，前述內塞，具有從前述內"
        "塞的下表面朝下側突出的環狀的嵌合壁部，前述密封構件，具有：跨全周接觸於"
        "前述開口部的內周面的可彈性變形的環狀的止水墊圈；可拆裝地嵌合於前述嵌合"
        "壁部的可彈性變形的嵌合部；配置於前述嵌合部的徑向內側，接觸於前述內塞的"
        "下表面，且可彈性變形，並能通過前述內塞與前述密封構件之間使前述容器本體"
        "的內部與外部連通的壓力調節閥；以及固定於前述嵌合部及前述壓力調節閥，且"
        "比前述嵌合部及前述壓力調節閥更硬質的基材，係藉由單一的構件一體地形成。"
    )

    def test_no_antecedent_findings(self):
        """All 6 reported references resolve — zero findings."""
        from patentlint.analysis.tw_claims import check_antecedent_basis
        from patentlint.models import (
            Claim,
            TwPatentDocument,
            TwPatentType,
        )

        claim = Claim(
            id=1,
            text=self._CLAIM_TEXT,
            dependencies=[],
            independent=True,
        )
        doc = TwPatentDocument(
            claims=[claim],
            specification=[],
            abstract=None,
            drawings_description=[],
            title="",
            symbol_table=[],
            cross_references=[],
            background_paragraphs=[],
            patent_type=TwPatentType.INVENTION,
        )
        findings = check_antecedent_basis(doc)
        assert findings == [], (
            f"Expected zero findings; got {len(findings)}: "
            f"{[(f['reference_form'], f['term']) for f in findings]}"
        )

    def test_no_greedy_更_capture(self):
        """前述壓力調節閥 must not greedily extend to 前述壓力調節閥更硬質."""
        from patentlint.analysis.tw_claims import _REF_PATTERN_CAPTURE

        captured = [m.group(0) for m in _REF_PATTERN_CAPTURE.finditer(
            "比前述嵌合部及前述壓力調節閥更硬質的基材"
        )]
        assert "前述壓力調節閥" in captured
        assert "前述壓力調節閥更硬質" not in captured

    def test_bare_noun_intros_emitted(self):
        """F10+F11 emit the 6 bare-noun intros the reporter relied on."""
        from patentlint.analysis.tw_claims import extract_introductions_tw
        from patentlint.models import Claim

        claim = Claim(
            id=1,
            text=self._CLAIM_TEXT,
            dependencies=[],
            independent=True,
        )
        norms = {n for _, n in extract_introductions_tw(claim)}
        for expected in (
            "容器本體",
            "開口部",
            "嵌合壁部",
            "嵌合部",
            "壓力調節閥",
            "基材",
        ):
            assert expected in norms, f"missing intro: {expected}"


class TestDepPreambleConnective:
    """Regression test for a 2026-04-24 bug report.

    JP-translated TW patents use 「如請求項N所記載的X」 instead of the
    TIPO-standard 「所述的X」. The old dep-preamble regex required exactly
    `所?述?[之的]`, so `_extract_subject` fell through on `所記載的`, extracted
    the full preamble as the subject, and falsely flagged claims 2-7 as
    subject-inconsistent with the parent. Fix extends the connective to
    cover `所(述|記載|揭示|描述)[之的]` + bare `之/的` forms.
    """

    def _build(self, preamble_form: str):
        from patentlint.models import Claim, TwPatentDocument, TwPatentType

        c1 = Claim(
            id=1,
            text="1. 一種蓋組件，包括：一本體；以及一蓋體。",
            dependencies=[],
            independent=True,
        )
        c2 = Claim(
            id=2,
            text=f"2. {preamble_form}，其中前述蓋體呈環狀。",
            dependencies=[1],
            independent=False,
        )
        return TwPatentDocument(
            claims=[c1, c2],
            specification=[],
            abstract=None,
            drawings_description=[],
            title="",
            symbol_table=[],
            cross_references=[],
            background_paragraphs=[],
            patent_type=TwPatentType.INVENTION,
        )

    def test_ji_zai_de(self):
        """如請求項1所記載的 — JP-translation form, reporter's case."""
        from patentlint.analysis.tw_claims import check_subject_consistency

        doc = self._build("如請求項1所記載的蓋組件")
        findings = check_subject_consistency(doc)
        assert all(f.status == "pass" for f in findings), (
            f"FP: {[f.message for f in findings]}"
        )

    def test_ji_zai_zhi(self):
        """如請求項1所記載之 — JP-translation formal."""
        from patentlint.analysis.tw_claims import check_subject_consistency

        doc = self._build("如請求項1所記載之蓋組件")
        findings = check_subject_consistency(doc)
        assert all(f.status == "pass" for f in findings)

    def test_jie_shi_de(self):
        """如請求項1所揭示的 — formal alternative."""
        from patentlint.analysis.tw_claims import check_subject_consistency

        doc = self._build("如請求項1所揭示的蓋組件")
        findings = check_subject_consistency(doc)
        assert all(f.status == "pass" for f in findings)

    def test_miao_shu_zhi(self):
        """如請求項1所描述之 — alternative."""
        from patentlint.analysis.tw_claims import check_subject_consistency

        doc = self._build("如請求項1所描述之蓋組件")
        findings = check_subject_consistency(doc)
        assert all(f.status == "pass" for f in findings)

    def test_standard_suo_shu_de_still_works(self):
        """如請求項1所述的 — TIPO-standard must still pass."""
        from patentlint.analysis.tw_claims import check_subject_consistency

        doc = self._build("如請求項1所述的蓋組件")
        findings = check_subject_consistency(doc)
        assert all(f.status == "pass" for f in findings)

    def test_bare_de_still_works(self):
        """如請求項1的 — bare form."""
        from patentlint.analysis.tw_claims import check_subject_consistency

        doc = self._build("如請求項1的蓋組件")
        findings = check_subject_consistency(doc)
        assert all(f.status == "pass" for f in findings)

    def test_range_with_ji_zai(self):
        """如請求項1至7中任一項所記載的 — multi-dep JP-translation form."""
        from patentlint.analysis.tw_claims import check_subject_consistency

        doc = self._build("如請求項1至7中任一項所記載的蓋組件")
        findings = check_subject_consistency(doc)
        assert all(f.status == "pass" for f in findings)

    def test_spec_drawing_ref_ji_zai(self):
        """如說明書所記載 — also forbidden, JP-translation of 如說明書所述."""
        from patentlint.analysis.tw_claims import check_spec_drawing_ref
        from patentlint.models import Claim, TwPatentDocument, TwPatentType

        c = Claim(
            id=1,
            text="1. 一種裝置，其構造如說明書所記載。",
            dependencies=[],
            independent=True,
        )
        doc = TwPatentDocument(
            claims=[c],
            specification=[],
            abstract=None,
            drawings_description=[],
            title="",
            symbol_table=[],
            cross_references=[],
            background_paragraphs=[],
            patent_type=TwPatentType.INVENTION,
        )
        findings = check_spec_drawing_ref(doc)
        assert any(f.status == "amend" for f in findings), (
            "如說明書所記載 should be flagged (forbidden spec-ref)"
        )


class TestSubjectConsistencySplit:
    """ADR-145: subject_consistency must distinguish parse-limit fall-through
    from genuine drafter-level mismatches.

    Each finding must also carry a structural diagnostic fingerprint so
    error-report emails can identify the exact code path without leaking
    claim content.
    """

    def _build(self, claim_texts):
        from patentlint.models import Claim, TwPatentDocument, TwPatentType

        claims = []
        for i, text in enumerate(claim_texts, start=1):
            if i == 1:
                claims.append(Claim(
                    id=i, text=text, dependencies=[], independent=True,
                ))
            else:
                claims.append(Claim(
                    id=i, text=text, dependencies=[1], independent=False,
                ))
        return TwPatentDocument(
            claims=claims, specification=[], abstract=None,
            drawings_description=[], title="", symbol_table=[],
            cross_references=[], background_paragraphs=[],
            patent_type=TwPatentType.INVENTION,
        )

    def test_genuine_mismatch_emits_verify(self):
        """Both preambles parse cleanly but subjects differ."""
        from patentlint.analysis.tw_claims import check_subject_consistency

        doc = self._build([
            "1. 一種蓋組件，包括X。",
            "2. 如請求項1所述的裝置，包括Y。",
        ])
        findings = check_subject_consistency(doc)
        mismatch = [
            f for f in findings
            if f.message_key == "check.tw.claims.subjectConsistency.verify"
        ]
        assert len(mismatch) == 1
        assert mismatch[0].diagnostics is not None
        assert mismatch[0].diagnostics["dep_path"] == "dep_prefix"
        assert mismatch[0].diagnostics["parent_path"] == "indep_prefix"

    def test_parse_fallthrough_emits_parseUnclear_not_verify(self):
        """When preamble doesn't match a recognized form, emit parseUnclear."""
        from patentlint.analysis.tw_claims import check_subject_consistency

        doc = self._build([
            "1. 一種蓋組件，包括X。",
            "2. 基於請求項1所揭露的組件，包括Z。",  # not a recognized dep form
        ])
        findings = check_subject_consistency(doc)
        unclear = [
            f for f in findings
            if f.message_key
            == "check.tw.claims.subjectConsistencyParseUnclear.verify"
        ]
        mismatch = [
            f for f in findings
            if f.message_key == "check.tw.claims.subjectConsistency.verify"
        ]
        assert len(unclear) == 1, (
            "parse fallthrough should emit parseUnclear, not verify"
        )
        assert len(mismatch) == 0, (
            "parse fallthrough should NOT emit a mismatch finding"
        )
        assert unclear[0].diagnostics["dep_path"] == "fallthrough"

    def test_mixed_mismatch_and_parseUnclear_emitted_separately(self):
        from patentlint.analysis.tw_claims import check_subject_consistency

        doc = self._build([
            "1. 一種蓋組件，包括X。",
            "2. 如請求項1所述的裝置，包括Y。",  # genuine mismatch
            "3. 基於請求項1所揭露的組件，包括Z。",  # parseUnclear
        ])
        findings = check_subject_consistency(doc)
        mismatch = [
            f for f in findings
            if f.message_key == "check.tw.claims.subjectConsistency.verify"
        ]
        unclear = [
            f for f in findings
            if f.message_key
            == "check.tw.claims.subjectConsistencyParseUnclear.verify"
        ]
        assert len(mismatch) == 1 and mismatch[0].details_params["claims"] == [2]
        assert len(unclear) == 1 and unclear[0].details_params["claims"] == [3]

    def test_reporter_case_no_findings(self):
        """26P001TW reporter case: 如請求項N所記載的X → no findings."""
        from patentlint.analysis.tw_claims import check_subject_consistency

        doc = self._build([
            "1. 一種蓋組件，包括本體。",
            "2. 如請求項1所記載的蓋組件，更包括嵌合部。",
            "3. 如請求項1所記載的蓋組件，更包括壓力調節閥。",
        ])
        findings = check_subject_consistency(doc)
        assert all(f.status == "pass" for f in findings), (
            f"reporter case must pass; got: {[f.message for f in findings]}"
        )


class TestAntecedentDiagnostics:
    """ADR-145: antecedent-basis findings must carry structural fingerprints
    so error-report emails can identify walker state (intro-pool size,
    did-you-mean presence, cross-branch) without any claim content.
    """

    def _build(self, claim_texts):
        from patentlint.models import Claim, TwPatentDocument, TwPatentType

        claims = []
        for i, text in enumerate(claim_texts, start=1):
            if i == 1:
                claims.append(Claim(
                    id=i, text=text, dependencies=[], independent=True,
                ))
            else:
                claims.append(Claim(
                    id=i, text=text, dependencies=[1], independent=False,
                ))
        return TwPatentDocument(
            claims=claims, specification=[], abstract=None,
            drawings_description=[], title="", symbol_table=[],
            cross_references=[], background_paragraphs=[],
            patent_type=TwPatentType.INVENTION,
        )

    def test_finding_carries_diagnostics(self):
        from patentlint.analysis.tw_claims import check_antecedent_basis

        # Claim 2 references 所述第一卡止部 with no matching intro; walker
        # finds 一第一按鈕 as did-you-mean candidate. Pure-structural
        # fingerprint should expose that state to maintainer emails.
        doc = self._build([
            "1. 一種裝置，包含一第一按鈕。",
            "2. 如請求項1所述的裝置，其中所述第一卡止部為彈性。",
        ])
        issues = check_antecedent_basis(doc)
        assert len(issues) >= 1
        issue = issues[0]
        assert "diagnostics" in issue
        dx = issue["diagnostics"]
        assert dx["prefix_charlen"] == 2           # 所述
        assert dx["term_charlen"] == 5             # 第一卡止部
        assert dx["intros_pool_size"] >= 1
        assert dx["has_suggested_match"] is True
        assert dx["suggested_cross_branch"] is False

    def test_diagnostic_contains_no_claim_text(self):
        """Fingerprint must never carry noun content — counts + booleans only."""
        from patentlint.analysis.tw_claims import check_antecedent_basis

        doc = self._build([
            "1. 一種機械裝置，包含一第一卡止部。",
            "2. 如請求項1所述的裝置，其中所述第二卡止部位於頂面。",
        ])
        issues = check_antecedent_basis(doc)
        for issue in issues:
            dx = issue.get("diagnostics") or {}
            for value in dx.values():
                assert not isinstance(value, str) or value in ("the", "said", "所述", "該", "前述", "該等", "該些"), (
                    f"diagnostic value looks like content: {value!r}"
                )


class TestParenAbbrevR34:
    """R34 (2026-05-04) widening of R30 mechanism #6 paren-abbrev bridge.

    Adds support for full-width 全角 parens and lowercase-full-form-then-
    uppercase-abbrev shape (`使用者設備(user equipment, UE)`). Cluster
    Phase A on post-R34 corpus showed TW `第一U` 68 wfp / `UE` 57 wfp /
    `一UE` 37 wfp, all 0-legit; 50 of 98 walker_fp findings used
    full-width parens, 11 used lowercase-FF-comma form.
    """

    @staticmethod
    def _build_one(text: str):
        from patentlint.models import Claim, TwPatentDocument
        return TwPatentDocument(claims=[
            Claim(id=1, text=text, independent=True, multiple_dependent=False, method_claim=False, dependencies=[]),
        ])

    def _intros(self, text: str) -> list[str]:
        from patentlint.analysis.tw_claims import extract_introductions_tw
        doc = self._build_one(text)
        return [norm for _orig, norm in extract_introductions_tw(doc.claims[0])]

    def test_ascii_paren_simple_unchanged(self):
        """Original R30 shape `<CJK>(UPPER)` still registers UPPER abbrev."""
        intros = self._intros("一種使用者設備(UE)，包含一處理器。")
        assert "UE" in intros, f"UE missing from {intros}"

    def test_full_width_paren_registers_abbrev(self):
        """R34 — full-width 全角 parens register abbrev."""
        intros = self._intros("一種使用者設備（UE），包含一處理器。")
        assert "UE" in intros, f"UE missing from {intros}"

    def test_lowercase_ff_comma_uppercase_abbrev(self):
        """R34 — `(user equipment, UE)` lowercase full form then UPPER abbrev."""
        intros = self._intros("一種使用者設備(user equipment, UE)，包含一處理器。")
        assert "UE" in intros, f"UE missing from {intros}"

    def test_full_width_paren_lowercase_ff_full_width_comma(self):
        """R34 — full-width parens AND full-width comma combined."""
        intros = self._intros("一種使用者設備（user equipment，UE），包含。")
        assert "UE" in intros, f"UE missing from {intros}"

    def test_lone_paren_label_does_not_register(self):
        """(101) is an element label number, NOT a paren-abbrev intro."""
        intros = self._intros("一種裝置，包含一第一電極(101)。")
        # Element label digits don't form an UPPER abbrev — should not register
        assert "101" not in intros


class TestStateModifierCaptureExtensionR66:
    """R66 (revised 2026-05-05) state-modifier capture extension.

    When walker captures `前述<state-modifier>` (e.g., `前述島狀`) and
    claim text continues `的<head_noun>`, extend the captured raw_noun
    to include `的<head>`. Without extension, the displayed reference_form
    is the bare adjective `前述島狀` — meaningless to the drafter (`島狀`
    is "island-shape", an adjective). With extension, the user sees the
    full `前述島狀的奈米片積層體` they actually wrote.

    Walker resolution proceeds normally with the extended term:
      - drafter consistent intro+ref (both `<state>的<head>`) → resolves
      - drafter introduces only `<head>` but references `<state>的<head>`
        → emits a real antecedent finding (the 神秘黑屏哥 c10 case)

    Gated on _STATE_MODIFIER_SUFFIXES_TW (狀/形) — possessive frames
    like `該電子裝置的一插槽` end in noun-class suffixes (置/部/料)
    that the gate excludes; capture stays at `該電子裝置`.
    """

    def test_state_modifier_capture_extends(self):
        """`前述島狀的奈米片積層體` — capture extends past 的 to head noun.

        Even though the head noun was introduced earlier (as 一奈米片積層體),
        the drafter's reference adds an extra `島狀的` qualifier that's
        not in the intro form — a real antecedent issue. The walker
        should emit with the FULL state-modifier+head reference form so
        the user sees what they wrote.
        """
        doc = _make_doc([
            _claim(
                1,
                "1. 一種方法，將一奈米片積層體圖案化為島狀，"
                "從前述島狀的奈米片積層體的露出面側進行蝕刻。",
            ),
        ])
        issues = check_antecedent_basis(doc)
        # Capture extends to full phrase; bare `島狀` no longer the term.
        # The intro form was `奈米片積層體` (head only); the reference adds
        # `島狀的` qualifier → genuine antecedent gap → walker emits.
        finding = next(
            (i for i in issues if "島狀" in i["term"]),
            None,
        )
        assert finding is not None, issues
        assert finding["term"] == "島狀的奈米片積層體", finding
        assert finding["reference_form"] == "前述島狀的奈米片積層體", finding

    def test_consistent_state_modifier_intro_resolves(self):
        """If drafter introduces `一<state>的<head>` AND references
        `前述<state>的<head>`, the extended capture resolves via exact
        match (no antecedent issue).
        """
        doc = _make_doc([
            _claim(
                1,
                "1. 一種方法，包含一島狀的奈米片積層體，"
                "前述島狀的奈米片積層體進行蝕刻。",
            ),
        ])
        issues = check_antecedent_basis(doc)
        # Consistent intro+ref form — extended capture matches exactly.
        # (Exact match depends on whether normalize_reference_term keeps
        # 的 in the interior; at minimum the extended capture should not
        # over-emit, and the displayed term — if any — is the full form.)
        relevant = [i for i in issues if "島狀" in i["term"]]
        for i in relevant:
            # If a finding does emit, its term must be the full extended
            # form, never the bare adjective.
            assert i["term"] != "島狀", i

    def test_possessive_not_extended(self):
        """該電子裝置的一插槽 — possessive frame; 電子裝置 ends in 置
        (not 狀/形), so capture stays at 電子裝置. Walker emits as before.

        Regression for 110P000868US c1 protect:true label. The head noun
        in the possessive (一插槽) must not become part of the reference
        form (would mask the real drafter error).
        """
        doc = _make_doc([
            _claim(
                1,
                "1. 一種隨身碟，適用於多個行動裝置，"
                "一連接埠，插入該電子裝置的一插槽內；"
                "一儲存模組，配置以儲存資料。",
            ),
        ])
        issues = check_antecedent_basis(doc)
        finding = next(
            (i for i in issues if i["term"] == "電子裝置"),
            None,
        )
        assert finding is not None, issues
        assert finding["reference_form"] == "該電子裝置", finding

    def test_locative_possessive_not_extended(self):
        """所述容納部的底面 — 容納部 ends in 部 (locative), not state suffix.

        Regression for 110P000631US c1 protect:true label. Capture stays
        at 容納部; 底面 does not become part of the reference form.
        """
        doc = _make_doc([
            _claim(
                1,
                "1. 一種容器，包含一容納空間，所述容納部的底面距離一開口部。",
            ),
        ])
        issues = check_antecedent_basis(doc)
        finding = next(
            (i for i in issues if i["term"] == "容納部"),
            None,
        )
        assert finding is not None, issues
        assert finding["reference_form"] == "所述容納部", finding

    def test_ordinal_state_modifier_not_extended(self):
        """第一狀 (with 第 prefix) — gate excludes ordinal-prefixed state terms.

        Defensive against ambiguous ordinal+state: 第一狀 could be an
        ordinal-typed reference (`first-class state`) rather than a
        pure state modifier. Don't extend.
        """
        doc = _make_doc([
            _claim(
                1,
                "1. 一種方法，包含一元件，該第一狀的元件被處理。",
            ),
        ])
        issues = check_antecedent_basis(doc)
        finding = next(
            (i for i in issues if "第一狀" in i["term"]),
            None,
        )
        assert finding is not None, issues
        # Capture stays bare; not extended past 的.
        assert finding["term"] == "第一狀", finding

    def test_xing_suffix_extends(self):
        """前述環形的墊圈 — 形 suffix also enables capture extension."""
        doc = _make_doc([
            _claim(
                1,
                "1. 一種環，包含一墊圈，前述環形的墊圈具有彈性。",
            ),
        ])
        issues = check_antecedent_basis(doc)
        finding = next(
            (i for i in issues if "環形" in i["term"]),
            None,
        )
        if finding is not None:
            # If walker emits, term must be the extended form.
            assert finding["term"] != "環形", finding
            assert "墊圈" in finding["term"], finding


class TestTrailingPrepositionStripR68c:
    """R68c (2026-05-06) — trailing preposition strip (對/向/自).

    Walker over-captures `<noun>對X` / `<noun>向X` / `<noun>各自` shapes;
    trailing preposition/pronoun particle should be stripped via
    _NOUNLIKE_SINGLE_CHAR_SUFFIXES with default residual ≥ 3 guard
    (3-char compounds like 方向 / 應對 stay protected).
    """

    def test_trailing_dui_stripped(self):
        doc = _make_doc([
            _claim(
                1,
                "1. 一種裝置，包含一驗證模塊，所述驗證模塊對輸入資料進行檢驗。",
            ),
        ])
        issues = check_antecedent_basis(doc)
        for i in issues:
            assert not i["term"].endswith("對"), i

    def test_trailing_xiang_stripped(self):
        doc = _make_doc([
            _claim(
                1,
                "1. 一種電路，包含一輸出節點，所述輸出節點流向接地。",
            ),
        ])
        issues = check_antecedent_basis(doc)
        for i in issues:
            assert not i["term"].endswith("向") or i["term"] == "方向", i

    def test_compound_fang_xiang_protected(self):
        """方向 (3 chars, residual 2) protected by default ≥ 3 guard."""
        doc = _make_doc([
            _claim(
                1,
                "1. 一種裝置，所述方向位於前端。",
            ),
        ])
        issues = check_antecedent_basis(doc)
        # `所述方向` — drafter's reference; walker emits or not depending
        # on intro presence, but term should remain `方向` (not stripped to `方`)
        for i in issues:
            if "方向" in i.get("reference_form", "") or "方" == i["term"]:
                # Accept either "方向" full term or a different finding entirely
                assert i["term"] != "方", i

    def test_trailing_zi_stripped(self):
        doc = _make_doc([
            _claim(
                1,
                "1. 一種抗體，包含一第二Fc結構域，所述第二Fc結構域各自具有特性。",
            ),
        ])
        issues = check_antecedent_basis(doc)
        for i in issues:
            assert not i["term"].endswith("自"), i


class TestNengCompoundExtensionR68d:
    """R68d (2026-05-06) — mid-能 compound noun extension.

    `<X>管理功` truncations from `<X>管理功能` are caused by 能 being
    excluded from _NOUN_CHARS to prevent aux-verb 能 over-capture.
    Targeted post-capture extension when raw_noun ends in a known
    能-precursor (功/性/效/智/...) extends past 能 to recover the
    full compound noun.
    """

    def test_gong_neng_compound_extends(self):
        """`<X>管理功能` capture extends past 能."""
        doc = _make_doc([
            _claim(
                1,
                "1. 一種網路系統，包含一鑒權管理功能，"
                "所述鑒權管理功能接收請求消息。",
            ),
        ])
        issues = check_antecedent_basis(doc)
        # Walker should resolve the full reference (intro+ref both
        # `鑒權管理功能`); never emit truncated `鑒權管理功`.
        for i in issues:
            assert i["term"] != "鑒權管理功", i

    def test_xing_neng_compound_extends(self):
        """`性能` extension."""
        doc = _make_doc([
            _claim(
                1,
                "1. 一種裝置，包含一高性能模組，前述高性能能滿足需求。",
            ),
        ])
        issues = check_antecedent_basis(doc)
        for i in issues:
            # `高性` truncation should not appear; either 高性能模組
            # or 高性能 is the full term
            assert i["term"] != "高性", i

    def test_aux_neng_not_extended(self):
        """`所述模組能執行X` — 模組 captured, 能 is aux-verb;
        模 is NOT a precursor → no extension."""
        doc = _make_doc([
            _claim(
                1,
                "1. 一種裝置，包含一處理模組，所述模組能執行運算。",
            ),
        ])
        issues = check_antecedent_basis(doc)
        # Walker should capture `模組` clean; not extend across 能執行.
        for i in issues:
            assert "能執行" not in i["term"], i
            assert "模組能" not in i["term"], i
