"""TW R66 - an introduction whose capture ran into a predicate still introduces
its head. Synthetic shapes only; the rule keys on grammar, never subject matter."""

from patentlint.analysis.tw_claims import check_antecedent_basis
from patentlint.models import Claim, TwPatentDocument


def _flagged(c1: str, c2: str | None = None) -> set[str]:
    claims = [Claim(id=1, text=c1, independent=True)]
    if c2:
        claims.append(Claim(id=2, text=c2, independent=False, dependencies=[1]))
    return {f["term"] for f in check_antecedent_basis(TwPatentDocument(claims=claims))}


def test_coverb_tail_with_an_object():
    assert "第一推出力" not in _flagged(
        "1. 一種裝置，包括：一底座及兩個插塊，所述底座能允許其中一個所述插塊以一第一推出力自其推出，"
        "並且允許另一個所述插塊以一第二推出力自其推出，並且所述第二推出力介於所述第一推出力的50%～60%之間。")


def test_two_character_verb_taking_an_object():
    assert "感測端" not in _flagged(
        "1. 一種電路，包括：一比較器，所述比較器的感測端耦接一基準電壓。",
        "2. 如請求項1所述的電路，更包括一分壓電路，連接所述比較器的所述感測端。")


def test_locative_postposition():
    assert "待機模式" not in _flagged(
        "1. 一種方法，用於一按鍵陣列且執行於一待機模式下的偵測。",
        "2. 如請求項1所述的方法，其中一處理器由一喚醒模式返回到該待機模式。")


def _tier(text: str, intro: str, term: str):
    from patentlint.analysis.tw_claims import _predicate_tail_intro_tw
    source = Claim(id=1, text=text, independent=True)
    ref = Claim(id=2, text="2. 如請求項1所述者。", independent=False, dependencies=[1])
    return _predicate_tail_intro_tw(term, {intro: (1, 1)}, [source, ref], ref, 0)


def test_tier_accepts_a_quantified_intro():
    assert _tier("1. 一種裝置，產生一回應資料向一主機發送。", "回應資料向", "回應資料") == "回應資料向"


def test_a_lone_coverb_is_a_predicate():
    assert _tier("1. 一種方法，輸出一低電位對形成於一導線的電容放電。", "低電位對", "低電位") == "低電位對"
    assert _tier("1. 一種系統，產生一警示訊號至一顯示面板。", "警示訊號至一顯示面板", "警示訊號") is not None


def test_dui_lexemes_are_not_coverbs():
    # 對位孔 is a noun ("alignment hole"): 標記 must not resolve against it.
    assert _tier("1. 一種板材，包括一標記對位孔。", "標記對位孔", "標記") is None


def test_verb_ending_in_yu():
    assert _tier("1. 一種板材，包括一隔離部，一兩側外露於一芯層。", "兩側外露於", "兩側") == "兩側外露於"


def test_relative_clause_capture_is_not_an_introduction():
    # `<VP>的X` is not an introduction in TW; a dirty capture of one must not
    # become one through this tier (8 gold-legit were silenced without this).
    assert _tier("1. 一種裝置，獲得與一命令相對應的回應資料向一主機發送。",
                 "回應資料向", "回應資料") is None


def test_coordinator_is_not_a_predicate():
    assert _tier("1. 一種電路，包括一第二節點與一第一節點之間的電阻。",
                 "第二節點與", "第二節點") is None


def test_ordinal_possessive_with_an_introduced_possessor_counts():
    # Wave C ruling (2026-10-24): the R9 ordinal exclusion is lifted when the
    # possessor is itself introduced.
    assert "第一輸入端" not in _flagged(
        "1. 一種電路，包括：一放大器，所述放大器的第一輸入端耦接一基準電壓。",
        "2. 如請求項1所述的電路，其中一分壓電路連接所述放大器的所述第一輸入端。")
