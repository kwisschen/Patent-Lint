# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
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
    """Return True if ``ch`` is a Japanese-specific kana character.

    Hiragana and Katakana are Japan-only — neither CN nor TW patents use
    these scripts. Kanji (CJK Unified Ideographs) is shared across CN, TW,
    and JP, so presence of kanji alone is not a Japanese-specificity
    signal; presence of kana is.
    """
    if not ch:
        return False
    cp = ord(ch)
    return 0x3040 <= cp <= 0x309F or 0x30A0 <= cp <= 0x30FF


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
    """Return True if ``text`` contains at least one hiragana or katakana.

    Strict presence check (not a ratio) because TW/CN patents should
    contain zero Japanese-specific kana — a single kana is enough to
    reject the document as Japanese.
    """
    if not text:
        return False
    return any(is_hiragana_or_katakana(ch) for ch in text)


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
