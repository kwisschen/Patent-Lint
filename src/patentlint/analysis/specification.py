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
