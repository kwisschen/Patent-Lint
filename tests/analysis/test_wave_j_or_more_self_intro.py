"""Wave J - the "one or more" quantifier family (一或多個, 兩個或更多個 ...; TW)
after a determiner. 該一或多個X is a reference, yet it registered X as its own
introduction, so an element only ever named that way was never flagged
(carried item 13). And 更 is not a noun character, so 該一或更多個X stopped
at 一或 and was never looked up at all.

Dropping the self-introduction exposed what it had been hiding: intros the
span hid, residue on both sides of a quantified pair, one-character
elements, possessive parts and article-less mentions. Each has its own basis.

Synthetic shapes only; each test fails with its mechanism disabled.
"""

from patentlint.analysis.tw_claims import check_antecedent_basis
from patentlint.models import Claim, TwPatentDocument


def _claims(texts):
    return [
        Claim(id=i + 1, text=t, independent=i == 0, dependencies=[] if i == 0 else [1])
        for i, t in enumerate(texts)
    ]


def _tw(*texts):
    return {f["term"] for f in check_antecedent_basis(TwPatentDocument(claims=_claims(texts)))}


def test_or_more_reference_without_intro_is_flagged():
    terms = _tw("一種系統，包括一主機，其中該一或多個暫存器耦接該主機。")
    assert any(t.startswith("暫存器") for t in terms)


def test_or_more_reference_with_intro_resolves():
    terms = _tw("一種系統，包括一或多個暫存器，其中該一或多個暫存器耦接一主機。")
    assert "暫存器" not in terms


def test_geng_quantifier_reference_is_looked_up():
    # 更 stopped the capture at 一或, a one-character key that was dropped.
    terms = _tw("一種系統，包括一主機，其中該一或更多個控制器耦接該主機。")
    assert any(t.startswith("控制器") for t in terms)


def test_geng_quantifier_reference_with_intro_resolves():
    terms = _tw("一種系統，包括兩個或更多個控制器，其中該兩個或更多個控制器耦接一主機。")
    assert "控制器" not in terms


def test_geng_step_over_needs_a_leading_quantifier():
    # The 或 here is not a quantifier at the head of the capture.
    terms = _tw("一種裝置，其中該膜層呈現下列一或更多者：一第一硬度及一第二硬度。")
    assert not any("更" in t for t in terms)


def test_plain_yi_intro_inside_a_skipped_span():
    terms = _tw("一種系統，包括一或多個運算器及一記憶體，該記憶體使該一或多個運算器執行一程序，該程序包括一步驟。")
    assert "程序" not in terms


def test_suo_relative_clause_keeps_its_registration():
    terms = _tw(
        "一種方法，包括：向該一或多個所選擇的存取點發送一封包，該封包針對該等所選擇的存取點中的每一者。"
    )
    assert not any(t.startswith("所") for t in terms)


def test_possessive_part_keeps_its_registration():
    # Ruling R6: a geometry part of an introduced owner has basis.
    terms = _tw("一種裝置，包括一框架，其中該框架之該一或多個側壁包括一塑膠。")
    assert "側壁" not in terms


def test_same_quantifier_shared_stem_with_residue_on_both_sides():
    terms = _tw(
        "一種機器，經組態以使用一或多個輔助軸來移動一手臂，其中該手臂沿著該一或多個輔助軸內滑動。"
    )
    assert not any(t.startswith("輔助軸") for t in terms)


def test_same_quantifier_stem_tolerates_a_line_break_space():
    terms = _tw("一種系統，包含一或多個 運算器，該一或多個運算器耦接至一記憶體。")
    assert not any(t.startswith("運算器") for t in terms)


def test_one_character_element_with_the_same_quantifier():
    terms = _tw("一種方法，包括：產生一或多個值；及將該一或多個值輸入到一模型中。")
    assert not any(t.startswith("值") for t in terms)


def test_article_less_mention_keeps_its_basis():
    terms = _tw("一種方法，包括利用一機械臂將貨件裝載至一車輛中，其中該機械臂抓取該一或多個貨件。")
    assert "貨件" not in terms
