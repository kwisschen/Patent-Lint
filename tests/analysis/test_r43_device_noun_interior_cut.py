# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
"""TW R43 - device-noun interior-cut exceptions + the vetoed-verb retry.

Reports kwisschen/patentlint-reports#537, #538 (the 處理器 head itself is
MEASURED AND WITHHELD - see _INTERIOR_CUT_EXCEPTIONS for the per-head numbers).
"""
from __future__ import annotations

import pytest

from patentlint.analysis.tw_claims import clean_noun_phrase_tw


@pytest.mark.parametrize("term", [
    "所述資料傳輸器",
    "所述準位調整器",
    "所述光學掃描器",
    "所述位移暫存器",
    "所述脈衝計數器",
    "所述輸入電壓多工器",
    "所述主控制器",
    "所述畫素電容器",
    "所述端上反射器",
    "所述組件偏振器",
    "所述偏光板偏光器",
    "所述卷芯集電器",
    "所述模型估計器",
    "所述填充指示器",
    "所述電子裝置攝影機",
    "所述基地台收發機",
    "所述輸送裝置輸送機",
    "所述中央處理單元",
    "所述電性連接器",
    "所述感測放大器",
])
def test_declared_device_noun_head_survives_the_interior_cut(term: str) -> None:
    """One head entry covers unbounded modifiers, because the R27 tail guard
    tests the remainder AT the cut and that remainder is always the bare head.

    Note the scope: this protects the cut AT THE HEAD. A modifier that itself
    contains an interior verb (`處理元件控制器`) still cuts at that earlier verb,
    which is correct - the head entry is not a licence to keep a whole clause.
    """
    assert clean_noun_phrase_tw(term) == term


@pytest.mark.parametrize("text,cleaned", [
    # A real clause boundary still cuts - a determiner before the object is
    # what separates it from a noun-modifier.
    ("所述儲存裝置包括控制器", "所述儲存裝置"),
    ("所述控制單元連接一顯示器", "所述控制單元"),
    ("底座設有一孔洞", "底座"),
    ("所述容置杯體設置有多數孔隙", "所述容置杯體"),
    # The R27 case the retry must not regress.
    ("所述對接連接器", "所述對接連接器"),
    # The #349 hard-coded 天線 guard.
    ("所述發射接收天線", "所述發射接收天線"),
])
def test_clause_boundaries_and_prior_guards_are_unchanged(
    text: str, cleaned: str
) -> None:
    assert clean_noun_phrase_tw(text) == cleaned


def test_vetoed_verb_retries_behind_the_compound() -> None:
    """The R43 mechanism: a veto used to discard the verb's ONLY candidate, so
    everything after the protected compound stayed uncut."""
    assert clean_noun_phrase_tw("所述電性連接器設有一開口") == "所述電性連接器"


def test_withheld_heads_still_truncate() -> None:
    """Pins the WITHHELD set so a future round notices it is changing them.
    處理器 (#537/#538) is blocked at 14 UNPAIRED-NEW, not on FN risk."""
    assert clean_noun_phrase_tw("所述神經網路處理器") == "所述神經網路"
    assert clean_noun_phrase_tw("所述資料選擇器") == "所述資料"
