# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
"""TW R42 - instrumental-coverb leading strips on the spec-support normalizer.

Report kwisschen/patentlint-reports#543.
"""
from __future__ import annotations

import pytest

from patentlint.analysis.tw_spec_support import _normalize_for_spec_support_tw


@pytest.mark.parametrize("phrase,head", [
    ("透過一人工智慧推論模組", "人工智慧推論模組"),   # the three reported phrases
    ("透過一後處理模組", "後處理模組"),
    ("透過一動態控制模組", "動態控制模組"),
    ("通過一影像擷取設備", "影像擷取設備"),
    ("經由一傳輸介面", "傳輸介面"),
    ("藉由一運算電路", "運算電路"),
])
def test_instrumental_coverb_is_stripped(phrase: str, head: str) -> None:
    assert _normalize_for_spec_support_tw(phrase) == head


@pytest.mark.parametrize("term", [
    "透過孔",   # "through-hole" - a real element name
    "通過孔",
    "利用率",
])
def test_residual_guard_protects_coverb_initial_compounds(term: str) -> None:
    assert _normalize_for_spec_support_tw(term) == term
