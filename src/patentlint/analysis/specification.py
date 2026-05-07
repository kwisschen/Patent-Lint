# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Specification section analysis.

Checks paragraph endings, numbering sequentiality, restrictive wording,
sequence listing references, and reference numeral consistency.
"""

import re
from collections import Counter

from patentlint.analysis.utils import _dx
from patentlint.models import CheckItem, ReferenceNumeral, SpecWordingResult

# Narrowing language per MPEP 2111.01(II): "critical, important, essential,
# vital, and necessary are indicative of limitations that narrow claim
# scope." Paired with absolute quantifiers (always, never, must, only,
# solely, every) and MPEP-adjacent narrowers (required, imperative,
# indispensable).
#
# Deliberately narrower than the historical lexicon (Phase 9 #72b audit,
# 2026-04-19): "invention", "particular", "specific", and "key" were
# removed because they dominated the verify noise with non-narrowing
# uses — "the invention relates to...", "a particular embodiment",
# "a specific example", "key feature" are all standard drafting
# conventions, not MPEP-flagged scope-narrowers.
_RESTRICTIVE_WORDING = re.compile(
    r"(?i)\b(always|never|must|solely|every|required|essential|critical|vital"
    r"|necessary|imperative|indispensable)\b"
)


def has_valid_ending(paragraph_text: str, is_description_of_drawings: bool = False) -> bool:
    """Check if a paragraph has valid ending punctuation."""
    t = paragraph_text.strip()
    base_endings = (
        t.endswith(".") or t.endswith('.\"') or t.endswith('.\u201D')
        or t.endswith("!") or t.endswith('!\"') or t.endswith('!\u201D')
        or t.endswith("?") or t.endswith('?\"') or t.endswith('?\u201D')
        or t.endswith(":")
    )
    if is_description_of_drawings:
        return base_endings or t.endswith(";") or t.endswith("; and")
    return base_endings


def are_paragraphs_sequential(paragraph_numbers: list[int]) -> bool:
    for i in range(1, len(paragraph_numbers)):
        if paragraph_numbers[i] - paragraph_numbers[i - 1] != 1:
            return False
    return True


def get_last_sequential_index(paragraph_numbers: list[int]) -> int:
    for i in range(1, len(paragraph_numbers)):
        if paragraph_numbers[i] - paragraph_numbers[i - 1] != 1:
            return i
    return len(paragraph_numbers)


def detect_restrictive_wording(paragraph_text: str, paragraph_number: int) -> SpecWordingResult:
    """Detect restrictive wording in a specification paragraph."""
    flagged: list[int] = []
    parts: list[str] = []

    for match in _RESTRICTIVE_WORDING.finditer(paragraph_text):
        parts.append(f'[{paragraph_number}] → "{match.group()}"\n              ')
        if paragraph_number not in flagged:
            flagged.append(paragraph_number)

    return SpecWordingResult(flagged_paragraphs=flagged, formatted_phrases="".join(parts))


# --- Reference numeral extraction (B2) ---

# Pattern A: noun phrase (1-4 words) followed by number: "base plate 102"
_REFNUM_AFTER_NOUN = re.compile(
    r"(?<![.\d])"
    r"(?:(?:the|a|an|said|each|first|second|third|fourth|fifth)\s+)?"
    r"((?:[a-z]{2,15}\s+){0,3}[a-z]{2,15})"
    r"\s+"
    r"(\d{2,4}[a-z]?)"  # optional single-letter suffix: 10a, 10b
    r"(?![\dA-Za-z])"   # no following digit/letter — anchored end
    r"(?!\.\d)"         # not followed by decimal point + digit
    r"(?![%°])",        # not followed by % or degree
    re.IGNORECASE,
)

# Pattern B: parenthetical numeral: "base plate (102)" / "(10a)"
_REFNUM_PARENS = re.compile(
    r"((?:[a-z]{2,15}\s+){0,3}[a-z]{2,15})"
    r"\s*\((\d{2,4}[a-z]?)\)",
    re.IGNORECASE,
)

# Pattern C: noun phrase + Latin-prefix reference designator like "LD1",
# "HD2", "R1", "C2", "IC3", "Q1a", "LED1", "MOSFET2". Common in
# electronics / circuit / semiconductor patents where reference labels
# carry component-type prefixes instead of pure digits. Example from
# testspec2: "first low-bridge switch LD1" / "second low-bridge switch LD2".
#
# The reference label MUST start with 1-5 uppercase letters, then 1-4
# digits, with optional single-letter suffix (e.g., "R1a"). Pure digit
# refs are handled by Pattern A above. Hyphenated forms ("LED-1") not
# captured here — drafters typically don't hyphenate.
#
# Module-level (not IGNORECASE) so the [A-Z] requirement on the
# prefix is enforced; the noun-phrase group uses an explicit case-
# insensitive char class.
# Letter-word fragment that allows internal hyphens ("low-bridge",
# "high-bridge", "field-effect"). First char must be a letter; subsequent
# chars are letters or interior hyphens. Trailing hyphen allowed in
# patent diction (rare); rejected by max-length cap.
_LATIN_WORD = r"[A-Za-z][A-Za-z\-]{1,18}"
_REFNUM_LATIN_PREFIX = re.compile(
    rf"((?:{_LATIN_WORD}\s+){{0,4}}{_LATIN_WORD})"
    r"\s+"
    r"([A-Za-z]{1,5}\d{1,4}[a-zA-Z]?)"
    r"(?![A-Za-z0-9])",
    re.IGNORECASE,
)

# Pattern D: parenthetical Latin-prefix: "switch (LD1)"
_REFNUM_LATIN_PAREN = re.compile(
    rf"((?:{_LATIN_WORD}\s+){{0,4}}{_LATIN_WORD})"
    r"\s*\(([A-Za-z]{1,5}\d{1,4}[a-zA-Z]?)\)",
    re.IGNORECASE,
)

# Latin-prefix denylist — common abbreviations / acronyms that look
# like reference designators but aren't. Filters obvious noise; extend
# as new collisions surface.
_LATIN_PREFIX_DENYLIST = frozenset({
    "FIG",  # FIG.1 / FIG1 — figure references, not element refs
    "FIGS",
    "EQ",   # EQ1 — equation reference
    "VOL",
    "NO",
    "PG",
    "PCT",  # patent treaty
    "USC",
    "USA",
    "ISO",  # standards
    "SEQ",  # sequence listings
    # Common chemistry abbreviations that take numerical position labels
    "PH",   # pH (case typo)
    "CO",   # CO2
    "DNA",
    "RNA",
    # Country codes that prefix patent / publication numbers in cited-by
    # tables and bibliography sections (drafter doesn't bind a refnum to
    # "US14123456" — that's a citation to a published US application).
    "US", "WO", "EP", "JP", "KR", "TW", "CN", "DE", "FR", "GB",
    "CA", "AU", "BR", "IN", "RU", "MX", "ES", "IT", "NL", "SE",
    "FI", "DK", "AT", "CH", "BE", "PT", "PL", "IL", "ZA",
    "HK", "SG", "AR", "TH", "VN", "MY", "ID",
    # Standards / technical-org prefixes
    "IEEE", "IETF", "RFC", "IEC", "ITU", "TS", "TR",
    # Common chemistry / physics unit prefixes that look like Latin refs
    "MM", "CM", "NM", "UM", "KM",
    "MV", "KV", "MA", "KA", "MS", "NS",
    "HZ", "KHZ", "MHZ", "GHZ", "WT", "MOL",
    # Telecom / radio standards that appear with version numbers and
    # would mis-fire as Latin-prefix refs
    "CDMA", "GSM", "LTE", "UMTS", "WCDMA", "CDMA2000",
    "P2P", "B2B", "B2C",
    # Software / network / format acronyms
    "SQL", "API", "URL", "URI", "URN", "JSON", "XML", "HTML", "CSS",
    "TCP", "UDP", "HTTP", "HTTPS", "FTP", "DNS", "MAC", "IP", "USB",
    "RSA", "AES", "SHA", "MD5",
    # Pharmaceutical / biological gene + protein nomenclature that
    # follows [A-Z]{2,5}\d{1,3} format. These are official symbols
    # (HER2, CDK4, EGFR, BRCA1, KRAS, etc.) — never refnums.
    "HER", "HER1", "HER2", "HER3", "HER4",
    "CDK", "CDK1", "CDK2", "CDK4", "CDK6", "CDK7", "CDK9",
    "EGFR", "VEGF", "VEGFR",
    "BRCA", "BRCA1", "BRCA2",
    "PTEN", "TP53", "KRAS", "NRAS", "HRAS", "BRAF",
    "FLT3", "FLT4", "JAK1", "JAK2", "JAK3",
    "PD1", "PDL1", "CTLA4",
    "STAT3", "MTOR", "AKT1", "AKT2",
    "RTK", "GPCR", "ATP", "ADP", "GTP", "CDP",
})

# Exclusion: unit followers
# Comprehensive scientific-unit pattern. Match longer suffixes first so
# "mmol" doesn't get truncated to "mm". Anchored with \b so partial
# matches don't fire (e.g. "mmA" wouldn't match "mm").
_UNIT_PATTERN = re.compile(
    r"^\s*(?:"
    # Length (long-first so mm doesn't shadow mmol etc.)
    r"mmHg|mmH2O|"
    r"µm|um|μm|nm|pm|fm|Å|angstrom"
    r"|mm|cm|dm|km|m|in|ft|yd|mil|mile|miles"
    # Time
    r"|days?|hours?|minutes?|seconds?|hr|hrs|min|mins|sec|secs"
    r"|ms|µs|μs|us|ns|ps|fs|s"
    # Frequency
    r"|kHz|MHz|GHz|THz|Hz"
    # Voltage / current / power / charge
    r"|kV|mV|µV|μV|V"
    r"|kA|mA|µA|μA|A"
    r"|kW|MW|GW|mW|µW|μW|W"
    r"|mC|µC|μC|nC|C"
    r"|kΩ|MΩ|mΩ|Ω|ohm|ohms"
    # Pressure
    r"|psi|psia|psig|bar|mbar|atm|torr|mmHg"
    r"|kPa|MPa|GPa|hPa|mPa|µPa|μPa|Pa"
    # Mass / weight
    r"|kg|mg|µg|μg|ng|pg|g"
    r"|lb|lbs|oz|ton|tons"
    # Concentration / amount
    r"|mol|mmol|µmol|μmol|nmol|pmol"
    r"|M|mM|µM|μM|nM|pM"
    r"|N|wt%|vol%|mol%|w/v|w/w|v/v"
    r"|ppm|ppb|ppt|phr|equiv|equivs"
    # Volume
    r"|mL|µL|μL|nL|pL|cL|dL|L"
    r"|cc|cm3|ml|liter|liters"
    # Temperature / energy / radiation
    r"|°C|°F|°R|°K|K|kK"
    r"|kJ|MJ|GJ|mJ|µJ|μJ|J"
    r"|kcal|cal|BTU|Wh|kWh|MWh"
    r"|eV|keV|MeV|GeV"
    r"|Sv|mSv|µSv|μSv|Gy|mGy|µGy|μGy|Bq|Ci"
    # Optical / magnetic
    r"|lm|lux|lx|cd|nit|nits|sr"
    r"|T|mT|µT|μT|G|Oe|Wb"
    # Data / network rate
    r"|bps|Kbps|Mbps|Gbps|Tbps|kbps|kB|MB|GB|TB|PB|kbit|Mbit|Gbit"
    r"|baud"
    # Sound / acceleration
    r"|dB|dBm|dBu|dBi|dBA"
    r"|rpm|fps|kph|mph|knots"
    r"|m/s|km/h|ft/s"
    # Angle
    r"|°|deg|rad|sr|arcsec|arcmin"
    # Percent (no boundary needed since it's punctuation)
    r"|%"
    r")\b",
)

# Exclusion: preceding keywords
_EXCLUDE_KEYWORDS = {
    "claim", "claims", "fig", "figs", "figure", "figures",
    "paragraph", "step", "table", "example", "embodiment",
    "equation", "patent", "no", "number", "page", "version",
    "vol", "chapter", "section", "part", "item",
    "approximately", "about",
    # Chemistry units / measurement context that produce phantom refnums
    "phr",  # parts per hundred resin (chemistry industry unit)
    "wt", "vol",  # weight-pct / volume-pct
    "ppm", "ppb",  # parts per million/billion
    "rpm", "psi", "bar",  # rotation / pressure
    # Time / quantity prefixes that anchor measurements not refnums
    "than", "over", "under", "exceed", "exceeds",
}


def _is_year(num_str: str) -> bool:
    """Check if a number looks like a year."""
    return bool(re.match(r"^(19|20)\d\d$", num_str))



# Leading function words to strip when extracting the HEAD NOUN of a
# `<noun_phrase> <numeral>` capture. Without this, each capture carries
# its sentential context (e.g., "from the water supply", "manipulate the
# water supply") and D1 inflates to false conflicts. Strip aggressively
# so only the noun itself remains.
_D1_LEADING_FUNCTION_WORDS = frozenset({
    # Articles + possessives
    "the", "a", "an", "said", "each", "every", "any", "some", "another", "this",
    "that", "these", "those", "one", "its", "their", "his", "her", "our", "your",
    "another", "such",
    # Ordinals (often part of compound name, but for D1 dedup we treat
    # 'first housing 102' and 'housing 102' as the same head noun via
    # the SEPARATE ordinal-aware extraction; this set is also used by
    # the simple strip path when ordinals don't matter)
    "first", "second", "third", "fourth", "fifth", "sixth", "seventh",
    "eighth", "ninth", "tenth",
    # Prepositions
    "from", "of", "to", "in", "on", "at", "with", "by", "for", "as",
    "into", "onto", "upon", "via", "near", "around", "above", "below",
    "between", "across", "through", "without", "within", "during",
    # Conjunctions / aspectuals
    "while", "when", "where", "and", "or", "but", "if", "after", "before",
    "until", "since", "than",
    # Common verbs that capture into the noun-phrase head
    "manipulate", "manipulates", "manipulating",
    "operate", "operates", "operating",
    "include", "includes", "including",
    "configure", "configured", "configuring",
    "open", "opens", "opening", "close", "closes", "closing",
    "shows", "showing", "show", "shown", "showed",
    "off", "out", "up", "down", "back",
    "having", "have", "has", "had",
    "comprising", "comprises", "comprise",
    "being", "been", "is", "are", "was", "were",
    # Google Patents bibliography page text that bleeds into HTML extracts
    "filed", "issued", "published", "granted", "abandoned", "expired",
    "designated", "exemplified", "given", "cited",
    "claimed", "claims", "wherein",
    # Section / structural headers from extracted patent HTML
    "description", "abstract", "summary", "background", "references",
    "field", "art", "embodiments", "claim",
    "respective", "respectively", "ninety",
    # Month names that appear in priority-date / filed-on contexts
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
    "connect", "connects", "connecting", "connected",
    "couple", "couples", "coupling", "coupled",
    "control", "controls", "controlling", "controlled",
    "provide", "provides", "providing", "provided",
    "form", "forms", "forming", "formed",
    "dispose", "disposes", "disposing", "disposed",
    "arrange", "arranges", "arranging", "arranged",
    "use", "uses", "using", "used",
    "also",
    # Walker-derived parity (mirrors CN/TW _CN_FRAGMENT_MARKERS) —
    # English equivalents that signal sentence-fragment captures.
    "based", "according",
    "obtained", "derived",
    "aforementioned", "above-mentioned",
    "perform", "performs", "performing", "performed",
    "execute", "executes", "executing", "executed",
    "obtain", "obtains", "obtaining",
    "derive", "derives", "deriving",
    "acquire", "acquires", "acquiring", "acquired",
    "reference", "references", "referencing", "referenced",
    "associate", "associates", "associating", "associated",
    "via", "through",
    # Demonstrative position
    "type", "kind",
    # Context-only nouns that creep in via "with respect to N" / "in
    # respect of N" / "such that N" / "ranges from N to" patterns —
    # pure noise as element identities, never real reference numerals.
    "respect", "regard", "regards", "case", "cases",
})


_D1_ORDINAL_WORDS = frozenset({
    "first", "second", "third", "fourth", "fifth",
    "sixth", "seventh", "eighth", "ninth", "tenth",
    "eleventh", "twelfth", "thirteenth", "fourteenth", "fifteenth",
    "1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "9th", "10th",
})


def _d1_extract_ordinal_and_head(phrase: str) -> tuple[str, str]:
    """Split the ordinal prefix from the head noun so we can detect
    'first switch LD1' vs 'third switch LD1' as distinct instances.

    Returns (ordinal_or_empty, head_noun).
    `'first low-bridge switch'` → `('first', 'low-bridge switch')`
    `'low-bridge switch'`       → `('', 'low-bridge switch')`
    `'from the water supply'`   → `('', 'water supply')`
    `'for'`                     → `('', '')`
    """
    words = phrase.strip().lower().split()
    # Strip leading articles/prepositions/verbs (NOT ordinals yet)
    while words and (
        words[0] in _D1_LEADING_FUNCTION_WORDS
        and words[0] not in _D1_ORDINAL_WORDS
    ):
        words.pop(0)
    # Capture ordinal if present
    ordinal = ""
    if words and words[0] in _D1_ORDINAL_WORDS:
        ordinal = words.pop(0)
    # Continue stripping leading function words after the ordinal
    while words and (
        words[0] in _D1_LEADING_FUNCTION_WORDS
        and words[0] not in _D1_ORDINAL_WORDS
    ):
        words.pop(0)
    # Strip trailing function words
    while words and words[-1] in _D1_LEADING_FUNCTION_WORDS:
        words.pop()
    if not words:
        return (ordinal, "")
    if len(words) == 1 and len(words[0]) < 2:
        return (ordinal, "")
    return (ordinal, " ".join(words))


def _d1_head_noun(phrase: str) -> str:
    """Backward-compatible head-noun extractor — strips ordinal too.
    Preserves the older behavior for callers that don't need ordinal
    discrimination.
    """
    _, head = _d1_extract_ordinal_and_head(phrase)
    return head


def extract_numeral_name_pairs(
    spec_text: str,
) -> list[tuple[str, str]]:
    """Yield every `<head_noun, numeral>` pair from spec text (one per
    occurrence — NOT aggregated).

    Used by check_numeral_consistency for D1 (same numeral → multiple
    different element names) detection. Different from
    extract_reference_numeral_inventory below, which collapses to
    one canonical name per numeral and is used for completeness checks.

    Returns list of (numeral_str, head_noun) tuples in document order.
    The numeral is a STRING — supports both pure-digit ("102") and
    Latin-prefix designators ("LD1", "HD2", "R1", "IC2", "Q1a") common
    in electronics/circuit patents. Pure-digit numerals are
    canonicalized to a string of just the digits ("102" not "0102").

    Names are normalized via _d1_head_noun so sentential context
    (prepositions, verbs, articles, ordinals) doesn't inflate the
    apparent name set per numeral. Empty-name pairs (function-word-only
    captures) are filtered out.

    Filters mirror the inventory extractor (year exclusion, unit
    exclusion, paragraph-marker exclusion, 5+digit exclusion).
    """
    pairs: list[tuple[str, str]] = []
    seen_spans: set[tuple[int, int]] = set()
    # Pure-digit patterns first; spans they cover are remembered so the
    # Latin-prefix patterns don't double-claim overlapping text.
    for pattern in [_REFNUM_AFTER_NOUN, _REFNUM_PARENS]:
        for m in pattern.finditer(spec_text):
            noun = m.group(1).strip().lower()
            num_str = m.group(2)

            if _is_year(num_str):
                continue
            if any(w in _EXCLUDE_KEYWORDS for w in noun.split()):
                continue
            after = spec_text[m.end():][:5]
            if _UNIT_PATTERN.match(after):
                continue
            before = spec_text[max(0, m.start() - 2):m.start()]
            if "[" in before:
                continue
            if len(num_str) >= 5:
                continue

            ordinal, head = _d1_extract_ordinal_and_head(noun)
            if not head:
                continue
            # Append ordinal as a marker so 'first switch' and 'third switch'
            # become distinct keys for D1 instance-collision detection.
            keyed_name = f"{ordinal}|{head}" if ordinal else head
            # Preserve letter suffix (10a vs 10b stay distinct).
            digit_part = ""
            for ch in num_str:
                if ch.isdigit():
                    digit_part += ch
                else:
                    break
            suffix = num_str[len(digit_part):]
            canonical = f"{int(digit_part)}{suffix}" if digit_part else num_str
            pairs.append((canonical, keyed_name))
            seen_spans.add((m.start(2), m.end(2)))

    # Latin-prefix patterns — captured AFTER digit patterns so spans
    # like "switch 1024" (digit) take precedence over a hypothetical
    # mis-greedy Latin match.
    for pattern in [_REFNUM_LATIN_PREFIX, _REFNUM_LATIN_PAREN]:
        for m in pattern.finditer(spec_text):
            noun = m.group(1).strip().lower()
            ref_raw = m.group(2)
            # Normalize Latin-prefix refnums to uppercase so case-
            # inconsistent drafter usage ("lens E1" vs "lens e1") clusters
            # under the same numeral. Drafter convention is uppercase;
            # lowercase appearances are typos / inconsistencies.
            ref = "".join(c.upper() if c.isalpha() else c for c in ref_raw)

            if (m.start(2), m.end(2)) in seen_spans:
                continue
            prefix = "".join(c for c in ref if c.isalpha()).upper()
            # Reject if either the alpha-prefix OR the full normalized
            # token (B2B/V02/P2P/CDMA2000) matches the denylist.
            if prefix in _LATIN_PREFIX_DENYLIST or ref in _LATIN_PREFIX_DENYLIST:
                continue
            if any(w in _EXCLUDE_KEYWORDS for w in noun.split()):
                continue
            before = spec_text[max(0, m.start() - 2):m.start()]
            if "[" in before:
                continue
            if noun.upper().split()[-1] == prefix:
                continue

            ordinal, head = _d1_extract_ordinal_and_head(noun)
            if not head:
                continue
            keyed_name = f"{ordinal}|{head}" if ordinal else head
            pairs.append((ref, keyed_name))
            seen_spans.add((m.start(2), m.end(2)))
    return pairs


_D1_CONTENT_STOPWORDS = frozenset({
    # Articles / prepositions / conjunctions that carry no element-name
    # meaning. When these appear in canonical_unique vs other_unique,
    # they shouldn't count as distinguishing content. Without this
    # filter, "terminal of the filter capacitor" vs "filter capacitors"
    # had cu={"terminal", "the"} and ou={"capacitors"} → false D1 (when
    # actually "the" / "of" are connective particles).
    "the", "of", "and", "or", "but", "with", "without",
    "for", "from", "into", "onto", "upon",
    "via", "through", "between", "across",
    "by", "as", "at", "in", "on", "to",
    "than", "over", "under", "above", "below",
    "while", "during", "after", "before",
    "such", "any", "some", "another",
    "having", "having", "include", "includes", "including",
    "comprising", "comprises", "comprise",
    "based", "according", "obtained",
    "primary", "secondary",
})


def _content_words(name: str) -> set[str]:
    """Return content-word set of a name for D1 disjointness comparison.

    Strips short tokens (≤2 chars), filters English stopwords (the/of/
    etc — connectives that carry no element-name meaning), and adds
    singularized variants so plural-vs-singular doesn't create false
    D1 conflicts. Three plural rules (English):
      -ies → -y  (boundaries → boundary, switches→switch via -es path)
      -es → ''   (boxes → box, when the unstripped is ≥6 chars)
      -s → ''    (lenses→lense via -s path; condensers → condenser)
    Stripped forms must be ≥4 chars to avoid short-fragment collisions
    like 'lens' → 'len'."""
    out: set[str] = set()
    for w in name.split():
        if len(w) <= 2:
            continue
        if w in _D1_CONTENT_STOPWORDS:
            continue
        out.add(w)
        # -ies → -y: "boundaries" → "boundary"
        if len(w) >= 6 and w.endswith("ies"):
            out.add(w[:-3] + "y")
        # -es → '': "boxes" → "box". Lower min length than -ies because
        # -es words tend to be shorter base nouns.
        if len(w) >= 6 and w.endswith("es"):
            out.add(w[:-2])
        # -s → '': "condenser" / "lens" — only when stripped form ≥4
        # chars to avoid adding 3-char fragments.
        if (
            len(w) >= 5
            and w.endswith("s")
            and not w.endswith(("ss", "us", "is", "ies"))
        ):
            out.add(w[:-1])
    return out


def _split_ordinal_key(keyed: str) -> tuple[str, str]:
    """Split 'first|low-bridge switch' → ('first', 'low-bridge switch').
    Empty-ordinal returns ('', head)."""
    if "|" in keyed:
        ordinal, _, head = keyed.partition("|")
        return ordinal, head
    return "", keyed


def _format_d1_name_for_display(keyed: str) -> str:
    """Reverse the 'ordinal|head' encoding for surface display."""
    ordinal, head = _split_ordinal_key(keyed)
    if ordinal:
        return f"{ordinal} {head}"
    return head


def _names_form_real_d1_conflict(names: list[str]) -> bool:
    """A list of (ordinal-keyed) names is a real D1 conflict if EITHER:
    (A) the same head noun appears with TWO OR MORE distinct ordinals
        (same element type, different instance → drafter assigned same
        numeral to two distinct instances; classic D1 typo), OR
    (B) two head nouns share NO content word (truly different elements
        sharing one numeral; the textbook D1 case).

    Plural/singular / modifier-variant / partial-name cases share a
    content word AND share ordinal, so they're NOT flagged.

    Returns True if any conflict pair exists; False otherwise.
    """
    if len(names) < 2:
        return False

    decomposed = [_split_ordinal_key(n) for n in names]

    # (A) Same head + 2+ distinct non-empty ordinals → instance collision
    head_to_ordinals: dict[frozenset, set[str]] = {}
    for ord_, head in decomposed:
        if not head:
            continue
        head_key = frozenset(_content_words(head))
        if not head_key:
            continue
        head_to_ordinals.setdefault(head_key, set()).add(ord_)
    for ordinals in head_to_ordinals.values():
        non_empty = {o for o in ordinals if o}
        if len(non_empty) >= 2:
            return True

    # (B) Different head nouns sharing no content word → element collision
    word_sets = [_content_words(head) for _, head in decomposed if head]
    for i in range(len(word_sets)):
        if not word_sets[i]:
            continue
        for j in range(i + 1, len(word_sets)):
            if not word_sets[j]:
                continue
            if not (word_sets[i] & word_sets[j]):
                return True
    return False


def check_numeral_consistency(spec_text: str) -> list[CheckItem]:
    """D1 — flag reference numerals that appear with multiple distinct
    element names (e.g., "housing 102" and "container 102" both used).

    Statutory: MPEP § 608.01(g) — "The same reference character should
    not be used to designate different elements." A real drafting error
    that's high-precision to detect: same numeral with two disjoint
    noun-phrase identities is virtually always a typo or copy-paste bug.

    NOTE: same NAME with different numerals is permitted (multiple
    instances of "pillar" each get their own number). This check
    deliberately does NOT flag that direction.

    Precision filter: names are a real conflict ONLY IF at least one
    pair of observed names shares no content word. This filters
    plural/singular variants ("lens" / "lenses") and partial-name
    variants ("water supply" / "the water supply") down to the
    truly-disjoint cases.

    Severity: FIX. The drafter should pick one numeral-name pairing
    and rectify the others.
    """
    from patentlint.models import CheckItem

    if not spec_text:
        return [CheckItem(
            status="pass",
            message="Reference numerals are consistent (no spec text).",
            message_key="check.spec.numeralConsistency.pass",
            reference="MPEP § 608.01(g)",
        )]

    pairs = extract_numeral_name_pairs(spec_text)
    if not pairs:
        return [CheckItem(
            status="pass",
            message="No reference numerals detected.",
            message_key="check.spec.numeralConsistency.pass",
            reference="MPEP § 608.01(g)",
        )]

    conflicts = _detect_d1_conflicts(pairs, latin_pattern=False)

    if not conflicts:
        return [CheckItem(
            status="pass",
            message="Reference numerals are consistent across the specification.",
            message_key="check.spec.numeralConsistency.pass",
            reference="MPEP § 608.01(g)",
        )]

    # Display sort: surface the MOST-CONFUSED numerals first so a new
    # mutation (e.g. drafter changes one LD3 → LD1) visibly bubbles into
    # the top-3 inline preview. Severity = number of distinct outliers,
    # then total non-canonical occurrences, then numeric order.
    def _severity_key(c: dict) -> tuple:
        outlier_total = sum(o["count"] for o in c["outliers"])
        n = c["numeral"]
        digit_prefix = ""
        for ch in n:
            if ch.isdigit():
                digit_prefix += ch
            else:
                break
        num_sort = (0, int(digit_prefix), n) if digit_prefix else (1, 0, n)
        return (-len(c["outliers"]), -outlier_total, num_sort)
    conflicts = sorted(conflicts, key=_severity_key)

    # Split by confidence: FIX (high-confidence drafter typo / instance
    # collision / consistent variant) vs REVIEW (low-confidence single-
    # occurrence outlier with zero shared content vs strong canonical —
    # could be sentence-fragment over-capture or rare drafter error).
    fix_conflicts = [c for c in conflicts if c.get("confidence") == "fix"]
    review_conflicts = [c for c in conflicts if c.get("confidence") == "review"]

    items: list[CheckItem] = []
    if fix_conflicts:
        items.append(_build_d1_check_item(
            fix_conflicts, status="amend", suffix="amend",
        ))
    if review_conflicts:
        items.append(_build_d1_check_item(
            review_conflicts, status="verify", suffix="verify",
        ))
    if items:
        return items
    return [CheckItem(
        status="pass",
        message="Reference numerals are consistent across the specification.",
        message_key="check.spec.numeralConsistency.pass",
        reference="MPEP § 608.01(g)",
    )]


def _build_d1_check_item(conflicts: list[dict], status: str, suffix: str) -> CheckItem:
    """Build a CheckItem for a slice of D1 conflicts (either fix-tier
    or review-tier). Shared between the two emit paths."""
    sample = conflicts[:8]
    extra = max(0, len(conflicts) - 8)
    findings = [
        {
            "numeral": c["numeral"],
            "canonical": _format_d1_name_for_display(c["canonical"]),
            "canonical_count": c["canonical_count"],
            "outliers": [
                {
                    "name": _format_d1_name_for_display(o["name"]),
                    "count": o["count"],
                    "confidence": o.get("confidence", "fix"),
                }
                for o in c["outliers"]
            ],
            "case": c["case"],
            "confidence": c.get("confidence", "fix"),
        }
        for c in sample
    ]
    inline = "; ".join(_format_inline_conflict(c) for c in sample[:3])
    if len(conflicts) > 3:
        inline = inline + f" (+{len(conflicts) - 3} more)"
    is_fix = (status == "amend")
    message_prefix = (
        f"{len(conflicts)} reference numeral(s) inconsistently used."
        if is_fix
        else f"{len(conflicts)} reference numeral(s) with possibly inconsistent naming — please review."
    )
    return CheckItem(
        status=status,
        message=f"{message_prefix} Examples: {inline}",
        message_key=f"check.spec.numeralConsistency.{suffix}",
        details_key="details.numeralConsistency",
        details_params={
            "count": len(conflicts),
            "findings": findings,
            "extra": extra,
            "inline_summary": inline,
        },
        reference="MPEP § 608.01(g)",
        diagnostics={
            "conflict_count": len(conflicts),
            "sample_numerals": [c["numeral"] for c in sample],
            "instance_collisions": sum(1 for c in conflicts if c["case"] == "instance"),
            "element_collisions": sum(1 for c in conflicts if c["case"] == "element"),
        },
    )


# ── D1 detection core (canonical + outliers) ─────────────────────────────
#
# Replaces the prior "≥2 per name + ≥3 total" precision-filter approach
# which was the load-bearing source of false negatives: a single-
# occurrence typo (the canonical D1 case — drafter changes ONE
# paragraph's numeral) was filtered out as noise.
#
# The new design is canonical-vs-outliers:
#
#   1. For each numeral, find the CANONICAL element name — the most
#      frequent name with at least N occurrences (3 for digit refs;
#      2 for Latin-prefix refs).
#   2. If no canonical exists (no name reaches the threshold), the
#      numeral is mostly chemistry/range noise → don't emit.
#   3. For each OTHER name on that numeral (any occurrence count),
#      emit if it represents a real conflict:
#        Case A (instance collision): same head noun but different
#          ordinal — drafter put same numeral on two distinct instances
#          (first switch + third switch both labeled LD1).
#        Case B (element collision): no shared content word with the
#          canonical — drafter typo (motor 10 + circuit 10).
#
# Single-occurrence outliers ARE real bugs by this definition. Multi-
# occurrence chemistry text doesn't form a canonical so it's ignored.

def _is_latin_prefix(num: str) -> bool:
    """Latin-prefix designators (LD1, R1, IC2) start with a letter."""
    return bool(num) and num[0].isalpha()


def _format_d1_name_for_display(keyed: str) -> str:
    """Reverse the 'ordinal|head' encoding for surface display."""
    ordinal, head = _split_ordinal_key(keyed)
    if ordinal:
        return f"{ordinal} {head}"
    return head


def _singularize_last_word(s: str) -> str:
    """Best-effort English singularization of the LAST word in `s`.

    Used by cluster merge so plural-vs-singular variants
    ("filter capacitors" vs "filter capacitor") cluster as the same
    noun. Rules: -ies→-y (boundaries→boundary), -es→strip
    (boxes→box), -s→strip (lenses→lense, caps→cap).
    Threshold ≥4 chars for stripped form so 3-char plurals like "caps"
    cluster with "cap" (the cluster check ALREADY requires the shorter
    form be ≥1 word; very short noise won't propagate further).
    """
    if not s:
        return s
    parts = s.rsplit(" ", 1)
    head = parts[-1]
    if not head:
        return s
    base = head
    if len(head) >= 5 and head.endswith("ies"):
        base = head[:-3] + "y"
    elif len(head) >= 5 and head.endswith("es"):
        base = head[:-2]
    elif (
        len(head) >= 4
        and head.endswith("s")
        and not head.endswith(("ss", "us", "is", "ies"))
    ):
        base = head[:-1]
    if base == head:
        return s
    return (parts[0] + " " + base) if len(parts) == 2 else base


def _merge_suffix_clusters_us(name_counts: "Counter[str]") -> "Counter[str]":
    """Merge suffix-equivalent names: if A's surface form ends with B's
    surface form (with B at least 2 content words), they refer to the same
    noun captured with un-stripped leading subjects. Keep the shortest
    member as cluster rep; sum counts."""
    from collections import Counter

    items = list(name_counts.items())
    n = len(items)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    surfaces = []
    for name, _ in items:
        ordinal, head = _split_ordinal_key(name)
        surfaces.append(((ordinal + " ") if ordinal else "") + head)

    def word_count(s: str) -> int:
        return len([w for w in s.split() if w])

    # Compare against BOTH raw and singularized forms of the shorter
    # surface so plural variants cluster: "terminal of the filter
    # capacitor" ends with " filter capacitor", which is the
    # singularized form of "filter capacitors" — should union.
    surfaces_sing = [_singularize_last_word(s) for s in surfaces]

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            si, sj = surfaces[i], surfaces[j]
            sj_sing = surfaces_sing[j]
            joined = (
                si == sj
                or si.endswith(" " + sj)
                or si.endswith("-" + sj)
                or si == sj_sing
                or si.endswith(" " + sj_sing)
                or si.endswith("-" + sj_sing)
            )
            if word_count(sj) >= 1 and joined:
                union(i, j)

    # Pick cluster rep = MOST FREQUENT (not shortest). Shortest-as-rep
    # would merge "control module" (10×) into bare "module" (1×) when
    # both share suffix — losing the identifying modifier. Most-frequent
    # picks the form the drafter actually used; shortest is tiebreaker.
    cluster_rep_count: dict[int, int] = {}
    cluster_rep_name: dict[int, str] = {}
    cluster_counts: Counter = Counter()
    for idx, (name, count) in enumerate(items):
        root = find(idx)
        cluster_counts[root] += count
        if root not in cluster_rep_count:
            cluster_rep_count[root] = count
            cluster_rep_name[root] = name
        else:
            cur_count = cluster_rep_count[root]
            if count > cur_count:
                cluster_rep_count[root] = count
                cluster_rep_name[root] = name
            elif count == cur_count:
                cur_ord, cur_head = _split_ordinal_key(cluster_rep_name[root])
                cur_surf = ((cur_ord + " ") if cur_ord else "") + cur_head
                new_surf = surfaces[idx]
                if len(new_surf) < len(cur_surf):
                    cluster_rep_name[root] = name

    merged: Counter = Counter()
    for root, total in cluster_counts.items():
        merged[cluster_rep_name[root]] = total
    return merged


def _detect_d1_conflicts(
    pairs: list[tuple[str, str]],
    latin_pattern: bool = False,
) -> list[dict]:
    """Build canonical + outliers per numeral; return list of conflict
    dicts with case classification.

    Each conflict dict has:
      'numeral': str — the reference numeral (digit or Latin-prefix)
      'canonical': str — most-frequent ordinal-keyed name
      'canonical_count': int
      'outliers': list[{'name': str, 'count': int}] — disjoint or
                  ordinal-different names (the actual conflicts)
      'case': 'instance' | 'element' — which D1 sub-case fired
    """
    from collections import Counter

    by_num_counts: dict[str, Counter] = {}
    for num, name in pairs:
        by_num_counts.setdefault(num, Counter())[name] += 1
    # Merge suffix-equivalent names per numeral so the cleanest short
    # form wins counts (e.g., 'present disclosure comprises lens' merges
    # into 'lens' before canonical selection).
    for num in list(by_num_counts.keys()):
        by_num_counts[num] = _merge_suffix_clusters_us(by_num_counts[num])

    def _sort_key(item: tuple[str, Counter]) -> tuple[int, int, str]:
        num = item[0]
        digit_prefix = ""
        for ch in num:
            if ch.isdigit():
                digit_prefix += ch
            else:
                break
        if digit_prefix:
            return (0, int(digit_prefix), num)
        return (1, 0, num)

    conflicts: list[dict] = []
    for num, name_counts in sorted(by_num_counts.items(), key=_sort_key):
        # Canonical-frequency threshold: a name must appear ≥2 times to
        # qualify as canonical for that numeral. Single-occurrence-only
        # captures (where every name is 1×) are mostly chemistry/range
        # noise and produce no canonical → no D1.
        # Latin-prefix refs accept canonical=1 — they're structurally
        # unique designators with much lower noise risk.
        canonical_threshold = 1 if _is_latin_prefix(num) else 2

        sorted_names = name_counts.most_common()
        if not sorted_names:
            continue
        canonical_name, canonical_count = sorted_names[0]
        if canonical_count < canonical_threshold:
            continue

        # Decompose canonical
        canonical_ord, canonical_head = _split_ordinal_key(canonical_name)
        canonical_words = _content_words(canonical_head)

        # Scan all OTHER names for real conflicts
        outlier_records: list[dict] = []
        case_instance = False
        for name, count in sorted_names[1:]:
            if name == canonical_name:
                continue
            other_ord, other_head = _split_ordinal_key(name)
            other_words = _content_words(other_head)

            # Suppress strip-residue outliers: the outlier name ends with
            # canonical name (full ord + head), or head ends with canonical
            # head. Captures un-stripped leading subjects: "present
            # disclosure comprises lens 10" vs canonical "lens 10".
            if (
                canonical_name
                and name != canonical_name
                and (name.endswith(" " + canonical_name)
                     or name.endswith("-" + canonical_name))
            ):
                continue
            if (
                canonical_head
                and other_head
                and other_ord == canonical_ord
                and (
                    other_head.endswith(" " + canonical_head)
                    or other_head == canonical_head
                )
            ):
                continue

            # Case A: same head, different ordinal → instance collision
            if (
                canonical_words
                and other_words
                and canonical_words & other_words
                and other_ord != canonical_ord
                and (canonical_ord or other_ord)
            ):
                outlier_records.append({"name": name, "count": count})
                case_instance = True
                continue

            # Case B: distinguishing-word collision. Strict disjoint
            # missed cases like "voltage threshold setting circuit" vs
            # "voltage difference calculating circuit" — they SHARE
            # ("voltage", "circuit") yet identify completely different
            # parts. Real test: if BOTH names have words the OTHER lacks,
            # they're naming different elements.
            canonical_unique = canonical_words - other_words
            other_unique = other_words - canonical_words
            if (
                canonical_words
                and other_words
                and canonical_unique
                and other_unique
            ):
                outlier_records.append({"name": name, "count": count})
                continue

        if outlier_records:
            # Confidence tier per outlier:
            #   "fix"    — high-confidence drafter typo: outlier_count ≥
            #              2 (drafter wrote it consistently), OR shares
            #              content with canonical (typo / variant of
            #              same name), OR instance collision (case A).
            #   "review" — low-confidence: 1× outlier with zero shared
            #              content vs strong canonical (≥10×). Likely
            #              sentence-fragment over-capture, but could be
            #              real D1 — surface as REVIEW for user judgment.
            for o in outlier_records:
                o_words = _content_words(
                    _split_ordinal_key(o["name"])[1]
                )
                shares_content = bool(canonical_words & o_words)
                strong_canonical = canonical_count >= 10
                weak_outlier = (o["count"] == 1)
                if case_instance or shares_content or not weak_outlier or not strong_canonical:
                    o["confidence"] = "fix"
                else:
                    o["confidence"] = "review"
            # Conflict-level severity = highest tier among outliers
            severity = (
                "fix" if any(o["confidence"] == "fix" for o in outlier_records)
                else "review"
            )
            conflicts.append({
                "numeral": num,
                "canonical": canonical_name,
                "canonical_count": canonical_count,
                "outliers": outlier_records,
                "case": "instance" if case_instance else "element",
                "confidence": severity,
            })

    return conflicts


def _format_inline_conflict(c: dict) -> str:
    """Plain-English one-line summary of a conflict.

    Format: numeral N used for: "name1" (N×), "name2" (M×)
    The colon-list form reads as "this numeral was used for these
    element names" without the cryptic "vs" / unbracketed "×N" that
    the original technical format had.
    """
    canonical = _format_d1_name_for_display(c["canonical"])
    parts = [f'"{canonical}" ({c["canonical_count"]}×)']
    for o in c["outliers"][:3]:
        name = _format_d1_name_for_display(o["name"])
        parts.append(f'"{name}" ({o["count"]}×)')
    if len(c["outliers"]) > 3:
        parts.append("…")
    return f"numeral {c['numeral']} used for: " + ", ".join(parts)


def extract_reference_numeral_inventory(
    spec_text: str,
) -> list[ReferenceNumeral]:
    """Extract a reference numeral inventory from specification text.

    Combines DD + Summary + Brief Description of Drawings into one pass.
    Returns sorted list of ReferenceNumeral with occurrence counts.
    """
    from patentlint.analysis.utils import clean_noun_phrase

    candidates: dict[int, str] = {}
    occurrence_count: Counter = Counter()

    for pattern in [_REFNUM_AFTER_NOUN, _REFNUM_PARENS]:
        for m in pattern.finditer(spec_text):
            noun = m.group(1).strip().lower()
            num_str = m.group(2)
            # Inventory bucket is the digit-only parent: 10a → 10.
            digit_only = "".join(ch for ch in num_str if ch.isdigit())
            if not digit_only:
                continue
            num = int(digit_only)

            # Exclusion: year (use digit-only form)
            if _is_year(digit_only):
                continue

            # Exclusion: keyword in noun phrase
            noun_words = noun.split()
            if any(w in _EXCLUDE_KEYWORDS for w in noun_words):
                continue

            # Exclusion: unit follower
            after = spec_text[m.end():][:5]
            if _UNIT_PATTERN.match(after):
                continue

            # Exclusion: bracket paragraph [0035]
            before = spec_text[max(0, m.start() - 2):m.start()]
            if "[" in before:
                continue

            # Exclusion: 5+ digits (patent number)
            if len(digit_only) >= 5:
                continue

            occurrence_count[num] += 1
            if num not in candidates:
                cleaned = clean_noun_phrase(noun)
                candidates[num] = cleaned if cleaned else noun

    # Confidence filter: require at least 2 occurrences
    result: list[ReferenceNumeral] = []
    for num in sorted(candidates):
        if occurrence_count[num] >= 2:
            result.append(ReferenceNumeral(
                number=num,
                element_name=candidates[num],
                occurrences=occurrence_count[num],
            ))

    return result


def check_required_sections(full_text: str) -> list[CheckItem]:
    """Check for required and optional sections per MPEP § 608.01(a).

    Uses existing section extractors where available, regex header matching
    for Title detection.

    Brief Description of Drawings is conditionally required per
    37 CFR 1.74 ("when there are drawings, there shall be a brief
    description"). We detect drawings via figure references parsed
    from the body — robust to the case where BDoD heading is removed
    while FIG. N references remain in the detailed description.
    """
    from patentlint.models import CheckItem
    from patentlint.analysis.drawings import _extract_figure_ids
    from patentlint.parser.sections import (
        extract_cross_reference_section,
        extract_background_section,
        extract_summary_section,
        extract_description_of_drawings_section,
        extract_detailed_description_section,
        extract_claims_section,
        extract_abstract_section,
        _ANY_SECTION_HEADER,
    )

    results: list[CheckItem] = []

    # --- Title detection ---
    # Title is typically text before the first section header.
    first_header = _ANY_SECTION_HEADER.search(full_text)
    title_text = full_text[:first_header.start()].strip() if first_header else full_text.strip()
    has_title = bool(title_text) and len(title_text) < 500  # sanity: title shouldn't be huge

    # --- Detect each section ---
    section_results: dict[str, bool] = {
        "Title of the Invention": has_title,
        "Cross-Reference to Related Applications": bool(extract_cross_reference_section(full_text)),
        "Background of the Invention": bool(extract_background_section(full_text)),
        "Brief Summary of the Invention": bool(extract_summary_section(full_text)),
        "Brief Description of the Drawings": bool(extract_description_of_drawings_section(full_text)),
        "Detailed Description of the Invention": bool(extract_detailed_description_section(full_text)),
        "Claims": bool(extract_claims_section(full_text)),
        "Abstract of the Disclosure": bool(extract_abstract_section(full_text)),
    }

    # 37 CFR 1.74: BDoD is conditional on drawings existing. Detect figure
    # references anywhere in the spec body — this catches cases where the
    # BDoD heading is removed but FIG. 1 / FIG. 2 still appear in the
    # detailed description.
    drawings_exist = bool(_extract_figure_ids(full_text))

    # Required sections — BDoD only required when drawings are present.
    required = [
        "Title of the Invention",
        "Background of the Invention",
        "Brief Summary of the Invention",
        "Detailed Description of the Invention",
        "Claims",
        "Abstract of the Disclosure",
    ]
    if drawings_exist:
        required.insert(3, "Brief Description of the Drawings")

    optional = [
        "Cross-Reference to Related Applications",
    ]

    missing_required = [name for name in required if not section_results[name]]

    if missing_required:
        results.append(CheckItem(
            status="amend",
            message=f"Missing required sections: {', '.join(missing_required)}",
            message_key="checks.required_sections_missing",
            details=", ".join(missing_required),
            details_key="details.missingSections",
            details_params={
                "list": ", ".join(missing_required),
                "flagged_phrases": {
                    "items": [{"kind": "section", "token": s} for s in missing_required]
                },
            },
            diagnostics=_dx(
                missing_count=len(missing_required),
                total_required=len(required),
                missing_sections=missing_required[:10],
                drawings_exist=drawings_exist,
                first_missing=missing_required[0] if missing_required else None,
            ),
        ))
    else:
        results.append(CheckItem(
            status="pass",
            message="All required sections per MPEP § 608.01(a) are present.",
            message_key="checks.required_sections_pass",
        ))

    # Optional sections
    for name in optional:
        if not section_results[name]:
            results.append(CheckItem(
                status="verify",
                message=f"Optional section not found: {name}. Include if applicable.",
                message_key="checks.optional_section_missing",
                details=name,
                details_key="details.optionalSectionGuidance",
                details_params={"name": name},
                diagnostics=_dx(
                    section_name=name,
                    total_optional=len(optional),
                    section_name_charlen=len(name),
                ),
            ))

    return results


_TITLE_TRADEMARK_RE = re.compile(r"[®™©]")
# Commercial / model-number pattern per MPEP § 608.01 — reject ALL-CAPS
# alphanumeric tokens that look like product codes (e.g. "AB-123", "X-9000").
_TITLE_MODEL_NUMBER_RE = re.compile(r"\b[A-Z]{2,}[- ]?\d{2,}[A-Z0-9\-]*\b")


# ── Scope-limit wording (US, MPEP § 2111 + Phillips v. AWH) ──────────────
#
# "The present invention" / "this invention" / "the invention" in spec body
# can become a claim-scope limit under Phillips v. AWH Corp 415 F.3d 1303
# (Fed. Cir. 2005) — the doctrine is that claims are interpreted in light
# of the spec, and statements characterizing "the present invention"
# are read as defining the invention itself.
#
# Different surface + different doctrine from check_restrictive_wording
# (which targets CLAIMS under MPEP § 2173.01 indefiniteness). No dupe.
#
# REVIEW level — advisory; many drafts use these phrases benignly. The
# check surfaces the count + sample paragraph indices so the drafter
# can review each occurrence and rephrase to "in some embodiments" /
# "the disclosed [system/method]" / "implementations may" etc. where
# scope-limit risk exists.
_SCOPE_LIMIT_WORDING_RE = re.compile(
    r"\bthe\s+(?:present\s+)?invention\b|\bthis\s+invention\b",
    re.IGNORECASE,
)


def check_scope_limit_wording(spec_body_text: str) -> list[CheckItem]:
    """Detect "the (present) invention" / "this invention" in US spec body.

    Returns a single VERIFY CheckItem when occurrences are present (with
    occurrence count + sample snippets in details_params), or a single
    PASS otherwise. Does NOT scan claims (those have separate restrictive-
    wording rules under § 2173.01).
    """
    from patentlint.models import CheckItem

    if not spec_body_text:
        return [CheckItem(
            status="pass",
            message="No scope-limiting phrases detected in specification.",
            message_key="check.spec.scopeLimitWording.pass",
            reference="MPEP § 2111; Phillips v. AWH Corp",
        )]

    matches = list(_SCOPE_LIMIT_WORDING_RE.finditer(spec_body_text))
    if not matches:
        return [CheckItem(
            status="pass",
            message="No scope-limiting phrases detected in specification.",
            message_key="check.spec.scopeLimitWording.pass",
            reference="MPEP § 2111; Phillips v. AWH Corp",
        )]

    # Capture short context windows around each match for the drafter
    # to triage. Cap at 5 samples (rest collapsed into +N more).
    samples: list[dict] = []
    for m in matches[:5]:
        start = max(0, m.start() - 24)
        end = min(len(spec_body_text), m.end() + 24)
        snippet = spec_body_text[start:end].replace("\n", " ").strip()
        samples.append({"phrase": m.group(0), "context": snippet})

    count = len(matches)
    return [CheckItem(
        status="verify",
        message=(
            f"Found {count} use(s) of 'the (present) invention' / "
            f"'this invention' in the specification."
        ),
        message_key="check.spec.scopeLimitWording.verify",
        details_key="details.scopeLimitWording",
        details_params={
            "count": count,
            "samples": samples,
            "extra": max(0, count - 5),
        },
        reference="MPEP § 2111; Phillips v. AWH Corp 415 F.3d 1303",
        diagnostics={
            "match_count": count,
            "sample_phrases": [s["phrase"] for s in samples],
        },
    )]


def check_title(title: str) -> list[CheckItem]:
    """Check US patent title length and prohibited content (MPEP § 606 / § 608.01).

    - Missing title: AMEND.
    - Title > 500 characters (MPEP § 606 hard cap): AMEND.
    - Title contains trademark symbol or model-number pattern: AMEND.
    - Title > 15 words (MPEP § 606 "preferably 2-7 words" soft guideline): VERIFY.
    - Otherwise: PASS.
    """
    clean = title.strip()
    if not clean:
        return [CheckItem(
            status="amend",
            message="Title is missing from specification.",
            message_key="check.spec.title.amendMissing",
            details_key="details.titleMissing",
            reference="MPEP § 606",
            diagnostics=_dx(
                reason_code="missing",
                title_charlen=0,
                title_raw_charlen=len(title),
                title_is_whitespace=bool(title and not title.strip()),
            ),
        )]

    results: list[CheckItem] = []

    charlen = len(clean)
    if charlen > 500:
        results.append(CheckItem(
            status="amend",
            message=f"Title has {charlen} characters (MPEP § 606 hard cap is 500).",
            message_key="check.spec.title.amendLength",
            details_key="details.titleLength",
            details_params={"count": charlen},
            reference="MPEP § 606",
            diagnostics=_dx(
                reason_code="length",
                char_count=charlen,
                threshold=500,
                overage=charlen - 500,
                first_30_chars=clean[:30],
                last_30_chars=clean[-30:],
            ),
        ))

    items: list[dict] = []
    tm = _TITLE_TRADEMARK_RE.search(clean)
    if tm:
        items.append({"kind": "trademark", "token": tm.group()})
    mn = _TITLE_MODEL_NUMBER_RE.search(clean)
    if mn:
        items.append({"kind": "model", "token": mn.group()})
    if items:
        results.append(CheckItem(
            status="amend",
            message="Title contains prohibited content (trademark or model number).",
            message_key="check.spec.title.amendContent",
            details_key="details.titleContent",
            details_params={"title_prohibited_items": {"items": items}},
            reference="MPEP § 608.01",
            diagnostics=_dx(
                reason_code="prohibited_content",
                flagged_count=len(items),
                title_charlen=charlen,
                flagged_kinds=[it.get("kind") for it in items],
                tokens_sample=[(it.get("token") or "")[:32] for it in items[:5]],
            ),
        ))

    word_count = len(clean.split())
    if word_count > 15 and charlen <= 500 and not items:
        results.append(CheckItem(
            status="verify",
            message=f"Title has {word_count} words — MPEP § 606 recommends a short, specific title.",
            message_key="check.spec.title.verify",
            details_key="details.titleWordCount",
            details_params={"count": word_count},
            reference="MPEP § 606",
            diagnostics=_dx(
                reason_code="wordy",
                word_count=word_count,
                threshold=15,
                title_charlen=charlen,
                first_30_chars=clean[:30],
            ),
        ))

    if not results:
        results.append(CheckItem(
            status="pass",
            message="Title meets MPEP § 606 requirements.",
            message_key="check.spec.title.pass",
            reference="MPEP § 606",
        ))

    return results


def has_sequence_listing_mismatch(full_text: str) -> bool:
    """Check if spec mentions SEQ ID NO but lacks a sequence listing statement."""
    mentions_seq = bool(re.search(r"(?i)SEQ\.?\s*(ID|NO)\.?\s*(NO\.)?", full_text))
    has_section = bool(re.search(r"(?i)STATEMENT REGARDING SEQUENCE LISTING", full_text))
    return mentions_seq and not has_section
