# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
"""TW R44 - V+於 stranding continued + plain trailing predicates.

Reports kwisschen/patentlint-reports#556, #558, #570, #579, #582, #584,
#593-#598, #618-#628.
"""
from __future__ import annotations

import pytest

from patentlint.analysis.tw_claims import (
    _TRAILING_VERB_DENYLIST,
    clean_noun_phrase_tw,
)


# --------------------------------------------------------------- V+於 stranding
# 於 is excluded from _NOUN_CHARS, so the noun scan halts AT it and leaves the
# verb's head glued to the captured noun - the 低/位/安裝/屬 shape from R41.

@pytest.mark.parametrize("dirty,clean", [
    # 垂直於 - report #556, the largest member of this round (12 gold FPs).
    ("置入方向垂直", "置入方向"),
    ("第二方向垂直", "第二方向"),
    # 等於 / 不等於 - reports #593-#598, the comparison predicates.
    ("占空比等", "占空比"),
    ("占空比不等", "占空比"),
])
def test_v_yu_stranding_is_stripped(dirty, clean):
    assert clean_noun_phrase_tw(dirty) == clean


# ------------------------------------------------------- plain trailing verbs

@pytest.mark.parametrize("dirty,clean", [
    ("引導配置工具指定", "引導配置工具"),      # #583/#585/#586
    ("引導配置工具動態", "引導配置工具"),      # #582 (動態修改)
    ("圓弧段相連", "圓弧段"),                  # #619-#621, #626
    ("範本自動生成", "範本"),                  # #580
    ("電容式半導體結構進一步限", "電容式半導體結構"),   # #618-f2, #623
    ("所述長條段的寬度等同", "所述長條段的寬度"),        # #627
    ("頻率未落入", "頻率"),                    # #597-f3
])
def test_trailing_predicate_is_stripped(dirty, clean):
    assert clean_noun_phrase_tw(dirty) == clean


# ------------------------------------------------- greedy-trim (R29 lesson)
# A shorter member must never dismantle the longer lexeme that shares its head.
# These are NOT independently-evidenced FP sources - they exist so the 1-char
# and 2-char members above cannot strand a fragment. Measured, not assumed:
# a bare 等 strips 參考電壓實質上彼此不相等 to ...不相 on TWI711261B c3.

@pytest.mark.parametrize("dirty,clean", [
    ("參考電壓實質上彼此不相等", "參考電壓實質上彼此"),
    ("第一長度與第二長度相等", "第一長度與第二長度"),
])
def test_greedy_trim_does_not_strand_a_fragment(dirty, clean):
    assert clean_noun_phrase_tw(dirty) == clean
    assert not clean_noun_phrase_tw(dirty).endswith(("相", "不", "均", "同"))


@pytest.mark.parametrize("longer,shorter", [
    ("相等", "等"),
    ("均等", "等"),
    ("同等", "等"),
    ("相連接", "相連"),
    ("所構成", "構成"),
    ("未落入", "落入"),
])
def test_longer_member_is_tried_before_the_head_it_shares(longer, shorter):
    """The denylist is a LENGTH-SORTED TUPLE and the strip loop breaks on the
    first match, so ordering is load-bearing. Rebuilding it as a set (which
    tests/eval/exception_head_bisect.py did before R44) silently randomizes
    this and measures a walker nobody would ship.
    """
    assert longer in _TRAILING_VERB_DENYLIST
    assert shorter in _TRAILING_VERB_DENYLIST
    order = list(_TRAILING_VERB_DENYLIST)
    assert order.index(longer) < order.index(shorter)


# ------------------------------------------------------------- FN guards
# Every member ships because its NOUN sense is a PREFIX followed by its head
# noun, which an endswith strip is structurally incapable of touching. Pin
# that, so a later round cannot quietly convert one into an interior cut.

