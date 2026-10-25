"""Wave E - the bare 輸出 / 輸入 element survives normalization (ruling R4),
and a method step names its own verb (ruling R7), both 2026-10-25.

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


class TestTwNormalizer:
    def test_bare_and_ordinal_io_nouns_survive(self):
        for term in ("輸出", "輸入", "第一輸出", "第二輸入", "一輸出"):
            assert clean_noun_phrase_tw(term) == term

    def test_set_as_is_the_predicate(self):
        assert clean_noun_phrase_tw("一輸出設定為一警示值") == "一輸出"
        assert clean_noun_phrase_tw("輸出設定成該預設模式") == "輸出"
        # Without 為 / 成 the noun 輸出設定 ("output setting") is kept.
        assert clean_noun_phrase_tw("輸出設定") == "輸出設定"

    def test_couple_to_is_the_predicate(self):
        assert clean_noun_phrase_tw("輸出耦合至所述比較器") == "輸出"
        assert clean_noun_phrase_tw("偵測線圈耦接至該節點") == "偵測線圈"

    def test_coupling_adverb_goes_with_the_verb(self):
        assert clean_noun_phrase_tw("開關節點電耦合至該電感器") == "開關節點"
        assert clean_noun_phrase_tw("介面通信耦合至一主機") == "介面"
        # Bare 光 is part of the noun, not an adverb.
        assert clean_noun_phrase_tw("照射光耦合至該波導") == "照射光"
        # A noun ending in 電 before 耦合 keeps its head.
        assert clean_noun_phrase_tw("電源耦合至該負載") == "電源"

    def test_connection_point_is_a_noun(self):
        assert clean_noun_phrase_tw("輸出連接處的電流") == "輸出連接"

    def test_bare_io_compound_is_not_cut(self):
        # 連接 / 旋轉 are interior verbs; the whole capture is the element name.
        assert clean_noun_phrase_tw("輸出連接") == "輸出連接"
        assert clean_noun_phrase_tw("第一輸出旋轉") == "第一輸出旋轉"


class TestTwWalker:
    def test_a_verb_gives_no_basis_to_its_noun(self):
        # Ruling R4: the only earlier 輸出 is the verb.
        assert "輸出" in _tw(
            "1. 一種系統，包括一控制器及一記錄器，所述控制器輸出一警示值，"
            "所述記錄器接收該輸出。")

    def test_set_as_introduces_the_output(self):
        assert "輸出" not in _tw(
            "1. 一種方法，包括：將一輸出設定為一警示值；以及因應於該輸出為該警示值，"
            "啟動一蜂鳴器。")

    def test_method_step_names_its_verb(self):
        assert "輸出" not in _tw(
            "1. 一種校正方法，包括：計算一偏移量；以及在一面板上輸出所述偏移量。",
            "2. 如請求項1所述的校正方法，其中所述輸出所述偏移量包括閃爍一指示燈。")

    def test_method_step_described_by_baokuo(self):
        assert "輸出" not in _tw(
            "1. 一種校正方法，包括：計算一偏移量；以及在一面板上輸出所述偏移量。",
            "2. 如請求項1所述的校正方法，其中所述輸出包括閃爍一指示燈。")

    def test_apparatus_output_is_still_a_thing(self):
        # Not a method claim and no object after the reference: R4 governs.
        assert "輸出" in _tw(
            "1. 一種校正裝置，包括一處理器，所述處理器輸出一偏移量。",
            "2. 如請求項1所述的校正裝置，其中所述輸出包括一數值。")


class TestTwPossessiveCoordinator:
    @staticmethod
    def _intro(text, term, intros):
        from patentlint.analysis.tw_claims import has_possessive_introduction_tw

        claim = Claim(id=1, text=text, independent=True)
        return has_possessive_introduction_tw(text, [claim], term, len(text), intros)

    def test_coordinator_ends_the_possessed_noun(self):
        assert self._intro("基於所述轉換單元的輸出及一控制訊號產生一影像。", "輸出", {"轉換單元": (1, 1)})

    def test_huo_ends_the_possessed_noun(self):
        assert self._intro("生成用於執行所述節點的次序或調度。", "次序", {"節點": (1, 1)})

    def test_noun_continuing_past_the_term_still_blocks(self):
        assert not self._intro("基於所述轉換單元的輸出電流產生一影像。", "輸出", {"轉換單元": (1, 1)})


class TestCn:
    def test_bare_and_ordinal_io_nouns_survive(self):
        for term in ("输出", "输入", "第一输出", "第二输入", "一输出"):
            assert clean_noun_phrase_cn(term) == term

    def test_bare_io_compound_is_not_cut(self):
        assert clean_noun_phrase_cn("输出连接") == "输出连接"
        assert clean_noun_phrase_cn("第一输出旋转") == "第一输出旋转"

    def test_set_as_and_couple_to(self):
        assert clean_noun_phrase_cn("一输出设定为一警示值") == "一输出"
        assert clean_noun_phrase_cn("输出耦合至所述比较器") == "输出"
        assert clean_noun_phrase_cn("输出连接处的电流") == "输出连接"
        assert clean_noun_phrase_cn("接地平面可操作地耦接至所述外壳") == "接地平面"

    def test_a_verb_gives_no_basis_to_its_noun(self):
        assert "输出" in _cn(
            "1. 一种系统，包括控制器和记录器，所述控制器输出一警示值，所述记录器用于接收所述输出。")

    def test_method_step_names_its_verb(self):
        assert "输出" not in _cn(
            "1. 一种校正方法，包括：计算偏移量；以及在面板上输出所述偏移量。",
            "2. 根据权利要求1所述的校正方法，其特征在于，所述输出所述偏移量包括闪烁指示灯。")


class TestGeometryPartRuling:
    """Ruling R6 (2026-10-25): 所述X的所述Y with X introduced gives Y basis only
    when Y is a geometry part; a terminal still flags."""

    def test_geometry_part_of_an_introduced_owner(self):
        assert "頂面" not in _tw(
            "1. 一種容器，包括一殼體，所述殼體的所述頂面設有一開口。")
        assert "顶面" not in _cn(
            "1. 一种容器，包括壳体，所述壳体的所述顶面设有开口。")

    def test_terminal_still_flags(self):
        assert "控制端" in _tw(
            "1. 一種電路，包括一開關，所述開關的所述控制端連接一電阻。")
        assert "控制端" in _cn(
            "1. 一种电路，包括开关，所述开关的所述控制端连接电阻。")

    def test_owner_must_be_introduced(self):
        assert "頂面" in _tw(
            "1. 一種容器，包括一蓋板，所述殼體的所述頂面設有一開口。")


class TestIoAttributiveIntro:
    def test_attributive_head_in_an_introducing_clause(self):
        assert "輸出連接" not in _tw(
            "1. 一種轉換器，包括一開關串，其中所述轉換器更包括所述開關串之中的輸出連接，"
            "且所述輸出連接處的電壓被維持。")
        assert "输出" not in _cn(
            "1. 一种电路，包括比较器，所述比较器具有连接到所述电路的第一输入和耦合到半桥电路的输出。",
            "2. 根据权利要求1所述的电路，其中所述输出经由触发器耦合到所述半桥电路。")

    def test_attributive_head_outside_an_introducing_clause_still_flags(self):
        # TW: no introducing verb in the clause, so the 的 phrase is not an intro.
        assert "輸出" in _tw(
            "1. 一種電路，包括一比較器，所述比較器用於接收半橋電路的輸出。",
            "2. 如請求項1所述的電路，其中所述輸出經由一觸發器耦合到所述半橋電路。")

    def test_couple_to_a_comparative(self):
        assert clean_noun_phrase_cn("第一端耦接至大于所述输入端子处的电压") == "第一端"
        # 于 is not a noun character, so the capture stops at the comparative head.
        assert clean_noun_phrase_cn("第一端耦接至大") == "第一端"


class TestIoRotation:
    def test_output_rotation_is_one_name(self):
        assert clean_noun_phrase_cn("输出旋转通过所述中心轴传递出去") == "输出旋转"
        assert clean_noun_phrase_tw("輸出旋轉經由該軸傳遞") == "輸出旋轉"

    def test_earlier_mention_before_a_coverb_introduces(self):
        assert not {"输入旋转", "输出旋转"} & _cn(
            "1. 一种减速器，包括驱动齿圈，其特征在于，输入旋转通过所述驱动齿圈传递；以及，"
            "输出旋转通过所述驱动齿圈传递出去；其中，当所述输入旋转通过所述驱动齿圈传递时，"
            "所述输出旋转通过所述驱动齿圈传递出去。")


class TestOwnerNamedWithAbbreviation:
    def test_possessive_owner_written_with_its_abbreviation(self):
        assert "輸出" not in _tw(
            "1. 一種顯示控制器，包括：高動態範圍(HDR)單元，被配置以接收多個層資料；以及摻合器，"
            "被配置以基於所述高動態範圍單元的輸出及第二控制訊號產生影像資料，並且基於"
            "所述高動態範圍單元的所述輸出產生畫素資料。")


class TestListFinalItemTw:
    def test_last_list_item_after_ji_introduces(self):
        assert "強化纖維基材" not in _tw(
            "1. 一種預浸體，具備一樹脂組成物，及強化纖維基材。",
            "2. 如請求項1之預浸體，其中前述強化纖維基材的厚度為一預設值。")

    def test_last_list_item_after_yiji_introduces(self):
        assert "定頻振盪訊號" not in _tw(
            "1. 一種電路，基於一電流訊號、一誤差訊號、以及定頻振盪訊號，產生一驅動訊號。",
            "2. 如請求項1所述的電路，其中所述定頻振盪訊號的頻率為一預設值。")


class TestOneCharacterDrops:
    """Wave E item 6: references the normalizer cut to one character, which the
    walker drops without checking (TW R75 / CN R81)."""

    def test_bao_and_bijiao_are_words(self):
        assert clean_noun_phrase_tw("電池包") == "電池包"
        assert clean_noun_phrase_tw("第二包") == "第二包"
        assert clean_noun_phrase_tw("比較") == "比較"
        assert clean_noun_phrase_cn("数据包") == "数据包"
        assert clean_noun_phrase_cn("比较") == "比较"
        # The stranded head of 包括 still strips.
        assert clean_noun_phrase_tw("驅動模組還包") == "驅動模組"

    def test_battery_pack_reference_is_checked(self):
        assert "電池包" in _tw(
            "1. 一種車輛，包括一車架，所述車架承載一馬達。",
            "2. 如請求項1所述的車輛，其中所述電池包具有一外殼。")

    def test_comparison_names_the_step(self):
        assert "比較" not in _tw(
            "1. 一種校正方法，包括：將一量測值與一閾值進行比較；及基於該比較，調整一增益。")
        assert "比较" not in _cn(
            "1. 一种校正方法，包括：将测量值与阈值进行比较；以及基于该比较，调整增益。")
