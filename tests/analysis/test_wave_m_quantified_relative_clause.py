"""Wave M - a quantifier right before a verb counts the head of the relative
clause that verb opens (一個含有量測數值的報告 introduces 報告), while a bare
relative clause still does not introduce in TW. Also the 封包 lexeme guard
(ruling R10: a shortened name of an introduced compound has no basis) and 組裝
as an introducing verb.

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


def test_quantified_relative_clause_introduces_its_head():
    assert "報告" not in _tw("一種方法，包括：產生一個含有量測數值的報告；以及傳送該報告。")


def test_quantified_relative_clause_in_a_dependent_claim_chain():
    # The Latin run inside the clause is what defeats the older 一X的Y arm.
    terms = _tw(
        "一種照明裝置，包括一LED陣列，該照明裝置更包含一配置於該LED陣列外部的偏轉配置。",
        "如請求項1之照明裝置，其中該偏轉配置包括一透鏡。",
    )
    assert "偏轉配置" not in terms


def test_bare_relative_clause_introduces_after_ruling_r13():
    # Ruling R13 (2026-10-27): the article-less object of an introducing verb
    # behind a relative clause introduces its head (see test_wave_o_*).
    assert "報告" not in _tw("一種方法，包括：產生含有量測數值的報告；以及傳送該報告。")


def test_bare_relative_clause_after_a_withheld_verb_still_flags():
    assert "報告" in _tw("一種方法，包括：輸入含有量測數值的報告；以及傳送該報告。")


def test_modifier_before_another_de_is_not_the_head():
    assert "報告" in _tw("一種方法，包括：接收一個含有量測數值的報告的摘要；以及傳送該報告。")


def test_single_character_you_does_not_open_a_clause():
    assert "判定" in _tw("一種方法，包括：回應並未出現一有效標籤的判定，停止一馬達；以及記錄該判定。")


def test_packet_keeps_its_name():
    terms = _tw("一種方法，包括：接收一第一訊號；以及加密所述第一封包。")
    assert "第一封包" in terms and "第一封" not in terms


def test_shortened_name_of_a_compound_has_no_basis():
    # Ruling R10: only 感測資料封包 was introduced.
    assert "封包" in _tw("一種方法，包括：傳輸一個含有感測資料封包的訊號；以及加密該封包。")


def test_assemble_introduces_its_object():
    assert "封包" not in _tw("一種裝置，包括一適以組裝封包之第一層，及一適以傳送該封包之第二層。")