@pytest.mark.parametrize("term", [
    "取得部",        # "acquisition unit" - 62 corpus occurrences
    "指定物",
    "動態範圍",
    "觸及率",        # 62 corpus occurrences
    "導電金屬",      # the 屬 lexeme guard from R41 must survive
    "該等效球面焦度",  # R29's 等效 re-split
    "等級",
])
def test_noun_prefix_senses_are_untouched(term):
    assert clean_noun_phrase_tw(term) == term


def test_bare_shengcheng_stays_withheld():
    """#579-f2 (範本生成) is NOT resolved and must not be silently re-opened.

    Bare 生成 measured 4 gold FPs ended but 1 UNPAIRED-NEW (TWI811098B c13
    emits the malformed 為多個相) and 1 silenced gold-legit (TW202516840A
    c15). The collocation 自動生成 ships instead and reaches #580. Re-open
    only by measuring the discriminator, not by re-arguing the token.
    """
    assert "生成" not in _TRAILING_VERB_DENYLIST
    assert "自動生成" in _TRAILING_VERB_DENYLIST
    assert clean_noun_phrase_tw("範本生成") == "範本生成"


@pytest.mark.parametrize("term", [
    "命令列取得一韌體",            # #584-f2
    "預測模型預測出排列組合",       # #570-f4
])
def test_object_final_captures_remain_open(term):
    """These end in the verb's OBJECT, so no endswith member can reach them.

    They need a cardinal-gated INTERIOR cut (the R35 傳遞一 shape) and are
    deliberately left open rather than fixed with an over-broad strip. Pinned
    so the gap stays visible in the next round.
    """
    assert clean_noun_phrase_tw(term) == term


# ============================================================== TW R45
# The V+於 family MINED rather than waited for, after #556 failed end to end.

def test_556_resolves_end_to_end():
    """R44 cleaned the REFERENCE but the finding survived on the INTRO side.

    插設於 strands its head exactly like 垂直於, so the introduction registered
    as 置入方向插設 while the reference cleaned to 置入方向 - a matched pair
    cleaned on ONE SIDE ONLY (the R29 desynchronization failure). The isolated
    cleaner looked correct; only this end-to-end reproducer showed it.
    """
    from patentlint.analysis.tw_claims import check_antecedent_basis
    from patentlint.models import TwPatentDocument
    from patentlint.parser.claims_tw import parse_tw_claims

    parsed = parse_tw_claims([
        "1. 一種密封型護目鏡，包含一支撐框架，沿一置入方向插設於一承載框體，及一扣合方向。",
        "2. 如請求項1所述的密封型護目鏡，其中，所述置入方向垂直於所述扣合方向。",
    ])
    doc = TwPatentDocument(claims=parsed, input_format="google_patents_html")
    findings = [f for f in check_antecedent_basis(doc)
                if f.get("category") != "tw_contamination"]
    assert findings == [], f"expected no findings, got {findings}"


@pytest.mark.parametrize("term", [
    "固定部", "固定件", "設置面", "安置部",
])
def test_r45_noun_prefix_senses_are_untouched(term):
    assert clean_noun_phrase_tw(term) == term


@pytest.mark.parametrize("token", ["耦接", "定位", "配置", "連接", "形成", "儲存"])
def test_r45_withheld_members_stay_withheld(token):
    """耦接 (28 FPs) and 定位 (19 FPs) look shippable and are NOT.

    Both measure 0 UNPAIRED-NEW, yet each silences gold-legit findings that do
    not contain the token at all (第二端子; 第一/第二較長段) - a newly-clean
    capture registering as a spurious INTRODUCTION and resolving a later
    reference by prefix, silencing a REAL defect. Re-open only by measuring
    that cascade, not by re-arguing the FP count.

    儲存 (30 FPs) is in the same class and is the sharpest case: it passes
    EVERY corpus gate and is caught only by
    ``TestBareNounIntroduction::test_possessive_de_still_flagged``. The gold
    corpus cannot see this class - do not re-add it on a green corpus run.
    """
    assert token not in _TRAILING_VERB_DENYLIST
