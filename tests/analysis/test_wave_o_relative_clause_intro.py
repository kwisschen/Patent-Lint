"""Wave O (TW R87 / CN R91) - rulings R13 and R14 (2026-10-27).

The article-less object of an introducing verb is an introduction even with a
relative clause in between, and so is a bare participle V的X.

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


# --- TW ------------------------------------------------------------------------

def test_tw_object_behind_a_relative_clause_introduces():
    terms = _tw(
        "一種終端，包括：一處理器，被配置為從一伺服器接收指示要使用的一參數的通知；以及",
        "如請求項1所述的終端，其中該所接收的通知還指示一期限。",
    )
    assert "通知" not in terms


def test_tw_bare_participle_introduces():
    assert "代碼" not in _tw("一種方法，包括：顯示自一伺服器接收的代碼；以及儲存該代碼。")


def test_tw_withheld_verb_still_flags():
    # 儲存 stays withheld; 輸入 joined the list in wave R (noun-guarded).
    assert "通知" in _tw("一種方法，包括：儲存指示一參數的通知；以及顯示該通知。")


def test_tw_wave_p_execute_introduces_its_object():
    # Wave P: 執行 and 形成 join the list (their gold-legit were R13 gold errors).
    assert "重選程序" not in _tw(
        "一種方法，包括：接收一配置訊息，該配置訊息指示是否執行考慮多個切片組的優先級的重選程序；以及執行該重選程序。"
    )


def test_tw_wave_p_form_introduces_its_object():
    assert "製程圖案" not in _tw("一種方法，包括：接收一設計佈局，以形成半導體裝置的製程圖案；以及修正該製程圖案。")


def test_tw_verb_plus_noun_tail_is_a_noun():
    # 接收器的信號: the receiver's signal, not the object of 接收.
    assert "信號" in _tw("一種裝置，包括一殼體，其中接收端的信號被放大，且該信號被濾波。")


def test_tw_verb_inside_a_reference_does_not_introduce():
    assert "推論" in _tw(
        "一種模型，包括：一輸入層，接收一輸入；一輸出層，基於該等接收輸入的推論而輸出；其中該推論為一分數。"
    )


def test_tw_closed_participle_does_not_govern_a_later_noun():
    assert "輸出電壓" in _tw(
        "一種轉換器，用以將在一節點處接收的輸入電壓轉換成另一節點處的輸出電壓，該輸出電壓為直流。"
    )


def test_tw_verb_inside_a_locative_does_not_introduce():
    assert "環境光" in _tw(
        "一種感測器，被配置以量測在包括顯示層的空間中的環境光，且該環境光被記錄。"
    )


def test_tw_determiner_in_the_remainder_does_not_introduce():
    assert "通知" in _tw("一種方法，包括：接收該伺服器發出的通知；以及儲存該通知。")


# --- CN ------------------------------------------------------------------------

def test_cn_object_behind_a_relative_clause_introduces():
    assert "参考层" not in _cn("一种结构，包括具有固定方向的参考层；其中所述参考层为铁磁体。")


def test_cn_bare_participle_introduces():
    assert "信息" not in _cn("一种系统，包括：控制器，被配置为基于从传感器接收的信息，控制电池；其中所述信息包括压力。")



def test_cn_wave_p_execute_introduces_its_object():
    assert "重选过程" not in _cn(
        "一种方法，包括：接收配置消息，所述配置消息指示是否执行考虑多个切片组的优先级的重选过程；以及执行所述重选过程。"
    )


def test_cn_wave_p_form_introduces_its_object():
    assert "第二层" not in _cn(
        "一种方法，包括：在线上挤出第一层，以及在所述第一层上形成不同聚合物的第二层。",
        "根据权利要求1所述的方法，其中所述第二层为氟聚合物。",
    )
