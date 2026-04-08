# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""Shared analysis utilities.

Extracted from analysis/claims.py for reuse across multiple checks.
"""

import re

# Hyphen-aware word token: matches "multi-stage", "non-transitory", "widget"
_WORD = r"\w+(?:-\w+)*"

# Captures noun phrases (up to 6 words) after "the"/"said" or "a"/"an".
_STOP_WORDS = (
    r"(?:is|are|was|were|has|have|had|do|does|did|being|been|"
    r"can|could|may|might|will|would|shall|should|must|"
    r"of|to|from|with|and|or|that|which|for|by|on|in|at|as|"
    r"along|between|through|within|upon|above|below|across|"
    r"toward|towards|against|around|during|into|onto|"
    r"beside|beneath|beyond|behind|before|after|among|about|"
    r"inside|outside|throughout|until|without|"
    r"but|if|so|yet|nor|who|whom|whose|where|when|while|"
    r"wherein|comprising|consisting|including|having|configured|"
    r"adapted|arranged|coupled|connected|mounted|disposed|storing|determining|corresponding|"
    r"extends|provides|receives|generates|produces|performs|"
    r"executes|transmits|operates|determines|defines|forms|"
    r"supports|enables|allows|causes|includes|contains|"
    r"encompasses|creates|maintains|controls|establishes|"
    r"represents|surrounds|overlaps|"
    r"a|an|the|said)"
)

_NP_CORE = rf"(?:(?!{_STOP_WORDS}\b){_WORD}\s+){{0,5}}(?:(?!{_STOP_WORDS}\b){_WORD})"
_NP_CAPTURE = rf"({_NP_CORE})"

_DEFINITE_REF = re.compile(
    rf"\b(?P<prefix>the|said)\s+(?P<noun>{_NP_CORE})",
    re.IGNORECASE,
)

_INDEFINITE_REF = re.compile(
    rf"\b(?:a|an)\s+{_NP_CAPTURE}",
    re.IGNORECASE,
)

# Extended introduction patterns for antecedent basis.
# Matches all standard patent element-introduction phrases:
#   a/an X, at least one/a/an X, one or more X, a plurality of X,
#   two/three/four X. Ordinals (first..tenth and beyond) are NOT consumed
#   as a prefix — they fall through to the generic ``(?:a|an)\s+`` arm and
#   are picked up by ``_NP_CORE`` as the leading word of the captured noun
#   phrase, so "a first engaging structure" yields the full phrase
#   "first engaging structure" rather than dropping the ordinal.
_INTRO_PATTERNS = re.compile(
    r"\b(?:"
    # Specific multi-word patterns first (before generic a/an)
    r"at\s+least\s+(?:one|a|an)\s+"        # at least one widget
    r"|one\s+or\s+more\s+"                  # one or more widgets
    r"|a\s+plurality\s+of\s+"              # a plurality of widgets
    r"|(?:one|two|three|four|five|six|seven|eight|nine|ten)\s+"  # five widgets
    # Generic a/an last — captures any following noun phrase, including
    # ones that begin with an ordinal (first/second/.../tenth/...)
    r"|(?:a|an)\s+"                          # a widget, a first widget, an apparatus
    r")" + _NP_CAPTURE,
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Noun phrase trailing-word cleanup
# ---------------------------------------------------------------------------

# Adverbs and patent function words — always strip from phrase end
_ADVERB_STOPS = {
    # Adverbs
    "further", "additionally", "generally", "respectively",
    "jointly", "collectively", "simultaneously", "preferably",
    "optionally", "selectively", "removably", "rotatably",
    "slidably", "pivotally", "movably", "fixedly",
    "substantially", "essentially", "approximately",
    "typically", "normally", "merely", "primarily",
    # Patent function words
    "thereof", "therein", "thereto", "thereby", "therefrom",
    "thereon", "therethrough", "therebetween",
    "according", "accordingly",
    "herein", "hereinafter", "hereinbefore",
    # Conjunctions/prepositions that shouldn't end a noun phrase
    "when", "where", "while", "so", "such",
}

# Universal patent verbs (appear in every technology area)
_VERB_STOPS = {
    # Be/have
    "is", "are", "was", "were", "has", "have", "had", "being",
    # Universal patent-drafting verbs (base / -s / -ed / -ing where unambiguous)
    "include", "includes", "including", "included",
    "comprise", "comprises", "comprising", "comprised",
    "consist", "consists", "consisting",
    "define", "defines", "defined", "defining",
    "provide", "provides", "provided", "providing",
    "form", "forms", "formed", "forming",
    "having",
    # Common 3rd-person present forms in patent descriptions
    "pushes", "pulls", "holds", "moves", "slides", "rotates",
    "engages", "extends", "receives", "supports", "contacts",
    "connects", "abuts", "faces", "carries", "covers",
    "executes", "transmits", "generates", "determines", "operates",
    "leaves", "allows", "enables", "prevents", "permits",
    "encompasses", "contains", "produces", "creates", "maintains",
    "controls", "establishes", "represents", "surrounds", "overlaps",
    # Modal verbs
    "must", "shall", "should", "can", "could", "may", "might", "will", "would",
}

# -ing words that are UNAMBIGUOUSLY verbs in patent context (never nouns)
_ING_VERB_ONLY = {
    "comprising", "consisting", "including", "having",
    "being", "using", "providing", "forming",
    "defining", "resulting",
}

# Known -ed words that are nouns, not participles
_ED_NOUNS = {"bed", "red", "shed", "led", "fed", "infrared", "overhead"}

# Prepositions that should not end a noun phrase
_PREPOSITION_STOPS = {
    "along", "between", "through", "within", "upon", "above", "below",
    "across", "toward", "towards", "against", "around", "during", "into",
    "onto", "over", "under", "from", "with", "without", "beside", "beneath",
    "beyond", "behind", "before", "after", "among", "about", "inside",
    "outside", "throughout", "near", "past", "until", "as", "via",
}

# Trailing conjunctions and relative pronouns
_TRAILING_FUNCTION_WORDS = {
    "and", "or", "but", "that", "which", "who", "whom", "whose",
    "where", "when", "while", "if", "so", "yet", "nor",
}

# Quantifiers/pronouns that should NOT be flagged as standalone elements
_QUANTIFIER_STOPS = {
    "one", "another", "other", "others",
    "plurality", "remainder", "rest",
    "each", "both", "either", "neither",
    "any", "some", "all", "none",
    "former", "latter",
    "first", "second", "third", "fourth", "fifth",
    "same", "certain", "particular",
    # Hyphen prefixes (belt-and-suspenders in case regex splits them)
    "non", "pre", "sub", "bi", "multi", "semi", "co", "re",
    "inter", "intra", "over", "under", "anti", "cross", "self", "single",
}


def _is_likely_past_participle(word: str) -> bool:
    """Detect -ed words that are likely verbs/participles, not nouns."""
    if not word.endswith("ed"):
        return False
    if word in _ED_NOUNS:
        return False
    return len(word) >= 5


# Known -es words that are nouns, not 3rd-person verbs
_ES_NOUNS = {
    "devices", "interfaces", "surfaces", "instances", "sequences",
    "databases", "voltages", "packages", "images", "edges", "bridges",
    "ridges", "passages", "stages", "ranges", "changes", "charges",
    "exchanges", "resources", "sources", "forces", "services",
    "grooves", "pieces", "valves", "processes", "addresses",
    "matrices", "indices", "vertices", "appendices",
    "structures",
    "lenses", "buses", "gases", "axes", "bases", "cases",
    "phases", "cables", "tables", "modules", "nodes", "modes",
    "types", "tubes", "plates", "gates", "states", "rates",
    "wires", "cores", "pores", "stores", "frames", "names",
    "files", "tiles", "holes", "poles", "roles", "rules",
    "lines", "zones", "tones", "sides", "guides", "codes",
    "diodes", "anodes", "cathodes", "electrodes",
}


def _is_likely_third_person_verb(word: str) -> bool:
    """Detect -s/-es words that are likely 3rd-person present verbs, not nouns."""
    if len(word) < 6:
        return False
    if word in _ES_NOUNS:
        return False
    verb_suffixes = ('ates', 'izes', 'ifies', 'ects', 'uces', 'ases', 'oses',
                     'ures', 'ises', 'ples', 'bles', 'ades', 'odes', 'udes',
                     'eases',
                     # Commit 9d: catch verbs like 'subtracts' (-cts),
                     # 'accepts' (-pts), 'converts' (-rts), 'consists' (-sts).
                     'cts', 'pts', 'rts', 'sts')
    return any(word.endswith(s) for s in verb_suffixes)


# Known -ing words that are legitimate nouns in patent context
_ING_NOUNS = {
    "ring", "spring", "string", "wiring", "bearing", "housing",
    "coating", "opening", "coupling", "mounting", "casing", "tubing",
    "spacing", "sealing", "shielding", "plating", "grounding",
    "bonding", "molding", "shaping", "imaging", "computing",
    "processing", "printing", "recording", "building", "ceiling",
    "setting", "fitting", "cutting", "routing", "lighting",
    "padding", "mapping", "logging", "binding", "lining",
    "timing", "rating", "loading", "testing",
}


def _should_strip_trailing(word: str) -> bool:
    w = word.lower().rstrip(".,;:")
    if (
        w in _ADVERB_STOPS
        or w in _VERB_STOPS
        or w in _ING_VERB_ONLY
        or w in _PREPOSITION_STOPS
        or w in _TRAILING_FUNCTION_WORDS
        or _is_likely_past_participle(w)
        or _is_likely_third_person_verb(w)
    ):
        return True
    # Strip trailing -ing verbs/gerunds (mirrors single-word rejection at clean_noun_phrase)
    if w.endswith("ing") and len(w) >= 6 and w not in _ING_NOUNS:
        return True
    return False


def clean_noun_phrase(phrase: str) -> str:
    """Strip trailing verbs, adverbs, and function words from a noun phrase."""
    words = phrase.strip().split()
    while words and _should_strip_trailing(words[-1]):
        words.pop()
    # Strip possessives: "device's" → "device", "users'" → "users"
    words = [w.replace("\u2019s", "").replace("'s", "").rstrip("\u2019'") for w in words]
    # Remove any tokens that became empty after stripping
    words = [w for w in words if w]
    result = " ".join(words) if words else phrase
    # Reject single-word results that are likely verbs/adjectives, not nouns
    if len(result.split()) == 1:
        w = result.lower().rstrip(".,;:")
        if w in _ING_VERB_ONLY:
            return ""
        if w.endswith("ing") and len(w) >= 6 and w not in _ING_NOUNS:
            return ""
    return result


# Abbreviation pattern: "full term (ABBREV) trailing_noun"
_ABBREVIATION_PATTERN = re.compile(
    r"\b(?:[a-z][\w-]*\s+){1,5}"    # 1-5 words before abbreviation
    r"\(([A-Z]{2,})\)\s*"            # (ABBREV) — 2+ uppercase letters
    r"(\w+)?",                        # optional trailing noun
)


def extract_abbreviation_intros(text: str) -> list[str]:
    """Extract abbreviated forms from parenthetical abbreviation patterns.

    E.g., "alternating current (AC) source" → "ac source"
    """
    results: list[str] = []
    for m in _ABBREVIATION_PATTERN.finditer(text):
        abbrev = m.group(1).lower()
        trailing = m.group(2)
        if trailing:
            results.append(f"{abbrev} {trailing.lower()}")
        results.append(abbrev)
    return results


# ---------------------------------------------------------------------------
# Extraction functions
# ---------------------------------------------------------------------------


# List-context introduction extraction.
#
# Patents commonly drop articles for the second-and-later items of a list:
#   "comprising a base, pivot, and arm"
#   "includes a base; pivot; and arm"
#   "selected from the group consisting of methanol, ethanol, and propanol"
# The bare nouns ('pivot', 'arm', 'ethanol', 'propanol') are introductions
# but the existing _INTRO_PATTERNS regex requires an article prefix and
# misses them. We capture the run after a list-context trigger word, then
# split on commas/semicolons/and/or to recover each list item.
#
# Extraction is *gated* on a list-context trigger so arbitrary commas
# elsewhere in claim text do not produce noise.
_LIST_CONTEXT_PATTERN = re.compile(
    r"\b(?:"
    r"includes?"
    r"|including"
    r"|comprises?"
    r"|comprising"
    r"|consisting(?:\s+essentially)?\s+of"
    r"|selected\s+from(?:\s+the\s+group(?:\s+consisting\s+of)?)?"
    r")\s*:?\s+"
    r"(?P<list>[^.\n]+)",
    re.IGNORECASE,
)

_LIST_ITEM_SPLIT = re.compile(r"[,;]|\s+and\s+|\s+or\s+", re.IGNORECASE)
_LEADING_ARTICLE = re.compile(r"^(?:a|an|the)\s+", re.IGNORECASE)
_LIST_CONTEXT_BREAKER = re.compile(r"\bwherein\b", re.IGNORECASE)


def extract_bare_noun_intros(text: str) -> list[str]:
    """Extract introductions from bare-noun list contexts.

    Three patterns previously missed by ``_INTRO_PATTERNS``:

    1. Semicolon-separated bare-noun lists::

           "the assembly includes a base; pivot; and arm"

       ``pivot`` and ``arm`` are bare nouns following an established list
       separator and inherit introduction status.

    2. Comma-separated preamble lists::

           "An apparatus comprising base, pivot, and arm"

       Same shape, comma instead of semicolon, no leading article on
       second-and-later items.

    3. Markush group members::

           "selected from the group consisting of methanol, ethanol, and propanol"

       Each chemical name is an introduction. The bare ``group`` itself
       should not be flagged as missing an antecedent — that false-positive
       is handled at the walker level in commit 9b.

    The captured run is truncated at ``wherein`` so wherein-clauses do not
    bleed into the list. Items are then split on ``,``/``;``/``and``/``or``,
    article-stripped, and run through ``clean_noun_phrase``.
    """
    refs: list[str] = []
    for m in _LIST_CONTEXT_PATTERN.finditer(text):
        list_text = m.group("list")
        breaker = _LIST_CONTEXT_BREAKER.search(list_text)
        if breaker:
            list_text = list_text[: breaker.start()]
        for raw in _LIST_ITEM_SPLIT.split(list_text):
            item = raw.strip()
            if not item:
                continue
            item = _LEADING_ARTICLE.sub("", item).strip()
            cleaned = clean_noun_phrase(item)
            if cleaned:
                refs.append(cleaned.lower())
    return refs


def extract_introductions(text: str) -> list[str]:
    """Extract all element-introduction noun phrases from patent text.

    Covers standard patent quantifiers (a/an, at least one, one or more,
    a plurality of, ordinals, bare numerals) AND bare-noun list contexts
    (comprising / includes / consisting of / selected from … X, Y, and Z).

    Returns list of lowercase noun phrases (may contain duplicates).
    """
    refs: list[str] = []
    for m in _INTRO_PATTERNS.finditer(text.lower()):
        cleaned = clean_noun_phrase(m.group(1).strip())
        if cleaned:
            refs.append(cleaned)
    refs.extend(extract_bare_noun_intros(text.lower()))
    return refs


def extract_noun_phrases(text: str) -> list[str]:
    """Extract meaningful noun phrases from patent text.

    Reused by antecedent basis check and spec support check.
    Returns deduplicated list of lowercase noun phrases.
    """
    phrases: set[str] = set()
    for m in _INDEFINITE_REF.finditer(text.lower()):
        cleaned = clean_noun_phrase(m.group(1).strip())
        if cleaned:
            phrases.add(cleaned)
    for m in _DEFINITE_REF.finditer(text.lower()):
        cleaned = clean_noun_phrase(m.group("noun").strip())
        if cleaned:
            phrases.add(cleaned)
    return sorted(phrases)


def extract_definite_refs(text: str) -> list[str]:
    """Extract definite references ('the X', 'said X') from text."""
    refs: list[str] = []
    for m in _DEFINITE_REF.finditer(text.lower()):
        cleaned = clean_noun_phrase(m.group("noun").strip())
        if cleaned:
            refs.append(cleaned)
    return refs


def extract_indefinite_refs(text: str) -> list[str]:
    """Extract indefinite references ('a X', 'an X') from text."""
    refs: list[str] = []
    for m in _INDEFINITE_REF.finditer(text.lower()):
        cleaned = clean_noun_phrase(m.group(1).strip())
        if cleaned:
            refs.append(cleaned)
    return refs
