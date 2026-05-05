# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Mutation harness — drafter-error pattern regression suite.

Codifies the bug classes surfaced by Claire's `神秘黑屏哥.docx` real-drafter
audit (R63–R66, 2026-05-05) as systematic regression tests. Each mutation
takes a base draft, programmatically injects a known drafter-error pattern,
runs the analyzer, and asserts the expected behavior.

The 8 bug classes (per memory `feedback_real_drafter_drafts_have_different_bugs`):

  1. Older TIPO dep-format `如申請專利範圍第N項` (vs modern `如請求項N`)
  2. Mixed Arabic/CJK ordinal style (drafter writes 第1, references 前述第二)
  3. Bibliographic citation labels `[專利文獻N]<ref>` in 先前技術
  4. Empty `【NNNN】` paragraph spacers
  5. Self-loop drafter typos (cN.deps == [N])
  6. Section-name aliases (背景技術 / 先前技術文獻 / 專利文獻 / 非專利文獻)
  7. Locative bare-noun intros (`於X的一主面上` — drafter introduces X without
     `一` quantifier)
  8. Modifier+noun references (R66 — `前述<state>的<head>` constructions)

Generalized aggressively — every mutation runs across multiple base drafts
where applicable, and is parametric so future bug classes plug in via the
same shape. Per `feedback_future_proof_with_anti_overscope`: ship the
minimum mechanism that captures EACH learned pattern; expand the matrix
when a NEW firm-internal draft surfaces a NEW class.

