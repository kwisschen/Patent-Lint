"""Wave M - a 所-relative clause in front of a referenced element (該所選擇的X,
該至少一個所選擇的X, 所述所确定的X) stopped the capture at 的: the finding
named the clause (所選擇) instead of the element, and the quantified form was
dropped as one character. The element is the head after 的, and a reference
of that shape no longer introduces itself. Rulings R10 / R11 (TW).

Synthetic shapes only; each test fails with its mechanism disabled.
"""

from patentlint.analysis.cn_claims import check_antecedent_basis_cn
from patentlint.analysis.tw_claims import check_antecedent_basis
from patentlint.models import Claim, CnPatentDocument, TwPatentDocument


def _claims(texts):
    return [
        Claim(id=i + 1, text=t, independent=i == 0, dependencies=[] if i == 0 else [1])
        for i, t in enumerate(texts)
    ]


def _tw(*texts):
    return {f["term"] for f in check_antecedent_basis(TwPatentDocument(claims=_claims(texts)))}


def _cn(*texts):
    return {f["term"] for f in check_antecedent_basis_cn(CnPatentDocument(claims=_claims(texts)))}


def test_tw_selected_element_resolves_on_its_introduction():
    assert _tw("一種方法，包括：選擇一存取點；及從該所選擇的存取點接收一回應。") == set()


def test_tw_selected_element_without_introduction_is_flagged_by_name():
    assert _tw("一種方法，包括：發送一請求；及從該所選擇的存取點接收一回應。") == {"存取點"}


def test_tw_quantified_selected_element_resolves():
    terms = _tw("一種方法，包括：選擇複數個存取點；向該等所選擇的存取點中的至少一個存取點發送一請求；"
                "及從該至少一個所選擇的存取點接收一回應。")
    assert terms == set()


def test_tw_head_keeps_time_word_and_drops_coverb():
    assert "傳輸時間" in _tw("一種方法，包括：接收一請求；及發送該所排程的傳輸時間。")
    assert _tw("一種方法，包括：發送一請求；及基於該所決定的位置來發送一信號。") == {"位置"}


def test_tw_required_voltage_is_a_noun_not_a_clause():
    terms = _tw("一種電路，包括一所需電壓；及一補償電壓，以補償該所需電壓的偏差。")
    assert "偏差" not in terms


def test_cn_selected_element_resolves_on_its_introduction():
    assert _cn("一种方法，包括：选择一接入点；以及从所述所选择的接入点接收一响应。") == set()


def test_cn_same_clause_repeat_is_an_introduction():
    terms = _cn("一种装置，处理器被配置为：确定与业务量相对应的所确定的聚合量；以及基于所述所确定的聚合量来确定一资源。")
    assert "聚合量" not in terms


def test_cn_different_clause_is_not_an_introduction():
    terms = _cn("一种装置，处理器被配置为：确定与业务量相对应的所需要的聚合量；以及基于所述所确定的聚合量来确定一资源。")
    assert "聚合量" in terms


def test_cn_selected_element_without_introduction_is_flagged():
    assert _cn("一种系统，包括一主机，其中所述所选择的接入点连接所述主机。") == {"接入点"}
