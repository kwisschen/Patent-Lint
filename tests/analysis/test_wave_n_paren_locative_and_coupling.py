"""Wave N - two TW report classes. A closing parenthesis ends a bare-noun
introduction before a locative 中/內 + 的/之 (位於X（Y）中的一頻段 introduces
X（Y）). In spec-support, a trailing 耦接 / 耦合 before 於 / 至 / a determiner is
the coupling verb, not part of the element.

Synthetic shapes only; each test fails with its mechanism disabled.
"""

from patentlint.analysis.tw_claims import check_antecedent_basis
from patentlint.analysis.tw_spec_support import _strip_trailing_predicate_before_marker
from patentlint.models import Claim, TwPatentDocument


def _tw(*texts):
    claims = [
        Claim(id=i + 1, text=t, independent=i == 0, dependencies=[] if i == 0 else [1])
        for i, t in enumerate(texts)
    ]
    return {f["term"] for f in check_antecedent_basis(TwPatentDocument(claims=claims))}


def test_paren_annotated_locative_mention_introduces():
    terms = _tw("一種電路，包括一第一訊號及一第二訊號，其中該第一訊號位於區域網路（LAN）中的一第一頻段，"
                "該第二訊號位於該區域網路（LAN）中的一第二頻段。")
    assert "區域網路（LAN）" not in terms


def test_paren_annotated_reference_without_mention_still_flags():
    terms = _tw("一種電路，包括一第一訊號，其中該第一訊號位於該區域網路（LAN）中的一第一頻段。")
    assert "區域網路（LAN）" in terms


def test_coupling_verb_before_marker_is_stripped():
    claim = "該第一開關的共接點耦接於該模組的一連接埠，且一電阻耦合至該共接點。"
    assert _strip_trailing_predicate_before_marker("共接點耦接", claim) == "共接點"
    assert _strip_trailing_predicate_before_marker("電阻耦合", claim) == "電阻"


def test_coupling_noun_before_de_is_kept():
    claim = "一種電路，其中一共接點耦接的方式為串聯。"
    assert _strip_trailing_predicate_before_marker("共接點耦接", claim) == "共接點耦接"


def test_spec_support_end_to_end_drops_the_coupling_verb():
    from patentlint.analysis.tw_spec_support import check_spec_support_tw

    claim = ("一種電路，包括一三工器、一模組、一第一開關及一第二開關，該三工器耦接於一外部天線，"
             "該第一開關的共接點耦接於該模組的一第一連接埠。")
    spec = ("本發明的電路包括三工器、模組、第一開關及第二開關。第一開關的共接點透過導線連接至模組的"
            "第一連接埠，三工器連接外部天線。") * 3

    def phrases(s):
        doc = TwPatentDocument(claims=[Claim(id=1, text=claim, independent=True, dependencies=[])], embodiment=[s])
        return [u.phrase for u in check_spec_support_tw(doc)]

    assert phrases(spec) == []
    # Still a finding, under the element's own name, when the spec lacks it.
    assert phrases(spec.replace("共接點", "公共端")) == ["共接點"]
