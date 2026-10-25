"""Wave F - the "one or more" quantifier family and the pre-clean quantifier
strip (TW / CN), the plural reference over ordinal siblings, and ruling R8
(2026-10-26: the process of X does not inherit basis from X).

Synthetic shapes only; each test fails with its mechanism disabled.
"""

from patentlint.analysis.cn_claims import (
    check_antecedent_basis_cn,
    normalize_reference_term_cn,
)
from patentlint.analysis.tw_claims import (
    check_antecedent_basis,
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


class TestQuantifierFamily:
    def test_cn_one_or_more_family_strips_whole(self):
        assert normalize_reference_term_cn("所述一个或多个温度探头") == "温度探头"
        assert normalize_reference_term_cn("所述一个或更多个温度探头") == "温度探头"

    def test_tw_one_or_more_family_strips_whole(self):
        assert normalize_reference_term("該一個或多個溫度探頭") == "溫度探頭"
        assert normalize_reference_term("該一或更多個溫度探頭") == "溫度探頭"

    def test_cn_family_reference_resolves_bare(self):
        found = _cn(
            "一种装置，包括一个或多个温度探头和一个壳体。",
            "根据权利要求1所述的装置，其中所述温度探头固定于所述壳体。",
        )
        assert "温度探头" not in found and "或多个温度探头" not in found

    def test_tw_family_reference_resolves_bare(self):
        found = _tw(
            "一種裝置，包括一個或多個溫度探頭及一殼體。",
            "如請求項1所述之裝置，其中該溫度探頭固定於該殼體。",
        )
        assert "溫度探頭" not in found

    def test_cn_more_than_one_steps_over_its_yu(self):
        # 于 is not a noun character; the reference used to stop at 一个或多.
        found = _cn(
            "一种装置，包括一个或多于一个光学探头，所述一个或多于一个光学探头安装在支架上。",
        )
        assert not any(t.startswith("或多") for t in found)


class TestPreCleanQuantifierStrip:
    def test_interior_cut_no_longer_leaves_only_the_quantifier(self):
        # The cut used to see the quantifier and stop inside the noun.
        assert normalize_reference_term_cn("所述一个或多个接收器阵列接收") != "或多个"
        assert normalize_reference_term("所述至少一個處理器執行") == "處理器"

    def test_the_later_strip_stays_single(self):
        assert normalize_reference_term("所述至少一個一次性容器") == "一次性容器"

    def test_stripped_quantifier_still_counts_toward_the_cut_floor(self):
        # 多個段包括… cut at 包括 with the quantifier attached; it still does.
        assert normalize_reference_term("所述多個段包括一階函數") == "段"

    def test_tw_long_quantified_reference_keeps_its_tail(self):
        # 一或多個 spends the 12-character budget; the tail 法 is restored.
        found = _tw(
            "一種系統，包括一或多個影像品質強化演算法，其中所述一或多個影像品質強化演算法應用於一畫素。",
        )
        assert not any(t.startswith("影像品質強化演算") for t in found)


class TestIntroNengGate:
    def test_truncated_intro_no_longer_introduces_its_stem(self):
        # 一个或多个身体功能 was captured as 身体功 -> a phantom 身体 intro.
        found = _cn(
            "一种方法，包括：检测与一个或多个身体功能相关联的信号。",
            "根据权利要求1所述的方法，其中所述身体的状态是稳定的。",
        )
        assert "身体" in found


class TestQuantifiedOneCharOwner:
    def test_possessive_on_a_quantified_one_char_element(self):
        found = _tw(
            "一種連接器，具有一導軌及複數個孔，其中該複數個孔之第二數目個孔沿著該導軌設置，且三大於該第二數目。",
        )
        assert "第二數目" not in found


class TestPluralOverOrdinalSiblings:
    def test_tw_plural_names_the_siblings(self):
        found = _tw(
            "一種連接器，包括一第一接腳及一第二接腳，該等接腳固定於一基座。",
        )
        assert "接腳" not in found

    def test_tw_singular_still_ambiguous(self):
        found = _tw(
            "一種連接器，包括一第一接腳及一第二接腳，該接腳固定於一基座。",
        )
        assert "接腳" in found


class TestRulingR8:
    def test_process_of_an_element_needs_its_own_introduction(self):
        found = _tw(
            "一種系統，包括一高爐及一控制器，所述控制器監測該高爐過程中的異常。",
        )
        assert "高爐過程" in found

    def test_the_element_itself_still_resolves(self):
        found = _tw(
            "一種系統，包括一高爐及一控制器，所述控制器監測該高爐的溫度。",
        )
        assert "高爐" not in found
