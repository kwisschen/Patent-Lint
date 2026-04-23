# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Shared language-script helpers for jurisdiction detection.

Used by :func:`detect_patent_document` (US), :func:`detect_patent_document_cn`
(CN), and the TW abstract character counter to distinguish CJK-script patent
drafts from Latin-script ones. The CJK block list covers what TIPO counts
toward the abstract limit and what CNIPA considers "Chinese content".
"""

from __future__ import annotations


def is_cjk_char(ch: str) -> bool:
    """Return True if ``ch`` is a CJK-script character.

    Includes CJK Unified Ideographs, CJK Extensions A–D, Hiragana, Katakana,
    Bopomofo, and fullwidth ASCII variants. Excludes ASCII-adjacent code
    points, half-width punctuation, and emoji. Preserved at its original
    scope because TIPO counts these (not Hangul) toward the 250-char
    abstract limit — :func:`count_cjk_chars` and :func:`cjk_ratio` are
    load-bearing for that rule.

    For broader East-Asian script detection that also catches Korean
    Hangul, use :func:`is_east_asian_char` / :func:`east_asian_ratio`.
    """
    if not ch:
        return False
    cp = ord(ch)
    return (
        0x4E00 <= cp <= 0x9FFF        # CJK Unified Ideographs
        or 0x3400 <= cp <= 0x4DBF      # CJK Extension A
        or 0x20000 <= cp <= 0x2A6DF    # CJK Extension B
        or 0x2A700 <= cp <= 0x2B73F    # CJK Extension C
        or 0x2B740 <= cp <= 0x2B81F    # CJK Extension D
        or 0x3040 <= cp <= 0x309F      # Hiragana
        or 0x30A0 <= cp <= 0x30FF      # Katakana
        or 0x3100 <= cp <= 0x312F      # Bopomofo
        or 0xFF01 <= cp <= 0xFF5E      # Fullwidth ASCII variants
    )


def is_hangul_char(ch: str) -> bool:
    """Return True if ``ch`` is a Korean Hangul character."""
    if not ch:
        return False
    cp = ord(ch)
    return (
        0xAC00 <= cp <= 0xD7AF         # Hangul Syllables (main block)
        or 0x1100 <= cp <= 0x11FF      # Hangul Jamo
        or 0x3130 <= cp <= 0x318F      # Hangul Compatibility Jamo
        or 0xA960 <= cp <= 0xA97F      # Hangul Jamo Extended-A
        or 0xD7B0 <= cp <= 0xD7FF      # Hangul Jamo Extended-B
    )


def is_hiragana_or_katakana(ch: str) -> bool:
    """Return True if ``ch`` is a JP-specific kana character.

    Narrower than the raw Hiragana/Katakana Unicode blocks: excludes the
    script=Common code points that sit inside those blocks (middle dot,
    double hyphen, prolonged sound mark, voicing marks), because they
    are routinely used in Traditional Chinese typography. Treating them
    as "JP-specific" causes jurisdiction detectors to reject legitimate
    TW/CN drafts on a single stray punctuation character.

    Covered code points (all Unicode script=Hiragana or script=Katakana):
      - U+3041..U+3096  hiragana syllables (small + full)
      - U+309D..U+309F  hiragana iteration marks + digraph yori
      - U+30A1..U+30FA  katakana syllables
      - U+30FD..U+30FF  katakana iteration marks + digraph koto

    Explicitly excluded (script=Common despite living in the blocks):
      - U+3040 / U+3097 / U+3098  unassigned
      - U+3099..U+309C  combining + standalone voicing marks
      - U+30A0  KATAKANA-HIRAGANA DOUBLE HYPHEN
      - U+30FB  KATAKANA MIDDLE DOT  (seen in TW "保溫・保冷" usage)
      - U+30FC  KATAKANA-HIRAGANA PROLONGED SOUND MARK

    Kanji (CJK Unified Ideographs) is shared across CN/TW/JP, so its
    presence is not a JP-specificity signal either.
    """
    if not ch:
        return False
    cp = ord(ch)
    return (
        0x3041 <= cp <= 0x3096  # hiragana syllables
        or 0x309D <= cp <= 0x309F  # hiragana iteration + digraph
        or 0x30A1 <= cp <= 0x30FA  # katakana syllables
        or 0x30FD <= cp <= 0x30FF  # katakana iteration + digraph
    )


def is_east_asian_char(ch: str) -> bool:
    """Return True if ``ch`` is any East-Asian script character.

    Union of :func:`is_cjk_char` (CN/TW/JP shared) and :func:`is_hangul_char`
    (Korean). Used by jurisdiction detectors to short-circuit the
    "is this a US patent" check on any Asian-script input.
    """
    return is_cjk_char(ch) or is_hangul_char(ch)


def contains_hangul(text: str) -> bool:
    """Return True if ``text`` contains at least one Hangul character.

    Strict presence check (not a ratio) because TW patents should contain
    zero Korean script — a single Hangul character is enough to reject
    the document as TW.
    """
    if not text:
        return False
    return any(is_hangul_char(ch) for ch in text)


def contains_hiragana_or_katakana(text: str) -> bool:
    """Return True if ``text`` contains at least one JP-specific kana.

    Strict presence check. Prefer :func:`jp_kana_ratio` when deciding
    whether to reject a document as JP — real-world TW/CN drafts
    translated from JP priority documents sometimes retain a handful
    of katakana for transliterated brand names or technical terms
    (< 0.5% of content). A ratio-aware check tolerates that while
    still catching genuine JP documents.
    """
    if not text:
        return False
    return any(is_hiragana_or_katakana(ch) for ch in text)


def jp_kana_count(text: str) -> int:
    """Count JP-specific kana characters (narrowed; excludes middle dot etc.)."""
    if not text:
        return 0
    return sum(1 for ch in text if is_hiragana_or_katakana(ch))


def jp_kana_ratio(text: str) -> float:
    """Return the JP kana share of non-whitespace characters in ``text``.

    Empty input returns 0.0. Mirrors :func:`cjk_ratio` / :func:`east_asian_ratio`
    so jurisdiction detectors can tolerate trace kana (< 0.5% typical for
    TW/CN drafts carrying JP-priority-doc artifacts) while still rejecting
    genuinely Japanese documents (tens of percent kana content).
    """
    if not text:
        return 0.0
    total = 0
    kana = 0
    for ch in text:
        if ch.isspace():
            continue
        total += 1
        if is_hiragana_or_katakana(ch):
            kana += 1
    if total == 0:
        return 0.0
    return kana / total


def hangul_ratio(text: str) -> float:
    """Return the Hangul share of non-whitespace characters in ``text``.

    Mirror of :func:`jp_kana_ratio` for the Korean side. Real-world
    TW/CN drafts contain zero Hangul, so the threshold can be tighter
    than the JP one (any non-trivial ratio indicates a KO document).
    """
    if not text:
        return 0.0
    total = 0
    hangul = 0
    for ch in text:
        if ch.isspace():
            continue
        total += 1
        if is_hangul_char(ch):
            hangul += 1
    if total == 0:
        return 0.0
    return hangul / total


def count_cjk_chars(text: str) -> int:
    """Count CJK-script characters in ``text``.

    Empty or ``None`` input returns 0.
    """
    if not text:
        return 0
    return sum(1 for ch in text if is_cjk_char(ch))


def cjk_ratio(text: str) -> float:
    """Return the CJK share of non-whitespace characters in ``text``.

    Returns 0.0 for empty input. Whitespace is excluded from the denominator
    so the ratio reflects *content* script, not document padding. A document
    that is 100% CJK returns 1.0; a pure-ASCII document returns 0.0.

    Does NOT count Hangul — see :func:`east_asian_ratio` for a broader
    measure that catches Korean patents too.
    """
    if not text:
        return 0.0
    total = 0
    cjk = 0
    for ch in text:
        if ch.isspace():
            continue
        total += 1
        if is_cjk_char(ch):
            cjk += 1
    if total == 0:
        return 0.0
    return cjk / total


def east_asian_ratio(text: str) -> float:
    """Return the East-Asian-script share of non-whitespace characters.

    Union of CJK (CN/TW/JP shared) and Hangul (KO). Jurisdiction detectors
    use this rather than :func:`cjk_ratio` so that a Korean patent uploaded
    to the US jurisdiction selector is correctly rejected before the
    English-header / English-claim heuristics fire.
    """
    if not text:
        return 0.0
    total = 0
    asian = 0
    for ch in text:
        if ch.isspace():
            continue
        total += 1
        if is_east_asian_char(ch):
            asian += 1
    if total == 0:
        return 0.0
    return asian / total
