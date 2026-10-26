"""Wave L - a "one or more" quantifier before the determiner (一或多個所述X,
"one or more of the X") is a reference. The wave J guard that keeps a
relative clause registered (該一或多個所選擇的X) also caught the 所 of 所述,
so 一或多個所述X introduced X itself and an element only ever named that
way was never flagged. And four predicates (呈一, 沿一, 相夾, a trailing
受壓) no longer run a reference past its element, TW and CN.

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


def test_quantifier_before_suoshu_without_intro_is_flagged():
    terms = _tw("一種支架，包括一底座及一線圈，所述線圈纏繞於所述底座的一個或多個所述立柱的其中一個。")
    assert "立柱" in terms


def test_quantifier_before_suoshu_with_intro_resolves():
    terms = _tw(
        "一種支架，包括一底座，所述底座包含一頂板及固定於所述頂板的一個或多個立柱。",
        "如請求項1所述的支架，更包括一線圈，所述線圈纏繞於一個或多個所述立柱的其中一個。",
    )
    assert "立柱" not in terms


def test_relative_clause_after_the_quantifier_still_registers():
    terms = _tw("一種方法，包括從一或多個所選擇的存取點接收一封包，並向該一或多個所選擇的存取點發送一回應。")
    assert not any(t.startswith("所選擇") or t.startswith("存取點") for t in terms)


def test_verb_cardinal_boundaries_end_the_reference():
    # 呈一 / 沿一 / 相夾 / 受壓 each ran the reference past its element, so
    # an element with no introduction was reported under a clause.
    terms = _tw(
        "一種機台，包括一底座，其中多個所述導軌沿一水平方向延伸，所述底座與所述蓋板相夾有一傾斜角度，"
        "所述簧片呈一閉合位置，且所述按鍵受壓而下移。"
    )
    assert {"導軌", "蓋板", "簧片", "按鍵"} <= terms


def test_pressed_surface_keeps_its_name():
    # 受壓 heads element names; only a trailing 受壓 is a predicate.
    terms = _tw("一種裝置，包括一殼體，其中所述受壓面朝向所述殼體。")
    assert "受壓面" in terms


def test_cn_verb_cardinal_boundaries_end_the_reference():
    from patentlint.analysis.cn_claims import check_antecedent_basis_cn
    from patentlint.models import CnPatentDocument

    text = (
        "一种机台，包括一底座，其中多个所述导轨沿一水平方向延伸，所述底座与所述盖板相夹有一倾斜角度，"
        "所述簧片呈一闭合位置，且所述按键受压而下移。"
    )
    doc = CnPatentDocument(claims=[Claim(id=1, text=text, independent=True, dependencies=[])])
    assert {"导轨", "盖板", "簧片", "按键"} <= {f["term"] for f in check_antecedent_basis_cn(doc)}
