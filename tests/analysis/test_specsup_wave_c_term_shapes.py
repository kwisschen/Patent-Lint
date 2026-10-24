"""Spec-support inventory shapes from wave C (TW, with CN mirrors).

Each test is a synthesized claim set; none is reporter text. Every case fails
when its rule is switched off (checked by disabling each helper in turn).
"""

from patentlint.analysis.cn_spec_support import check_spec_support_cn
from patentlint.analysis.tw_spec_support import check_spec_support_tw
from patentlint.models import Claim, CnPatentDocument, TwPatentDocument


def _claims(texts):
    return [
        Claim(id=i + 1, text=t, independent=i == 0, dependencies=[] if i == 0 else [1])
        for i, t in enumerate(texts)
    ]


def _tw(*texts):
    doc = TwPatentDocument(claims=_claims(texts), embodiment=["本發明關於一種裝置。"])
    return [f.phrase for f in check_spec_support_tw(doc)]


def _cn(*texts):
    doc = CnPatentDocument(claims=_claims(texts), embodiment=["本发明涉及一种装置。"])
    return [f.phrase for f in check_spec_support_cn(doc)]


class TestTwInventoryShapes:
    def test_quantified_back_reference_is_not_an_introduction(self):
        out = _tw(
            "1. 一種夾具，包括至少一夾片及一底座。",
            "2. 如請求項1所述的夾具，其中，所述至少一夾片彎折成型，所述至少一夾片呈L形。",
        )
        assert out == ["夾具", "夾片", "底座"]

    def test_back_reference_stays_when_nothing_introduces_it(self):
        # The extractor can miss the real introduction; the reference is then
        # the element's only inventory entry and must not be dropped.
        out = _tw(
            "1. 一種夾具，包括一底座。",
            "2. 如請求項1所述的夾具，其中，所述多個卡榫設置於邊緣。",
        )
        assert any(t.startswith("卡榫") for t in out)

    def test_connector_fragment_with_text_after_it(self):
        # R67 required the fragment to end the span; text after it hid it.
        from patentlint.analysis.tw_spec_support import _starts_inside_compound_tw

        assert _starts_inside_compound_tw("連接器在鎖固於所述殼體", "器在鎖固於")
        assert _starts_inside_compound_tw("執行器更經", "器更")
        # 執行 with any other suffix is the verb taking a real object.
        assert not _starts_inside_compound_tw("執行層析分離製程", "層析分離製程")

    def test_latin_head_keeps_its_comparison_verb_off(self):
        from patentlint.analysis.tw_spec_support import _spec_support_final_term_tw

        assert _spec_support_final_term_tw("KD等於", "KD等於", "其中，KD等於零。") == "KD"

    def test_actuator_fragment(self):
        out = _tw("1. 一種系統，包括一執行器，其中，該執行器更經一閘道接收一指令。")
        assert "器更" not in out and "執行器" in out

    def test_preposition_word_heads_keep_their_first_character(self):
        out = _tw("1. 一種終端，包括一自動對焦模組及一自然對流散熱片。")
        assert "自動對焦模組" in out and "自然對流散熱片" in out
        assert "動對焦模組" not in out and "然對流散熱片" not in out

    def test_relative_suo_clause_keeps_the_noun(self):
        out = _tw("1. 一種系統，其中當所述處理器接收一感測裝置所量測的一溫度值。")
        assert "感測裝置" in out
        assert not any("所量" in t for t in out)

    def test_made_of_keeps_the_material(self):
        out = _tw("1. 一種電容，其中一隔離層由一石墨片製成。")
        assert "石墨片" in out and "石墨片製" not in out

    def test_comparison_verb_and_cut_off_verb_phrase(self):
        out = _tw(
            "1. 一種方法，其中當一溫度閾值等於一預設值時。",
            "2. 如請求項1所述的方法，其中所述外殼包含有嵌設於所述底座的一墊片。",
        )
        assert "溫度閾值" in out
        assert not any(t.endswith("於") for t in out)

    def test_comparison_verb_stranded_by_the_capture(self):
        out = _tw("1. 一種電路，包括：一輸出頻率等於一參考頻率，一頂部低於一底板。")
        assert "頂部" in out
        assert "頻率等" not in out and "頂部低" not in out

    def test_parenthetical_latin_gloss(self):
        out = _tw("1. 一種電池，包括一硫酸鋰(Li2SO4)及一電極。")
        assert "硫酸鋰" in out and "Li2SO4" not in out

    def test_markush_frame_keeps_its_last_member(self):
        out = _tw("1. 一種組成物，包括一添加劑，所述添加劑選自由甲醇、乙醇及丙二醇所組成之群組。")
        assert "群組" not in out and "丙二醇" in out
        assert not any("組成之" in t for t in out)

    def test_conjunction_exposed_by_an_interior_cut(self):
        out = _tw("1. 一種裝置，包括一第一閥門及至少一第二閥門。")
        assert "第一閥門及" not in out and "第一閥門" in out


