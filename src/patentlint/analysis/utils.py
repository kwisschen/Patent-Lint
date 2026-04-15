# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
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
    # Additional 3sg verb forms observed over-capturing NP boundaries in
    # US fixtures (testspec2/3/6, test6, testspec9). Empirical denylist —
    # each form verified against the fixture that surfaced it.
    "exhibit", "exhibits", "exhibited", "exhibiting",
    "compare", "compares", "compared", "comparing",
    "apply", "applies", "applied", "applying",
    "turn", "turns", "turned", "turning",
    "stop", "stops", "stopped", "stopping",
    "multiply", "multiplies", "multiplied", "multiplying",
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

# Trailing bare cardinals — strip when the captured NP ends on a cardinal
# because the regex bled past a verb+numeral chain (e.g. "respectively
# define two"). Only applied when the phrase has additional tokens so a
# standalone "two" / "three" captured from "the two" / "the three" is
# preserved and handled elsewhere.
_TRAILING_CARDINAL_STOPS = {
    "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
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
                     'cts', 'pts', 'rts', 'sts',
                     # Commit 10b: catch 'outputs' (-uts). Surfaced by the
                     # testspec5 browser smoke test where claim 2 captured
                     # 'the surge detection driver circuit outputs' as a
                     # reference term. Other gaps (-its, -rns, -ops, -ies)
                     # deferred to Phase 9.
                     'uts')
    return any(word.endswith(s) for s in verb_suffixes)


# Tokens that, when sitting immediately before a -uts word, mean the
# -uts word is the head noun and must NOT be stripped. Articles and
# the prepositional 'of' are the load-bearing cases ('the outputs',
# 'plurality of inputs'). See the guard in clean_noun_phrase.
_UTS_GUARD_PRECEDERS = {"the", "a", "an", "said", "of"}

# -ly words that are nouns in patent context. Trailing -ly adverbs are
# stripped unless the word is in this allowlist.
_LY_NOUN_ALLOWLIST = {
    "supply", "assembly", "family", "anomaly", "reply", "ally", "rally",
    "subassembly", "resupply",
}


# Trailing distributive quantifiers ("the four unit regions each",
# "the groups each having X") — these are post-modifier quantifiers, not part
# of the noun phrase. Stripping them bilaterally (intro + reference) dedups
# distributive references against plain plural intros.
_DISTRIBUTIVE_QUANTIFIERS = frozenset({"each", "both", "all", "every"})


def _is_trailing_distributive(word: str) -> bool:
    return word in _DISTRIBUTIVE_QUANTIFIERS


def _is_trailing_ly_adverb(word: str) -> bool:
    """Detect -ly adverbs that terminate over-captured NPs.

    Patent intro / reference captures routinely bleed past a noun into an
    adverb+participle post-modifier ("a microphone electrically connected to
    …"). The `_STOP_WORDS` regex stops at the participle ("connected") but
    leaves the -ly adverb attached to the noun. Strip when trailing.
    """
    if len(word) < 5 or not word.endswith("ly"):
        return False
    if word in _LY_NOUN_ALLOWLIST:
        return False
    return True


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
        or _is_trailing_ly_adverb(w)
        or _is_trailing_distributive(w)
    ):
        return True
    # Strip trailing -ing verbs/gerunds (mirrors single-word rejection at clean_noun_phrase)
    if w.endswith("ing") and len(w) >= 6 and w not in _ING_NOUNS:
        return True
    return False


# Contextual verb stops: words that are ambiguous between noun and verb use
# (irregular past participles like `output`/`input`; verb/plural-noun pairs
# like `range`/`ranges`). Strip from the trailing position of a captured NP
# only when the source-text token immediately following the span is in the
# complement set — that signals verb use ("the signals output TO the driver",
# "the agent ranges FROM X to Y"). Plain "the outputs" / "the temperature
# ranges" (no following complement) keeps the head noun.
_CONTEXTUAL_VERB_STOPS = {
    "output":  frozenset({"to", "from", "by", "with", "via", "on", "into", "onto", "toward", "towards"}),
    "input":   frozenset({"to", "from", "by", "with", "via", "on", "into", "onto"}),
    "range":   frozenset({"from", "between", "to", "over", "in", "through"}),
    "ranges":  frozenset({"from", "between", "to", "over", "in", "through"}),
    "ranged":  frozenset({"from", "between", "to", "over", "in", "through"}),
    "ranging": frozenset({"from", "between", "to", "over", "in", "through"}),
}

