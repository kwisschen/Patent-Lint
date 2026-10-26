"""Wave K - the CN mirror of TW R82 (a determiner plus a one-or-more quantifier
no longer introduces itself, with the same bases for what that hid), and
abbreviation introductions in both jurisdictions: an introduction that spells
out an abbreviation (一个或多个人工智能/机器学习(AI/ML)模型, 一二維(2D)影像)
also introduces the abbreviated name the later references use.

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


def _cn(*texts):
    return {f["term"] for f in check_antecedent_basis_cn(CnPatentDocument(claims=_claims(texts)))}


def _tw(*texts):
    return {f["term"] for f in check_antecedent_basis(TwPatentDocument(claims=_claims(texts)))}


def test_cn_or_more_reference_without_intro_is_flagged():
    terms = _cn("一种系统，包括一主机，其中所述一个或多个寄存器耦接所述主机。")
    assert any(t.startswith("寄存器") for t in terms)


def test_cn_or_more_reference_with_intro_resolves():
    terms = _cn("一种系统，包括一个或多个寄存器，其中所述一个或多个寄存器耦接一主机。")
    assert not any(t.startswith("寄存器") for t in terms)


def test_cn_possessive_part_keeps_its_registration():
    terms = _cn("一种装置，包括一框架，其中所述框架的所述一个或多个侧壁包括一塑料。")
    assert "侧壁" not in terms


def test_cn_same_quantifier_shared_stem():
    # Residue on both sides: the intro keys 处理设备从… and the reference 处理设备实例化….
    terms = _cn(
        "一种方法，包括：由一个或更多个处理设备从用户设备接收启动交易处理的请求；"
        "以及由所述一个或更多个处理设备实例化交易处理智能合约。"
    )
    assert not any(t.startswith("处理设备") for t in terms)


def test_cn_skipped_key_with_an_article_less_mention_keeps_its_basis():
    terms = _cn(
        "一种控制器，包括：根据两种或多种工作模式控制一电路的控制逻辑；其中，所述两种或更多种工作模式中的每种工作模式确定一电压。",
        "如权利要求1所述的控制器，其中所述工作模式包括一高增益模式。",
    )
    assert "工作模式" not in terms


def test_cn_one_character_element_before_a_preposition():
    # 以 ends the noun scan, so the mention is the element itself.
    terms = _cn("一种装置，包括通过一个或更多个轴以串联布置的多个泵，其中所述泵经由所述一个或更多个轴联接到一马达。")
    assert not any(t.startswith("轴") for t in terms)


def test_cn_abbreviation_intro():
    terms = _cn("一种方法，包括调用一个或多个人工智能/机器学习(AI/ML)模型，并从所述一个或多个AI/ML模型接收一结果。")
    assert not any(t.startswith("AI/ML") for t in terms)


def test_tw_abbreviation_intro_with_a_digit_led_abbreviation():
    terms = _tw("一種方法，包括取得一二維(2D)影像，其中該2D影像包括一像素。")
    assert "2D影像" not in terms


def test_tw_one_character_element_before_a_possessive():
    # 的 ends the noun scan, so 一或多個值 is the element itself.
    terms = _tw("一種方法，包括：獲得與一輸入相對應的一或多個值的一指示；及將該一或多個值輸入到一模型中。")
    assert not any(t.startswith("值") for t in terms)


def test_abbreviation_expansion_cannot_be_a_clause():
    # 三維(3D) is spelled out here, but the span before it is a clause, so the
    # abbreviation names nothing that was introduced.
    terms = _tw("一種裝置，包括多個垂直互連，其中該多個垂直互連形成三維(3D)電感器，且該3D電感器耦接一基板。")
    assert any(t.startswith("3D電感器") for t in terms)
