"""CN wave C - the mirror of Christopher's two TW introduction rulings
(2026-10-24): an ordinal possessive with an introduced possessor, and a short
article-less noun as the object of an introducing verb, are introductions.

Synthetic shapes only; each test fails with its mechanism disabled.
"""

from patentlint.analysis.cn_claims import check_antecedent_basis_cn, has_possessive_introduction_cn
from patentlint.models import Claim, CnPatentDocument


def _flagged(c1: str, c2: str) -> set[str]:
    claims = [Claim(id=1, text=c1, independent=True),
              Claim(id=2, text=c2, independent=False, dependencies=[1])]
    return {f["term"] for f in check_antecedent_basis_cn(CnPatentDocument(claims=claims))}


def test_ordinal_possessive_with_an_introduced_possessor():
    assert "第二参数" not in _flagged(
        "1. 一种系统，包括一控制器，并依据所述控制器的第二参数调整一输出。",
        "2. 如权利要求1所述的系统，其中所述第二参数为一温度上限。")


def test_relative_clause_on_an_introduced_element_introduces():
    claim = Claim(id=1, text="所述立柱沿垂直于所述底座的第二方向延伸。", independent=True)
    assert has_possessive_introduction_cn(
        claim.text, [claim], "第二方向", 99, {"底座": (1, 1)})
    claim = Claim(id=1, text="所述控制器用于网络中的第一转发装置。", independent=True)
    assert not has_possessive_introduction_cn(
        claim.text, [claim], "第一转发装置", 99, {"控制器": (1, 1)})


def test_short_bare_object_of_a_verb():
    assert "电阻" not in _flagged(
        "1. 一种电路，包括一开关，所述开关的第二端连接电阻的第一端。",
        "2. 如权利要求1所述的电路，其中所述电阻的第二端接地。")


def test_action_after_jinxing_is_not_an_element():
    assert "排序" in _flagged(
        "1. 一种方法，包括：对多个数据进行排序。",
        "2. 如权利要求1所述的方法，其中所述排序依据一权重值。")
