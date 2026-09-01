# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
"""Engine-2 term-quality gate: every declared jurisdiction must be REACHABLE.

The US arm was declared in three places - `_PREDICATE_TAILS_US`, the US branch
of `_term_defects`, and `_EXPECTED_BAD["US"]` - while `--juris` accepted only
TW and CN, so the arm existed and could never run. On the very engine that
produced reports #688/#689. These tests pin the arms shut against that.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval.specsup_corpus_runner import (  # noqa: E402
    _EXPECTED_BAD,
    _checker,
    _term_defects,
)


@pytest.mark.parametrize("juris", sorted(_EXPECTED_BAD))
def test_every_declared_jurisdiction_has_a_reachable_checker(juris: str) -> None:
    """A jurisdiction with a pinned residual must have a runnable checker."""
    assert _checker(juris) is not None


def test_us_classifier_catches_the_reported_class() -> None:
    """Non-vacuity: a gate at 0 bad terms is worthless if it catches nothing.

    `local statistical values respective` is the exact term reports #688/#689
    filed, before #467 fixed it. The gate must be able to see that class.
    """
    assert _term_defects("US", "local statistical values respective")


@pytest.mark.parametrize("term", [
    "first signal indicative",
    "circuit responsive",
    "product operable",
    "processor configured",
])
def test_us_classifier_covers_the_whole_predicative_class(term: str) -> None:
    assert _term_defects("US", term)


@pytest.mark.parametrize("term", [
    "edge band region",
    "local statistical values",
    "image capturing circuit",
])
def test_us_classifier_leaves_clean_noun_phrases_alone(term: str) -> None:
    assert _term_defects("US", term) == []


def test_tw_and_cn_classifiers_still_see_their_classes() -> None:
    assert _term_defects("TW", "以擷取一")      # 以擷取一
    assert _term_defects("TW", "屬於一色相值區間")
    assert _term_defects("TW", "漸縮部且容置於")


# --- Engine 1 (antecedent walker) shares the SAME classifier ---------------

def test_engine1_gate_reuses_the_engine2_classifier() -> None:
    """The two engines must not develop separate notions of 'not a noun phrase'.

    `walker_term_quality` imports `_term_defects` rather than copying it. The
    US R48 round was a lesson in what re-implementing a sibling's logic costs.
    """
    from eval import walker_term_quality as w1
    src = Path(w1.__file__).read_text(encoding="utf-8")
    assert "from eval.specsup_corpus_runner import _term_defects" in src
    assert "def _term_defects" not in src, "classifier was copied, not imported"


def test_engine1_residual_pins_exist_for_every_jurisdiction() -> None:
    from eval.walker_term_quality import _EXPECTED_BAD_ENGINE1
    assert set(_EXPECTED_BAD_ENGINE1) == {"TW", "CN", "US"}
    assert all(v >= 0 for v in _EXPECTED_BAD_ENGINE1.values())
