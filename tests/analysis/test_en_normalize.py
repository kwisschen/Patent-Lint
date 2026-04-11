# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""Unit tests for English morphology normalization (en_normalize.py)."""

import pytest

from patentlint.analysis.en_normalize import _depluralize_word, en_number_key


class TestDepluralizeWord:
    """Test _depluralize_word rules 1-4 and guards."""

    # Rule 1: -ies -> -y
    def test_rule1_bodies(self):
        assert _depluralize_word("bodies") == "body"

    def test_rule1_assemblies(self):
        assert _depluralize_word("assemblies") == "assembly"

    def test_rule1_cavities(self):
        assert _depluralize_word("cavities") == "cavity"

    # Rule 2: -sses -> -ss
    def test_rule2_processes(self):
        assert _depluralize_word("processes") == "process"

    def test_rule2_classes(self):
        assert _depluralize_word("classes") == "class"

    def test_rule2_grasses(self):
        assert _depluralize_word("grasses") == "grass"

    # Rule 3: -(x|z|ch|sh)es -> strip -es
    def test_rule3_switches(self):
        assert _depluralize_word("switches") == "switch"

    def test_rule3_boxes(self):
        assert _depluralize_word("boxes") == "box"

    def test_rule3_brushes(self):
        assert _depluralize_word("brushes") == "brush"

    # Rule 4: plain -s
    def test_rule4_inductors(self):
        assert _depluralize_word("inductors") == "inductor"

    def test_rule4_circuits(self):
        assert _depluralize_word("circuits") == "circuit"

    def test_rule4_components(self):
        assert _depluralize_word("components") == "component"

    # Guard cases: _NOT_PLURAL_ENDINGS
    @pytest.mark.parametrize("word", [
        "bus", "apparatus", "focus", "radius", "nucleus",  # -us
        "basis", "axis", "analysis", "thesis", "chassis",  # -is
        "gas", "bias", "canvas",                           # -as
        "logo",                                            # -os (no trailing s)
    ])
    def test_guard_not_plural(self, word):
        assert _depluralize_word(word) == word

    # -ss guard (double-s words that are NOT -sses plurals)
    def test_guard_glass(self):
        assert _depluralize_word("glass") == "glass"

    def test_guard_process_singular(self):
        assert _depluralize_word("process") == "process"

    # Short-word guards
    def test_empty_string(self):
        assert _depluralize_word("") == ""

    def test_single_char(self):
        assert _depluralize_word("a") == "a"

    def test_as_short(self):
        assert _depluralize_word("as") == "as"

    def test_is_short(self):
        assert _depluralize_word("is") == "is"


class TestEnNumberKey:
    """Test en_number_key last-token-only normalization."""

    def test_multi_word_plural(self):
        assert en_number_key("first filter inductors") == "first filter inductor"

    def test_single_word(self):
        assert en_number_key("inductors") == "inductor"

    def test_idempotent_singular(self):
        assert en_number_key("first filter inductor") == "first filter inductor"

    def test_premodifier_untouched(self):
        assert en_number_key("sales report") == "sales report"

    def test_empty_string(self):
        assert en_number_key("") == ""

    def test_multi_word_ies(self):
        assert en_number_key("first bodies") == "first body"

    def test_multi_word_guarded(self):
        assert en_number_key("communication bus") == "communication bus"
