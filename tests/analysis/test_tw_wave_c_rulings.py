"""TW wave C - Christopher's two introduction rulings (2026-10-24).

1. An ordinal possessive (所述X的第一Y / 所述X之第一Y) introduces the first Y of
   X when X is itself an introduced element.
2. An article-less earlier mention as the object of an introducing verb, a
   bare possessor in that object included, is an introduction (the TW reading
   of the CN rule).

Synthetic shapes only; each test fails with its mechanism disabled.
"""

from patentlint.analysis.tw_claims import check_antecedent_basis
from patentlint.models import Claim, TwPatentDocument


def _flagged(c1: str, c2: str | None = None) -> set[str]:
    claims = [Claim(id=1, text=c1, independent=True)]
    if c2:
        claims.append(Claim(id=2, text=c2, independent=False, dependencies=[1]))
    return {f["term"] for f in check_antecedent_basis(TwPatentDocument(claims=claims))}


class TestOrdinalPossessive:
    def test_possessive_with_de_introduces_the_ordinal(self):
        assert "第一接腳" not in _flagged(
            "1. 一種電路，包括一比較器，所述比較器的第一接腳耦接一基準電壓。",
            "2. 如請求項1所述的電路，更包括一分壓電路，連接所述比較器的所述第一接腳。")

    def test_possessive_with_zhi_introduces_the_ordinal(self):
        assert "第二參數" not in _flagged(
            "1. 一種系統，包括一控制器，並依據所述控制器之第二參數調整一輸出。",
            "2. 如請求項1所述的系統，其中所述第二參數為一溫度上限。")

    def test_relative_clause_on_an_introduced_element_introduces(self):
        # Ruling 3 (2026-10-24): the relative clause introduces the ordinal.
        from patentlint.analysis.tw_claims import has_possessive_introduction_tw

        intros = {"底座": (1, 1), "控制器": (1, 1)}
        claim = Claim(id=1, text="所述立柱沿垂直於所述底座的第二方向延伸。", independent=True)
        assert has_possessive_introduction_tw(claim.text, [claim], "第二方向", 99, intros)
        # The determiner governing the ordinal itself is a reference.
        claim = Claim(id=1, text="其中該固定的第一抗原結合於該底座。", independent=True)
        assert not has_possessive_introduction_tw(claim.text, [claim], "第一抗原", 99, intros)
        # The element opening its own clause is not what 的 modifies.
        claim = Claim(id=1, text="所述控制器用於網路中的第一轉發裝置。", independent=True)
        assert not has_possessive_introduction_tw(claim.text, [claim], "第一轉發裝置", 99, intros)

    def test_possessor_must_be_introduced(self):
        from patentlint.analysis.tw_claims import has_possessive_introduction_tw

        claim = Claim(id=1, text="一分壓電路連接所述比較器的第一接腳。", independent=True)
        assert not has_possessive_introduction_tw(claim.text, [claim], "第一接腳", 99, {"電路": (1, 1)})


class TestBareObject:
    def test_bare_possessor_in_a_verb_object(self):
        assert "電阻" not in _flagged(
            "1. 一種電路，包括一開關，所述開關的第二端連接電阻的第一端。",
            "2. 如請求項1所述的電路，其中所述電阻的第二端接地。")

    def test_short_noun_at_a_clause_boundary_still_needs_one(self):
        assert "電阻" in _flagged(
            "1. 一種電路，包括一開關，其中，電阻接地。",
            "2. 如請求項1所述的電路，其中所述電阻連接所述開關。")

    def test_action_after_jinxing_is_not_an_element(self):
        assert "排序" in _flagged(
            "1. 一種方法，包括：對多個資料進行排序。",
            "2. 如請求項1所述的方法，其中所述排序依據一權重值。")

    def test_verb_taking_an_object_is_not_a_noun(self):
        assert "識別" in _flagged(
            "1. 一種方法，包括：接收識別該產品的一請求。",
            "2. 如請求項1所述的方法，其中所述識別依據一標籤。")
