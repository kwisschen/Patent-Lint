"""Wave D - bare 有 / 導入 introduce their object (ruling 2, 2026-10-24).

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


class TestTw:
    def test_bare_you_introduces_a_short_object(self):
        assert "凹槽" not in _tw(
            "1. 一種模具，包括一模板，所述模板的表面成型有凹槽。",
            "2. 如請求項1所述的模具，其中所述凹槽的長度為一預設值。")

    def test_bare_you_introduces_a_long_object(self):
        assert "多孔碳材料層" not in _tw(
            "1. 一種腔體，其內表面塗佈有多孔碳材料層。",
            "2. 如請求項1所述的腔體，其中所述多孔碳材料層的厚度為一預設值。")

    def test_daoru_introduces(self):
        assert "惰性氣體" not in _tw(
            "1. 一種爐體，包括一噴嘴，所述噴嘴用以導入惰性氣體。",
            "2. 如請求項1所述的爐體，其中所述惰性氣體的流量為一預設值。")

    def test_restrictive_you_does_not_introduce(self):
        assert "感測器" in _tw(
            "1. 一種裝置，包括一殼體，所述殼體僅有感測器。",
            "2. 如請求項1所述的裝置，其中所述感測器的數量為二。")

    def test_negation_does_not_introduce(self):
        assert "凹槽" in _tw(
            "1. 一種模具，包括一模板，所述模板沒有凹槽。",
            "2. 如請求項1所述的模具，其中所述凹槽的長度為一預設值。")


class TestCn:
    def test_bare_you_introduces(self):
        assert "复合涂层" not in _cn(
            "1. 一种线，所述线的表面涂覆有复合涂层。",
            "2. 根据权利要求1所述的线，其中所述复合涂层的厚度为一预设值。")

    def test_daoru_introduces(self):
        assert "惰性气体" not in _cn(
            "1. 一种炉体，包括一喷嘴，所述喷嘴用以导入惰性气体。",
            "2. 根据权利要求1所述的炉体，其中所述惰性气体的流量为一预设值。")

    def test_you_heading_a_word_is_not_the_verb(self):
        # 有机 is "organic": 机溶剂 after it is a fragment, not an element.
        from patentlint.analysis.cn_claims import _bare_noun_verb_led_cn

        text = "一种载体，所述载体负载有机溶剂。"
        assert not _bare_noun_verb_led_cn(text, text.index("机溶剂"))
        text = "一种载体，所述载体负载有溶剂。"
        assert _bare_noun_verb_led_cn(text, text.index("溶剂"))


class TestNonOrdinalPossessiveTw:
    """Ruling R5 (2026-10-25): 所述X的Y introduces Y when X is introduced.

    Tested on the helper: the end-to-end shapes are often also reached by the
    F10b 的 + component-noun pattern or a supplementary arm.
    """

    @staticmethod
    def _intro(text, term, intros):
        from patentlint.analysis.tw_claims import has_possessive_introduction_tw

        claim = Claim(id=1, text=text, independent=True)
        return has_possessive_introduction_tw(text, [claim], term, len(text), intros)

    def test_possessive_of_an_introduced_element_introduces(self):
        assert self._intro("接收用於所述映射表的條目的更新指標。", "條目", {"映射表": (1, 1)})

    def test_owner_must_be_introduced(self):
        assert not self._intro("接收用於所述映射表的條目的更新指標。", "條目", {"主機": (1, 1)})

    def test_owner_must_be_the_element_itself(self):
        # A relative clause (所述映射表儲存的條目) is not a plain possessive.
        assert not self._intro("接收所述映射表儲存的條目。", "條目", {"映射表": (1, 1)})

    def test_mention_introduces_only_the_noun_read_there(self):
        # 的條目集合 introduces 條目集合, not 條目.
        assert not self._intro("接收用於所述映射表的條目集合的更新指標。", "條目", {"映射表": (1, 1)})
