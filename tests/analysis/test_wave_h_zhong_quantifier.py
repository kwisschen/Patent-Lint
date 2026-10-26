"""Wave H - the 種 measure word after "at least" / plural quantifiers (至少一種,
至少兩種, 複數種, 三種 ...; TW / CN). It was in neither quantifier list, so both
sides keyed a garbage 種X. Fixing that exposed the item-13 self-introduction:
a quantified reference (該至少一種X) must not introduce X, yet it can lean on an
earlier mention written with the same quantifier whose capture carries a
predicate or a modifier.

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
    extract_introductions_tw,
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


class TestZhongFamilyNormalizes:
    @pytest.mark.parametrize("q", ["至少一種", "至少兩種", "複數種", "若干種", "三種"])
    def test_tw_both_sides(self, q):
        assert normalize_reference_term(f"該{q}溶劑") == "溶劑"
        assert normalize_candidate_intro(f"{q}溶劑") == "溶劑"

    @pytest.mark.parametrize("q", ["至少一种", "至少两种", "复数种", "三种"])
    def test_cn_both_sides(self, q):
        assert normalize_reference_term_cn(f"所述{q}溶剂") == "溶剂"
        assert normalize_candidate_intro_cn(f"{q}溶剂") == "溶剂"

    def test_tw_ordinal_kept(self):
        claim = Claim(id=1, text="一種裝置，包括一第三種電極。", independent=True, dependencies=[])
        assert "第三種電極" in {n for _, n in extract_introductions_tw(claim)}

    def test_tw_bare_reference_resolves(self):
        found = _tw("一種組合物，包括至少一種溶劑及一容器，該溶劑置於該容器中。")
        assert "溶劑" not in found

    def test_cn_bare_reference_resolves(self):
        found = _cn("一种组合物，包括至少一种溶剂和一个容器，所述溶剂置于所述容器中。")
        assert "溶剂" not in found


class TestQuantifiedReferenceDoesNotIntroduce:
    def test_tw_reference_alone_fires(self):
        found = _tw(
            "一種方法，包括取得一樣本。",
            "如請求項1所述之方法，其中偵測該至少一種病原體，且該病原體存在於該樣本中。",
        )
        assert "病原體" in found

    def test_cn_reference_alone_fires(self):
        found = _cn(
            "一种方法，包括获取一个样本。",
            "根据权利要求1所述的方法，其中检测所述至少一种病原体，且所述病原体存在于所述样本中。",
        )
        assert "病原体" in found

    def test_tw_determiner_after_quantifier_does_not_introduce(self):
        found = _tw(
            "一種裝置，包括一記憶部。",
            "如請求項1所述之裝置，其中該記憶部儲存複數種前述安全參數，且前述安全參數受限。",
        )
        assert any(t.startswith("安全參數") for t in found)


class TestSharedQuantifierMention:
    def test_tw_intro_with_predicate(self):
        found = _tw(
            "一種方法，包括使一樣本與至少一種消化酵素接觸。",
            "如請求項1所述之方法，其中該至少一種消化酵素包括胃蛋白酶。",
        )
        assert "消化酵素" not in found

    def test_tw_intro_with_modifier(self):
        found = _tw(
            "一種方法，包括使一樣本與至少一種具有以下通式之金屬有機化合物接觸。",
            "如請求項1所述之方法，其中該至少一種金屬有機化合物之含量為百分之一。",
        )
        assert "金屬有機化合物" not in found

    def test_cn_intro_with_predicate(self):
        found = _cn(
            "一种方法，包括使样本与至少一种消化酶接触。",
            "根据权利要求1所述的方法，其中所述至少一种消化酶包括胃蛋白酶。",
        )
        assert "消化酶" not in found

    def test_tw_bare_reference_gets_no_shared_reading(self):
        found = _tw(
            "一種方法，包括使一樣本與至少一種消化酵素接觸。",
            "如請求項1所述之方法，其中該消化酵素包括胃蛋白酶。",
        )
        assert any(t.startswith("消化酵素") for t in found)


class TestZhongRescan:
    def test_tw_second_zhong_intro(self):
        claim = Claim(
            id=1,
            text="一種感測器，包括與一電極耦合的至少一種適體或至少一種寡核苷酸，其中該寡核苷酸固定於該電極。",
            independent=True,
            dependencies=[],
        )
        assert ("至少一種寡核苷酸", "寡核苷酸") in extract_introductions_tw(claim)

    def test_tw_verb_yi_inside_zhong_span(self):
        found = _tw(
            "一種方法，包括偵測至少兩種訊號；從該等至少兩種訊號產生一校驗曲線；及基於該校驗曲線決定一濃度。"
        )
        assert "校驗曲線" not in found