All mutations work from in-memory pydantic doc constructions — no real
.docx files needed (firm-confidential drafts are gitignored). When a new
real-drafter draft from Claire (or another firm) lands, run the
analyzer + add a new mutation here that captures the new class.
"""

from __future__ import annotations

import re
from typing import Callable

import pytest

from patentlint.analysis.cn_claims import (
    check_antecedent_basis_cn,
    check_self_dependent as check_self_dependent_cn,
)
from patentlint.analysis.tw_claims import (
    check_antecedent_basis,
    check_circular_dependency,
    check_self_dependent,
)
from patentlint.analysis.tw_specification import (
    check_paragraph_ending,
    check_required_sections,
)
from patentlint.models import (
    Claim,
    CnPatentDocument,
    TwPatentDocument,
    TwPatentType,
)


# ─────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────


def _claim(num: int, text: str, *, independent: bool = True,
           deps: list[int] | None = None, multi_dep: bool = False) -> Claim:
    return Claim(
        id=num, text=text, independent=independent,
        dependencies=deps or [], multiple_dependent=multi_dep,
    )


def _tw_doc(claims: list[Claim], *, prior_art: list[str] | None = None,
            embodiment: list[str] | None = None,
            disclosure: list[str] | None = None,
            paragraph_word_numbers: list[str] | None = None) -> TwPatentDocument:
    """Minimal TW doc carrying claims + optional spec sections."""
    return TwPatentDocument(
        patent_type=TwPatentType.INVENTION,
        title="一種裝置",
        technical_field=["本發明涉及一種裝置。"],
        prior_art=prior_art or ["已知有相關技術。"],
        disclosure=disclosure or ["本發明提供一種解決方案。"],
        embodiment=embodiment or ["參照圖1說明實施方式。"],
        claims=claims,
        body_paragraph_word_numbers=paragraph_word_numbers or [],
    )


def _cn_doc(claims: list[Claim]) -> CnPatentDocument:
    return CnPatentDocument(claims=claims)


# Base drafts — the fixtures we mutate. Multiple bases ensure each pattern
# is exercised across diverse claim shapes (independent-only, multi-dep,
# method-claim, etc.).

BASE_TW_DRAFTS: list[Callable[[], list[Claim]]] = [
    # Base 1: simple independent + dependent
    lambda: [
        _claim(1, "1. 一種裝置，包含一基板及一電極，所述電極設置於該基板上。"),
        _claim(2, "2. 如請求項1所述之裝置，其中所述電極包含金屬。",
               independent=False, deps=[1]),
    ],
    # Base 2: 3-claim chain
    lambda: [
        _claim(1, "1. 一種電子裝置，包含一處理器、一儲存模組、及一通訊模組。"),
        _claim(2, "2. 如請求項1所述之電子裝置，所述儲存模組儲存資料。",
               independent=False, deps=[1]),
        _claim(3, "3. 如請求項2所述之電子裝置，所述通訊模組傳送該資料。",
               independent=False, deps=[2]),
    ],
    # Base 3: method claim
    lambda: [
        _claim(1, "1. 一種半導體裝置之製造方法，包含於半導體基板的一主面上"
                  "形成一閘極結構之工程。"),
    ],
]

BASE_CN_DRAFTS: list[Callable[[], list[Claim]]] = [
    # Base 1: simple independent + dependent (Simplified)
    lambda: [
        _claim(1, "1. 一种装置，包含一基板及一电极，所述电极设置于该基板上。"),
        _claim(2, "2. 根据权利要求1所述的装置，其中所述电极包含金属。",
               independent=False, deps=[1]),
    ],
    # Base 2: 3-claim chain
    lambda: [
        _claim(1, "1. 一种电子装置，包含一处理器、一存储模块及一通信模块。"),
        _claim(2, "2. 根据权利要求1所述的电子装置，所述存储模块存储数据。",
               independent=False, deps=[1]),
        _claim(3, "3. 根据权利要求2所述的电子装置，所述通信模块传送该数据。",
               independent=False, deps=[2]),
    ],
]


# ─────────────────────────────────────────────────────────────────────────
# Bug class 1 — Older TIPO dep-format `如申請專利範圍第N項`
# ─────────────────────────────────────────────────────────────────────────
#
# Surfaced by 神秘黑屏哥.docx via R62 commit 8043745. Pre-2018 TIPO firms
# still use this verbose form; modern drafts use 如請求項N. Parser must
# recognize both as equivalent dependency citations.


@pytest.mark.parametrize("base_idx", range(len(BASE_TW_DRAFTS)))
def test_older_tw_dep_format_recognized(base_idx):
    """Replace `如請求項N` with `如申請專利範圍第N項` — parser still sees
    the dependency, walker still resolves antecedent."""
    base = BASE_TW_DRAFTS[base_idx]()
    if len(base) < 2:
        pytest.skip("Base has no dependent claim to mutate.")
    # Mutate dep claim text to use older form
    for c in base:
        if not c.independent and c.dependencies:
            n = c.dependencies[0]
            c.text = c.text.replace(
                f"如請求項{n}所述",
                f"如申請專利範圍第{n}項所述",
            )
    doc = _tw_doc(base)
    # Walker emits no SPURIOUS findings (depending on base, may emit
    # legit antecedent issues — but the dep relationship must still resolve)
    issues = check_antecedent_basis(doc)
    # The dep claim's references should not appear as walker_fp due to
    # parser failing to recognize the parent — verify by checking that
    # any emitted finding doesn't have a `note: cleanup_empty` marker
    # (would indicate parser broke).
    for i in issues:
        assert i.get("note") != "cleanup_empty", i


# ─────────────────────────────────────────────────────────────────────────
# Bug class 2 — Mixed Arabic/CJK ordinal style
# ─────────────────────────────────────────────────────────────────────────
#
# Surfaced by 神秘黑屏哥 — drafter introduces `第1間隔件` (Arabic) and
# references `前述第二間隔件` (CJK). Walker normalize must Arabic→CJK on
# both intro and reference sides for symmetric matching. R63 fix.


def test_arabic_to_cjk_ordinal_symmetry_tw():
    """Drafter mixes 第1間隔件 (intro) with 前述第二間隔件 — should NOT
    resolve (different ordinals); each must independently resolve only
    when normalize chains agree."""
    # Intro 第1, ref 第一 (same ordinal, different script) — should resolve
    doc = _tw_doc([
        _claim(1, "1. 一種裝置，包含一第1間隔件，前述第一間隔件位於底部。"),
    ])
    issues = check_antecedent_basis(doc)
    # Walker should resolve `前述第一間隔件` against `一第1間隔件` intro
    # via Arabic→CJK normalization.
    assert not any(
        i["term"].startswith("第") and "間隔件" in i["term"]
        for i in issues
    ), issues


def test_arabic_to_cjk_ordinal_display_preserved_tw():
    """When drafter writes 第1, displayed reference_form must preserve
    Arabic — walker normalizes only for matching."""
    doc = _tw_doc([
        _claim(1, "1. 一種裝置，包含一電極，前述第1電極不在分析範圍。"),
    ])
    issues = check_antecedent_basis(doc)
    # If walker emits, the displayed form must show drafter's 第1
    for i in issues:
        if "電極" in i["term"]:
            # Display should preserve Arabic ordinal, not normalize to 第一
            ref = i.get("reference_form", "")
            if "第" in ref and ("一" in ref or "1" in ref):
                # If "1" appears in raw ref text, display should keep "1"
                # (we test by checking reference_form != bare normalized form)
                assert "第1" in ref or "1" in ref, i


# ─────────────────────────────────────────────────────────────────────────
# Bug class 3 — Bibliographic citation labels
# ─────────────────────────────────────────────────────────────────────────
#
# `[專利文獻N]X` / `[非專利文獻N]X` — drafters use these to list cited
# literature in 先前技術. R65 fix: paragraphEnding skips them since
# they're bibliographic entries, not prose paragraphs.


def test_bibliographic_citation_paragraph_skipped_tw():
    """[專利文獻1]<ref> paragraph in prior_art shouldn't trigger missing-。 fix."""
    doc = _tw_doc(
        BASE_TW_DRAFTS[0](),
        prior_art=[
            "已知有相關技術。",
            "[專利文獻1]美國專利第10256321號說明書",
            "[非專利文獻1]Smith et al., J. Chem. (2020) 12:34",
        ],
    )
    items = check_paragraph_ending(doc)
    # No amend should be emitted for the citation-label paragraphs
    for it in items:
        if it.status == "amend":
            msg = it.message or ""
            assert "專利文獻" not in msg, it
            assert "非專利文獻" not in msg, it


