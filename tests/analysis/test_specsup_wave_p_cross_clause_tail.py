"""Spec-support: a capture that runs over a clause comma (wave P).

包含一電源模組，供電給所述處理器 was registered as an introduction whose
normalized form is the second clause, so the verb 供電 reached the inventory.
Synthesized claims; each case fails with the filter switched off.
"""

from patentlint.analysis.cn_spec_support import check_spec_support_cn
from patentlint.analysis.tw_spec_support import check_spec_support_tw
from patentlint.models import Claim, CnPatentDocument, TwPatentDocument


def _claims(texts):
    return [
        Claim(id=i + 1, text=t, independent=i == 0, dependencies=[] if i == 0 else [1])
        for i, t in enumerate(texts)
    ]


def _tw(*texts):
    doc = TwPatentDocument(claims=_claims(texts), embodiment=["本發明關於一種裝置。"])
    return [f.phrase for f in check_spec_support_tw(doc)]


def _cn(*texts):
    doc = CnPatentDocument(claims=_claims(texts), embodiment=["本发明涉及一种装置。"])
    return [f.phrase for f in check_spec_support_cn(doc)]


def test_tw_clause_after_the_comma_is_not_a_term():
    out = _tw("1. 一種設備，包含一處理器及一電源模組，供電給所述處理器。")
    assert "電源模組" in out
    assert not any(t.startswith("供電") for t in out)


def test_cn_clause_after_the_comma_is_not_a_term():
    out = _cn("1. 一种设备，包含处理器和电源模块，供电给所述处理器。")
    assert "电源模块" in out
    assert not any(t.startswith("供电") for t in out)