class TestTwTwoIntroductionSpan:
    def test_word_internal_yi_is_not_a_second_element(self):
        from patentlint.analysis.tw_spec_support import _spans_two_introductions_tw

        assert _spans_two_introductions_tw("側板延展形成一凸緣", {"凸緣"})
        assert not _spans_two_introductions_tw("四分之一波片", {"波片"})
        assert not _spans_two_introductions_tw("第十一電晶體", {"電晶體"})
        assert not _spans_two_introductions_tw("乳糖一水合物", {"水合物"})
        assert not _spans_two_introductions_tw("數據歸一化", {"化"})


class TestCnMirrors:
    def test_preposition_word_heads(self):
        out = _cn("1. 一种装置，包括一从动齿轮及一自锁机构。")
        assert "从动齿轮" in out and "自锁机构" in out
        assert "动齿轮" not in out and "锁机构" not in out

    def test_comparison_verb_stranded_by_the_capture(self):
        out = _cn("1. 一种方法，其中当一温度阈值等于一预设值时。")
        assert "温度阈值" in out and "温度阈值等" not in out

    def test_parenthetical_latin_gloss(self):
        out = _cn("1. 一种电池，包括一硫酸锂(Li2SO4)及一电极。")
        assert "硫酸锂" in out and "Li2SO4" not in out

    def test_markush_frame_keeps_its_last_member(self):
        out = _cn("1. 一种组合物，包括一添加剂，所述添加剂选自由甲醇、乙醇和丙二醇组成的群组。")
        assert "群组" not in out and "丙二醇" in out
        assert not any("组成的" in t for t in out)


class TestReferenceConfirmedTerms:
    """A run-on term shrinks to the name the drafter refers back to."""

    def test_run_on_shrinks_to_the_referenced_head(self):
        out = _tw("1. 一種散熱器，包括一殼體，所述殼體的一側板延伸成型一凸緣，所述凸緣抵接於所述側板。")
        assert "側板" in out and "側板延伸成型" not in out

    def test_no_reference_no_shrink(self):
        out = _tw("1. 一種散熱器，包括一殼體，所述殼體的一側板延伸成型一凸緣。")
        assert "側板" not in out

    def test_compound_with_a_suffix_head_is_kept(self):
        # 感測 heads 感測器: verb + component suffix is a noun.
        out = _tw("1. 一種裝置，包括一探頭感測器，所述探頭電連接一主機。")
        assert "探頭感測器" in out

    def test_verb_plus_closing_noun_is_left_alone(self):
        # 訊號執行程式 (a name) / 第一層獲得指示 (a run-on) read both ways;
        # neither shrinks, even with the head referenced.
        out = _tw("1. 一種系統，包括一訊號執行程式，其中所述訊號的強度大於一閾值。")
        assert "訊號執行程式" in out

    def test_coordination_is_not_a_predicate(self):
        out = _tw("1. 一種組成物，包括一抗體或其片段，所述抗體為單株抗體。")
        assert not any(t == "抗體" for t in out) or any("片段" in t for t in out)


class TestReferenceConfirmedTermsCn:
    def test_run_on_shrinks_to_the_referenced_head(self):
        out = _cn("1. 一种散热器，包括一壳体，所述壳体的一侧板延伸成型一凸缘，所述凸缘抵接于所述侧板。")
        assert "侧板" in out and "侧板延伸成型" not in out

    def test_relative_clause_head_is_not_shrunk_away(self):
        out = _cn("1. 一种方法，包括：发送一发送时长有关的信息，其中所述发送时长的单位为毫秒。")
        assert "发送时长" not in out or any("信息" in t for t in out)