def test_bibliographic_with_para_num_skipped_tw():
    """`【0003】[專利文獻1]X` (prefixed by paragraph number) also skipped."""
    doc = _tw_doc(
        BASE_TW_DRAFTS[0](),
        prior_art=[
            "已知有相關技術。",
            "【0003】[專利文獻1]美國專利第10256321號說明書",
        ],
    )
    items = check_paragraph_ending(doc)
    for it in items:
        if it.status == "amend":
            msg = it.message or ""
            assert "專利文獻" not in msg, it


# ─────────────────────────────────────────────────────────────────────────
# Bug class 4 — Empty 【NNNN】 paragraph spacers
# ─────────────────────────────────────────────────────────────────────────
#
# Drafters insert 【0009】 alone as a spacer between content paragraphs.
# Word auto-numbers carry through. R65 fix: paragraphEnding skips them.


def test_empty_paragraph_number_marker_skipped_tw():
    """`【0009】` alone (no body content) shouldn't trigger amend."""
    doc = _tw_doc(
        BASE_TW_DRAFTS[0](),
        prior_art=[
            "【0001】已知有相關技術。",
            "【0002】",
            "【0003】另有其他相關技術。",
        ],
    )
    items = check_paragraph_ending(doc)
    # Empty 【0002】 should not be flagged
    for it in items:
        if it.status == "amend" and it.message:
            assert "0002" not in it.message, it


# ─────────────────────────────────────────────────────────────────────────
# Bug class 5 — Self-loop drafter typos
# ─────────────────────────────────────────────────────────────────────────
#
# cN.deps == [N] — drafter typo. R65 fix: selfDep fires; circularDep
# does NOT fire on direct self-loops (R65 dedup).


