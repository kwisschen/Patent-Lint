# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
"""D1 (numeralConsistency) - a determiner inside a captured name, and 约 ("about").

Reports #796 / #800 (TW). All text here is synthesised.
"""
from patentlint.analysis.cn_specification import (
    _cn_detect_d1_conflicts,
    _cn_extract_numeral_name_pairs,
)


def _conflicts(text):
    return _cn_detect_d1_conflicts(_cn_extract_numeral_name_pairs(text))


def _names(text, numeral):
    return sorted({n for k, n in _cn_extract_numeral_name_pairs(text) if k == numeral})


def test_clause_before_an_embedded_determiner_is_not_part_of_the_name():
    """#796 / #800: the same element, captured once through `返回至所述` and
    once through `移動至一`, read as two names and fired a phantom conflict."""
    text = (
        "所述滑座返回至所述第一鎖定位置P1。之後，所述滑座移動至一第一鎖定位置P1。"
        "所述滑座朝向所述第一鎖定位置P1移動。"
    )
    assert _names(text, "P1") == ["第一|鎖定位置"]
    assert _conflicts(text) == []


def test_a_real_conflict_behind_a_fragment_still_fires():
    """Cutting the fragment must EXPOSE a genuine one-character discrepancy,
    never hide it."""
    text = "閉鎖鉤30設於框體。閉鎖鉤30可轉動。當所述閉鎖溝30脫離時，框體打開。"
    confs = _conflicts(text)
    assert len(confs) == 1
    names = {confs[0]["canonical"], *(o["name"] for o in confs[0]["outliers"])}
    assert names == {"閉鎖鉤", "閉鎖溝"}


def test_a_fragment_marker_name_is_not_rescued_by_the_cut():
    """`...通過所述孔進入插座20` was dropped whole (通過 is a fragment marker).
    Cutting at 所述 would strip the marker and rescue `孔進入插座`."""
    text = "順應性插座20固定於基板。順應性插座20具有端子。導線可以通過所述孔進入插座20。"
    assert _names(text, "20") == ["順應性插座"]


def test_a_numeral_after_yue_is_a_quantity_not_a_designator():
    """`间隔大约150`: 150 after 约 is a measured spacing, so it must not stand
    beside the real designator `表面150` as a second name."""
    assert _names("表面150平坦。间隔大约150。", "150") == ["表面"]


def test_a_content_compound_ending_in_yue_is_kept():
    """Exact function-char bigrams only: 合约 / 条约 are real element names."""
    assert _names("所述智能合约20与所述节点30通信。", "20") == ["智能合约"]


def test_a_bare_gai_inside_yinggai_is_not_a_determiner():
    """應該 ("should") contains 該; only 所述 and coverb + 一 are cut."""
    assert _names("所述殼體應該包覆電路板20。", "20") == ["殼體應該包覆電路板"]
