"""Wave G - the rest of the "or more" quantifier family (TW / CN): the
classifier spellings (一种或多种 / 一組或多組 / 一条或多条) and the two/three-or-more
spellings (兩個或更多個 / 两个或多个 / 二或多種). Wave F added the 一个或多个 family;
these stayed in neither list, so an intro keyed 或多种X and a bare later
reference could never match it. Adding them to the intro alternation needed two
intro-side repairs: a rescan where a span swallowed a later quantifier, and the
时 compound right after the quantifier (两个或更多个时间点).

Synthetic shapes only; each test fails with its mechanism disabled.
"""

import pytest

from patentlint.analysis.cn_claims import (
    check_antecedent_basis_cn,
    normalize_candidate_intro_cn,
    normalize_reference_term_cn,
)
from patentlint.analysis.tw_claims import (
    check_antecedent_basis,
    normalize_candidate_intro,
    normalize_reference_term,
)
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


class TestClassifierFamilyNormalizes:
    @pytest.mark.parametrize("q", ["一种或多种", "一种或更多种", "一种或者多种", "一组或多组", "一组或更多组", "一条或多条"])
    def test_cn_both_sides_strip_whole(self, q):
        assert normalize_reference_term_cn(f"所述{q}溶剂") == "溶剂"
        assert normalize_candidate_intro_cn(f"{q}溶剂") == "溶剂"

    @pytest.mark.parametrize("q", ["一種或多種", "一種或更多種", "一種或者多種", "一組或多組", "一組或更多組", "一條或多條"])
    def test_tw_both_sides_strip_whole(self, q):
        assert normalize_reference_term(f"該{q}溶劑") == "溶劑"
        assert normalize_candidate_intro(f"{q}溶劑") == "溶劑"


class TestClassifierFamilyResolves:
    def test_cn_bare_reference_after_classifier_intro(self):
        found = _cn(
            "一种组合物，包括一种或多种添加剂和一种溶剂。",
            "根据权利要求1所述的组合物，其中所述添加剂溶解于所述溶剂。",
        )
        assert not any(t.startswith("添加剂") for t in found)

    def test_tw_bare_reference_after_classifier_intro(self):
        found = _tw(
            "一種組合物，包括一種或多種添加劑及一溶劑。",
            "如請求項1所述之組合物，其中該添加劑溶解於該溶劑。",
        )
        assert not any(t.startswith("添加劑") for t in found)

    def test_tw_group_classifier(self):
        assert "參數" not in _tw("一種裝置，包括一組或多組參數及一處理器，該處理器讀取該參數。")

    def test_cn_unintroduced_element_still_fires(self):
        found = _cn(
            "一种组合物，包括一种或多种添加剂和一种溶剂。",
            "根据权利要求1所述的组合物，其中所述催化剂溶解于所述溶剂。",
        )
        assert any(t.startswith("催化剂") for t in found)


class TestClassifierFamilyCaptureBudget:
    # The intro pattern's quantifier alternation decides where the 12-character
    # noun budget starts. Without the family member the budget is spent on
    # 种或多种 and a long intro registers truncated garbage.
    _CN_INTRO = "一种组合物，其特征在于，一种或多种聚氧乙烯山梨醇酐脂肪酸酯分散于一种溶剂中。"
    _TW_INTRO = "一種組合物，其特徵在於，一種或多種聚氧乙烯山梨醇酐脂肪酸酯分散於一溶劑中。"

    def test_cn_long_intro_resolves(self):
        found = _cn(self._CN_INTRO, "根据权利要求1所述的组合物，其中所述聚氧乙烯山梨醇酐脂肪酸酯溶解于所述溶剂。")
        assert not any(t.startswith("聚氧乙烯") for t in found)

    def test_tw_long_intro_resolves(self):
        found = _tw(self._TW_INTRO, "如請求項1所述之組合物，其中該聚氧乙烯山梨醇酐脂肪酸酯溶解於該溶劑。")
        assert not any(t.startswith("聚氧乙烯") for t in found)

    def test_cn_sibling_compound_still_fires(self):
        found = _cn(self._CN_INTRO, "根据权利要求1所述的组合物，其中所述聚氧乙烯山梨醇酐脂肪醇醚溶解于所述溶剂。")
        assert any(t.startswith("聚氧乙烯山梨醇酐脂肪醇醚") for t in found)


class TestTwoOrMoreFamily:
    @pytest.mark.parametrize("q", ["两个或更多个", "两个或多个", "两种或更多种", "三个或更多个"])
    def test_cn_both_sides_strip_whole(self, q):
        assert normalize_reference_term_cn(f"所述{q}电极") == "电极"
        assert normalize_candidate_intro_cn(f"{q}电极") == "电极"

    @pytest.mark.parametrize("q", ["兩個或更多個", "兩個或多個", "二或更多個", "二或多種", "三個或更多個"])
    def test_tw_both_sides_strip_whole(self, q):
        assert normalize_reference_term(f"該{q}電極") == "電極"
        assert normalize_candidate_intro(f"{q}電極") == "電極"

    def test_tw_bare_reference_after_two_or_more_intro(self):
        found = _tw("一種組合物，包括二或多種賦形劑，其中該賦形劑係以一總量存在。")
        assert not any(t.startswith("賦形劑") for t in found)


class TestSwallowedQuantifierRescan:
    def test_tw_second_or_more_intro_is_registered(self):
        found = _tw(
            "一種分配器，將一輸入光波之兩個或多個副本分別傳送至兩個或多個輸出接口；"
            "其中一偵測器接收來自該等輸出接口中之一者的一光波。"
        )
        assert "輸出接口" not in found

    def test_cn_second_or_more_intro_is_registered(self):
        found = _cn(
            "一种分配器，将一输入光波的两个或多个副本分别传送至两个或多个输出接口；"
            "其中一个探测器接收来自所述输出接口中的一者的光波。"
        )
        assert "输出接口" not in found


class TestOrFamilyShiIntro:
    def test_cn_time_point_after_two_or_more(self):
        found = _cn(
            "一种系统，包括处理器，所述处理器获得在两个或更多个时间点处的信号值，"
            "并评估在所述两个或更多个时间点之间的差异。"
        )
        assert "时间点" not in found