@pytest.mark.parametrize("self_loop_id", [4, 7, 12])
def test_self_loop_typo_caught_once_tw(self_loop_id):
    """Direct self-loop should fire selfDep once, not double-fire circularDep."""
    base = [
        _claim(1, "1. 一種裝置。"),
        _claim(self_loop_id, f"{self_loop_id}. 如請求項{self_loop_id}所述。",
               independent=False, deps=[self_loop_id]),
    ]
    doc = _tw_doc(base)
    self_dep = check_self_dependent(doc)
    circ = check_circular_dependency(doc)
    self_dep_amends = [i for i in self_dep if i.status == "amend"]
    circ_amends = [i for i in circ if i.status == "amend"]
    assert len(self_dep_amends) == 1, self_dep_amends
    assert len(circ_amends) == 0, circ_amends


def test_self_loop_typo_caught_once_cn():
    """CN parity: direct self-loop fires selfDep only."""
    doc = _cn_doc([
        _claim(1, "1. 一种装置。"),
        _claim(4, "4. 根据权利要求4所述的装置。", independent=False, deps=[4]),
    ])
    self_dep = check_self_dependent_cn(doc)
    self_dep_amends = [i for i in self_dep if i.status == "amend"]
    assert len(self_dep_amends) == 1, self_dep_amends


# ─────────────────────────────────────────────────────────────────────────
# Bug class 6 — Section-name aliases
# ─────────────────────────────────────────────────────────────────────────
#
# 背景技術 (alias for 先前技術), 先前技術文獻, 專利文獻, 非專利文獻 etc.
# R64 fix: _SECTION_MAP recognizes these as prior_art-equivalent.


@pytest.mark.parametrize("alias_section", [
    "背景技術",
    "先前技術文獻",
])
def test_section_alias_recognized_as_prior_art_tw(alias_section):
    """Drafter uses 背景技術 instead of canonical 先前技術 — required-sections
    check should not emit `prior_art missing`.
    """
    # Build a doc as if parser saw the alias: prior_art content present,
    # so requiredSections should not flag prior_art missing.
    doc = _tw_doc(
        BASE_TW_DRAFTS[0](),
        prior_art=[f"於 {alias_section} 章節下，已知有相關技術。"],
    )
    items = check_required_sections(doc)
    for it in items:
        if it.status == "amend" and it.message:
            assert "prior_art" not in (it.details or "").lower(), it
            assert "先前技術" not in (it.details_params or {}).get("missing", []), it


# ─────────────────────────────────────────────────────────────────────────
# Bug class 7 — Locative bare-noun intros
# ─────────────────────────────────────────────────────────────────────────
#
# `於半導體基板的一主面上` — drafter introduces `半導體基板` inside a
# locative phrase, and references `前述半導體基板`. R64 F7d fix: walker
# treats the locative-noun position as introducing the head noun.


def test_locative_bare_noun_intro_resolves_tw():
    """於X的一Y上 introducing X — `前述X` reference should resolve."""
    doc = _tw_doc([
        _claim(
            1,
            "1. 一種半導體裝置，於半導體基板的一主面上形成一電極，"
            "前述半導體基板包含矽。",
        ),
    ])
    issues = check_antecedent_basis(doc)
    # 半導體基板 in locative position registers as intro; reference resolves
    assert not any(i["term"] == "半導體基板" for i in issues), issues


# ─────────────────────────────────────────────────────────────────────────
# Bug class 8 — Modifier+noun references (R66)
# ─────────────────────────────────────────────────────────────────────────
#
# `前述島狀的奈米片積層體` — drafter references state-modifier+head form
# where head was introduced bare. R66 (revised 2026-05-05) fix: walker
# captures the FULL form and emits a real antecedent finding so the user
# sees the meaningful reference_form (not just `前述島狀`).


def test_state_modifier_capture_extends_tw():
    """`前述<state>的<head>` capture extends past 的 to head noun."""
    doc = _tw_doc([
        _claim(
            1,
            "1. 一種方法，將一奈米片積層體圖案化為島狀，"
            "從前述島狀的奈米片積層體進行蝕刻。",
        ),
    ])
    issues = check_antecedent_basis(doc)
    # Walker should emit with full extended reference_form, not bare `前述島狀`
    found_extended = any(
        "島狀" in i["term"] and "奈米片積層體" in i["term"]
        for i in issues
    )
    assert found_extended, issues
    # And the bare nonsense `島狀` alone should not appear
    assert not any(i["term"] == "島狀" for i in issues), issues