_NEXT_WORD_RE = re.compile(r"\s*([A-Za-z][A-Za-z'\u2019-]*)")


def strip_contextual_verb(term: str, following_text: str) -> str:
    """Strip a trailing ambiguous verb form when following text confirms verb use.

    ``following_text`` is the source text immediately after the captured span.
    """
    if not term:
        return term
    words = term.split()
    if not words:
        return term
    last = words[-1].lower().rstrip(".,;:")
    complements = _CONTEXTUAL_VERB_STOPS.get(last)
    if not complements:
        return term
    m = _NEXT_WORD_RE.match(following_text)
    if not m:
        return term
    if m.group(1).lower() not in complements:
        return term
    return " ".join(words[:-1])


def clean_noun_phrase(phrase: str) -> str:
    """Strip trailing verbs, adverbs, and function words from a noun phrase."""
    words = phrase.strip().split()
    while words:
        last = words[-1].lower().rstrip(".,;:")
        # Trailing bare cardinal ("respectively define two") — strip only
        # when the phrase has other tokens, so standalone "two" captured
        # from "the two" survives to be handled by the walker's quantifier
        # stop-list.
        if last in _TRAILING_CARDINAL_STOPS and len(words) > 1:
            words.pop()
            continue
        if not _should_strip_trailing(words[-1]):
            break
        # Guard for the -uts suffix: 'inputs' / 'outputs' are ambiguous
        # between verb ('the circuit outputs the signal') and plural noun
        # ('the inputs', 'plurality of outputs'). The general suffix rule
        # cannot tell them apart, so apply this disambiguator: only strip
        # the -uts word when popping would leave a real noun behind. If
        # the remaining phrase would end on an article or preposition,
        # the -uts word IS the head noun — keep it.
        candidate = words[-1].lower().rstrip(".,;:")
        if candidate.endswith("uts") and len(words) >= 2:
            prev = words[-2].lower().rstrip(".,;:")
            if prev in _UTS_GUARD_PRECEDERS:
                break
        if candidate.endswith("uts") and len(words) < 2:
            # Standalone 'outputs' / 'inputs' is also a head noun, not a verb.
            break
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
    # Allow the list run to span newlines; patent drafters put each list
    # item on its own line ("comprising:\n  a pigment;\n  polyurethane
    # microparticles ..."). The period is still a hard boundary, and the
    # capture stops at ``wherein`` so an outer ``comprising`` trigger
    # doesn't swallow inner ``includes`` triggers later in the same claim.
    r"(?P<list>(?:(?!\bwherein\b)[^.])+)",
    re.IGNORECASE | re.DOTALL,
)

