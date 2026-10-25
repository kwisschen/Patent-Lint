"""CN R79 - mirror of TW R66: an introduction whose capture ran into a
predicate still introduces its head. Synthetic shapes only."""

from patentlint.analysis.cn_claims import check_antecedent_basis_cn
from patentlint.models import Claim, CnPatentDocument


def _flagged(c1: str, c2: str | None = None) -> set[str]:
    claims = [Claim(id=1, text=c1, independent=True)]
    if c2:
        claims.append(Claim(id=2, text=c2, independent=False, dependencies=[1]))
    return {f["term"] for f in check_antecedent_basis_cn(CnPatentDocument(claims=claims))}


def _tier(text: str, intro: str, term: str):
    from patentlint.analysis.cn_claims import _predicate_tail_intro_cn

    source = Claim(id=1, text=text, independent=True)
    ref = Claim(id=2, text="2. 根据权利要求1所述者。", independent=False, dependencies=[1])
    return _predicate_tail_intro_cn(term, {intro: (1, 1)}, [source, ref], ref, 0)


def test_verb_taking_an_object():
    assert _tier("1. 一种组件，包括一导线焊接于一基板。", "导线焊接", "导线") == "导线焊接"


def test_coverb_tail():
    # 向 with no object after it: only the coverb signal decides.
    assert _tier("1. 一种装置，包括一推杆向外伸出。", "推杆向", "推杆") == "推杆向"


def test_intro_must_be_a_real_introduction():
    # A bare relative clause is not an introduction; its dirty capture must not
    # become one here.
    assert _tier("1. 一种装置，其中相对应的导线焊接于一基板。", "导线焊接", "导线") is None


def test_end_to_end():
    assert "导线" not in _flagged(
        "1. 一种组件，包括一基板及一导线焊接于所述基板。",
        "2. 根据权利要求1所述的组件，其中所述导线的长度为一预设值。")
