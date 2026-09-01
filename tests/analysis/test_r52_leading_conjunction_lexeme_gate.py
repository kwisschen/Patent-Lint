# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
"""TW R52 / CN R65 - lexeme-gated leading conjunction (Engine 2 only).

Closes the documented Engine-2 term-quality residuals: TW 1 -> 0, CN 5 -> 2.
"""
from __future__ import annotations

import pytest

from patentlint.analysis.cn_spec_support import _has_leading_conj_bing_cn
from patentlint.analysis.tw_spec_support import _has_leading_conjunction_tw


# --- the connective must be rejected --------------------------------------

@pytest.mark.parametrize("term", [
    "並包含一組n-1個二極體",   # the documented TW residual
    "並將訊號",
    "並使該裝置",
    "並具有一外殼",
])
def test_tw_leading_connective_is_rejected(term: str) -> None:
    assert _has_leading_conjunction_tw(term) is True


@pytest.mark.parametrize("term", [
    "并且在", "并且当", "并且-",   # the three documented CN residuals
    "并将数据",
    "并使所述装置",
])
def test_cn_leading_connective_is_rejected(term: str) -> None:
    assert _has_leading_conj_bing_cn(term) is True


# --- the noun lexemes must survive: this is the whole point of the gate ----

@pytest.mark.parametrize("term", [
    "並聯", "並聯電路", "並列電容", "並排結構", "並行匯流排",
])
def test_tw_conjunction_noun_lexemes_are_preserved(term: str) -> None:
    """`並聯` occurs 118x in the corpus - a bare 並 cut would destroy it."""
    assert _has_leading_conjunction_tw(term) is False


@pytest.mark.parametrize("term", [
    "并联", "并联电路", "并列结构", "并排布置", "并行总线",
])
def test_cn_conjunction_noun_lexemes_are_preserved(term: str) -> None:
    assert _has_leading_conj_bing_cn(term) is False


@pytest.mark.parametrize("term", ["並", "并", "", "並A", "并A"])
def test_bare_or_too_short_is_never_rejected(term: str) -> None:
    assert _has_leading_conjunction_tw(term) is False
    assert _has_leading_conj_bing_cn(term) is False


def test_expected_bad_pins_were_lowered_not_raised() -> None:
    """The residual table is a ratchet: lowering is a win, raising a regression."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from eval.specsup_corpus_runner import _EXPECTED_BAD
    assert _EXPECTED_BAD["TW"] == 0
    assert _EXPECTED_BAD["CN"] == 2
    assert _EXPECTED_BAD["US"] == 0