_LIST_ITEM_SPLIT = re.compile(r"[,;]|\s+and\s+|\s+or\s+", re.IGNORECASE)
# Semicolon-dominant lists (multi-line "comprising:" / "includes:" blocks)
# split on ``;`` only, so internal commas/"and" inside a single item do not
# fragment the item (e.g. "X connected to A, B, and C" stays one item).
_SEMICOLON_SPLIT = re.compile(r";")
_LEADING_AND = re.compile(r"^\s*and\s+", re.IGNORECASE)
# Only ``a``/``an`` are stripped — list items starting with ``the`` are
# back-references, not introductions, and must not be re-registered.
_LEADING_ARTICLE = re.compile(r"^(?:a|an)\s+", re.IGNORECASE)
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
        # Pick the list separator. When semicolons are present the list
        # is a semicolon-dominant enumeration where a single item can
        # contain internal commas and "and" ("X connected to A, B, and
        # C"), so splitting on commas/and would mis-fragment items and
        # surface back-references like "the <X>" as false intros. Fall
        # back to comma/and/or only for pure-comma lists (Markush groups
        # and single-line "comprising a, b, and c" preambles).
        if ";" in list_text:
            raw_items = _SEMICOLON_SPLIT.split(list_text)
        else:
            raw_items = _LIST_ITEM_SPLIT.split(list_text)
        for raw in raw_items:
            item = _LEADING_AND.sub("", raw.strip()).strip()
            if not item:
                continue
            item = _LEADING_ARTICLE.sub("", item).strip()
            # Reduce each item to its head NP via the core NP pattern so
            # multi-line list items like "polyurethane microparticles
            # having a glass transition temperature of 40°C" collapse to
            # "polyurethane microparticles" (stops at the post-modifier
            # "having"). Items whose first token is a stop word (e.g.
            # "when the impermeable medium contains...") produce no NP
            # match and are skipped.
            np_match = re.match(rf"\s*({_NP_CORE})", item, re.IGNORECASE)
            if not np_match:
                continue
            cleaned = clean_noun_phrase(np_match.group(1).strip())
            if cleaned:
                refs.append(cleaned.lower())
    return refs


_DEFINITE_PRECEDER = re.compile(r"(?:\bthe|\bsaid)\s+$", re.IGNORECASE)


def extract_introductions(text: str) -> list[str]:
    """Extract all element-introduction noun phrases from patent text.

    Covers standard patent quantifiers (a/an, at least one, one or more,
    a plurality of, ordinals, bare numerals) AND bare-noun list contexts
    (comprising / includes / consisting of / selected from … X, Y, and Z).

    Returns list of lowercase noun phrases (may contain duplicates).

    Matches preceded by ``the`` or ``said`` are back-references, not
    introductions, and are filtered out. This prevents quantified
    back-references like ``the two second edges`` from re-introducing
    ``second edges`` in downstream claims and masking the real earlier
    intro.
    """
    lowered = text.lower()
    refs: list[str] = []
    for m in _INTRO_PATTERNS.finditer(lowered):
        preceding = lowered[max(0, m.start() - 8) : m.start()]
        if _DEFINITE_PRECEDER.search(preceding):
            continue
        cleaned = clean_noun_phrase(m.group(1).strip())
        if cleaned:
            refs.append(cleaned)
    refs.extend(extract_bare_noun_intros(lowered))
    return refs


def extract_introductions_permissive(text: str) -> list[str]:
    """Variant of extract_introductions used by the cross-claim fallback
    registry (Fix #47). When an intro match is filtered (preceded by
    ``the``/``said``), advances by a single char rather than consuming past
    the match — so a later unfiltered trigger inside the filtered span
    (e.g. ``the two X ... two Y``) still surfaces. Emission-path extraction
    stays unchanged.
    """
    lowered = text.lower()
    refs: list[str] = []
    pos = 0
    while pos < len(lowered):
        m = _INTRO_PATTERNS.search(lowered, pos)
        if not m:
            break
        preceding = lowered[max(0, m.start() - 8) : m.start()]
        if _DEFINITE_PRECEDER.search(preceding):
            pos = m.start() + 1
            continue
        cleaned = clean_noun_phrase(m.group(1).strip())
        if cleaned:
            refs.append(cleaned)
        pos = m.end()
    refs.extend(extract_bare_noun_intros(lowered))
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


def token_set_jaccard(a: str, b: str) -> float:
    """Token-set Jaccard similarity over whitespace-split lowercase tokens.

    Used by the antecedent walker's did-you-mean suggestion layer (commit 10):
    when a definite reference has no exact-match introduction, the highest
    Jaccard intro in the same claim's ancestor set is offered as a hint when
    similarity is at least 0.5. Morphological variants such as "common voltage
    difference calculation circuit" vs "common voltage difference calculating
    circuit" share four of five tokens (Jaccard 0.667) and surface as a
    suggestion rather than being silently matched.
    """
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)
