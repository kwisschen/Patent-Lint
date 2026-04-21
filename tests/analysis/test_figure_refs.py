# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Tests for patentlint.analysis.figure_refs."""

import pytest

from patentlint.analysis.figure_refs import (
    CN_PARSER,
    TW_PARSER,
    US_PARSER,
)


# ── US singletons and classic forms ────────────────────────────────────


@pytest.mark.parametrize(
    "text, expected",
    [
        ("FIG. 1", {"1"}),
        ("Fig. 1", {"1"}),
        ("FIG 1", {"1"}),
        ("Figure 1", {"1"}),
        ("FIG. 1A", {"1A"}),
        ("FIG. 1(a)", {"1A"}),
        ("FIGS. 1 to 3", {"1", "2", "3"}),
        ("FIGS. 1-3", {"1", "2", "3"}),
        ("FIGS. 1\u20133", {"1", "2", "3"}),
        ("FIGS. 1 through 3", {"1", "2", "3"}),
        ("FIGS. 2A to 2C", {"2A", "2B", "2C"}),
    ],
    ids=[
        "FIG_dot_1",
        "Fig_dot_1",
        "FIG_no_dot",
        "Figure_spelled",
        "suffix_bare",
        "suffix_paren",
        "range_to",
        "range_hyphen",
        "range_endash",
        "range_through",
        "range_alpha",
    ],
)
def test_us_singletons(text, expected):
    assert US_PARSER.extract(text).ids == expected


# ── US enumeration ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text, expected",
    [
        ("FIGS. 1, 2 and 3", {"1", "2", "3"}),
        ("FIGS. 1, 2, and 3", {"1", "2", "3"}),
        ("FIGS. 1, 2, 3", {"1", "2", "3"}),
        ("FIGS. 1 and 5", {"1", "5"}),
        ("FIG. 1 and 2", {"1", "2"}),
    ],
    ids=[
        "comma_and",
        "oxford_comma",
        "comma_only",
        "and_is_list_not_range",
        "singular_fig_and",
    ],
)
def test_us_enumeration(text, expected):
    assert US_PARSER.extract(text).ids == expected


# ── TW singletons ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text, expected",
    [
        ("圖1", {"1"}),
        ("圖5A", {"5A"}),
        ("第1圖", {"1"}),
        ("第5A圖", {"5A"}),
    ],
    ids=["prefix_num", "prefix_suffix", "sfx_prefix_num", "sfx_prefix_suffix"],
)
def test_tw_singletons(text, expected):
    assert TW_PARSER.extract(text).ids == expected


# ── TW ranges ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text, expected",
    [
        ("圖1至圖3", {"1", "2", "3"}),
        ("圖1到圖3", {"1", "2", "3"}),
        ("圖1～圖3", {"1", "2", "3"}),
        ("圖1～3", {"1", "2", "3"}),
        ("圖1-3", {"1", "2", "3"}),
        ("圖1\u2013圖3", {"1", "2", "3"}),
        ("圖5A至圖5C", {"5A", "5B", "5C"}),
        ("圖5A～5C", {"5A", "5B", "5C"}),
    ],
    ids=[
        "zhi", "dao", "fullwidth_tilde", "tilde_bare",
        "hyphen", "endash", "alpha_zhi", "alpha_tilde_bare",
    ],
)
def test_tw_ranges(text, expected):
    assert TW_PARSER.extract(text).ids == expected


# ── TW enumeration ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text, expected",
    [
        ("圖1、圖2、圖3", {"1", "2", "3"}),
        ("圖1、2、3", {"1", "2", "3"}),
        ("圖1及圖2", {"1", "2"}),
        ("圖1與圖3", {"1", "3"}),
        ("圖1、圖2及圖3", {"1", "2", "3"}),
        ("圖1至圖3及圖7", {"1", "2", "3", "7"}),
    ],
    ids=[
        "dunhao_prefix", "dunhao_bare", "ji", "yu_list_not_range",
        "dunhao_ji", "range_then_list",
    ],
)
def test_tw_enumeration(text, expected):
    assert TW_PARSER.extract(text).ids == expected


# ── TW compound-noun negatives ─────────────────────────────────────────


@pytest.mark.parametrize(
    "text",
    [
        "世界地圖100",
        "電子地圖510",
        "連結縮圖511",
        "代表縮圖701",
        "使用者縮圖801",
        "示意圖",
        "流程圖",
        "架構圖",
        "預覽影像705～714",
        "步驟S301",
    ],
    ids=[
        "ditu_100", "dianzi_ditu_510", "suotu_511", "daibiao_suotu_701",
        "user_suotu_801", "shiyitu", "liuchengtu", "jiagoutu",
        "preview_range", "step_S301",
    ],
)
def test_tw_compound_noun_negatives(text):
    assert TW_PARSER.extract(text).ids == frozenset()


