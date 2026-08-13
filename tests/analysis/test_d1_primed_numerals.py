# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
"""Primed reference designators (reports #445 / #447).

By patent drafting convention a primed numeral (``110'``) designates a
DISTINCT element from its unprimed parent (``110``) - typically the same part
in a second embodiment. The D1 extractors used to drop the prime, so the two
clustered under one numeral and a legitimately-different element name read as
a §608.01(g) / 专利法实施细则 §21 inconsistency the drafter never committed.

TWO codepoints are accepted - the ASCII apostrophe and the right single
quotation mark Word autocorrects it into - and they fold together so a draft
mixing them still clusters, while the prime COUNT stays significant. The
typographic prime U+2032 / double prime U+2033 are deliberately EXCLUDED: in
real drafting they are measurement symbols (minutes, arc-minutes, inches) more
often than designators, and admitting them read a lab protocol's `for 30' at
RT` as a reference designator.
"""

from patentlint.analysis.cn_specification import _cn_extract_numeral_name_pairs
from patentlint.analysis.specification import extract_numeral_name_pairs

APOS = "'"      # '
RSQUO = "’"     # ’  (Word autocorrect)
PRIME = "′"     # ′  (U+2032 - minutes / arc-minutes, NOT a designator)
DPRIME = "″"    # ″  (U+2033 - inches / seconds, NOT a designator)


class TestPrimedDesignatorsUS:
    def test_primed_is_distinct_from_parent(self):
        text = (
            "The multiplexing structure 110 is planar. "
            "Two multiplexing devices 110" + APOS + " are utilized."
        )
        pairs = dict(extract_numeral_name_pairs(text))
        assert "110" in pairs
        assert "110" + APOS in pairs
        assert pairs["110"] != pairs["110" + APOS]

    def test_prime_codepoints_fold_together(self):
        """A draft mixing ' and ’ must cluster them as ONE designator.

        Word autocorrects inconsistently within a single document, so both
        forms routinely appear side by side for the same element.
        """
        for ch in (APOS, RSQUO):
            text = "The lens 205" + ch + " is convex."
            nums = [n for n, _ in extract_numeral_name_pairs(text)]
            assert nums == ["205" + APOS], f"{ch!r} did not fold onto the apostrophe"

    def test_double_prime_stays_distinct_from_single(self):
        text = "The sleeve 24" + APOS + " and the sleeve 24" + APOS * 2 + " differ."
        nums = {n for n, _ in extract_numeral_name_pairs(text)}
        assert nums == {"24" + APOS, "24" + APOS * 2}

    def test_typographic_prime_is_a_MEASUREMENT_not_a_designator(self):
        """U+2032 / U+2033 are minutes / arc-minutes / inches in real drafts.

        Admitting them read `equilibrated for 30' at RT` (a lab incubation
        time) as designator `30'` and manufactured a FIX-tier conflict on
        US20230382973A1. They must behave exactly as they did before the
        primed-designator work - i.e. fold into the unprimed parent.
        """
        pairs = extract_numeral_name_pairs("equilibrated for 30" + PRIME + " at RT and then run")
        assert all(not n.endswith(APOS) for n, _ in pairs), pairs
        assert extract_numeral_name_pairs("an order for a 40" + DPRIME + " panel") == []

    def test_possessive_is_not_a_prime(self):
        """`the housing 102's surface` must still count against 102.

        FN-safety here rests on regex backtracking, not on the charset: the
        greedy prime match fails the trailing anchor on the `s` and falls back.
        """
        pairs = extract_numeral_name_pairs("The housing 102" + APOS + "s surface is flat.")
        assert [n for n, _ in pairs] == ["102"]

    def test_parenthesised_primed_numeral_is_captured(self):
        """`(25')` never matched before - the prime sat before the paren."""
        pairs = dict(extract_numeral_name_pairs("The toothed member (25" + APOS + ") is shown."))
        assert "25" + APOS in pairs

    def test_four_digit_primed_numeral_survives_the_long_token_filter(self):
        pairs = dict(extract_numeral_name_pairs("The bracket 1234" + APOS + " differs."))
        assert "1234" + APOS in pairs

    def test_long_token_exclusion_is_otherwise_unchanged(self):
        """Guard the narrowing: a decade is not a designator, and the
        unprimed 4-digit-plus-letter form stays excluded exactly as before."""
        assert extract_numeral_name_pairs("Research in the 1950s discovered it.") == []
        assert extract_numeral_name_pairs("The bracket 1234a differs.") == []
        assert extract_numeral_name_pairs("The device 12345 is long.") == []


class TestPrimedDesignatorsCN:
    def test_primed_is_distinct_from_parent(self):
        text = "平顶波分复用结构110包括基板。平顶波分复用器件110" + APOS + "被采用。"
        pairs = dict(_cn_extract_numeral_name_pairs(text))
        assert "110" in pairs
        assert "110" + APOS in pairs
        assert pairs["110"] != pairs["110" + APOS]

    def test_prime_codepoints_fold_together(self):
        for ch in (APOS, RSQUO):
            text = "初级行星齿121" + ch + "与太阳轮啮合。"
            nums = [n for n, _ in _cn_extract_numeral_name_pairs(text)]
            assert nums == ["121" + APOS], f"{ch!r} did not fold onto the apostrophe"

    def test_fullwidth_parenthesised_primed_numeral_is_captured(self):
        """`（25’）` never matched before - the prime sat before the paren."""
        text = "轮齿轮构件的周向齿（25" + RSQUO + "）形成次级行星齿。"
        pairs = dict(_cn_extract_numeral_name_pairs(text))
        assert "25" + APOS in pairs

    def test_letter_suffix_still_works(self):
        pairs = dict(_cn_extract_numeral_name_pairs("导光板501a设于壳体。"))
        assert "501a" in pairs
