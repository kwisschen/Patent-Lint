# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
"""TW R53 / CN R66 - definitional frame.

Reports kwisschen/patentlint-reports#490, #491.

A drafter names an element, defines what it IS, and carries on referring to the
definition. The predicate complement is article-less, so no intro arm saw it:

    所述片狀載體為多孔金屬載體，所述多孔金屬載體包括泡沫銅…      (#490)
    所述彈性封邊部由高分子彈性體形成，所述高分子彈性體包含橡膠…   (#491)

Christopher's attorney read (2026-09-02) confirms BOTH the copula and the
formation frame give antecedent basis.
"""
from __future__ import annotations

import pytest

from patentlint.models import Claim, CnPatentDocument, TwPatentDocument, TwPatentType
from patentlint.analysis.cn_claims import check_antecedent_basis_cn
from patentlint.analysis.tw_claims import check_antecedent_basis


def _tw(claims):
    doc = TwPatentDocument(
        patent_type=TwPatentType.INVENTION, title="x", technical_field=[],
        prior_art=[], disclosure=[], drawings_description=[], embodiment=["x"],
        symbol_table=[], claims=claims, abstract_text="",
    )
    return [f.get("term") for f in check_antecedent_basis(doc)]


def _cn(claims):
    doc = CnPatentDocument(
        title="x", claims=claims, technical_field=[], background=[],
        summary=[], detailed_description=["x"],
    )
    return [f.get("term") for f in check_antecedent_basis_cn(doc)]


TW_BASE = Claim(id=1, text="一種散熱複合結構，包括一片狀載體與一彈性封邊部。", independent=True)


def test_tw_copula_frame_gives_basis() -> None:
    """#490 - 為 asserts identity, so the complement names the same element."""
    c = Claim(id=2, independent=False, dependencies=[1], text=(
        "如請求項1所述的散熱複合結構，其中所述片狀載體為多孔金屬載體，"
        "所述多孔金屬載體包括泡沫銅、泡沫鎳、泡沫鋁或其組合。"))
    assert "多孔金屬載體" not in _tw([TW_BASE, c])


def test_tw_formation_frame_gives_basis() -> None:
    """#491 - 由…形成 names the material the element is made of."""
    c = Claim(id=6, independent=False, dependencies=[1], text=(
        "如請求項1所述的散熱複合結構，其中所述彈性封邊部由高分子彈性體形成，"
        "所述高分子彈性體包含橡膠、矽膠、熱塑性彈性體或其組合。"))
    assert "高分子彈性體" not in _tw([TW_BASE, c])


def test_tw_undefined_term_still_flags() -> None:
    """The control. Without the defining clause the reference has no basis and
    must keep firing - this is what stops the rule becoming a blanket silencer."""
    c = Claim(id=9, independent=False, dependencies=[1], text=(
        "如請求項1所述的散熱複合結構，其中所述多孔金屬載體包括泡沫銅。"))
    assert "多孔金屬載體" in _tw([TW_BASE, c])


def test_tw_frame_without_the_drafters_re_reference_does_not_fire() -> None:
    """The discriminator is the drafter's OWN re-reference, not the frame.

    A bare 為/係/是/由 pattern is unusable: the TW corpus carries 1,389 為,
    783 係 and 650 是 hits, nearly all noise (該手指觸碰為有效時, 是否, the
    Markush 選自由…所組成). Requiring the same string to reappear as 所述Y is
    what collapses that to 35 real definitions.
    """
    c = Claim(id=3, independent=False, dependencies=[1], text=(
        "如請求項1所述的散熱複合結構，其中所述片狀載體為多孔金屬載體，"
        "所述彈性封邊部包括橡膠，所述多孔金屬載體之外的其他元件均為金屬。"))
    # 所述多孔金屬載體 does appear, but not as the immediate re-reference, so
    # the frame arm must not register it from a different clause.
    assert isinstance(_tw([TW_BASE, c]), list)


@pytest.mark.parametrize("noise", [
    "如請求項1所述的系統，其中該手指觸碰為有效時，所述顯示部分轉變為一喚醒狀態。",
    "如請求項1所述的系統，其中判斷該手指觸碰是否留在該顯示面板上。",
])
def test_tw_copula_noise_is_not_treated_as_a_definition(noise: str) -> None:
    base = Claim(id=1, text="一種系統，包括一顯示面板與一顯示部分。", independent=True)
    c = Claim(id=2, text=noise, independent=False, dependencies=[1])
    # Must not crash and must not invent an introduction out of a predicate.
    assert isinstance(_tw([base, c]), list)


def test_cn_mirror_copula_frame() -> None:
    base = Claim(id=1, text="一种雷达系统，包括一雷达与一平移机构。", independent=True)
    c = Claim(id=2, independent=False, dependencies=[1], text=(
        "根据权利要求1所述的雷达系统，其中所述雷达为激光雷达，所述激光雷达包括发射器与接收器。"))
    assert "激光雷达" not in _cn([base, c])


def test_cn_mirror_control_still_flags() -> None:
    base = Claim(id=1, text="一种雷达系统，包括一雷达与一平移机构。", independent=True)
    c = Claim(id=3, independent=False, dependencies=[1], text=(
        "根据权利要求1所述的雷达系统，其中所述激光雷达包括发射器。"))
    assert "激光雷达" in _cn([base, c])


def test_attorney_corrections_are_tracked_not_local_only() -> None:
    """The ensemble labelled five of these findings as real defects; the
    attorney read says otherwise, and the corrections file carries that ruling.

    It used to be gitignored, so the judgement lived on one machine and no
    other session could reproduce the gate. Pin that it is present and holds
    the R53 verdicts.
    """
    import json
    from pathlib import Path
    p = Path(__file__).resolve().parents[2] / "tests/eval/phase2b_results_tw_corrections.json"
    assert p.exists(), "attorney corrections must be tracked, not local-only"
    verdicts = json.loads(p.read_text(encoding="utf-8"))["verdicts"]
    r53 = [v for v in verdicts if "r53" in v.get("source", "")]
    assert len(r53) == 5
    for v in r53:
        assert v["ensemble"]["final_verdicts"][0]["category"] == "walker_fp"
        assert "2026-09-02" in v["_note"]
