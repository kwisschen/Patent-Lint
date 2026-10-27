"""Wave R - TW 輸入 joins the relative-clause introducing verbs (ruling R13: the
article-less object behind a relative clause introduces its head), guarded
where 輸入 is the noun "input": after an ordinal, after 的 / 之, as the object
of 接收, after 電壓, and before / or 之.

Synthetic shapes only; each test fails with its mechanism disabled.
"""

from patentlint.analysis.tw_claims import check_antecedent_basis
from patentlint.models import Claim, TwPatentDocument


def _tw(*texts):
    claims = [
        Claim(id=i + 1, text=t, independent=i == 0, dependencies=[] if i == 0 else [1])
        for i, t in enumerate(texts)
    ]
    return {f["term"] for f in check_antecedent_basis(TwPatentDocument(claims=claims))}


def test_shuru_relative_clause_introduces_its_head():
    terms = _tw("一種控制器，其回應於從主機裝置輸入的寫入命令，執行一寫入操作，並且記錄所述寫入命令的時間。")
    assert "寫入命令" not in terms


def _converter(lead):
    return _tw("一種轉換器，其經配置以將" + lead + "轉換成第二節點處的輸出電流，其中所述輸出電流為直流。")


def test_shuru_after_an_ordinal_is_the_noun():
    assert "輸出電流" in _converter("第二輸入電壓")


def test_shuru_after_de_is_the_noun():
    assert "輸出電流" in _converter("在一第一節點處接收的輸入電壓")


def test_shuru_before_a_slash_is_the_noun():
    assert "輸出電流" in _converter("輸入/輸出節點處的電壓")


def test_shuru_before_zhi_is_the_noun():
    assert "輸出電流" in _converter("多個電壓輸入之間的差值")


def test_shuru_as_the_object_of_jieshou_is_the_noun():
    assert "輸出電流" in _converter("該等接收輸入")
