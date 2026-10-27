"""Wave Q (CN R93 / TW R89 / US R61) - measure words, connection clauses, 并排, 距离.

Synthetic shapes only; each test fails with its mechanism disabled.
"""

from patentlint.analysis.claims import check_antecedent_basis as check_us
from patentlint.analysis.cn_claims import check_antecedent_basis_cn, clean_noun_phrase_cn
from patentlint.analysis.tw_claims import check_antecedent_basis, clean_noun_phrase_tw
from patentlint.models import Claim, CnPatentDocument, TwPatentDocument
from patentlint.parser.claims import parse_claims


def _claims(texts):
    return [
        Claim(id=i + 1, text=t, independent=i == 0, dependencies=[] if i == 0 else [1])
        for i, t in enumerate(texts)
    ]


def _tw(*texts):
    return {f["term"] for f in check_antecedent_basis(TwPatentDocument(claims=_claims(texts)))}


def _cn(*texts):
    return {f["term"] for f in check_antecedent_basis_cn(CnPatentDocument(claims=_claims(texts)))}


# --- cardinal + measure word (#974 / #975) ----------------------------------------

def test_cn_cardinal_measure_word_introduces_the_bare_noun():
    assert _cn("一种接口，所述接口的壳体设置有若干根信号端子，所述信号端子镀金。") == set()


def test_cn_measure_word_before_a_determiner_reference():
    assert _cn("一种装置，包括底板和两条导线，两条所述导线固定于所述底板。") == set()


def test_cn_classifier_reference_resolves():
    assert _cn("一种装置，包括底板和两条导线，所述条导线固定于所述底板。") == set()


def test_cn_measure_word_that_opens_a_word_is_kept():
    # 条形 is "strip-shaped": both sides keep it, so they still pair.
    assert clean_noun_phrase_cn("两条形槽") != "形槽"
    assert _cn("一种装置，包括两条形槽，所述两条形槽平行。") == set()


def test_tw_cardinal_measure_word_introduces_the_bare_noun():
    assert _tw("一種支架，由四根彎狀桿件構成，該彎狀桿件的一端固定。") == set()


def test_tw_classifier_reference_resolves():
    assert _tw("一種裝置，包括一底板及兩條導線，該條導線固定於所述底板。") == set()


# --- capture-final 电连接 (#975) -----------------------------------------------------

def test_cn_capture_final_electrical_connection_is_the_verb():
    assert clean_noun_phrase_cn("导线电连接") == "导线"
    assert clean_noun_phrase_cn("导管可拆卸地电连接") == "导管"


def test_cn_electrical_connector_nouns_are_kept():
    assert clean_noun_phrase_cn("电连接件") == "电连接件"
    assert clean_noun_phrase_cn("所述电连接") != "所述"


def test_tw_capture_final_electrical_connection_is_the_verb():
    assert clean_noun_phrase_tw("導線電連接") == "導線"


# --- connection clause introduces (CN article-less ruling / TW R15) ----------------

def test_cn_coverb_object_before_a_connection_verb_introduces():
    assert _cn("一种装置，包括底板，所述底板通过信号导线电连接于一壳体；所述信号导线为铜线。") == set()


def test_cn_clause_final_connection_with_a_comitative_introduces():
    assert "插座结构" not in _cn("一种装置，包括底板，所述底板与插座结构连接，所述插座结构具有凹槽。")


def test_cn_network_connection_is_a_noun():
    assert "网络" in _cn("一种方法，包括：建立网络连接；其中所述网络为局域网。")


def test_tw_coverb_object_before_a_connection_verb_introduces():
    assert _tw("一種裝置，包括一底板，所述底板經由信號導線電連接於一殼體；所述信號導線為銅線。") == set()


def test_tw_connection_clause_with_a_comitative_introduces():
    assert "控制信號端" not in _tw("一種電路，包括一開關，所述開關的控制端與控制信號端電連接，所述控制信號端接收信號。")


def test_tw_locative_before_a_connection_verb_does_not_introduce():
    # Ruling R15 covers connection clauses with 與 / 通過 / 經由, not 在X連接至.
    assert "轉動關節" in _tw("一種裝置，包括一手臂，在轉動關節連接至該手臂，且所述轉動關節旋轉。")


# --- 并排 (#973) and 距离 (#976) ---------------------------------------------------

def test_cn_side_by_side_adverb_is_cut():
    assert clean_noun_phrase_cn("第二方向并排设置") == "第二方向"
    assert clean_noun_phrase_cn("并联电路") == "并联电路"


def test_tw_side_by_side_adverb_is_cut():
    assert clean_noun_phrase_tw("第二方向並排設置") == "第二方向"


def test_cn_distance_before_a_determiner_is_the_coverb():
    assert clean_noun_phrase_cn("导线距离所述底板") == "导线"
    assert _cn("一种装置，包括底板和导线，所述导线距离所述底板的高度小于1毫米。") == set()


# --- US: the N or more X (#972) ---------------------------------------------------

def test_us_cardinal_before_or_more_is_not_a_term():
    doc = parse_claims(
        "1. A module, comprising a base and a spacer.\n"
        "2. The module according to claim 1, wherein a number of spacers is two or more, "
        "and the two or more spacers are aligned."
    )
    assert "two" not in {f.get("term") for f in check_us(doc)}


def test_cn_reference_keeping_its_cardinal_measure_word_resolves():
    assert _cn("一种装置，包括驱动手的四根成排手指，所述四根成排手指可弯曲。") == set()


def test_tw_reference_keeping_its_cardinal_measure_word_resolves():
    assert _tw("一種支架，由四根彎狀桿件構成，該四根彎狀桿件的一端固定。") == set()