# ── TW mixed forms ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text, expected",
    [
        ("第1圖與圖2", {"1", "2"}),
        ("參見圖1及圖5A", {"1", "5A"}),
    ],
    ids=["sfx_prefix_and_prefix", "canjian_prefix"],
)
def test_tw_mixed(text, expected):
    assert TW_PARSER.extract(text).ids == expected


# ── TW realistic paragraph (110P000368 regression) ─────────────────────


_TW_BRIEF = """圖1顯示推薦適地性數位內容的系統架構實施例圖；
圖2顯示推薦適地性數位內容的系統中伺服系統與使用者裝置之功能元件實施例圖；
圖3顯示推薦適地性數位內容的方法中形成使用者喜好的實施例流程圖；
圖4顯示推薦適地性數位內容的方法實施例流程圖；
圖5顯示實現推薦適地性數位內容的方法的軟體程式的主頁實施例示意圖；
圖6顯示推薦適地性數位內容的方法中播放數位內容的實施例流程圖；
圖7顯示實現推薦適地性數位內容的方法的軟體程式的數位內容預覽頁面實施例示意圖；
圖8顯示實現推薦適地性數位內容的方法的軟體程式的數位內容播放頁實施例示意圖；
圖9顯示推薦適地性數位內容的方法中形成推薦的主題標籤的實施例流程圖；以及
圖10顯示形成推薦的主題標籤的方法中採用位置區塊的實施例流程圖。"""

_TW_DETAILED = """圖1顯示推薦適地性數位內容的系統架構實施例圖，如圖所示，系統提出一個伺服系統12，通過網路10向終端各種使用者裝置101, 103提供數位內容服務。
圖2顯示推薦適地性數位內容的系統中伺服系統與使用者裝置之功能元件實施例圖。
圖3顯示推薦適地性數位內容的方法中形成使用者喜好的實施例流程圖。
圖5顯示實現推薦適地性數位內容的方法的軟體程式的主頁實施例示意圖，其中執行於使用者裝置中的瀏覽程式啟始以一電子地圖510為背景的圖形使用者介面。
主頁50的影像，其中可以電子地圖510為背景影像。
圖中顯示主頁50中包括多個連結縮圖511、513、515。
圖6顯示推薦適地性數位內容的方法中播放數位內容的實施例流程圖。
預覽頁面可參考圖7顯示的數位內容預覽頁面實施例示意圖，其中顯示一數位內容預覽頁面70，畫面中範例顯示有代表縮圖701與主題標籤703。
圖8顯示一數位內容播放頁80，其中顯示播放中的數位內容，其他資訊還有使用者縮圖801。
根據圖9所示形成推薦的主題標籤的實施例流程圖，可參考圖10顯示採用位置區塊的實施例圖，將世界地圖100切割為多個區塊。
圖4顯示推薦適地性數位內容的方法實施例流程圖。"""

_EXPECTED_FIGS = {str(i) for i in range(1, 11)}
_FALSE_POSITIVES = {"100", "504", "510", "511", "701", "801"}


def test_tw_realistic_110P000368():
    brief_result = TW_PARSER.extract(_TW_BRIEF)
    detailed_result = TW_PARSER.extract(_TW_DETAILED)

    assert brief_result.ids == _EXPECTED_FIGS
    assert detailed_result.ids == _EXPECTED_FIGS
    assert brief_result.ids & detailed_result.ids == _EXPECTED_FIGS
    assert brief_result.ids & _FALSE_POSITIVES == frozenset()
    assert detailed_result.ids & _FALSE_POSITIVES == frozenset()


# ── CN singletons and forms ────────────────────────────────────────────


@pytest.mark.parametrize(
    "text, expected",
    [
        ("图1", {"1"}),
        ("附图1", {"1"}),
        ("第1图", {"1"}),
        ("图5A", {"5A"}),
        ("图1至图3", {"1", "2", "3"}),
        ("图1、图2、图3", {"1", "2", "3"}),
        ("图1、2、3", {"1", "2", "3"}),
        ("图1与图3", {"1", "3"}),
        ("图1和图2", {"1", "2"}),
    ],
    ids=[
        "tu", "futu", "di_N_tu", "suffix", "range_zhi",
        "dunhao_prefix", "dunhao_bare", "yu_list", "he_list",
    ],
)
def test_cn_singletons(text, expected):
    assert CN_PARSER.extract(text).ids == expected


