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
    r"(\d{2,4})"
    r"(?!\d)"        # not followed by another digit
    r"(?!\.\d)"      # not followed by decimal point + digit
    r"(?![%°])"      # not followed by % or degree
    r"\b",
    re.IGNORECASE,
)

# Pattern B: parenthetical numeral: "base plate (102)"
_REFNUM_PARENS = re.compile(
    r"((?:[a-z]{2,15}\s+){0,3}[a-z]{2,15})"
    r"\s*\((\d{2,4})\)",
    re.IGNORECASE,
)

# Exclusion: unit followers
_UNIT_PATTERN = re.compile(
    r"^\s*(?:mm|cm|m|km|µm|nm|in|ft|°[CF]|K|%|Hz|kHz|MHz|GHz|THz"
    r"|V|mV|kV|A|mA|W|kW|MW|Ω|psi|bar|atm|Pa|kPa|MPa"
    r"|g|kg|mg|lb|oz|mol|L|mL|dB|s|ms|µs|ns|rpm)\b",
)

# Exclusion: preceding keywords
_EXCLUDE_KEYWORDS = {
    "claim", "claims", "fig", "figs", "figure", "figures",
    "paragraph", "step", "table", "example", "embodiment",
    "equation", "patent", "no", "number", "page", "version",
    "vol", "chapter", "section", "part", "item",
    "approximately", "about",
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
    # Articles
    "the", "a", "an", "said", "each", "every", "any", "some", "another", "this",
    "that", "these", "those", "one",
    # Ordinals (often part of compound name, but for D1 dedup we treat
    # 'first housing 102' and 'housing 102' as the same head noun)
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
    # Demonstrative position
    "type", "kind", "form",
    # Context-only nouns that creep in via "with respect to N" / "in
    # respect of N" / "such that N" / "ranges from N to" patterns —
    # pure noise as element identities, never real reference numerals.
    "respect", "such", "respect", "regard", "regards", "case", "cases",
    "side", "sides",  # "side" alone is too generic; "left side" / "lower side" pass through
})


def _d1_head_noun(phrase: str) -> str:
    """Strip leading function words from a captured noun phrase to get
    the bare head noun for D1 comparison.

    `'from the water supply'` → `'water supply'`
    `'manipulate the water supply'` → `'water supply'`
    `'water supply'` → `'water supply'`
    `'first housing'` → `'housing'`
    `'for'` → `''` (drop — pure preposition, not a real element name)

    Also drops trailing function words that crept in (`'water supply by'`).
    Returns empty string for phrases that reduce to nothing.
    """
    words = phrase.strip().lower().split()
    while words and words[0] in _D1_LEADING_FUNCTION_WORDS:
        words.pop(0)
    while words and words[-1] in _D1_LEADING_FUNCTION_WORDS:
        words.pop()
    if not words:
        return ""
    # Single 1-char fragment → drop. Usually noise (regex catches odd splits).
    if len(words) == 1 and len(words[0]) < 2:
        return ""
    return " ".join(words)


def extract_numeral_name_pairs(
    spec_text: str,
) -> list[tuple[int, str]]:
    """Yield every `<head_noun, numeral>` pair from spec text (one per
    occurrence — NOT aggregated).

    Used by check_numeral_consistency for D1 (same numeral → multiple
    different element names) detection. Different from
    extract_reference_numeral_inventory below, which collapses to
    one canonical name per numeral and is used for completeness checks.

    Returns list of (numeral_int, head_noun) tuples in document order.
    Names are normalized via _d1_head_noun so sentential context
    (prepositions, verbs, articles, ordinals) doesn't inflate the
    apparent name set per numeral. Empty-name pairs (function-word-only
    captures) are filtered out.

    Filters mirror the inventory extractor (year exclusion, unit
    exclusion, paragraph-marker exclusion, 5+digit exclusion).
    """
    pairs: list[tuple[int, str]] = []
    for pattern in [_REFNUM_AFTER_NOUN, _REFNUM_PARENS]:
        for m in pattern.finditer(spec_text):
            noun = m.group(1).strip().lower()
            num_str = m.group(2)
            num = int(num_str)

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

            head = _d1_head_noun(noun)
            if not head:
                continue
            pairs.append((num, head))
    return pairs