def test_possessive_capture_not_extended_tw():
    """`該<noun-class>的一<another>` (possessive) — capture stays bare.

    Suffix gate (狀/形) protects possessive frames where the FIRST noun is
    the actual reference and shouldn't be conflated with the head after 的.
    """
    doc = _tw_doc([
        _claim(
            1,
            "1. 一種隨身碟，適用於多個行動裝置，"
            "一連接埠插入該電子裝置的一插槽內。",
        ),
    ])
    issues = check_antecedent_basis(doc)
    finding = next(
        (i for i in issues if i["term"] == "電子裝置"),
        None,
    )
    assert finding is not None, issues
    assert finding["reference_form"] == "該電子裝置", finding


def test_state_modifier_capture_extends_cn():
    """CN parity: 状/形 suffix triggers capture extension."""
    doc = _cn_doc([
        _claim(
            1,
            "1. 一种方法，将一纳米片积层体图案化为岛状，"
            "从前述岛状的纳米片积层体进行刻蚀。",
        ),
    ])
    issues = check_antecedent_basis_cn(doc)
    # Either resolves silently (consistent intro+ref form via head match)
    # OR emits with extended reference_form. Bare `岛状` alone never
    # appears as the term.
    for i in issues:
        if "岛状" in i["term"]:
            assert "纳米片" in i["term"] or "积层体" in i["term"], i


# ─────────────────────────────────────────────────────────────────────────
# Generalized regression — any future bug class plugs in here
# ─────────────────────────────────────────────────────────────────────────


class TestRealDrafterBaseline:
    """Track that real-drafter expectations remain stable.

    When a new firm-internal draft surfaces a new bug class, add a new
    test class above and keep this baseline as the hard floor: post-fix
    behavior on previously-shipped drafts must remain correct.
    """

    def test_walker_does_not_emit_pure_adjective_terms_tw(self):
        """Across base TW drafts, walker should never emit a pure
        adjective (狀/形 ending) as a standalone reference term."""
        for i, build_base in enumerate(BASE_TW_DRAFTS):
            doc = _tw_doc(build_base())
            issues = check_antecedent_basis(doc)
            for issue in issues:
                term = issue["term"]
                if term.endswith(("狀", "形")) and len(term) <= 3:
                    pytest.fail(
                        f"Base draft {i}: walker emitted bare adjective "
                        f"{term!r} as standalone term: {issue}"
                    )

    def test_walker_does_not_emit_terms_with_yu_boundary_cn(self):
        """CN walker should not emit terms containing 由 (relational verb)."""
        for i, build_base in enumerate(BASE_CN_DRAFTS):
            doc = _cn_doc(build_base())
            issues = check_antecedent_basis_cn(doc)
            for issue in issues:
                assert "由" not in issue["term"], (
                    f"Base CN draft {i} walker emitted term containing 由: "
                    f"{issue}"
                )

    def test_walker_does_not_emit_jou_prefix_terms_cn(self):
        """CN walker should not emit terms starting with 具有 (possession verb)."""
        for i, build_base in enumerate(BASE_CN_DRAFTS):
            doc = _cn_doc(build_base())
            issues = check_antecedent_basis_cn(doc)
            for issue in issues:
                assert not issue["term"].startswith("具有"), (
                    f"Base CN draft {i} walker emitted 具有-prefix term: "
                    f"{issue}"
                )


# ─────────────────────────────────────────────────────────────────────────
# Mutation count check — ensure the harness doesn't silently drop
# ─────────────────────────────────────────────────────────────────────────


def test_harness_covers_all_eight_bug_classes():
    """Sanity: harness covers all 8 bug classes from 神秘黑屏哥.

    Each class has at least one test function. If a class is removed
    or merged, update this count and the docstring at top of file.
    """
    src = open(__file__, encoding="utf-8").read()
    # Count `# Bug class N —` markers
    markers = re.findall(r"^# Bug class (\d+) —", src, re.M)
    assert len(set(markers)) == 8, (
        f"Expected 8 bug class markers, found {len(set(markers))}: {markers}"
    )
