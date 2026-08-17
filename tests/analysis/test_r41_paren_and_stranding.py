# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
"""TW R41 / CN R63 - paren-annotation asymmetry mirror + V+於 stranding + 經 gate.

Reports kwisschen/patentlint-reports#533, #535, #539, #542.
"""
from __future__ import annotations

import pytest

from patentlint.analysis.cn_claims import (
    check_antecedent_basis_cn,
    clean_noun_phrase_cn,
)
from patentlint.analysis.tw_claims import (
    check_antecedent_basis,
    clean_noun_phrase_tw,
)
from patentlint.models import CnPatentDocument, TwPatentDocument
from patentlint.parser.claims_cn import parse_cn_claims_docx
from patentlint.parser.claims_tw import parse_tw_claims


def _tw(claims: list[str]) -> list[dict]:
    parsed = parse_tw_claims([f"{i + 1}. {c}" for i, c in enumerate(claims)])
    doc = TwPatentDocument(claims=parsed, input_format="google_patents_html")
    return [f for f in check_antecedent_basis(doc)
            if f.get("category") != "tw_contamination"]


def _cn(claims: list[str]) -> list[dict]:
    parsed = parse_cn_claims_docx("\n".join(
        f"{i + 1}.{c}" for i, c in enumerate(claims)))
    doc = CnPatentDocument(claims=parsed, input_format="google_patents_html")
    return check_antecedent_basis_cn(doc)


# --------------------------------------------------------------- V+於 stranding

@pytest.mark.parametrize("dirty,clean", [
    ("所述控制系統安裝", "所述控制系統"),   # #542, 安裝於
    ("所述背景類型屬", "所述背景類型"),      # #539, 屬於
    ("目標畫素資料所屬", "目標畫素資料"),
])
def test_tw_v_yu_stranding_strips(dirty: str, clean: str) -> None:
    assert clean_noun_phrase_tw(dirty) == clean


@pytest.mark.parametrize("noun", [
    "導電金屬",      # 金屬 is the element name, not a stranded verb
    "連接金屬",
    "金屬",
    "菌屬",
    "重新附屬",      # the drafter's own nominalization
    "業者所專屬",
    "安裝端",        # 安裝 as a PREFIX is untouched by a trailing strip
])
def test_tw_shu_lexeme_guard_protects_real_nouns(noun: str) -> None:
    assert clean_noun_phrase_tw(noun) == noun


@pytest.mark.parametrize("dirty,clean", [
    ("所述控制系统安装", "所述控制"),
    ("所述背景类型属", "所述背景类型"),
])
def test_cn_v_yu_stranding_strips(dirty: str, clean: str) -> None:
    assert clean_noun_phrase_cn(dirty) == clean


def test_cn_jinshu_guard_protects_metal() -> None:
    assert clean_noun_phrase_cn("导电金属") == "导电金属"


# ------------------------------------------------------------------- interior 經

@pytest.mark.parametrize("dirty,clean", [
    ("一共聚物經氫化反應而獲得", "一共聚物"),      # #533 / #535
    ("所述共聚物經氫化反應", "所述共聚物"),
    ("所述線路經由一開關", "所述線路"),
])
def test_tw_jing_cuts_the_verb_reading(dirty: str, clean: str) -> None:
    assert clean_noun_phrase_tw(dirty) == clean


@pytest.mark.parametrize("term", [
    "所述經量化權重資訊",          # participle at the head of the term
    "該經壓縮輸入資料",
    "第一經加擾資料",              # ordinal is head, not noun
    "多個經摺疊",                  # quantifier is head
    "所述神經網路模型",            # 神經
    "所述第一神經網路模型",
    "第二換能器之間之經增強撓性區域",      # genitive resets the segment
    "第二換能器之間之第一經增強撓性區域",
])
def test_tw_jing_guard_protects_the_participle_reading(term: str) -> None:
    assert clean_noun_phrase_tw(term) == term


def test_cn_jing_guard_protects_manager_compound() -> None:
    """项目经理 is a NOUN; cutting it manufactured a spurious 项目 intro that
    silenced a real defect on CN111815283B c3."""
    assert clean_noun_phrase_cn("项目经理修改模块") == "项目经理"


def test_cn_jing_cuts_the_verb_reading() -> None:
    assert clean_noun_phrase_cn("一共聚物经氢化反应而获得") == "一共聚物"


# --------------------------------------------------- paren-annotation asymmetry

def test_tw_annotated_reference_resolves_against_bare_intro() -> None:
    """The MIRROR of F3 Rule 4: `該氣囊(14)` against an article-less `氣囊`."""
    findings = _tw([
        "一種導管，其包含多個超音波換能器以及一環狀氣囊組件，"
        "該環狀氣囊組件(14)之表面平行於該等超音波換能器之表面。",
    ])
    assert not [f for f in findings if f["term"].startswith("環狀氣囊組件")]


def test_tw_paren_numeral_typo_still_fires() -> None:
    """The L1/L2 guard: when BOTH sides carry an annotation it must match
    exactly, so a mismatched numeral is still a defect."""
    findings = _tw([
        "一種裝置，其包含一第二長度(L1)之支臂，所述第二長度(L2)大於一第一長度。",
    ])
    assert [f for f in findings if "第二長度" in f["term"]]


def test_cn_annotated_reference_resolves_against_bare_intro() -> None:
    findings = _cn([
        "一种电路，包括：一输入电压端子以及一可选择电压源电路，"
        "来自所述可选择电压源电路(7)的输入电压耦接至所述输入电压端子。",
    ])
    assert not [f for f in findings if f["term"].startswith("可选择电压源电路")]


def test_cn_fullwidth_paren_annotation_is_recognised() -> None:
    """CN drafts use （） heavily; the pre-existing rule was half-width only."""
    findings = _cn([
        "一种连接器，包括一绝缘本体壳体，所述绝缘本体壳体（10）设置有一开口。",
    ])
    assert not [f for f in findings if f["term"].startswith("绝缘本体壳体")]
