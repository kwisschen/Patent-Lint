# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""CJK ordinal-guard pre-filter for the TW/CN antecedent walker's
did-you-mean layer.

Per the Phase 8b calibration v2 report, character-bigram Jaccard
similarity over CJK patent terms cannot distinguish between terms that
differ only in an ordinal or polarity prefix (第一電極 / 第二電極 score
~0.67 because they share two of three bigrams). These pairs must NOT be
suggested to each other as did-you-mean candidates: the attorney meant
exactly what they wrote, the terms are different components.

The guard is narrow-by-default: it fires only when two terms share a
common suffix AND differ in one of four recognised prefix families.
False negatives (missing a real ordinal mismatch) are tolerable; false
positives (blocking a legitimate typo suggestion) are not. The guard
is consulted by the walker as a pre-filter over every (reference,
candidate) pair before Jaccard similarity is computed.

Four guard patterns per the calibration v2 spec:

1. **Numeric-ordinal prefix** — 第一X / 第二X (also 第1X / 第2X, mixed
   Arabic/CJK numerals supported on either side). Fires only if the
   suffix strings after the ordinal are equal.
2. **Polarity/type prefix** — 陽/陰, 正/負, 凸/凹, 主/副, 內/外, 上/下,
   左/右, 前/後. Fires only if the suffix after the single-char prefix
   is equal on both sides.
3. **Latin-letter type prefix** — P型X / N型X. Fires only if the letters
   differ AND the suffix after 型 is equal.
4. **Digit-G generation prefix** — 5G網路 / 4G網路. Fires only if the
   digit prefix differs AND the suffix after the digit(s)+G is equal.

The guard is symmetric: ``ordinal_guard(a, b) == ordinal_guard(b, a)``
for every pair.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Pattern 1: numeric ordinal prefix (第N, N ∈ {一..十, 百, 千, 0-9+})
# ---------------------------------------------------------------------------

# Match 第 followed by a CJK digit character or an Arabic digit sequence.
# The captured group is the numeral token (used only for equality check;
# the guard fires regardless of whether the two numerals are the same
# string — it fires when they DIFFER).
_CJK_DIGITS = "一二三四五六七八九十百千萬兩零"
_NUMERIC_ORDINAL = re.compile(rf"^第([{_CJK_DIGITS}]+|\d+)(.*)$")


# ---------------------------------------------------------------------------
# Pattern 2: polarity / type prefix (single-character binary pairs)
# ---------------------------------------------------------------------------

# Each frozenset represents a binary polarity family. A pair is guarded
# only if the two terms start with DIFFERENT members of the same family.
_POLARITY_FAMILIES: tuple[frozenset[str], ...] = (
    frozenset({"陽", "陰"}),
    frozenset({"正", "負"}),
    frozenset({"凸", "凹"}),
    frozenset({"主", "副"}),
    frozenset({"內", "外"}),
    frozenset({"上", "下"}),
    frozenset({"左", "右"}),
    frozenset({"前", "後"}),
)


# ---------------------------------------------------------------------------
# Pattern 3: Latin-letter type prefix (LetterX + 型 + suffix)
# ---------------------------------------------------------------------------

_LETTER_TYPE = re.compile(r"^([A-Za-z])型(.*)$")


# ---------------------------------------------------------------------------
# Pattern 4: digit-G generation prefix (\d+G + suffix)
# ---------------------------------------------------------------------------

_DIGIT_G = re.compile(r"^(\d+)G(.*)$")


def _numeric_ordinal_guard(a: str, b: str) -> bool:
    ma = _NUMERIC_ORDINAL.match(a)
    mb = _NUMERIC_ORDINAL.match(b)
    if not (ma and mb):
        return False
    # Guard fires only when the two ordinal numerals differ but the
    # trailing noun is the same (e.g. 第一電極 vs 第二電極).
    if ma.group(1) == mb.group(1):
        return False
    return ma.group(2) == mb.group(2) and ma.group(2) != ""


def _polarity_guard(a: str, b: str) -> bool:
    if not a or not b:
        return False
    head_a, head_b = a[0], b[0]
    if head_a == head_b:
        return False
    for family in _POLARITY_FAMILIES:
        if head_a in family and head_b in family:
            # Suffixes must match exactly for the guard to fire.
            return a[1:] == b[1:] and a[1:] != ""
    return False


def _letter_type_guard(a: str, b: str) -> bool:
    ma = _LETTER_TYPE.match(a)
    mb = _LETTER_TYPE.match(b)
    if not (ma and mb):
        return False
    if ma.group(1).upper() == mb.group(1).upper():
        return False
    return ma.group(2) == mb.group(2) and ma.group(2) != ""


def _digit_g_guard(a: str, b: str) -> bool:
    ma = _DIGIT_G.match(a)
    mb = _DIGIT_G.match(b)
    if not (ma and mb):
        return False
    if ma.group(1) == mb.group(1):
        return False
    return ma.group(2) == mb.group(2) and ma.group(2) != ""


def ordinal_guard(term_a: str, term_b: str) -> bool:
    """Return True iff the pair should be short-circuited to no-match.

    Symmetric: ``ordinal_guard(a, b) == ordinal_guard(b, a)``.
    Narrow-by-default: fires only when a recognised prefix family
    differs AND the trailing noun is identical.
    """
    if not term_a or not term_b:
        return False
    if term_a == term_b:
        return False
    # Each pattern is independently symmetric; OR them together.
    return (
        _numeric_ordinal_guard(term_a, term_b)
        or _polarity_guard(term_a, term_b)
        or _letter_type_guard(term_a, term_b)
        or _digit_g_guard(term_a, term_b)
    )
