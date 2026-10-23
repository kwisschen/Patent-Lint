# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
"""CN R71 / TW R65.

1. A CN reference whose interior cut lands on the head of a declared compound
   (连接 in 主机连接器) resolves against the drafter's whole introduction
   through a last-resort, exact-match tier - mirror of TW R27/R43.
2. 建立 is an interior verb boundary in both walkers, gated off when it heads
   a compound noun (建立请求 / 建立模块).
3. Spec-support drops the 其中之一 / 其中另一 fragments and strips a leading
   作为 / 作為.

Every input is synthetic.
"""
from patentlint.models import Claim, CnPatentDocument, TwPatentDocument, TwPatentType
from patentlint.analysis.cn_claims import check_antecedent_basis_cn, clean_noun_phrase_cn
from patentlint.analysis.tw_claims import clean_noun_phrase_tw
from patentlint.analysis.cn_spec_support import check_spec_support_cn
from patentlint.analysis.tw_spec_support import check_spec_support_tw


def _cn_terms(*texts):
    claims = [
        Claim(id=i + 1, text=t, independent=(i == 0), dependencies=([] if i == 0 else [1]))
        for i, t in enumerate(texts)
    ]
    return [f["term"] for f in check_antecedent_basis_cn(CnPatentDocument(title="x", claims=claims))]


_CN_C1 = (
    "1.一种传输系统，包括：传输线，其包含第一连接器；以及主机装置，其包含主机连接器，"
    "所述主机连接器连接所述传输线的所述第一连接器。"
)


class TestTailCompoundTier:
    def test_reference_resolves_against_whole_compound_intro(self):
        assert _cn_terms(_CN_C1) == []

    def test_dependent_claim_reference_resolves(self):
        dep = "2.如权利要求1所述的传输系统，其中所述传输线还包含稳压单元，其连接于所述主机连接器。"
        assert _cn_terms(_CN_C1, dep) == []

    def test_reference_with_no_introduction_still_fires(self):
        assert _cn_terms("1.一种传输系统，包括：主机装置；其中所述主机连接器传输信号。") == ["主机"]

    def test_in_place_cut_is_unchanged(self):
        # The tier is additive: the cleaner still cuts on every in-place path.
        assert clean_noun_phrase_cn("主机连接器") == "主机"
        assert clean_noun_phrase_cn("主机连接器", protect_tail_compounds=True) == "主机连接器"


class TestJianliBoundary:
    def test_cn_clause_verb_is_cut(self):
        assert clean_noun_phrase_cn("外接装置建立数据链路") == "外接装置"

    def test_cn_compound_heads_are_kept(self):
        for t in ("会话建立模块", "连接建立请求", "无线建立消息"):
            assert clean_noun_phrase_cn(t) == t

    def test_tw_clause_verb_is_cut(self):
        assert clean_noun_phrase_tw("基站建立支援") == "基站"

    def test_tw_compound_heads_are_kept(self):
        for t in ("連線建立請求", "會話建立模組"):
            assert clean_noun_phrase_tw(t) == t


_CN_SS_CLAIM = (
    "1.一种控制系统，包括：第一引脚及第二引脚；以及控制单元，所述控制单元基于检测结果确定"
    "所述第一引脚及所述第二引脚的其中之一作为输入端，其中另一作为输出端。"
)
_CN_SS_SPEC = (
    "本发明的控制系统包括第一引脚、第二引脚以及控制单元。控制单元根据检测结果将第一引脚设为"
    "输入端，并将第二引脚设为输出端。"
)


def _phrases(findings):
    return [f.get("phrase") if isinstance(f, dict) else getattr(f, "phrase", f) for f in findings]


def test_cn_spec_support_drops_connective_fragments():
    doc = CnPatentDocument(
        claims=[Claim(id=1, text=_CN_SS_CLAIM, independent=True)],
        technical_field=[], background=[], summary=[_CN_SS_SPEC],
        detailed_description=[_CN_SS_SPEC], drawings_description=[],
    )
    assert _phrases(check_spec_support_cn(doc)) == []


def test_tw_spec_support_drops_connective_fragments():
    claim = (
        "1.一種控制系統，包括：第一腳位及第二腳位；以及控制單元，所述控制單元基於偵測結果決定"
        "所述第一腳位及所述第二腳位的其中之一作為輸入端，其中另一作為輸出端。"
    )
    spec = (
        "本發明的控制系統包括第一腳位、第二腳位以及控制單元。控制單元根據偵測結果將第一腳位設為"
        "輸入端，並將第二腳位設為輸出端。"
    )
    doc = TwPatentDocument(
        patent_type=TwPatentType.INVENTION, title="x", technical_field=[], prior_art=[],
        disclosure=[], drawings_description=[], embodiment=[spec], symbol_table=[],
        claims=[Claim(id=1, text=claim, independent=True)], abstract_text="",
    )
    assert _phrases(check_spec_support_tw(doc)) == []
