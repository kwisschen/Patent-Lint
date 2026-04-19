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
    points, half-width punctuation, and emoji.
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