def _content_words(name: str) -> set[str]:
    """Return content-word set of a name for D1 disjointness comparison.

    Strips short tokens (≤2 chars) and adds both the original and a
    singularized variant so `'condenser lens'` and `'condenser lenses'`
    share `'lens'`. Handles English `s` and `es` plural endings.
    """
    out: set[str] = set()
    for w in name.split():
        if len(w) <= 2:
            continue
        out.add(w)
        # Add singularized variants — both 's' and 'es' stripped forms,
        # so plural forms intersect with their singulars regardless of
        # which one the drafter wrote first.
        if (
            len(w) >= 4
            and w.endswith("s")
            and not w.endswith(("ss", "us", "is"))
        ):
            out.add(w[:-1])
        if len(w) >= 5 and w.endswith("es"):
            out.add(w[:-2])
    return out


def _names_form_real_d1_conflict(names: list[str]) -> bool:
    """A list of names is a real D1 conflict only if AT LEAST ONE PAIR
    shares no content word. Plural/singular / modifier-variant / partial-
    name cases all share a content word and are correctly NOT flagged.

    Returns True if a disjoint pair exists; False otherwise.
    """
    if len(names) < 2:
        return False
    word_sets = [_content_words(n) for n in names]
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

    # Build numeral → ordered-distinct-names AND counts.
    # Two precision filters:
    # 1. Each name kept only if it appears ≥2 times for this numeral
    #    (single occurrences are regex noise from chemistry/range text).
    # 2. The numeral itself must appear ≥3 times total — real reference
    #    numerals are repeated; one-off matches are mostly measurements
    #    (e.g., "10 wt%", "from 100 to 200").
    from collections import Counter
    by_numeral_counts: dict[int, Counter] = {}
    by_numeral_total: Counter = Counter()
    for num, name in pairs:
        by_numeral_counts.setdefault(num, Counter())[name] += 1
        by_numeral_total[num] += 1

    by_numeral: dict[int, list[str]] = {}
    for num, name_counts in by_numeral_counts.items():
        if by_numeral_total[num] < 3:
            continue
        # Preserve doc-order for surface display; dedupe; keep only ≥2x.
        seen: list[str] = []
        seen_set: set[str] = set()
        for raw_num, raw_name in pairs:
            if raw_num != num or raw_name in seen_set:
                continue
            if name_counts[raw_name] < 2:
                continue
            seen_set.add(raw_name)
            seen.append(raw_name)
        if seen:
            by_numeral[num] = seen

    conflicts = [
        (num, names)
        for num, names in sorted(by_numeral.items())
        if len(names) > 1 and _names_form_real_d1_conflict(names)
    ]

    if not conflicts:
        return [CheckItem(
            status="pass",
            message="Reference numerals are consistent across the specification.",
            message_key="check.spec.numeralConsistency.pass",
            reference="MPEP § 608.01(g)",
        )]

    # Cap displayed conflicts at 8 to bound payload size; "extra" carries
    # the overflow count for the drafter.
    sample = conflicts[:8]
    extra = max(0, len(conflicts) - 8)
    findings = [
        {"numeral": num, "names": names[:5]}  # cap names per numeral too
        for num, names in sample
    ]
    return [CheckItem(
        status="amend",
        message=(
            f"{len(conflicts)} reference numeral(s) used with multiple "
            f"different element names (D1)."
        ),
        message_key="check.spec.numeralConsistency.amend",
        details_key="details.numeralConsistency",
        details_params={
            "count": len(conflicts),
            "findings": findings,
            "extra": extra,
        },
        reference="MPEP § 608.01(g)",
        diagnostics={
            "conflict_count": len(conflicts),
            "sample_numerals": [num for num, _ in sample],
            "max_names_per_numeral": max(len(names) for _, names in conflicts),
        },
    )]


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
            num = int(num_str)

            # Exclusion: year
            if _is_year(num_str):
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
            if len(num_str) >= 5:
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
