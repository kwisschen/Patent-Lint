# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""CJK tokenization helper — character-bigram path (ADR-094).

Provides stateless character-bigram tokenization for TW and CN antecedent
walker did-you-mean layers. No NLP dependency, no lemmatization, no
tokenizer library. The helper strips standard CJK punctuation, preserves
Latin characters and Arabic digits as-is, and returns a sorted deduped
list of overlapping character bigrams (or a unigram fallback for strings
of length < 2 after stripping).

Contract and known limits are documented in ADR-094
(``docs/architectural-decisions.md``). Both ``tokenize_tw`` and
``tokenize_cn`` share a single implementation via ``_tokenize_bigrams``;
the separation is API-level only, for call-site clarity and forward
compatibility with jurisdiction-specific normalization (deferred to
Phase 10+).
"""

from __future__ import annotations

# Standard CJK punctuation stripped at tokenize time. Latin punctuation
# is preserved because Chinese patent text sometimes embeds English
# acronyms, model numbers, and formulas where punctuation is semantic.
_CJK_PUNCTUATION = "。！？，、；：「」『』（）《》【】"


def _tokenize_bigrams(text: str) -> list[str]:
    """Return sorted deduped overlapping character bigrams.

    Steps (per ADR-094 contract):
        1. Strip CJK punctuation
        2. If stripped length < 2, return [stripped] (unigram fallback);
           an empty stripped string returns [].
        3. Otherwise, return sorted unique overlapping bigrams.
    """
    stripped = "".join(ch for ch in text if ch not in _CJK_PUNCTUATION)
    if not stripped:
        return []
    if len(stripped) < 2:
        return [stripped]
    bigrams = {stripped[i:i + 2] for i in range(len(stripped) - 1)}
    return sorted(bigrams)


def tokenize_tw(text: str) -> list[str]:
    """Tokenize traditional Chinese text into overlapping character bigrams.

    Steps:
        1. Strip CJK punctuation: 。！？，、；：「」『』（）《》【】
        2. Preserve Latin characters, Arabic digits, and whitespace as-is
        3. If stripped length < 2, return [stripped_text] (unigram fallback)
        4. Otherwise, return sorted deduped list of overlapping bigrams

    Example:
        tokenize_tw("組成物") -> ["成物", "組成"]
        tokenize_tw("光") -> ["光"]
        tokenize_tw("USB接口") -> ["B接", "SB", "US", "接口"]
    """
    return _tokenize_bigrams(text)


def tokenize_cn(text: str) -> list[str]:
    """Tokenize simplified Chinese text. Currently identical to tokenize_tw.

    Separate function maintained for call-site clarity and forward
    compatibility with jurisdiction-specific normalization
    (traditional/simplified equivalence, deferred to Phase 10+).
    """
    return _tokenize_bigrams(text)


def jaccard(a_tokens: list[str], b_tokens: list[str]) -> float:
    """Jaccard similarity over two token lists.

    Convenience helper for the walker's did-you-mean layer so callers
    don't have to reach for ``token_set_jaccard`` from ``analysis.utils``
    (which splits on whitespace and is English-specific).
    """
    set_a = set(a_tokens)
    set_b = set(b_tokens)
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)
