"""Wave R - CN 至少一个 right after a determiner (所述至少一个X) is a reference and
no longer introduces itself; the wave K repairs for the "one or more" family
(same-quantifier stem, a skipped key the draft also named article-less, the
possessive part of an introduced owner) carry over to it. Also the 呈,
相比 and 沿 / 沿着 predicate boundaries.

Synthetic shapes only; each test fails with its mechanism disabled.
"""

from patentlint.analysis.cn_claims import check_antecedent_basis_cn, clean_noun_phrase_cn
from patentlint.models import Claim, CnPatentDocument


def _claims(texts):
    return [
        Claim(id=i + 1, text=t, independent=i == 0, dependencies=[] if i == 0 else [1])
        for i, t in enumerate(texts)
    ]


def _cn(*texts):
    return {f["term"] for f in check_antecedent_basis_cn(CnPatentDocument(claims=_claims(texts)))}


def test_at_least_one_reference_without_intro_is_flagged():
    terms = _cn("一种装置，包括一壳体，其中所述至少一个滤波器固定于所述壳体。")
    assert "滤波器" in terms


def test_at_least_one_reference_with_intro_resolves():
    terms = _cn("一种装置，包括一壳体和至少一个滤波器，其中所述至少一个滤波器固定于所述壳体。")
    assert "滤波器" not in terms


def test_at_least_one_possessive_part_keeps_its_registration():
    # Ruling R6: a part of an introduced owner.
    terms = _cn("一种装置，包括一框架，其中所述框架的所述至少一个侧壁包括一塑料。")
    assert "侧壁" not in terms


def test_at_least_one_same_quantifier_shared_stem():
    # Residue on both sides: the intro keys 驱动模块紧固…, the reference 驱动模块来….
    terms = _cn(
        "一种方法，包括：将至少一个驱动模块紧固到一底座；"
        "以及使用该至少一个驱动模块来旋转所述底座。"
    )
    assert not any(t.startswith("驱动模块") for t in terms)


def test_at_least_one_skipped_key_with_an_article_less_mention():
    # 中的对应端子 names 端子 article-less in the parent (CN ruling 2026-10-23).
    terms = _cn(
        "一种连接器，包括多个第一端子和多个第二端子，其中所述多个第一端子与所述多个第二端子中的对应端子接合。",
        "如权利要求1所述的连接器，其中所述至少一个端子与配合的所述端子接触。",
    )
    assert "端子" not in terms


def test_trailing_cheng_is_stripped():
    terms = _cn("一种装置，包括一阀体，其中所述阀芯呈，并且所述阀体连接所述阀芯。")
    assert "阀芯呈" not in terms


def test_interior_cheng_before_its_shape_object():
    terms = _cn("一种装置，包括一底座，其中所述垫片呈U型。")
    assert "垫片" in terms and not any(t.startswith("垫片呈") for t in terms)


def test_cheng_xian_opens_a_word():
    # 呈现 is not cut: 内容呈现模块 is one name.
    terms = _cn("一种装置，包括一处理器，其中所述内容呈现模块连接所述处理器。")
    assert "内容呈现模块" in terms


def test_trailing_comparison_xiangbi():
    terms = _cn("一种结构，包括一通孔，其中一盲孔与所述槽体相比具有较小的直径。")
    assert "槽体" in terms and "槽体相比" not in terms


def test_yan_zhe_coverb_ends_the_reference():
    terms = _cn("一种装置，包括一导轨，其中所述滑块沿着所述导轨移动。")
    assert "滑块" in terms and not any(t.startswith("滑块沿") for t in terms)


def test_bare_yan_coverb_ends_the_reference():
    terms = _cn("一种装置，包括一底座，其中所述转轴沿轴向延伸。")
    assert "转轴" in terms and not any(t.startswith("转轴沿") for t in terms)


def test_yan_inside_an_edge_noun_is_not_cut():
    # 边沿 is "the edge": the interior cut leaves 容器边沿 whole.
    terms = _cn("一种装置，包括一底座，其中所述容器边沿向外翻折。")
    assert "容器边" not in terms


def test_trailing_yan_strip_keeps_an_edge_noun():
    # The trailing 沿 strip used to cut 第一上沿 ("first upper edge") to 第一;
    # after an adverb (基本上沿) it is still the coverb.
    assert clean_noun_phrase_cn("第一上沿") == "第一上沿"
    assert clean_noun_phrase_cn("容器边沿") == "容器边沿"
    assert clean_noun_phrase_cn("辅助层沿") == "辅助层"
