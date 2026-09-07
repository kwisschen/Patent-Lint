# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
"""The Engine-1 mid-word-truncation discriminator is pinned here.

The gate itself runs over the corpus and is maintainer-only. What CAN be pinned
in CI is the DISCRIMINATOR: a term that stops inside a word must be caught, and
a real element name that merely precedes a verb must NOT be. That second half is
the whole point - two string detectors were built and measured before this one,
and both died on exactly that case at a 25-30% false-positive rate.

Skips when the dev-time segmenter is absent, which is the normal CI state.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

EVAL_DIR = Path(__file__).resolve().parents[1] / "eval"


def _arm():
    sys.path.insert(0, str(EVAL_DIR))
    import walker_term_quality as w
    cut = w._load_segmenter()
    if cut is None:
        pytest.skip("dev-time segmenter not installed (pip install -e '.[eval]')")
    return w, cut


class TestMidWordDiscriminator:
    def test_a_term_stopping_inside_a_word_is_caught(self):
        w, cut = _arm()
        # cuts the compound in half - not a noun phrase in any reading
        assert w._ends_midword(
            "\u7535\u538b\u7b9d",                              # a two-char compound, cut in half
            "\u6240\u8ff0\u7535\u538b\u7b9d\u4f4d\u7535\u8def",      # the real element continues
            cut,
        ) is True

    def test_a_real_element_before_a_verb_is_NOT_caught(self):
        """The false-positive mode that killed the two string detectors."""
        w, cut = _arm()
        assert w._ends_midword(
            "\u8fdc\u7a0b\u8bbe\u5907",            # a complete element name
            "\u5411\u8fdc\u7a0b\u8bbe\u5907\u4f20\u8f93\u6570\u636e",  # followed by a VERB
            cut,
        ) is False

    def test_one_clean_occurrence_acquits_the_term(self):
        """A boundary shown anywhere in the document settles the term."""
        w, cut = _arm()
        text = ("\u5411\u8fdc\u7a0b\u8bbe\u5907\u4f20\u8f93\u6570\u636e\uff0c"
                "\u6240\u8ff0\u8fdc\u7a0b\u8bbe\u5907\u3002")
        assert w._ends_midword("\u8fdc\u7a0b\u8bbe\u5907", text, cut) is False

    def test_absent_term_is_not_flagged(self):
        w, cut = _arm()
        assert w._ends_midword("\u4e0d\u5b58\u5728", "\u5176\u4ed6\u5185\u5bb9", cut) is False


def test_the_gate_module_imports_without_the_segmenter():
    """CI has no segmenter; the module must still import and skip cleanly."""
    sys.path.insert(0, str(EVAL_DIR))
    import walker_term_quality as w
    assert "US" not in w._EXPECTED_MIDWORD, "English is space-delimited"
    assert set(w._EXPECTED_MIDWORD) == {"TW", "CN"}