# ── CN compound-noun negatives ─────────────────────────────────────────


@pytest.mark.parametrize(
    "text",
    [
        "示意图",
        "流程图",
        "电子地图510",
    ],
    ids=["shiyitu", "liuchengtu", "dianzi_ditu_510"],
)
def test_cn_negatives(text):
    assert CN_PARSER.extract(text).ids == frozenset()


# ── Ordered preservation ───────────────────────────────────────────────


def test_ordered_preserved():
    text = "FIG. 3 shows X. FIG. 1 shows Y. FIG. 2 shows Z."
    result = US_PARSER.extract(text)
    assert result.ordered == ("3", "1", "2")


def test_ordered_deduplicates():
    text = "FIG. 1 shows X. FIG. 2 shows Y. FIG. 1 shows Z again."
    result = US_PARSER.extract(text)
    assert result.ordered == ("1", "2")


# ── Span accuracy ─────────────────────────────────────────────────────


def test_spans_accurate_singleton():
    text = "See FIG. 1 for details."
    result = US_PARSER.extract(text)
    assert len(result.spans) == 1
    start, end = result.spans[0]
    assert text[start:end] == "FIG. 1"


def test_spans_accurate_range():
    text = "See FIGS. 1-3 for details."
    result = US_PARSER.extract(text)
    assert len(result.spans) == 1
    start, end = result.spans[0]
    assert text[start:end] == "FIGS. 1-3"


# ── TW view-type figures (NOT blocked by guard) ──────────────────────────


@pytest.mark.parametrize(
    "text, expected",
    [
        ("俯視圖5", {"5"}),
        ("剖視圖3", {"3"}),
        ("立體圖2", {"2"}),
        ("爆炸圖1", {"1"}),
        ("側視圖4A", {"4A"}),
    ],
    ids=["fuShiTu", "pouShiTu", "liTiTu", "baoZhaTu", "ceShiTu_suffix"],
)
def test_tw_view_type_figures_not_blocked(text, expected):
    assert TW_PARSER.extract(text).ids == expected


# ── TW verbal reference contexts (NOT blocked) ──────────────────────────


@pytest.mark.parametrize(
    "text, expected",
    [
        ("如圖1所示", {"1"}),
        ("參見圖3", {"3"}),
        ("根據圖9", {"9"}),
        ("參考圖10", {"10"}),
        ("請參閱圖2", {"2"}),
        ("配合圖6", {"6"}),
    ],
    ids=["ruTu", "canJian", "genJu", "canKao", "canYue", "peiHe"],
)
def test_tw_verbal_reference_contexts(text, expected):
    assert TW_PARSER.extract(text).ids == expected


# ── TW blocklist compounds (BLOCKED by guard) ───────────────────────────


@pytest.mark.parametrize(
    "text",
    [
        "地圖100",
        "縮圖511",
        "示意圖5",
        "流程圖3",
        "架構圖1",
        "略圖2",
        "草圖7",
        "藍圖99",
        "版圖300",
        "拼圖8",
        "製圖4",
    ],
    ids=[
        "diTu", "suoTu", "shiYiTu", "liuChengTu", "jiaGouTu",
        "lueTu", "caoTu", "lanTu", "banTu", "pinTu", "zhiTu",
    ],
)
def test_tw_blocklist_compounds(text):
    assert TW_PARSER.extract(text).ids == frozenset()


# ── TW adversarial edge cases ────────────────────────────────────────────


@pytest.mark.parametrize(
    "text, expected",
    [
        ("圖", set()),
        ("圖A", set()),
        ("圖0", {"0"}),
        ("圖01", {"01"}),
        ("圖1後接圖2", {"1", "2"}),
    ],
    ids=["bare_tu", "tu_letter_only", "tu_zero", "tu_leading_zero", "tu_mid_sentence"],
)
def test_tw_adversarial(text, expected):
    assert TW_PARSER.extract(text).ids == expected


# ── CN verbal and view-type (NOT blocked) ────────────────────────────────


@pytest.mark.parametrize(
    "text, expected",
    [
        ("如图1所示", {"1"}),
        ("参见图3", {"3"}),
        ("根据图9", {"9"}),
        ("俯视图5", {"5"}),
        ("剖视图3", {"3"}),
        ("立体图2", {"2"}),
    ],
    ids=["ruTu", "canJian", "genJu", "fuShiTu", "pouShiTu", "liTiTu"],
)
def test_cn_verbal_and_view_type(text, expected):
    assert CN_PARSER.extract(text).ids == expected
