"""Wave D - a change or motion verb before 至 / 到 is the predicate (TW, CN).

Synthetic shapes only; each test fails with its mechanism disabled.
"""

from patentlint.analysis.cn_claims import check_antecedent_basis_cn, clean_noun_phrase_cn
from patentlint.analysis.tw_claims import check_antecedent_basis, clean_noun_phrase_tw
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
    def test_motion_verb_before_dao_is_cut(self):
        assert _tw(
            "1. 一種閥門，包括一閥體，所述閥體具有一開啟位置。",
            "2. 如請求項1所述的閥門，其中，該閥體由該開啟位置返回到一關閉位置。",
        ) == set()

    def test_change_verb_before_zhi_is_cut(self):
        assert clean_noun_phrase_tw("液位下降至一警戒值") == "液位"

    def test_intro_side_cut_before_yi_matches(self):
        # The intro capture stops before 一, leaving 到 at the end.
        assert clean_noun_phrase_tw("電壓上升到") == "電壓"

    def test_noun_pair_and_quantity_are_kept(self):
        assert clean_noun_phrase_tw("第一表面到所述第二表面") == "第一表面"
        assert clean_noun_phrase_tw("移動裝置") == "移動裝置"

    def test_trailing_quantity_opener_is_stripped(self):
        assert "厚度至少" not in _tw(
            "1. 一種電池，包括一殼體。",
            "2. 如請求項1所述的電池，其中所述厚度至少為2 mm。",
        )

    def test_adverb_rule_still_runs_before_the_quantity_strip(self):
        assert clean_noun_phrase_tw("迴路集體地至少覆蓋一區域") == "迴路"


class TestCn:
    def test_motion_verb_before_dao_is_cut(self):
        assert _cn(
            "1. 一种阀门，包括一阀体，所述阀体具有一开启位置。",
            "2. 根据权利要求1所述的阀门，其中，该阀体由该开启位置返回到一关闭位置。",
        ) == set()

    def test_change_verb_before_zhi_is_cut(self):
        assert clean_noun_phrase_cn("液位下降至一警戒值") == "液位"
        assert clean_noun_phrase_cn("电压上升到") == "电压"

    def test_trailing_quantity_opener_is_stripped(self):
        assert clean_noun_phrase_cn("厚度至少为2") == "厚度"
