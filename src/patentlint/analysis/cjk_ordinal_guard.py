# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
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
_CJK_DIGITS = "一二三四五六七八九十百千萬兩零万两"
_NUMERIC_ORDINAL = re.compile(rf"^第([{_CJK_DIGITS}]+|\d+)(.*)$")


# ---------------------------------------------------------------------------
# Arabic-to-CJK ordinal normalization (R33 walker-mine M2)
# ---------------------------------------------------------------------------

# Per the round-1 cluster discovery, JP-translated TW + CN drafts retain
# half-width Arabic digits in 第N constructions (`第1電極`, `第2端子`)
# where canonical TW/CN style uses CJK numerals (`第一電極`, `第二端子`).
# The walker's normalize_reference_term / normalize_candidate_intro
# currently treat them as distinct intro/reference identities, so a
# parent claim using `第一X` and a dep claim referencing `第1X` (or vice
# versa) emits a spurious antecedent-basis finding. This helper folds
# the two forms together at normalization time, keyed only on the 1-2
# digit range that covers ordinary patent ordinals (1..99). Element
# label numbers (101) etc. are unaffected because they lack a leading
# 第 character.

_ARABIC_TO_CJK_DIGIT: dict[str, str] = {
    "0": "零", "1": "一", "2": "二", "3": "三", "4": "四",
    "5": "五", "6": "六", "7": "七", "8": "八", "9": "九",
}


def _arabic_digits_to_cjk_numeral(digits: str) -> str:
    """Convert a 1-2 char Arabic digit string to its CJK numeral form.

    Returns: "1" → "一", "10" → "十", "20" → "二十", "25" → "二十五",
    "99" → "九十九". Returns the input unchanged if it falls outside
    1..99 (single 0, 3+ digit strings, or non-digit input).
    """
    if not digits.isdigit() or not 1 <= len(digits) <= 2:
        return digits
    n = int(digits)
    if n == 0:
        return "零"
    if 1 <= n <= 9:
        return _ARABIC_TO_CJK_DIGIT[digits]
    if 10 <= n <= 19:
        ones = _ARABIC_TO_CJK_DIGIT[str(n - 10)] if n > 10 else ""
        return "十" + ones
    if 20 <= n <= 99:
        tens = _ARABIC_TO_CJK_DIGIT[str(n // 10)]
        ones_digit = n % 10
        ones = _ARABIC_TO_CJK_DIGIT[str(ones_digit)] if ones_digit else ""
        return tens + "十" + ones
    return digits


# `(?!\d)` blocks 3+ digit ordinal labels (e.g., `第123A段`) which are
# rare and more likely to be raw element identifiers than ordinals; the
# pattern requires `第` immediately followed by exactly 1-2 digits.
_ARABIC_ORDINAL_RUN = re.compile(r"第(\d{1,2})(?!\d)")


def normalize_arabic_ordinal_to_cjk(text: str) -> str:
    """Fold half-width Arabic ordinals (第1, 第2) to CJK form (第一, 第二).

    Used by TW + CN walker normalize_reference_term* and
    normalize_candidate_intro* for ADR-095 symmetry. The transformation
    is a no-op on text already in CJK form, so it is safe to apply
    unconditionally at the start of the normalization pipeline.
    """
    if not text or "第" not in text:
        return text
    return _ARABIC_ORDINAL_RUN.sub(
        lambda m: "第" + _arabic_digits_to_cjk_numeral(m.group(1)),
        text,
    )


# ---------------------------------------------------------------------------
# Pattern 2: polarity / type prefix (single-character binary pairs)
# ---------------------------------------------------------------------------

# Each frozenset represents a binary polarity family. A pair is guarded
# only if the two terms start with DIFFERENT members of the same family.
_POLARITY_FAMILIES: tuple[frozenset[str], ...] = (
    frozenset({"陽", "陰", "阳", "阴"}),
    frozenset({"正", "負", "负"}),
    frozenset({"凸", "凹"}),
    frozenset({"主", "副"}),
    frozenset({"內", "外", "内"}),
    frozenset({"上", "下"}),
    frozenset({"左", "右"}),
    frozenset({"前", "後", "后"}),
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
