# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""English morphology normalization for antecedent-basis matching.

This module provides normalization helpers applied at the comparison
boundary, never at intro registration time. Stored terms and display
forms remain untouched; only lookup keys are normalized.

Architectural analogue of TW walker ADR-095 Rule 3: symmetric
normalization of reference term and candidate intro.
"""

from __future__ import annotations

# Word endings that look plural but are not. Keep ordered by specificity.
# -ss: glass, class, process (handled separately via -sses rule)
# -us: bus, apparatus, focus, radius, nucleus
# -is: basis, axis, analysis, thesis, chassis
# -as: gas, bias, canvas
# -os: logo, silo, ratio (plain -os is rarely a plural in patents)
_NOT_PLURAL_ENDINGS = ("ss", "us", "is", "as", "os")


def _depluralize_word(word: str) -> str:
    """Return the singular form of a single English word.

    Rules applied in order (first match wins):
      1. -ies  -> -y       (bodies -> body, assemblies -> assembly)
      2. -sses -> -ss      (processes -> process, classes -> class)
      3. -xes / -zes / -ches / -shes -> strip -es
         (switches -> switch, boxes -> box, brushes -> brush)
      4. plain -s -> strip, with _NOT_PLURAL_ENDINGS guard
         (inductors -> inductor, circuits -> circuit;
          bus / basis / gas / logo stay unchanged)

    Minimum-length guards prevent degenerate strips on short words.
    Returns the input unchanged if no rule applies.
    """
    if not word:
        return word
    lowered = word.lower()

    # Rule 1: -ies -> -y
    if len(lowered) > 3 and lowered.endswith("ies"):
        return word[:-3] + "y"

    # Rule 2: -sses -> -ss
    if len(lowered) > 4 and lowered.endswith("sses"):
        return word[:-2]

    # Rule 3: -(x|z|ch|sh)es -> strip -es
    if len(lowered) > 3 and (
        lowered.endswith("xes")
        or lowered.endswith("zes")
        or lowered.endswith("ches")
        or lowered.endswith("shes")
    ):
        return word[:-2]

    # Rule 4: plain -s with guards
    # R39 (2026-05-04): tightened minimum from `>2` to `>3`. 3-char
    # `-s` words in patent claims are dominantly acronym-plurals
    # (`OMS`, `OFT` no, `OMS` yes, `UEs`, `APs`, `MACs`) where the
    # trailing s is part of the acronym, not a plural marker.
    # Stripping caused walker over-bridges: ref `OM` was silenced by
    # intro `OMS` because both depluralized to `om`. Real 3-char
    # plurals (`pcs`, `kids`) are uncommon in formal patent claim
    # language; the larger word base (>=4 chars) covers ordinary
    # patent vocabulary (`circuits`, `inductors`, `signals`, etc.).
    if len(lowered) > 3 and lowered.endswith("s"):
        for bad in _NOT_PLURAL_ENDINGS:
            if lowered.endswith(bad):
                return word
        return word[:-1]

    return word


def en_number_key(term: str) -> str:
    """Return a number-agnostic lookup key for an English noun phrase.

    Depluralizes the LAST token only. Premodifier plurals
    ('sales report', 'goods train') are idiomatic and do not
    participate in antecedent-basis matching in patent claims.

    The input is assumed to already be lowercase and
    clean_noun_phrase'd. This function does not apply those
    transforms itself.

    Examples:
        en_number_key("first filter inductors") -> "first filter inductor"
        en_number_key("processes") -> "process"
        en_number_key("bodies") -> "body"
        en_number_key("apparatus") -> "apparatus"  # guarded
        en_number_key("bus") -> "bus"              # guarded
    """
    if not term:
        return term
    parts = term.rsplit(" ", 1)
    if len(parts) == 2:
        head, tail = parts
        return f"{head} {_depluralize_word(tail)}"
    return _depluralize_word(term)
