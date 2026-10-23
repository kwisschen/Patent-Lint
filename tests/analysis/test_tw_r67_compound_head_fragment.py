"""TW R67 - the bare verb-object arm opening INSIDE a connector compound
(所述<X>連接器為一<Y>) must not put the fragment it leaves into the
spec-support inventory. Synthetic shapes only."""

from patentlint.analysis.tw_spec_support import (
    _starts_inside_compound_tw,
    check_spec_support_tw,
)
from patentlint.models import Claim, TwPatentDocument

_SPEC = "本裝置包括一底板及多個訊號連接器，訊號連接器包含一連接柱，連接柱呈中空狀。"


def _phrases(*texts: str) -> list[str]:
    claims = [
        Claim(id=i + 1, text=t, independent=(i == 0), dependencies=([] if i == 0 else [1]))
        for i, t in enumerate(texts)
    ]
    return [f.phrase for f in check_spec_support_tw(
        TwPatentDocument(claims=claims, embodiment=[_SPEC]))]


def test_fragment_after_a_connector_compound_is_not_a_term():
    phrases = _phrases(
        "1. 一種裝置，包括一底板及多個訊號連接器，所述訊號連接器包含一連接柱。",
        "2. 如請求項1所述的裝置，其中，所述訊號連接器為一母座連接器，並且所述連接柱呈中空狀。")
    assert not any(p.startswith(("器", "柱")) for p in phrases)


def test_only_compound_heading_verbs_qualify():
    assert _starts_inside_compound_tw("連接器為一母座", "器為一母座")
    # An ordinary verb's object that starts with a suffix character is a real term.
    assert not _starts_inside_compound_tw("包括頂壁", "頂壁")
    # A quantifier prefix is not a verb.
    assert not _starts_inside_compound_tw("一組合艙", "組合艙")
