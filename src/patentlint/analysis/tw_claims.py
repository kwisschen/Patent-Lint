# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""TW claims structural checks.

Sixteen pure functions checking Taiwan patent claim formatting
against TIPO rules (專利法施行細則 and 專利審查基準).
"""

from __future__ import annotations

import re

from patentlint.analysis.cjk_ordinal_guard import ordinal_guard
from patentlint.analysis.cjk_tokenize import jaccard, tokenize_tw
from patentlint.models import CheckItem, Claim, TwPatentDocument

# Did-you-mean Jaccard threshold (ADR-094). Char-bigram Jaccard at 0.40
# is the calibration v2 sweet spot: high enough to suppress noise pairs,
# low enough to surface morphological/quantifier variants the exact-match
# pass missed. The threshold is fixed at the analysis layer; the strict-
# plural escape hatch in the walker is the only knob exposed to callers.
_DIDYOUMEAN_THRESHOLD = 0.40

# Recognized TW dependency format patterns
_TW_DEP_FORMAT = re.compile(
    r"如請求項\s*\d+"
    r"(?:\s*(?:~|至|到)\s*\d+)?"
    r"(?:\s*(?:或|、)\s*\d+)*"
    r"(?:\s*中\s*任一?項)?"
    r"\s*所?述?[之的]?"
)

# Bare reference numeral: CJK char followed by 2-4 digits not in parens.
# Exclude: ordinals (第N), measurements (digits followed by unit chars/°),
# and dependency refs (請求項N).
_BARE_NUMERAL = re.compile(
    r"(?<!\()(?<=[\u4e00-\u9fff])"  # preceded by CJK, not by (
    r"(?<!第)(?<!請求項)"            # not ordinal 第N or 請求項N
    r"\s?\d{2,4}"                    # 2-4 digit number
    r"(?!\))"                        # not followed by )
    r"(?!\d)"                        # must match full number, no partial
    r"(?![°℃%a-zA-Z])"              # not followed by unit/measurement
)

# Subject extraction: text before 其特徵在於 or first comma
_PREAMBLE_END = re.compile(r"(?:其特徵在於|其改良在於|，|,)")

# Dependent claim subject: text after 所述之/所述的 or bare 之 (如請求項N之)
_DEP_SUBJECT = re.compile(r"(?:所述[之的]|(?<=\d)[之的])(.+?)(?:，|,|其特徵|其改良|$)")

# Leading quantifier for normalization
_LEADING_QUANTIFIER = re.compile(r"^(?:一種|一個|該|所述|所述的)\s*")

# Transitional phrases (broader set per prompt)
_TRANSITION_PHRASES = ("其特徵在於", "其改良在於", "包含", "包括", "其中包括")

# Spec/drawing reference patterns in claims
_SPEC_REF = re.compile(r"如說明書|如圖|參見說明書|參見圖|參照說明書|參照附圖|如圖所示")


def _extract_subject(claim_text: str) -> str:
    """Extract subject name from claim preamble."""
    # Strip leading claim number pattern (e.g., "1. ")
    text = re.sub(r"^\s*\d+\s*[.．]\s*", "", claim_text)
    # For dependent claims: extract subject after 所述之/所述的/之
    dep_match = _DEP_SUBJECT.search(text)
    if dep_match:
        return dep_match.group(1).strip()
    # For independent claims: text before 其特徵在於 or first comma
    match = _PREAMBLE_END.search(text)
    if match:
        return text[:match.start()].strip()
    return ""


def _normalize_subject(subject: str) -> str:
    """Strip leading quantifiers for comparison."""
    return _LEADING_QUANTIFIER.sub("", subject).strip()


# ── Check 11 ─────────────────────────────────────────────────────────────


def check_claims_sequential(doc: TwPatentDocument) -> list[CheckItem]:
    """Verify claim numbers are sequential from 1."""
    claims = doc.claims
    if not claims:
        return [CheckItem(
            status="pass",
            message="No claims to check.",
            message_key="check.tw.claims.sequential.pass",
            reference="專利審查基準",
        )]

    for i, claim in enumerate(claims):
        expected = i + 1
        if claim.id != expected:
            detail = f"expected {expected}, found {claim.id}"
            return [CheckItem(
                status="amend",
                message=f"Claim numbering is not sequential: {detail}.",
                message_key="check.tw.claims.sequential.amend",
                details=detail,
                details_key="details.tw.claimsSequential",
                details_params={"detail": detail},
                reference="專利審查基準",
            )]

    return [CheckItem(
        status="pass",
        message="Claim numbers are sequential.",
        message_key="check.tw.claims.sequential.pass",
        reference="專利審查基準",
    )]


# ── Check 12 ─────────────────────────────────────────────────────────────


def check_dependency_format(doc: TwPatentDocument) -> list[CheckItem]:
    """Check dependent claims use recognized TW dependency format."""
    dependents = [c for c in doc.claims if not c.independent]
    if not dependents:
        return [CheckItem(
            status="pass",
            message="No dependent claims to check.",
            message_key="check.tw.claims.dependencyFormat.pass",
            reference="專利法施行細則 §18",
        )]

    bad_count = 0
    for claim in dependents:
        if not _TW_DEP_FORMAT.search(claim.text):
            bad_count += 1

    if bad_count:
        return [CheckItem(
            status="amend",
            message=f"{bad_count} claim(s) with unrecognized dependency format.",
            message_key="check.tw.claims.dependencyFormat.amend",
            details=f"{bad_count} claims",
            details_key="details.tw.dependencyFormat",
            details_params={"count": str(bad_count)},
            reference="專利法施行細則 §18",
        )]

    return [CheckItem(
        status="pass",
        message="All dependency references use recognized format.",
        message_key="check.tw.claims.dependencyFormat.pass",
        reference="專利法施行細則 §18",
    )]


# ── Check 13 ─────────────────────────────────────────────────────────────


def check_self_dependent(doc: TwPatentDocument) -> list[CheckItem]:
    """Check if any claim depends on itself."""
    bad = [c.id for c in doc.claims if c.id in c.dependencies]

    if bad:
        claims_str = ", ".join(str(i) for i in bad)
        return [CheckItem(
            status="amend",
            message=f"Self-dependent claims found: {claims_str}.",
            message_key="check.tw.claims.selfDependent.amend",
            details=claims_str,
            details_key="details.tw.selfDependent",
            details_params={"claims": claims_str},
            reference="專利法施行細則 §18",
        )]

    return [CheckItem(
        status="pass",
        message="No self-dependent claims.",
        message_key="check.tw.claims.selfDependent.pass",
        reference="專利法施行細則 §18",
    )]


# ── Check 14 ─────────────────────────────────────────────────────────────


def check_circular_dependency(doc: TwPatentDocument) -> list[CheckItem]:
    """Detect circular dependency chains."""
    claims_by_id = {c.id: c for c in doc.claims}

    def has_cycle(start_id: int) -> list[int] | None:
        visited: set[int] = set()
        path: list[int] = []
        current = start_id
        while current in claims_by_id:
            if current in visited:
                return path
            visited.add(current)
            path.append(current)
            claim = claims_by_id[current]
            if claim.independent or not claim.dependencies:
                return None
            current = claim.dependencies[0]
        return None

    for claim in doc.claims:
        if not claim.independent:
            cycle = has_cycle(claim.id)
            if cycle:
                claims_str = " → ".join(str(i) for i in cycle)
                return [CheckItem(
                    status="amend",
                    message=f"Circular dependency chain found: {claims_str}.",
                    message_key="check.tw.claims.circularDependency.amend",
                    details=claims_str,
                    details_key="details.tw.circularDependency",
                    details_params={"claims": claims_str},
                    reference="專利法施行細則 §18",
                )]

    return [CheckItem(
        status="pass",
        message="No circular dependencies.",
        message_key="check.tw.claims.circularDependency.pass",
        reference="專利法施行細則 §18",
    )]


# ── Check 15 ─────────────────────────────────────────────────────────────


def check_forward_dependency(doc: TwPatentDocument) -> list[CheckItem]:
    """Check if any claim depends on a higher-numbered claim."""
    bad = [c.id for c in doc.claims if any(d > c.id for d in c.dependencies)]

    if bad:
        claims_str = ", ".join(str(i) for i in bad)
        return [CheckItem(
            status="amend",
            message=f"Forward-referencing claims found: {claims_str}.",
            message_key="check.tw.claims.forwardDependency.amend",
            details=claims_str,
            details_key="details.tw.forwardDependency",
            details_params={"claims": claims_str},
            reference="專利法施行細則 §18",
        )]

    return [CheckItem(
        status="pass",
        message="No forward dependencies.",
        message_key="check.tw.claims.forwardDependency.pass",
        reference="專利法施行細則 §18",
    )]


# ── Check 16 ─────────────────────────────────────────────────────────────


def check_single_sentence(doc: TwPatentDocument) -> list[CheckItem]:
    """Each claim must have exactly one 。 at end, no 。 in middle."""
    bad_count = 0
    for claim in doc.claims:
        text = claim.text.strip()
        period_count = text.count("。")
        if period_count != 1 or not text.endswith("。"):
            bad_count += 1

    if bad_count:
        return [CheckItem(
            status="amend",
            message=f"{bad_count} claim(s) not written as a single sentence.",
            message_key="check.tw.claims.singleSentence.amend",
            details=f"{bad_count} claims",
            details_key="details.tw.singleSentence",
            details_params={"count": str(bad_count)},
            reference="專利法施行細則 §18",
        )]

    return [CheckItem(
        status="pass",
        message="All claims are single sentences.",
        message_key="check.tw.claims.singleSentence.pass",
        reference="專利法施行細則 §18",
    )]


# ── Check 17 ─────────────────────────────────────────────────────────────


def check_ref_numeral_parens(doc: TwPatentDocument) -> list[CheckItem]:
    """Find reference numerals in claims not enclosed in parentheses."""
    bad_count = 0
    for claim in doc.claims:
        if _BARE_NUMERAL.search(claim.text):
            bad_count += 1

    if bad_count:
        return [CheckItem(
            status="verify",
            message=f"{bad_count} claim(s) with reference numerals not in parentheses.",
            message_key="check.tw.claims.refNumeralParens.verify",
            details=f"{bad_count} claims",
            details_key="details.tw.refNumeralParens",
            details_params={"count": str(bad_count)},
            reference="專利法施行細則 §19",
        )]

    return [CheckItem(
        status="pass",
        message="All reference numerals in claims are in parentheses.",
        message_key="check.tw.claims.refNumeralParens.pass",
        reference="專利法施行細則 §19",
    )]


# ── Check 18 ─────────────────────────────────────────────────────────────


def check_subject_consistency(doc: TwPatentDocument) -> list[CheckItem]:
    """Check dependent claim subjects match their parent claim subjects."""
    claims_by_id = {c.id: c for c in doc.claims}
    dependents = [c for c in doc.claims if not c.independent]

    if not dependents:
        return [CheckItem(
            status="pass",
            message="No dependent claims to check.",
            message_key="check.tw.claims.subjectConsistency.pass",
            reference="專利審查基準",
        )]

    bad_count = 0
    for claim in dependents:
        if not claim.dependencies:
            continue
        parent_id = claim.dependencies[0]
        parent = claims_by_id.get(parent_id)
        if not parent:
            continue

        dep_subject = _normalize_subject(_extract_subject(claim.text))
        parent_subject = _normalize_subject(_extract_subject(parent.text))

        if dep_subject and parent_subject and dep_subject != parent_subject:
            bad_count += 1

    if bad_count:
        return [CheckItem(
            status="verify",
            message=f"{bad_count} dependent claim(s) with inconsistent subject name.",
            message_key="check.tw.claims.subjectConsistency.verify",
            details=f"{bad_count} claims",
            details_key="details.tw.subjectConsistency",
            details_params={"count": str(bad_count)},
            reference="專利審查基準",
        )]

    return [CheckItem(
        status="pass",
        message="All dependent claim subjects match parent.",
        message_key="check.tw.claims.subjectConsistency.pass",
        reference="專利審查基準",
    )]


# ── Check 19 ─────────────────────────────────────────────────────────────


def check_transition_phrase(doc: TwPatentDocument) -> list[CheckItem]:
    """Check independent claims contain a transitional phrase."""
    independents = [c for c in doc.claims if c.independent]
    if not independents:
        return [CheckItem(
            status="pass",
            message="No independent claims to check.",
            message_key="check.tw.claims.transitionPhrase.pass",
            reference="專利法施行細則 §20",
        )]

    bad_count = 0
    for claim in independents:
        if not any(phrase in claim.text for phrase in _TRANSITION_PHRASES):
            bad_count += 1

    if bad_count:
        return [CheckItem(
            status="verify",
            message=f"{bad_count} independent claim(s) missing transitional phrase.",
            message_key="check.tw.claims.transitionPhrase.verify",
            details=f"{bad_count} claims",
            details_key="details.tw.transitionPhrase",
            details_params={"count": str(bad_count)},
            reference="專利法施行細則 §20",
        )]

    return [CheckItem(
        status="pass",
        message="All independent claims contain a transitional phrase.",
        message_key="check.tw.claims.transitionPhrase.pass",
        reference="專利法施行細則 §20",
    )]


# ── Check 20 ─────────────────────────────────────────────────────────────

# CNIPA simplified Chinese terms that should not appear in TW documents
_CNIPA_TERMS = ["权利要求", "说明书", "背景技术", "具体实施方式", "发明内容", "附图说明", "其特征在于"]


def check_cn_terminology(doc: TwPatentDocument) -> list[CheckItem]:
    """Scan claims for CNIPA simplified Chinese terminology."""
    all_text = " ".join(c.text for c in doc.claims)
    found = [term for term in _CNIPA_TERMS if term in all_text]

    if found:
        return [CheckItem(
            status="verify",
            message=f"CNIPA terminology found: {', '.join(found)}.",
            message_key="check.tw.claims.cnTerminology.verify",
            details=", ".join(found),
            details_key="details.tw.cnTerminology",
            details_params={"detail": ", ".join(found)},
            reference=None,
        )]

    return [CheckItem(
        status="pass",
        message="Claims use correct TIPO terminology.",
        message_key="check.tw.claims.cnTerminology.pass",
        reference=None,
    )]


# ── Check 21 ─────────────────────────────────────────────────────────────

_SPEC_DRAWING_REF = re.compile(
    r"如說明書所述|如圖\d*所示|參見說明書|參見圖|見說明書|見圖"
)


def check_spec_drawing_ref(doc: TwPatentDocument) -> list[CheckItem]:
    """Check claims do not reference spec or drawings."""
    found_refs: list[str] = []
    for claim in doc.claims:
        matches = _SPEC_DRAWING_REF.findall(claim.text)
        found_refs.extend(matches)

    if found_refs:
        detail = ", ".join(sorted(set(found_refs)))
        return [CheckItem(
            status="amend",
            message=f"Claims reference specification or drawings: {detail}.",
            message_key="check.tw.claims.specDrawingRef.amend",
            details=detail,
            details_key="details.tw.specDrawingRef",
            details_params={"detail": detail},
            reference="專利法施行細則 §19",
        )]

    return [CheckItem(
        status="pass",
        message="No specification or drawing references in claims.",
        message_key="check.tw.claims.specDrawingRef.pass",
        reference="專利法施行細則 §19",
    )]


# ── Check 22 ─────────────────────────────────────────────────────────────


def check_multi_dep_on_multi_dep(doc: TwPatentDocument) -> list[CheckItem]:
    """Multi-dependent claim must not depend on another multi-dependent claim."""
    multi_dep_ids = {c.id for c in doc.claims if c.multiple_dependent}
    if not multi_dep_ids:
        return [CheckItem(
            status="pass",
            message="No multi-dependent-on-multi-dependent claims.",
            message_key="check.tw.claims.multiDepOnMultiDep.pass",
            reference="專利法施行細則 §18",
        )]

    claims_by_id = {c.id: c for c in doc.claims}

    def _get_all_deps(claim_id: int, visited: set[int] | None = None) -> set[int]:
        """Get all transitive dependencies."""
        if visited is None:
            visited = set()
        if claim_id in visited:
            return visited
        visited.add(claim_id)
        claim = claims_by_id.get(claim_id)
        if claim:
            for dep in claim.dependencies:
                _get_all_deps(dep, visited)
        return visited

    bad = []
    for claim in doc.claims:
        if claim.multiple_dependent:
            all_deps = _get_all_deps(claim.id)
            all_deps.discard(claim.id)
            if all_deps & multi_dep_ids:
                bad.append(claim.id)

    if bad:
        claims_str = ", ".join(str(i) for i in bad)
        return [CheckItem(
            status="amend",
            message=f"Multi-dependent claim depends on another multi-dependent claim: {claims_str}.",
            message_key="check.tw.claims.multiDepOnMultiDep.amend",
            details=claims_str,
            details_key="details.tw.multiDepOnMultiDep",
            details_params={"claims": claims_str},
            reference="專利法施行細則 §18",
        )]

    return [CheckItem(
        status="pass",
        message="No multi-dependent-on-multi-dependent claims.",
        message_key="check.tw.claims.multiDepOnMultiDep.pass",
        reference="專利法施行細則 §18",
    )]


# ── Check 23 ─────────────────────────────────────────────────────────────


def check_multi_dep_alternative(doc: TwPatentDocument) -> list[CheckItem]:
    """Multi-dependent claims must use alternative form (或/任一項)."""
    multi_deps = [c for c in doc.claims if c.multiple_dependent]
    if not multi_deps:
        return [CheckItem(
            status="pass",
            message="All multi-dependent claims use alternative form.",
            message_key="check.tw.claims.multiDepAlternative.pass",
            reference="專利法施行細則 §18",
        )]

    bad = []
    for claim in multi_deps:
        if "或" not in claim.text and "任一項" not in claim.text:
            bad.append(claim.id)

    if bad:
        claims_str = ", ".join(str(i) for i in bad)
        return [CheckItem(
            status="amend",
            message=f"Multi-dependent claim(s) not in alternative form: {claims_str}.",
            message_key="check.tw.claims.multiDepAlternative.amend",
            details=claims_str,
            details_key="details.tw.multiDepAlternative",
            details_params={"claims": claims_str},
            reference="專利法施行細則 §18",
        )]

    return [CheckItem(
        status="pass",
        message="All multi-dependent claims use alternative form.",
        message_key="check.tw.claims.multiDepAlternative.pass",
        reference="專利法施行細則 §18",
    )]


# ── Check 24 ─────────────────────────────────────────────────────────────


def check_title_subject_match(doc: TwPatentDocument) -> list[CheckItem]:
    """Check title matches independent claim subjects."""
    if not doc.title or not doc.claims:
        return [CheckItem(
            status="pass",
            message="Title consistent with independent claim subjects.",
            message_key="check.tw.claims.titleSubjectMatch.pass",
            reference="專利審查基準",
        )]

    independents = [c for c in doc.claims if c.independent]
    if not independents:
        return [CheckItem(
            status="pass",
            message="Title consistent with independent claim subjects.",
            message_key="check.tw.claims.titleSubjectMatch.pass",
            reference="專利審查基準",
        )]

    title_norm = _normalize_subject(doc.title)
    subjects = []
    for claim in independents:
        subj = _normalize_subject(_extract_subject(claim.text))
        if subj:
            subjects.append(subj)

    if not subjects:
        return [CheckItem(
            status="pass",
            message="Title consistent with independent claim subjects.",
            message_key="check.tw.claims.titleSubjectMatch.pass",
            reference="專利審查基準",
        )]

    # Check if title overlaps with any subject
    for subj in subjects:
        if subj in title_norm or title_norm in subj:
            return [CheckItem(
                status="pass",
                message="Title consistent with independent claim subjects.",
                message_key="check.tw.claims.titleSubjectMatch.pass",
                reference="專利審查基準",
            )]

    subjects_str = ", ".join(subjects)
    detail = f"Title: {doc.title}; Independent claim subjects: {subjects_str}"
    return [CheckItem(
        status="verify",
        message="Title may not match independent claim subjects.",
        message_key="check.tw.claims.titleSubjectMatch.verify",
        details=detail,
        details_key="details.tw.titleSubjectMatch",
        details_params={"detail": detail},
        reference="專利審查基準",
    )]


# ── Check 25 ─────────────────────────────────────────────────────────────

# Reference numeral in parentheses in claim text
_CLAIM_NUMERAL = re.compile(r"\((\d+)\)")


def check_claims_symbol_table_consistency(doc: TwPatentDocument) -> list[CheckItem]:
    """Verify reference numerals in claims are defined in 符號說明.

    Per 專利法施行細則 §19, reference numerals in claims are optional.
    When absent, the check passes vacuously. When present, every numeral
    used in claims must be defined in 符號說明; the reverse direction
    (符號說明 entries not used in claims) is NOT a defect — symbol
    tables legitimately cover all figure elements regardless of which
    appear in claim language.

    Emits structured details_params with claim-number locations for
    each undefined numeral, allowing the frontend formatter to render
    "99 (claim 1, claim 3), 100 (claim 5)" in the user's locale.
    """
    if not doc.symbol_table:
        return [CheckItem(
            status="pass",
            message="No 符號說明 entries to check against claims.",
            message_key="check.tw.claims.symbolTableConsistency.pass",
            reference="專利法施行細則 §19",
        )]

    # Collect numerals from claims (parenthesized form only, per §19),
    # tracking which claim numbers contain each numeral.
    numeral_to_claims: dict[str, list[int]] = {}
    for claim in doc.claims:
        for m in _CLAIM_NUMERAL.finditer(claim.text):
            numeral = m.group(1)
            if numeral not in numeral_to_claims:
                numeral_to_claims[numeral] = []
            if claim.id not in numeral_to_claims[numeral]:
                numeral_to_claims[numeral].append(claim.id)

    claim_numerals = set(numeral_to_claims.keys())

    # Early return: claims contain no reference numerals (allowed by §19).
    if not claim_numerals:
        return [CheckItem(
            status="pass",
            message="Claims contain no reference numerals; consistency check not applicable.",
            message_key="check.tw.claims.symbolTableConsistency.noClaimNumerals",
            reference="專利法施行細則 §19",
        )]

    # Collect numerals from symbol table (handle ranges like S21~S25)
    symbol_numerals: set[str] = set()
    for entry in doc.symbol_table:
        nums = re.findall(r"\d+", entry.numeral)
        symbol_numerals.update(nums)

    # Only flag the directionally meaningful case: numerals used in claims
    # but undefined in 符號說明. The reverse is allowed.
    missing_numerals = sorted(claim_numerals - symbol_numerals, key=int)

    if missing_numerals:
        # Build structured payload: list of {numeral, claims} dicts.
        # Frontend formatter will render this as
        # "99 (claim 1, claim 3), 100 (claim 5)" in the user's locale.
        numerals_with_locations = [
            {
                "numeral": n,
                "claims": sorted(numeral_to_claims[n]),
            }
            for n in missing_numerals
        ]
        return [CheckItem(
            status="verify",
            message=f"Reference numerals in claims undefined in 符號說明: {', '.join(missing_numerals)}",
            message_key="check.tw.claims.symbolTableConsistency.verify",
            details_key="details.tw.claims.symbolTableConsistency.missingFromTable",
            details_params={"numerals_with_locations": numerals_with_locations},
            reference="專利法施行細則 §19",
        )]

    return [CheckItem(
        status="pass",
        message="All reference numerals in claims are defined in 符號說明.",
        message_key="check.tw.claims.symbolTableConsistency.pass",
        reference="專利法施行細則 §19",
    )]


# ── Check 26 ─────────────────────────────────────────────────────────────

# Boundary character class for the noun-phrase regex captures.
#
# Excluded categories (characters that NEVER appear inside a legitimate
# patent reference noun phrase, so the regex can safely terminate at them):
#
# - Whitespace and punctuation: \s ， 。 ； ： 、 (existing)
# - Conjunctions: 及 與 和 (existing)
# - Genitive markers: 之 的 (existing)
# - Reference-form prefix start: 該 (existing — prevents two adjacent
#   references from being captured as one noun span)
# - Auxiliary verbs / adverbs: 將 能 須 應 皆 (added 2026-04-09)
# - Passive marker: 被 (added 2026-04-09)
# - Prepositions: 於 以 在 (在 added 2026-04-09 round 3 — high-frequency
#   preposition that was contaminating findings like 該識別資料在 in
#   110P000868). 用 was added in round 2 (Bug B) but REMOVED in round 5 —
#   it was breaking 使用者 compounds (該多個使用者 captured as 多個使
#   then normalized to 使). See round 5 note below.
# - Connectives: 並 且 其 而 還 另 (或 added in round 2 but REMOVED in
#   round 5 — was breaking 一或多個 quantifier; see round 5 note)
# - Temporal particle: 時 (added 2026-04-09)
#
# Round 2 Bug B note: 用 was originally added because 第二無線通訊模組用
# was capturing past the head noun, defeating the ordinal guard's
# suffix-strict comparison and producing the misleading suggestion
# "所述第二無線通訊模組用 → 第一無線通訊模組".
#
# Round 5 reversal of round 2 Bug B (2026-04-09): 用 removed because the
# round 2 fix had a worse failure mode — it broke 使用者/使用/應用/適用
# compounds. In 110P000368 Claim 7 the regex captured 該多個使 (stopping
# at 用 in 使用者) instead of 該多個使用者. The trailing-strip + residual
# ≥ 3 guard via _NOUNLIKE_SINGLE_CHAR_SUFFIXES handles trailing 用
# contamination instead: 第二無線通訊模組用 → 第二無線通訊模組 (residual
# 7 ≥ 3, strip allowed); 應用 / 適用 / 使用 (2-char compounds, residual
# 1, strip blocked) preserved. Grep confirms 使用者 ×269, 使用 ×364,
# 應用 ×102, 適用 ×9 in the 10-fixture corpus, all preserved.
#
# Round 5 reversal of round 2 連接ive 或 (2026-04-09): 或 removed
# because the round 2 fix terminated 一或多個 quantifier mid-capture in
# references like 該前一或多個主題標籤 (110P000368). Trailing 或
# contamination is handled by _TRAILING_VERB_DENYLIST instead. Grep
# confirms 或門/或物/或非門/或邏輯 all 0 in the 10-fixture corpus, so
# no compound-noun risk and no exception coordination needed.
#
# NOT excluded (would break legitimate compound nouns):
# - 一 (would break 第一X ordinals — handled by _INTRO_PATTERN's negative
#   lookbehind on bare 一; for _REF_PATTERN_CAPTURE the ordinal forms are
#   protected because they don't begin with 一)
# - 中 上 下 內 外 前 後 (positional g-strip layer; 中 and 後 have
#   trailing-strip + residual guard added in round 5 for fragments like
#   該資料庫中 / 該瀏覽程式產生後)
# - 連 編 識 通 傳 旋 接 設 (verb characters that ARE inside compounds
#   like 連接器, 編碼器, 識別碼, 通訊模組, 傳動件 — handled at the
#   interior-cut layer with an exceptions set)
#
# Upper bound reduced from 16 to 12 because real reference noun phrases
# rarely exceed 8 chars (longest plausible: 第二無線通訊模組 = 8 chars,
# 該所述前述 prefix is stripped before this regex applies). 12 leaves
# headroom for ordinal+qualifier+head-noun compounds without permitting
# the runaway captures observed in the 2026-04-09 smoke test.
_NOUN_CHARS = r"[^\s，。；：、及與和之的該將能須應皆被於以並且其而還另時在]{2,12}"

# Introduction patterns — ordered longest-first so 至少一個 / 複數個 are
# matched as single tokens before their shorter prefixes (一 / 複數). The
# regex returns the noun via group 1; the (?:...) alternation in group 0
# carries the quantifier prefix (used by the walker only for diagnostic
# purposes).
#
# The bare ``一`` alternative carries a negative lookbehind for ``第``
# so it does NOT match the ordinal ``第一X`` (otherwise ``第一剛輪`` would
# be parsed as quantifier ``一`` + noun ``剛輪`` and the legitimate
# ``一第一剛輪`` introduction would be mis-attributed to ``剛輪``).
#
# It additionally carries a negative lookahead for ``同`` and ``體`` so
# it does NOT match the idiomatic compound prefixes ``一同`` ("together
# with") and ``一體`` ("as one body"), which are adverbial constructions
# rather than element introductions. Without this guard,
# ``與一柔性軸承一同構成一波產生器`` matched at the ``一`` in ``一同`` and
# captured ``同構成一波產生器`` as group 1, producing the contaminated
# intro ``同構成一波產生器`` (Bug C2 from 2026-04-09 phase8b diagnosis).
#
# Other potentially-idiomatic forms (一側, 一端) are NOT excluded
# because they ARE legitimate noun introductions in many claims
# (一第一端, 一第二端, 一側面). Their contaminated forms (一側設置...,
# 一端透過樞軸...) require lazy regex matching and are deferred to
# Phase 9.
_INTRO_MULTI_QUANTIFIERS = (
    # Round 5 addition: multi-char quantifier "one or more X" — common
    # in JP-origin TW translations. Grep confirms 一或多個 ×59 in
    # 110P000368 + 110P000868 (variants 一或更多 / 一或一個以上 /
    # 一或者多個 all 0). Coordinated with the round 5 removal of 或
    # from _NOUN_CHARS exclusion — without that removal, the regex
    # would still terminate at 或 mid-quantifier even with this entry.
    "一或多個",
    # F4: generalized 至少N個? — covers 至少一個, 至少一, 至少三個,
    # 至少四個, etc. Replaces old 至少一個/至少一 literals.
    r"至少[一二三四五六七八九十百千\d]+個?",
    # F4: bare-two quantifier. 兩個X (with counter) is unambiguous.
    # Bare 兩X (without counter) needs a negative lookahead: 兩端 (both
    # ends) and 兩側 (both sides) are body-part compounds, NOT intros.
    # Corpus: 兩曲柄 ×1 (intro), 兩端 ×3, 兩側 ×2 (all non-intro).
    "兩個",
    r"兩(?![端側])",
    # F4b: bare N個 quantifier (CJK numerals only). Arabic digits
    # excluded — 100個 etc. are measurements, not intros. Safe from
    # N個所述X false positives because F3 Rule 1a discards captures
    # starting with 所述.
    r"[二三四五六七八九十]+個",
    "一個", "一種", "一對",
    "複數個", "多個", "數個",
    "複數",
)
# Weight/molar composition intro: N重量份(至M重量份)的X introduces noun X.
# Units: 重量份, 重量百分比, 莫耳, wt%, mol%.  Only 重量份 appears in the
# current 10-fixture corpus; others included for forward-compat.
_WEIGHT_UNITS = r"(?:重量份|重量百分比|莫耳|wt%|mol%)"
_WEIGHT_COMPOSITION_PREFIX = (
    r"\d+(?:\.\d+)?" + _WEIGHT_UNITS
    + r"(?:至\d+(?:\.\d+)?" + _WEIGHT_UNITS + r")?的"
)
# Definitional intro: 定義為X, 稱為X, 記為X, 表示為X — introduces noun X.
# Optional 一 handles both 定義為X and 定義為一X uniformly.
# Corpus attestation: 定義為 ×22 across 110P000158/110P000631/110P000633;
# 稱為/記為/表示為 have 0 corpus occurrences but are standard TIPO drafting
# patterns included for forward-compat.
_DEFINITIONAL_PREFIX = r"(?:定義為|稱為|記為|表示為)一?"
_INTRO_PATTERN = re.compile(
    r"(?:"
    + _WEIGHT_COMPOSITION_PREFIX
    + r"|" + _DEFINITIONAL_PREFIX
    + r"|(?:" + "|".join(_INTRO_MULTI_QUANTIFIERS) + r"|(?<!第)一(?![同體])))"
    + f"({_NOUN_CHARS})"
)

# Reference: 該/所述/前述/該等/該些 + noun (2-16 CJK characters). Captured
# with named groups so the walker can preserve the original prefix when
# constructing finding records.
_REFERENCE_PREFIXES = ("該等", "該些", "所述", "前述", "該")
_REF_PATTERN_CAPTURE = re.compile(
    r"(?P<prefix>" + "|".join(_REFERENCE_PREFIXES) + r")"
    + f"(?P<noun>{_NOUN_CHARS})"
)


# ── Phase 8b TW walker — reference-term normalization (ADR-095) ──────────
#
# Three sequential transformations applied before computing antecedent
# matches or did-you-mean similarity scores:
#
#   1. Trailing-verb strip (parser correctness fix, ADR-095 Rule 1)
#   2. Leading-quantifier strip (ADR-095 Rule 2)
#   3. Number-neutral antecedent matching (implicit in symmetric stripping)
#
# ``normalize_reference_term`` composes all three for the reference side;
# ``normalize_candidate_intro`` applies the same normalization to intro
# candidates. Both sides are stripped symmetrically so number-neutral
# matching works (複數外齒狀結構 ↔ 該外齒狀結構 → both normalize to 外齒狀結構).

# ADR-095 Rule 1: trailing-verb denylist.
# Ordered longest-first so greedy matching strips 還包含 as one token
# before 還 strips as another. Tuple form is required because
# ``sorted(..., key=len, reverse=True)`` is applied once at import time.
_TRAILING_VERB_DENYLIST: tuple[str, ...] = tuple(sorted(
    (
        # Verb suffixes
        "包含", "包括", "含有", "具有", "係", "為", "是", "設有", "具備",
        # Preposition-verbs
        "通過", "經由", "藉由", "基於", "透過", "根據", "依據",
        # Conjunction starters (multi-char longest)
        "還包含", "還包括",
        "並且", "以及",
        "並", "且", "其", "其中", "還", "另",
        # Partial captures — single-character fragments that indicate the
        # regex stopped mid-word. Ordered after multi-char tokens.
        "包", "通", "經", "藉",
        # Reference-form prefix fragments stranded by interior cuts.
        # When clean_noun_phrase_tw cuts ``電子組件所包含`` at 包含, the
        # leading-of-the-stripped-prefix character ``所`` is left behind
        # as a stray. Same for 前 (start of 前述). 所-terminated
        # compound nouns (研究所, 場所, 事務所) are protected by the
        # residual ≥ 3 guard in clean_noun_phrase_tw via
        # _NOUNLIKE_SINGLE_CHAR_SUFFIXES below; 前 has no such guard
        # because it appears overwhelmingly as a prefix in patent
        # Chinese, not a suffix (see the comment on the constant).
        "所", "前",
        # Resultative particles (added 2026-04-09)
        "到", "出",
        # === Added 2026-04-10 F2 ===
        # 介: verb particle from 介於 ("falls between"). Corpus
        #     attestation: 第一夾角介於 on 110P000158 c1/c3. Compound
        #     nouns with medial 介 (使用者介面, 操作介面, 介電) have 介
        #     in non-trailing position — unaffected by trailing strip.
        #     中介裝置 (介 at pos 1) has residual 中 (1 char < 3),
        #     protected by general residual guard.
        "介",
        # === Added 2026-04-09 round 4 ===
        # 位 fragment of truncated 位於 verb (regex stopped at 於 which
        # is in the _NOUN_CHARS exclusion class). Compound nouns
        # 位置/位元/數位/第一位/第二位 are protected by the residual ≥ 3
        # guard via _NOUNLIKE_SINGLE_CHAR_SUFFIXES below.
        "位",
        # === Added 2026-04-09 round 5 ===
        # 或: connective ("or"). Removed from _NOUN_CHARS in round 5 to
        #     unblock the 一或多個 quantifier; trailing 或 contamination
        #     (該全世界或) is handled here instead. Grep confirms
        #     或門/或物/或非門/或邏輯 all 0 in the 10-fixture corpus —
        #     no compound-noun risk, no residual guard needed (general
        #     residual ≥ 1 floor suffices).
        "或",
        # 中: positional particle ("inside/within"). Stranded at the
        #     trailing edge of captures like 該資料庫中. Compound forms
        #     中心/中央/中文/中段/中部/中層/中環/中間 are 2-char with 中
        #     at position 0; protected by residual ≥ 3 guard via
        #     _NOUNLIKE_SINGLE_CHAR_SUFFIXES below. Grep: 中心 ×93,
        #     中央 ×10, 中文 ×30 — all preserved.
        "中",
        # 後: positional particle ("after/behind"). Stranded at the
        #     trailing edge of captures like 該瀏覽程式產生後. Compound
        #     forms 後輪/後方/後續 (and the unobserved 後端/後蓋/後座)
        #     are 2-char with 後 at position 0; protected by residual
        #     ≥ 3 guard. Grep: 後輪 ×11, 後方 ×1, 後續 ×14 — all
        #     preserved. Note: 後 also appears as a leading qualifier
        #     in 後一X patterns ("the next X"), handled by
        #     strip_leading_qualifier — different code path, no conflict.
        "後",
        # 用: preposition ("use/for"). Removed from _NOUN_CHARS in
        #     round 5 (reversal of round 2 Bug B fix); trailing 用
        #     contamination (第二無線通訊模組用 → 第二無線通訊模組)
        #     handled here with residual ≥ 3 guard. Compound forms
        #     使用/應用/適用/作用/信用/通用 are 2-char and protected
        #     by the guard (residual after stripping ≤ 1, < 3).
        #     使用者 (3-char) is protected at the regex level —
        #     it doesn't END in 用, so the trailing strip never
        #     applies to it. Grep: 使用 ×364, 應用 ×102, 適用 ×9,
        #     作用 ×2, 使用者 ×269 — all preserved.
        "用",
        # === Round 5 cascade additions ===
        # Surfaced after the round 5 removal of 用/或 from _NOUN_CHARS
        # unblocked the regex to capture longer noun spans that include
        # trailing positional particles 上/內 (previously hidden because
        # the regex stopped at 用 in 使用者介面上 / at 或 in 全世界或地域內).
        #
        # 上: positional particle ("on/above"). Stranded at the trailing
        #     edge of captures like 該使用者介面上 (110P000368). Compound
        #     forms 上方/上端/上述/上層/上部 are 2-char with 上 at
        #     position 0; protected by residual ≥ 3 guard via
        #     _NOUNLIKE_SINGLE_CHAR_SUFFIXES. Grep: 上方 ×20, 上端 ×65,
        #     上述 ×45, 上下 ×3 — all preserved.
        "上",
        # 內: positional particle ("inside/within"). Stranded at the
        #     trailing edge of captures like 該地域內 (110P000368).
        #     Compound forms 內部/內側/內徑/內側面 have 內 at position 0
        #     of a 2- or 3-char compound; protected by residual ≥ 3
        #     guard. Grep: 內部 ×40, 內側 ×76, 內徑 ×3, 內側面 ×2 —
        #     all preserved.
        "內",
        # Adverbs that ended up trailing after interior cut
        "分別", "皆",
        # Positional particle (parallel to 時)
        "處",
        # === Added 2026-04-10 F3 ===
        # 至: preposition ("to/until") from V至 patterns like 解鎖指令至
        #     (110P000868 c8) and 傳送至 (109P001046 c12). Corpus safety:
        #     min residual 6 across 65 occurrences. No compound-noun risk.
        "至",
        # 依序: adverb ("in order") from 第二方向依序 (110P000633 c10/c19).
        #     Corpus safety: min residual 15 across 12 occurrences. No
        #     compound-noun risk.
        "依序",
        # 擷取: verb ("capture/acquire") from 影像擷取裝置擷取
        #     (110P000633 c3 after ref-marker truncation). Corpus safety:
        #     min residual 2 (影像擷取 → 影像). Protected by residual ≥ 3
        #     guard via _NOUNLIKE_GUARDED_SUFFIXES below — 影像擷取 (4 chars,
        #     residual 2 < 3) preserved, 影像擷取裝置擷取 (8 chars, residual
        #     6 ≥ 3) stripped.
        "擷取",
    ),
    key=len,
    reverse=True,
))

# Noun-like single-char trailing suffixes that get the residual ≥ 3 guard
# in clean_noun_phrase_tw. These are the denylist members where the
# 1-char form is itself a productive noun-suffix morpheme rather than a
# verb fragment, so a too-eager strip damages real compound nouns.
#
# 所 stays here because its compound-noun forms (研究所, 場所, 事務所,
# 避難所) are all position-[-1] suffixes of the compound.
#
# 位 added 2026-04-09 round 4: 位 appears as the fragment of a
# truncated 位於 verb when the regex stops at 於 (which is already in
# the _NOUN_CHARS exclusion class). Adding it to trailing strip with
# the residual ≥ 3 guard catches the truncation
# (第二容置空間(225)位 → 第二容置空間(225)) while preserving compound
# forms 位置/位元/數位/第一位/第二位 because their residual after
# stripping 位 would be ≤ 2 (位置 → 1, 第一位 → 2). Grep confirmed
# 位置 ×392, 數位 ×197, 第一位 ×3, 第二位 ×2 in the 10-fixture corpus,
# all preserved by the guard.
#
# 前 is NOT in this set despite being a noun morpheme in 以前/之前,
# because those grammatical adverbs are rare in claim text while 前
# appears overwhelmingly as a PREFIX in mechanical patent terms
# (前端, 前述, 前方, 前蓋, 前緣). Keeping 前 in this set would preserve
# 齒輪前 fragments that should strip to 齒輪. Compound prefixes like
# 前端 are unaffected because they don't end in 前 — only the
# trailing-strip codepath cares about this set. The 以前/之前 over-strip
# (以/之) is accepted as a known limit; a Phase 9 follow-up may
# generalize this set into a compound-noun allowlist that handles
# both 所-suffix and 前-suffix cases without the prefix/suffix conflict.
#
# 中 added 2026-04-09 round 5: positional particle ("inside/within")
# stranded at the trailing edge of captures like 該資料庫中. Compound
# forms 中心/中央/中文 (and the absent-from-corpus 中段/中部/中層/中環/
# 中間) all have 中 at position 0 of a 2-char compound, so residual after
# stripping is ≤ 1 (中心 → 心 → 1, 中央 → 央 → 1) — protected by
# residual ≥ 3 guard. Grep confirms 中心 ×93, 中央 ×10, 中文 ×30 in
# the 10-fixture corpus, all preserved.
#
# 後 added 2026-04-09 round 5: positional particle ("after/behind")
# stranded at the trailing edge of captures like 該瀏覽程式產生後. Compound
# forms 後輪/後方/後續 (and the absent-from-corpus 後端/後蓋/後座/後背/
# 後門) all have 後 at position 0 of a 2-char compound, so residual after
# stripping is ≤ 1 — protected by the same guard. Grep: 後輪 ×11,
# 後方 ×1, 後續 ×14 in the corpus, all preserved. Note that 後 ALSO
# appears as a leading qualifier in patterns like 後一X ("the next X"),
# handled by strip_leading_qualifier on the leading-position codepath
# — different from this trailing-position guard, no conflict.
#
# 用 added 2026-04-09 round 5: preposition ("use/for"). Removed from
# _NOUN_CHARS in round 5 (reversal of round 2 Bug B fix) so that
# 使用者 compounds capture cleanly. Trailing 用 contamination
# (第二無線通訊模組用 → 第二無線通訊模組, residual 7 ≥ 3) handled
# here with the residual ≥ 3 guard. Compound forms 使用/應用/適用/
# 作用/信用/通用 are all 2-char with 用 at position [-1]; residual
# after stripping is 1 → preserved. 使用者 (3 chars) does NOT end
# in 用 so the trailing strip never applies. Grep: 使用 ×364,
# 應用 ×102, 適用 ×9, 作用 ×2, 使用者 ×269 — all preserved.
#
# 上 added 2026-04-09 round 5 cascade: positional particle ("on/
# above") stranded at the trailing edge of captures like 該使用者介面上.
# Surfaced after the round 5 用 removal unblocked the regex past 用
# in 使用者介面上 — pre-cascade the regex stopped at 用 and 該使用者介面上
# was never captured at all. Compound forms 上方/上端/上述/上層/上部
# all have 上 at position 0 of a 2-char compound — protected by the
# trailing-strip's position check (endswith fires only at position -1),
# NOT by the residual guard. Grep: 上方 ×20, 上端 ×65, 上述 ×45, 上下 ×3
# in the corpus, all preserved. Listed in _NOUNLIKE_RELAXED_SUFFIXES
# (residual ≥ 2 instead of ≥ 3) — see below for why.
#
# 內 added 2026-04-09 round 5 cascade: positional particle ("inside/
# within") stranded at the trailing edge of captures like 該地域內.
# Surfaced after the round 5 或 removal unblocked the regex past 或
# in 全世界或地域內. Compound forms 內部/內側/內徑 have 內 at position 0
# of a 2-char compound (protected by position check, not residual guard);
# 內側面 is 3-char with 內 at position 0 (same protection). Listed in
# _NOUNLIKE_RELAXED_SUFFIXES — see below.
_NOUNLIKE_SINGLE_CHAR_SUFFIXES: frozenset[str] = frozenset(
    {"所", "位", "中", "後", "用", "上", "內",
     # F3: 擷取 (2-char) — despite the set name, the residual guard
     # mechanism works with any length. 影像擷取 (4 chars, residual 2)
     # protected; 影像擷取裝置擷取 (8 chars, residual 6) strips correctly.
     "擷取"}
)

# Relaxed-guard subset: members of _NOUNLIKE_SINGLE_CHAR_SUFFIXES that
# get residual ≥ 2 instead of the default ≥ 3. The default ≥ 3 protects
# 3-char compounds where the suffix sits at position -1 of a productive
# noun (研究所, 第一位). The relaxed ≥ 2 lets 3-char positional fragments
# (地域內 → 地域, 範圍內 → 範圍, 基板上 → 基板, 面上 → 面) strip correctly
# while still protecting 2-char productive compounds ending in 上/內
# (室內/國內/海上/桌上 — residual 1, blocked by ≥ 2).
#
# Why 上/內 specifically: their productive 2-char compound forms put the
# particle at position 0 (上方/上端/內側/內部), so the trailing-strip
# never even considers them — the position check alone protects those.
# At position -1 they appear almost exclusively as positional fragments
# in patent claim text ("within the X" / "on the X"), not as standalone
# nouns. Corpus grep for 室內/國內/海上/桌上 etc. on the 10-fixture set
# returned 0 hits; 範圍內 ×3 and 基板上 ×4 are the only 3-char position-(-1)
# matches and both should strip.
#
# 所/位/中/後/用 stay at the strict ≥ 3 guard because they DO have
# productive 3-char compounds ending in the suffix (研究所, 第一位) or
# because the corpus is too small to confidently relax (中/後/用).
_NOUNLIKE_RELAXED_SUFFIXES: frozenset[str] = frozenset({"上", "內"})

# ADR-095 Rule 2: leading quantifiers (stripped from both sides).
# Ordered longest-first so 至少一個 is stripped as a single token before
# 至少一 is stripped.
_LEADING_QUANTIFIER_DENYLIST: tuple[str, ...] = tuple(sorted(
    (
        # Round 5 addition: 一或多個 multi-char quantifier (parallel to
        # _INTRO_MULTI_QUANTIFIERS). Stripped from both reference and
        # intro sides so 該前一或多個主題標籤 ↔ 該主題標籤 normalize to
        # the same head noun.
        "一或多個",
        "至少一個", "至少一",
        "一個", "一種", "一對",
        "複數個", "多個", "數個",
        "複數",
        "一",
    ),
    key=len,
    reverse=True,
))

# Reference-form prefixes: stripped from reference terms only. The walker
# strips these before applying the leading-quantifier pass, so 該第一電極
# becomes 第一電極 (quantifier strip leaves 第一電極 since 第一 is not in
# _LEADING_QUANTIFIER_DENYLIST — ordinals are part of the head noun).
_REFERENCE_FORM_PREFIXES: tuple[str, ...] = tuple(sorted(
    ("該等", "該些", "所述", "前述", "該"),
    key=len,
    reverse=True,
))

# Plural reference-form prefixes — a strict subset of reference-form
# prefixes that explicitly mark plural reference. These are used by the
# strict_plural_reference_matching escape hatch (default False per
# ADR-095) and by the ``detect_plural_reference`` helper below.
_PLURAL_REFERENCE_PREFIXES: tuple[str, ...] = tuple(sorted(
    ("該等", "該些", "前述複數", "所述複數", "所述多個"),
    key=len,
    reverse=True,
))


# Interior-boundary tokens — when one of these multi-char tokens appears
# mid-noun the walker truncates the noun at that point. Distinct from
# ``_TRAILING_VERB_DENYLIST`` (suffix stripping); these are interior cuts
# applied BEFORE the trailing-strip pass. Necessary because the regex
# noun capture is greedy: ``該底座設有一孔洞`` captures
# ``底座設有一孔洞``, and the trailing-strip alone cannot recover
# ``底座`` because the trailing token is ``孔洞`` (a real noun, not a
# verb).
#
# Two families:
#   1. Verb tokens (設有/包含/...) — split greedy noun spans at the verb.
#   2. Reference-form prefixes (所述/前述/該等/該些) — split greedy noun
#      spans when a downstream reference begins inside the captured
#      window. The single-char 該 is handled in the regex character
#      class itself; multi-char prefixes need this interior cut because
#      the regex would otherwise consume past them.
#
# In-claim verbs like 驅動/讀取/輸出/連接 are NOT in this set: they
# legitimately appear inside compound nouns (動力輸出系統, 連接器, 數據輸出
# 介面). The walker handles those cases via longest-intro-prefix matching
# instead — see ``check_antecedent_basis``.
#
# Ordered longest-first so 設有/包含 strip before single-char tokens.
_INTERIOR_VERB_BOUNDARIES: tuple[str, ...] = tuple(sorted(
    (
        # === Existing entries (preserve) ===
        "設有", "包含", "包括", "具有", "含有", "具備",
        "係為", "係於", "為", "是", "係",
        # Reference-form prefixes (multi-char)
        "所述", "前述", "該等", "該些",

        # === Added 2026-04-09 from smoke-test fixtures ===
        # Verb phrases (longest-first; exact tokens observed in fixtures)
        "傳送接收到", "傳送一顯示影像資", "輸出一解鎖指令至",
        "通訊連接時", "電性連接", "被帶動而向", "分別定義",
        "無法存取", "設置有", "拔除時",
        "連接一第一電子裝", "擷取一使用者",

        # 3-char verb phrases
        "電性連", "所施予", "將帶動", "被帶動",

        # 2-char unambiguous verbs (NOT noun-internal in any common
        # compound observed in 2026-04-09 fixtures)
        "對應", "相對", "相反", "響應", "解鎖",
        "讀取", "寫入", "計算", "處理", "感測",
        "偵測", "監控", "監測", "調整", "修改",
        "更新", "刪除", "增加", "減少", "選擇",
        "決定", "判別", "辨識", "驅動",

        # === Added 2026-04-09 round 2 (Bug A1 + C1 from diagnosis) ===
        # Verbs observed in real fixtures during Phase 8b round 1 smoke
        # test that contaminated reference and intro captures. Each was
        # risk-reviewed against _INTERIOR_CUT_EXCEPTIONS membership and
        # against the 10 fixtures' noun compounds:
        #   定義: not interior to any common compound — safe.
        #   啟始: not interior — safe.
        #   判斷: 判斷器 not present in fixtures — safe.
        #   持續: not interior — safe.
        #   涵蓋: not interior — safe.
        #   放大: 放大器 IS present (108P001015 ×1) — added to
        #         exceptions below.
        #   存取: not interior — safe.
        #   構成: not interior to common compounds — safe.
        #   設置: catches cases where 設置有 isn't present — safe.
        #   透過/通過/經由/藉由: preposition-verbs (already in trailing
        #         denylist) — adding to interior boundaries cuts greedy
        #         capture mid-phrase, parallel to 設有/包含 split.
        #   基於/根據/依據: connective preposition-verbs — same.
        #   染色: 染色墨水 IS present (110P000633 ×40) — added to
        #         exceptions below as a coordinated change.
        #   識別: 識別碼/識別資料/識別資訊/識別號/識別子 are already in
        #         _INTERIOR_CUT_EXCEPTIONS from Phase 8b round 1.
        #         Commit 1's prefix-aware protection lets cuts fire on
        #         the remainder past the protected compound, so a
        #         capture like 識別資料識別 preserves 識別資料 via the
        #         exception prefix and cuts at the second 識別 via the
        #         remainder search.
        #   傳送: 傳送器 is already in _INTERIOR_CUT_EXCEPTIONS — same
        #         prefix-aware protection logic applies.
        #   接收: 接收器 is already in _INTERIOR_CUT_EXCEPTIONS — same.
        "定義", "啟始", "判斷", "持續", "涵蓋", "放大", "存取",
        "構成", "設置",
        "透過", "通過", "經由", "藉由",
        "基於", "根據", "依據",
        "染色",
        "識別", "傳送", "接收",

        # === Added 2026-04-09 round 3 (round 2 spot-check residuals) ===
        # Verbs visible in round 2 residual contamination with no
        # compound-noun risk per the 10-fixture grep:
        #   到: resultative particle ("arrive at"). 到器 absent (0).
        #       到達 present (7) but always as verb compound
        #       (狀態到達限制條件, 扭力到達預定扭力時) — cutting at 到
        #       correctly extracts the head noun in those cases.
        #   形成: "to form". 形成器/形成物 absent (0).
        #   鎖合: "to lock". 鎖合器/鎖合件 absent (0).
        #   傳輸: "to transmit". 傳輸器/傳輸線/傳輸帶 absent (0).
        "到", "形成", "鎖合", "傳輸",

        # === Added 2026-04-09 round 4 (round 3 spot-check residuals) ===
        # Each verb risk-reviewed against the 10-fixture grep:
        #   連接: 連接器/連接部/第一連接部/第二連接部/第三連接部
        #         already in _INTERIOR_CUT_EXCEPTIONS (round 1; grep
        #         confirms 連接器 ×4, 連接部 ×72, 第一/第二/第三連接部
        #         ×13/13/21 in 109P001046). Round 2's prefix-aware
        #         protection covers all 連接X compounds — a captured
        #         X連接部連接 preserves X連接部 via the exception
        #         prefix and cuts at the second 連接 via the remainder
        #         search (load-bearing test: 第一連接部連接 → 第一連接部).
        #   旋轉: 旋轉編碼器 already in exceptions (round 1; grep
        #         confirms ×5 in 110P000641). Other 旋轉X compounds
        #         (旋轉軸/件/器/盤/座) absent (0) per grep — no new
        #         exceptions needed.
        #   帶動: 帶動輪 ×2 in 110P000641 per grep — added to
        #         _INTERIOR_CUT_EXCEPTIONS in round 4 block below.
        #         帶動器/帶動件 absent (0).
        #   篩選: 篩選器/篩選件/篩選網 all absent (0) per grep — no
        #         compound-noun risk, no new exceptions needed.
        "連接", "旋轉", "帶動", "篩選",

        # === Added 2026-04-09 round 5 (110P000368 manual review residuals) ===
        # 區分: "to distinguish/divide" verb in method claims. Observed
        #       in 110P000368 Claim 6 contaminating 該地域區分 → should
        #       cut at 區分 to extract 該地域. Risk-reviewed:
        #       區分器/區分件/區分碼 all absent (0) in the 10-fixture
        #       grep — no exception coordination needed.
        "區分",

        # === Added 2026-04-09 round 5 cascade ===
        # Verbs that became visible after the round 5 用/或 removal
        # from _NOUN_CHARS unblocked longer regex captures. Each
        # risk-reviewed against the 10-fixture grep:
        #   顯示: "to display" — 顯示器 ×9, 顯示裝置 ×32, 顯示單元 ×3
        #         all added to _INTERIOR_CUT_EXCEPTIONS in the round 5
        #         cascade block above. Round 2's prefix-aware protection
        #         lets a captured 顯示器顯示 preserve 顯示器 via the
        #         exception prefix and cut at the second 顯示 via the
        #         remainder search.
        #   上傳: "to upload" — 上傳器/件/介面/區/功能/模組 all 0 per
        #         grep, no exception coordination needed.
        #   瀏覽: "to browse" — 瀏覽器 ×2 added to exceptions above;
        #         瀏覽程式 ×56 already present in exceptions from
        #         the original method-claim block. Both compounds
        #         protected by prefix-aware exception logic.
        "顯示", "上傳", "瀏覽",

        # === Added 2026-04-09 round 5 cascade tail ===
        # Surfaced by 110P000368 production smoke test after the
        # initial cascade landed: contamination patterns 瀏覽程式產生
        # (intro side) and 地域內各地 (reference side) needed dedicated
        # cuts to bring the fixture's count below the round 4 baseline.
        #   產生: "to generate/produce" — 110P000368 c1 captures
        #         一瀏覽程式產生的 as the noun span; cut at 產生 leaves
        #         瀏覽程式 (in exceptions). Risk-reviewed: 產生器 ×40
        #         in 110P000641 (波產生器), all naturally protected by
        #         the position-2 check (產生 at position 1 of 波產生器
        #         fails idx > 1). 波產生器 also added to exceptions
        #         above as documented insurance.
        #   各地: "various places" — 110P000368 c6/c10 reference
        #         該地域內各地 normalizes to 地域 only after cutting at
        #         各地. Grep: 各地 ×3 (all in 110P000368, all
        #         contamination patterns). 各地區/各地方 ×0 — safe.
        "產生", "各地",

        # === Added 2026-04-10 F3 ===
        # 依序: adverb ("in order") in V依序V patterns. Needed as
        #       interior cut (not just trailing strip) because the
        #       greedy {2,12} capture extends past 依序 into the
        #       following clause: 第二方向依序對多個所述焊 → should cut
        #       at 依序 to extract 第二方向. Risk: 依序器/依序件 all 0 in
        #       10-fixture corpus, no exception coordination needed.
        "依序",

        # === Added 2026-04-10 F5 ===
        # 相互: adverb "mutually" — 上端邊緣相互銜接 should cut at 相互
        #       to extract 上端邊緣. 相互作用 has 相互 at START, never
        #       interior. Grep: X相互 ×0 as compound noun — safe.
        # 朝向: verb/preposition "face toward" — 底部朝向下方 should cut
        #       at 朝向 to extract 底部. 朝向 as standalone noun
        #       ("orientation") is the head noun, never mid-compound.
        #       Grep: X朝向 as compound noun ×0 — safe.
        "相互", "朝向",

        # NOT added (interior to legitimate noun compounds):
        # 編碼 (編碼器), 識別 (識別碼/識別資料),
        # 通訊 (通訊模組), 傳動 (傳動件),
        # 接收 (接收器), 輸出 (輸出裝置), 輸入 (輸入裝置),
        # 儲存 (儲存器), 認證 (認證單元), 銜接 (第一銜接部)
        # These are caught by their LONGER multi-char forms above
        # (傳送接收到, 連接一第一電子裝, etc.) which are unambiguous.
    ),
    key=len,
    reverse=True,
))


# Exception set: compound nouns containing interior-verb tokens that
# should NOT be cut. When the captured text (or any prefix of it) is
# in this set, clean_noun_phrase_tw skips the interior-cut pass entirely
# and proceeds straight to the trailing-strip phase.
#
# Maintenance philosophy: false negatives (missing exception → walker
# doesn't find an antecedent) are the cheap failure mode. The risk
# of having too few entries is verb-contamination, which is the
# expensive failure mode (visible garbage findings).
#
# Seeded from compound nouns observed in 2026-04-09 fixtures.
_INTERIOR_CUT_EXCEPTIONS: frozenset[str] = frozenset({
    # Connection / connector compounds
    "連接器", "連接部", "連接埠", "連接點", "連接線",
    "第一連接部", "第二連接部", "第三連接部",
    "電連接器", "電性連接部",

    # Encoder / decoder
    "編碼器", "解碼器", "旋轉編碼器", "光學編碼器",

    # Identification compounds
    "識別碼", "識別資料", "識別資訊", "識別號", "識別子",

    # Communication module compounds
    "通訊模組", "通訊埠", "通訊單元", "通訊介面",
    "行動通訊模組", "無線通訊模組", "有線通訊模組",
    "第一通訊模組", "第二通訊模組",
    "第一無線通訊模組", "第二無線通訊模組", "第三無線通訊模組",

    # Transmission compounds
    "傳送器", "接收器", "發射器", "發送器", "收發器",

    # Authentication compounds
    "認證單元", "認證模組", "認證裝置", "認證功能單元",

    # Engagement / connection part compounds (from screenshot 1)
    "銜接部", "第一銜接部", "第二銜接部", "第三銜接部",
    "扣接部", "第一扣接部", "第二扣接部",

    # Wheel / structural compounds (from screenshot 2)
    "後輪", "前輪", "傳動輪", "從動輪", "主動輪",
    "曲柄", "踏板", "弧面", "第一弧面", "第二弧面",
    "輪軸", "傳動件",

    # Misc structural compounds observed in TW patent claims
    "上端邊緣", "下端邊緣", "外側邊緣", "內側邊緣",
    "容納部", "容置部", "容置杯體", "杯體",
    "環形壓接部", "壓接部", "壓接環",
    "開口部", "封閉部",
    "頂壁", "底壁", "側壁", "頂部", "底部", "側部",

    # Method-claim compounds
    "數位內容", "適地性數位內容", "主題標籤",
    "瀏覽程式", "伺服器", "使用者介面",

    # === Added 2026-04-09 round 2 (coordinated with new boundary verbs) ===
    # When 放大 / 染色 are added as interior-cut verbs, these compound
    # nouns must be protected first so the cut doesn't damage them.
    # 放大器: 108P001015 fixture has 1 occurrence.
    # 染色墨水: 110P000633 fixture has 40 occurrences.
    "放大器",
    "染色墨水",

    # === Added 2026-04-09 round 4 (coordinated with new boundary verbs) ===
    # When 帶動 is added as an interior-cut verb, 帶動輪 must be
    # protected first. Grep confirmed 帶動輪 ×2 in 110P000641.
    # Other 帶動X compounds (帶動器, 帶動件) absent (0) per grep —
    # not added speculatively.
    "帶動輪",

    # === Added 2026-04-09 round 5 cascade ===
    # Coordinated with the cascade-added interior boundary verbs
    # 顯示/上傳/瀏覽. Each compound was risk-grepped against the
    # 10-fixture corpus before adding the bare verb to the boundaries:
    #   顯示器 ×9 in 4 fixtures
    #   顯示裝置 ×32 in 2 fixtures
    #   顯示單元 ×3 in 1 fixture
    #   瀏覽器 ×2 in 1 fixture (瀏覽程式 already present above)
    # 上傳器/件/介面/區/功能/模組 all 0 per grep — no exceptions
    # needed for 上傳.
    "顯示器", "顯示裝置", "顯示單元",
    "瀏覽器",

    # === Added 2026-04-09 round 5 cascade tail (產生 boundary) ===
    # Coordinated with the addition of 產生 to interior verbs.
    # 波產生器 ×40 across the corpus (110P000641 harmonic-reducer
    # patent: 波產生器, 一波產生器, 所述波產生器, 成一波產生器, etc.) —
    # the only 產生器 compound observed. Bare 波產生器 is naturally
    # protected by the position-2 check (產生 sits at position 1 of
    # 波產生器, fails the > 1 check), but adding to the exception
    # set is documented insurance for any longer captured spans.
    "波產生器",

    # === Added F4 session: 連接面 (connecting surface) ===
    # 110P000158 has 第一連接面 / 第二連接面 ×4. Without protection,
    # interior verb 連接 truncates 第一連接面 → 第一 (bare ordinal).
    # Root cause of walker_bug.regex_noun_class_narrow — the label
    # name was misleading; the actual bug is interior-verb overcutting.
    "連接面", "第一連接面", "第二連接面",
})


def clean_noun_phrase_tw(text: str) -> str:
    """Strip trailing verbs and conjunction fragments from a TW reference term.

    Two-phase cleanup:

    1. Interior-verb truncation — find the first occurrence of any
       ``_INTERIOR_VERB_BOUNDARIES`` token and cut everything from that
       position onward. Recovers ``底座`` from greedy regex captures
       like ``底座設有一孔洞``.

       Skipped if the captured text (or any prefix of it) is in
       ``_INTERIOR_CUT_EXCEPTIONS`` — that means the captured text is a
       known compound noun that contains an interior-verb token as
       part of its identity, not as a clause boundary.

    2. Trailing-verb stripping — iteratively remove the longest matching
       suffix in ``_TRAILING_VERB_DENYLIST``. Handles parser-bug
       captures like ``諧波減速模組還包`` (strips ``包`` → ``諧波減速模組還``
       → strips ``還`` → ``諧波減速模組``).

    Note: the walker MAY leave a leading char of the next clause when
    that char does not match any denylist entry (e.g., ``遊戲控制器通過第``
    strips ``過`` → ``遊戲控制器通第`` → strips ``通`` (single-char
    trailing token) → ``遊戲控制器第``, leaving a stray ``第`` because ``第``
    is not a verb fragment). This is acceptable for the walker: leftover
    fragments produce mismatches at comparison time and are surfaced via
    the did-you-mean hint if similarity is high enough.
    """
    if not text:
        return text

    # Phase 1: interior-verb truncation, with prefix-aware exception
    # protection.
    #
    # If the captured text starts with a protected compound noun (e.g.
    # 容置杯體 in 容置杯體設置有多數孔隙), we PRESERVE the compound but
    # still cut at any verb that appears AFTER the compound. The
    # interior-cut search runs on text[protected_prefix_len:] only, and
    # any cut position is offset back to the original string by adding
    # protected_prefix_len. When the entire captured text is itself a
    # protected compound, protected_prefix_len == len(text) and the
    # remainder is empty, so no cut fires.
    def _longest_protected_prefix(s: str) -> int:
        """Return the length of the longest prefix of ``s`` that is in
        ``_INTERIOR_CUT_EXCEPTIONS``, or 0 if no prefix matches.

        Walks from longest to shortest so the first match returned is
        the longest one. The exact-match case (entire ``s`` is in
        exceptions) is handled by the loop starting at ``len(s)``.
        """
        for i in range(len(s), 1, -1):
            if s[:i] in _INTERIOR_CUT_EXCEPTIONS:
                return i
        return 0

    protected_prefix_len = _longest_protected_prefix(text)
    search_text = text[protected_prefix_len:]
    search_offset = protected_prefix_len

    earliest_idx: int | None = None
    for verb in _INTERIOR_VERB_BOUNDARIES:
        idx = search_text.find(verb)
        # Require ≥1 char before the verb in the search remainder (so
        # the verb isn't at position 0 of the remainder), AND ≥2 chars
        # total before the verb in the absolute original text.
        if idx >= 0 and (idx + search_offset) > 1:
            absolute_idx = idx + search_offset
            if earliest_idx is None or absolute_idx < earliest_idx:
                earliest_idx = absolute_idx

    current = text[:earliest_idx] if earliest_idx is not None else text

    # Phase 2: trailing-verb stripping (iterative).
    # Safety bound to prevent pathological iteration.
    for _ in range(16):
        stripped = False
        for verb in _TRAILING_VERB_DENYLIST:
            if not current.endswith(verb):
                continue
            # General floor: never strip to empty.
            if len(current) <= len(verb):
                continue
            # Noun-like single-char suffixes (所) require residual ≥ 3 to
            # preserve 2- and 3-char compound nouns that legitimately end
            # in the suffix: 場所 (2), 研究所 (3), 事務所 (3), 避難所 (3).
            # 前 is NOT in this set — see _NOUNLIKE_SINGLE_CHAR_SUFFIXES
            # for the prefix-vs-suffix rationale. Verb-like single-char
            # fragments (包/通/經/藉/還/並/且/其/另/係/為/是) keep the
            # looser residual ≥ 1 floor — they are statute boilerplate
            # or parser cuts, not noun morphemes, so 齒輪還 → 齒輪 must
            # still strip. Multi-char tokens (包含, 包括) don't need the
            # guard because their over-strip residuals are longer by
            # construction.
            #
            # Relaxed-guard subset (上, 內) uses ≥ 2 instead of ≥ 3 so
            # 3-char positional fragments (地域內 → 地域, 範圍內 → 範圍,
            # 基板上 → 基板) strip while 2-char productive compounds
            # (their corpus count is 0) and position-0 compounds
            # (內側/上方, protected by the endswith position check) are
            # unaffected. See _NOUNLIKE_RELAXED_SUFFIXES for rationale.
            if verb in _NOUNLIKE_SINGLE_CHAR_SUFFIXES:
                min_residual = 2 if verb in _NOUNLIKE_RELAXED_SUFFIXES else 3
                if (len(current) - len(verb)) < min_residual:
                    continue
            current = current[: -len(verb)]
            stripped = True
            break
        if not stripped:
            break
    return current


def strip_leading_quantifier(text: str) -> str:
    """Strip one matching leading quantifier (ADR-095 Rule 2).

    Applied symmetrically to both reference terms and candidate intros
    so 複數外齒狀結構 ↔ 該外齒狀結構 both normalize to 外齒狀結構. Strip
    is NOT iterative — applied once per term — so compound terms where
    a quantifier-like morpheme is part of the head noun (e.g., 一次性
    starting with 一) are not over-stripped.
    """
    if not text:
        return text
    for q in _LEADING_QUANTIFIER_DENYLIST:
        if text.startswith(q) and len(text) > len(q):
            return text[len(q):]
    return text


def strip_reference_form_prefix(text: str) -> str:
    """Strip one matching reference-form prefix (該/所述/前述/該等/該些).

    Applied only to reference terms (the walker's flagged side). Intros
    do not carry reference-form prefixes, so
    ``normalize_candidate_intro`` skips this step.
    """
    if not text:
        return text
    for prefix in _REFERENCE_FORM_PREFIXES:
        if text.startswith(prefix) and len(text) > len(prefix):
            return text[len(prefix):]
    return text


# Leading qualifier strip — handles definite-article-plus-qualifier
# patterns where the qualifier is a positional or relational modifier
# that doesn't introduce a new claim element.
#
# Legal basis: US Federal Circuit case law on "the corresponding X" and
# "the previous X" treats these as scope-clarifying qualifiers, not new
# elements requiring their own antecedent. TIPO general principles in
# 專利侵權判斷要點 are consistent with this reading. JP-origin TW
# translations frequently use 對應/前 patterns because Japanese claim
# style standardizes them (対応する, 前記).
#
# The walker strips these qualifiers as part of normalization so the
# bare noun matches the ancestor chain. Strict mode (per
# strict_qualifier_matching config flag) disables this strip and treats
# qualified references as distinct elements requiring their own
# antecedent — for firms with stricter house rules.

# Relational qualifiers: strip unconditionally when they appear at
# the start of a normalized term. Each can have an optional 地 or 的
# adverbial suffix.
_LEADING_RELATIONAL_QUALIFIERS: tuple[str, ...] = (
    "對應地", "對應的", "對應",
    "相應地", "相應的", "相應",
    "相對地", "相對的", "相對",
    "相關地", "相關的", "相關",
)

# Position qualifiers: strip ONLY when followed by a quantifier
# (一/二/.../複數/多個/etc.). 前/後 form compound nouns when followed
# by other characters (前端, 後輪), so the quantifier lookahead is
# what distinguishes qualifier-use (前一X) from compound-use (前端).
_LEADING_POSITION_QUALIFIERS: tuple[str, ...] = ("前", "後")
_QUANTIFIER_AFTER_POSITION: tuple[str, ...] = (
    # Round 5 addition: 一或多個 must come BEFORE bare 一 so the
    # multi-char form is matched as a unit (前一或多個X strips the
    # qualifier+quantifier and leaves X). The strip iterates this tuple
    # in order and uses .startswith(), so longest-first matters.
    "一或多個",
    "一", "二", "三", "四", "五", "六", "七", "八", "九", "十",
    "1", "2", "3", "4", "5", "6", "7", "8", "9",
    "複數", "多個", "數個", "至少",
)


def strip_leading_qualifier(
    text: str,
    *,
    strict_qualifier_matching: bool = False,
) -> str:
    """Strip leading qualifier modifiers from a normalized reference term.

    Handles two patterns per ADR-095 addendum (2026-04-09):

    1. Relational qualifiers: 對應X, 相應X, 相對X, 相關X (with optional
       adverbial suffix 地/的). Stripped unconditionally — these never
       form compound nouns with the following character in patent claim
       text.

    2. Position qualifiers: 前X, 後X — but ONLY when X starts with a
       quantifier (一/二/.../複數/多個). 前一X = "previous one X" is
       a qualifier; 前端 = "front end" is a compound noun. The
       quantifier lookahead distinguishes the two cases.

    When strict_qualifier_matching is True the strip is disabled entirely
    and qualified references are treated as distinct elements. Default
    is False (lenient). Per ADR-095 the strict mode exists as an escape
    hatch for firms with stricter house rules; the default matches US
    Federal Circuit precedent and TIPO general principles.
    """
    if strict_qualifier_matching or not text:
        return text

    # Try relational qualifiers first (longest-first via the ordering
    # in _LEADING_RELATIONAL_QUALIFIERS).
    for q in _LEADING_RELATIONAL_QUALIFIERS:
        if text.startswith(q) and len(text) > len(q):
            return text[len(q):]

    # Try position qualifiers with quantifier lookahead.
    for q in _LEADING_POSITION_QUALIFIERS:
        if text.startswith(q) and len(text) > len(q):
            remainder = text[len(q):]
            for quant in _QUANTIFIER_AFTER_POSITION:
                if remainder.startswith(quant):
                    return remainder

    return text


def normalize_reference_term(
    text: str,
    *,
    strict_qualifier_matching: bool = False,
) -> str:
    """Normalize a flagged reference term for antecedent matching.

    Composes:
        strip_reference_form_prefix    (該/所述/前述/該等/該些)
        → strip_leading_qualifier      (對應/相應/前+quantifier — NEW)
        → clean_noun_phrase_tw         (interior cut + trailing strip)
        → strip_leading_quantifier     (一/一個/複數/...)
    """
    t = strip_reference_form_prefix(text)
    t = strip_leading_qualifier(t, strict_qualifier_matching=strict_qualifier_matching)
    t = clean_noun_phrase_tw(t)
    t = strip_leading_quantifier(t)
    return t


def normalize_candidate_intro(
    text: str,
    *,
    strict_qualifier_matching: bool = False,
) -> str:
    """Normalize an introduction candidate for antecedent matching.

    Composes:
        strip_leading_qualifier        (NEW — for symmetry with refs)
        → clean_noun_phrase_tw
        → strip_leading_quantifier
        → strip_reference_form_prefix  (round 3 fix — symmetry with
          ``normalize_reference_term``)

    The trailing ``strip_reference_form_prefix`` is load-bearing for
    intro spans like ``一個所述第一弧面`` (110P000641 c15/c19): the
    ``_INTRO_PATTERN`` greedily matches ``一個`` as the quantifier and
    captures ``所述第一弧面`` as the bare noun group. Without this
    strip, the intro lands in ``intros_by_term`` keyed as
    ``所述第一弧面`` while the corresponding reference normalizes to
    ``第一弧面``, the exact-match path fails, and did-you-mean surfaces
    a structurally meaningless ``所述第一弧面 → 所述第一弧面``
    suggestion. Stripping the reference-form prefix here restores the
    invariant that the intro and reference normalize to the same
    string when they refer to the same entity.
    """
    t = strip_leading_qualifier(text, strict_qualifier_matching=strict_qualifier_matching)
    t = clean_noun_phrase_tw(t)
    t = strip_leading_quantifier(t)
    t = strip_reference_form_prefix(t)
    return t


def detect_plural_reference(text: str) -> bool:
    """Return True iff ``text`` starts with a plural reference-form prefix.

    Used by the strict_plural_reference_matching escape hatch to flag
    plural reference forms even when the underlying antecedent match
    is number-neutral. Default walker behaviour (strict=False) does
    NOT flag these; this helper exists so the strict mode path can
    detect and warn. See ADR-095 for the decision rationale.
    """
    return any(text.startswith(p) for p in _PLURAL_REFERENCE_PREFIXES)


def get_ancestor_chain_tw(claim: Claim, all_claims: list[Claim]) -> list[Claim]:
    """Return [claim, ...ancestors] walking the full multi-parent BFS.

    Mirrors ``claims.get_ancestor_chain`` (US walker) — multi-dependent
    claims (e.g. ``如請求項1或3所述``) collect introductions from every
    ancestor path. Cycle protection via the ``visited`` set means a
    self-referencing or circular dependency cannot loop forever.

    Per ADR-092, the walker uses the FULL ancestor chain (not just the
    immediate parent) to resolve introductions, while preamble checks use
    the immediate parent. This is intentional: 引用記載型式 cross-category
    dependents legitimately reference components introduced in any
    ancestor along the chain.
    """
    claims_by_id = {c.id: c for c in all_claims}
    chain: list[Claim] = [claim]
    visited: set[int] = {claim.id}
    queue: list[int] = list(claim.dependencies)
    while queue:
        parent_id = queue.pop(0)
        if parent_id in visited:
            continue
        visited.add(parent_id)
        parent = claims_by_id.get(parent_id)
        if parent is None:
            continue
        chain.append(parent)
        queue.extend(parent.dependencies)
    return chain


# Characters that indicate word-internal 一 (not a separate intro site).
# Corpus-verified list: 第 (ordinal), 另/任/某/唯/同/單/統 (compound
# quantifier prefixes where 一 is bound to the preceding morpheme).
_WORD_INTERNAL_YI_PREDECESSORS = frozenset("第另任某唯同單統")

# Regex for capturing the noun after a split 一 position, using the same
# character class as _NOUN_CHARS but as a standalone pattern.
_SPLIT_YI_NOUN_RE = re.compile(r"一(" + _NOUN_CHARS + r")")


def _postprocess_intro_capture(
    bare_noun: str,
    match: re.Match,  # type: ignore[type-arg]
    claim_text: str,
) -> list[str]:
    """Post-process a greedy _INTRO_PATTERN capture to repair over-captures.

    Returns a list of candidate noun strings, each to be passed through
    ``clean_noun_phrase_tw`` + ``normalize_candidate_intro`` via the
    existing pipeline.

    Three repair rules, applied in order:

    Rule 1 — Reference-marker check:
      If the bare noun starts with a reference-form prefix, the entire
      capture is a false intro.  Discard but re-scan the full matched
      span for embedded 一 positions (Rule 3).
      If the bare noun contains a reference-form prefix at position > 0,
      truncate at that position.

    Rule 2 — Embedded 一 splitting:
      After Rule 1's truncation (if any), check the resulting candidate
      for non-word-internal 一 at positions > 0 and split.

    Rule 3 — Re-scan discarded spans:
      If Rule 1 discarded the entire noun, re-scan the full matched span
      for 一 positions and extract nouns after them.
    """
    # Rule 1a: starts with ref prefix → try re-scan first; if no
    # recovery sites found, strip the prefix and return the remainder
    # (preserves the existing normalize_candidate_intro strip for cases
    # like 一個所述第一弧面 where the 所述 is a greedy-capture artifact
    # and the real intro is 第一弧面).
    for prefix in _REFERENCE_FORM_PREFIXES:
        if bare_noun.startswith(prefix):
            # Re-scan the full matched span for 一 sites
            recovered = _rescan_for_yi(
                match.group(0), match.start(), claim_text,
            )
            if recovered:
                return recovered
            # No 一 recovery sites — strip the ref prefix and return
            # the remainder for normal normalization.
            remainder = bare_noun[len(prefix):]
            return [remainder] if remainder else []

    # Rule 1b: contains ref prefix at position > 0 → truncate
    for prefix in _REFERENCE_FORM_PREFIXES:
        idx = bare_noun.find(prefix)
        if idx > 0:
            bare_noun = bare_noun[:idx]
            break

    # Rule 2: embedded 一 splitting
    candidates: list[str] = []
    yi_positions = [i for i, ch in enumerate(bare_noun) if ch == "一" and i > 0]

    if not yi_positions:
        return [bare_noun]

    # Find the first non-word-internal 一
    split_pos: int | None = None
    for pos in yi_positions:
        preceding_char = bare_noun[pos - 1]
        if preceding_char not in _WORD_INTERNAL_YI_PREDECESSORS:
            split_pos = pos
            break

    if split_pos is None:
        return [bare_noun]

    # The part before the split 一 is one candidate
    leading_part = bare_noun[:split_pos]
    if leading_part:
        candidates.append(leading_part)

    # The noun after 一 — re-extract from claim_text at the absolute
    # position to get the full noun span (the bare_noun may have been
    # truncated by the {2,12} upper bound).
    abs_start = match.start() + (len(match.group(0)) - len(match.group(1))) + split_pos
    remaining_text = claim_text[abs_start:]
    yi_match = _SPLIT_YI_NOUN_RE.match(remaining_text)
    if yi_match:
        candidates.append(yi_match.group(1))
    elif split_pos + 1 < len(bare_noun):
        # Fallback: use what's left in bare_noun after 一
        candidates.append(bare_noun[split_pos + 1:])

    return candidates


def _rescan_for_yi(
    full_span: str,
    span_start: int,
    claim_text: str,
) -> list[str]:
    """Re-scan a full matched span for 一 intro sites.

    Used when Rule 1a discards the entire noun because it starts with
    a reference-form prefix. Recovers intro sites like 旋轉編碼器 from
    spans like ``一個所述感測器為一旋轉編碼器``.

    Skips any extracted noun that starts with a reference-form prefix
    (catches the quantifier-prefix ``一`` at position 0, whose noun
    ``個所述...`` inherits the ref prefix that triggered the discard).
    """
    candidates: list[str] = []
    for i, ch in enumerate(full_span):
        if ch != "一":
            continue
        # Skip the first 一 at position 0 — it is always the quantifier
        # prefix (一/一個/一種/...) that triggered the original match.
        if i == 0:
            continue
        # Skip word-internal 一 (preceded by 第/另/etc.)
        if full_span[i - 1] in _WORD_INTERNAL_YI_PREDECESSORS:
            continue
        # Extract noun after this 一 from the claim text
        abs_pos = span_start + i
        remaining = claim_text[abs_pos:]
        yi_match = _SPLIT_YI_NOUN_RE.match(remaining)
        if yi_match:
            candidates.append(yi_match.group(1))
    return candidates


# --- Supplementary bare-noun intro patterns (F9/F8/F7/F6/F5) ---
# These capture intro sites that _INTRO_PATTERN misses because the noun
# lacks a 一/quantifier prefix. Each pattern is narrowly scoped to
# minimize false positives.

_INSTRUMENTAL_PATTERN = re.compile(
    r'透過([\u4e00-\u9fff]{2,}(?:\([A-Za-z0-9]+\))?)(?:連接|連結)',
)

_VP_MODIFIER_PATTERN = re.compile(
    r'相配合的([\u4e00-\u9fff]{2,}(?:\([A-Za-z0-9]+\))?)',
)

# CJK char class excluding 的 (U+7684) — prevents captures spanning through 的
_CJK_NO_DE = r'[\u4e00-\u7683\u7685-\u9fff]'

_PARTICIPIAL_YI_DE_PATTERN = re.compile(
    r'一[\u4e00-\u9fff]+?的(' + _CJK_NO_DE + r'{2,}(?:\([A-Za-z0-9]+\))?)'
)

_POST_DE_ORDINAL_PATTERN = re.compile(
    r'的(第[一二三四五六七八九十\d]+' + _CJK_NO_DE + r'+(?:\([A-Za-z0-9]+\))?)'
)

_DE_NOUN_RE = re.compile(
    r'的(' + _CJK_NO_DE + r'{2,}(?:\([A-Za-z0-9]+\))?)'
)

_BARE_AFTER_VERB_PATTERN = re.compile(
    r'(?:'
    # Structural
    r'具有|包含|包括|含有|設有'
    r'|'
    # Installation
    r'設置|配置|安裝|裝設'
    r'|'
    # Formation
    r'形成|構成'
    r'|'
    # Provision/connection
    r'提供|連接|連結'
    r')'
    r'(第[一二三四五六七八九十\d]+' + _CJK_NO_DE + r'+(?:\([A-Za-z0-9]+\))?'
    r'|' + _CJK_NO_DE + r'+\([A-Za-z0-9]+\))'
    r'(?![的之])'
)

_CLAUSE_BOUNDARY_RE = re.compile(r'[；，、。]')

_REF_PREFIX_SET = ('所述', '該', '前述')

# F5a: Ref-prefix possessive (所述|該|前述)X的Y
# Split into two variants to prevent verb-contaminated X:
# - With paren-numeral on X: no CJK length limit (numeral anchors boundary)
# - Without paren-numeral: X limited to 2-4 CJK (rejects 框架相配合 etc.)
_REF_POSSESSIVE_WITH_NUM = re.compile(
    r'(?:所述|該|前述)'
    r'[\u4e00-\u7683\u7685-\u9fff]{2,}\([A-Za-z0-9]+\)'
    r'的'
    r'([\u4e00-\u7683\u7685-\u9fff]{2,}(?:\([A-Za-z0-9]+\))?)'
)
_REF_POSSESSIVE_NO_NUM = re.compile(
    r'(?:所述|該|前述)'
    r'[\u4e00-\u7683\u7685-\u9fff]{2,4}'
    r'的'
    r'([\u4e00-\u7683\u7685-\u9fff]{2,}(?:\([A-Za-z0-9]+\))?)'
)

# F5b: 一X(N)的Y — intro with paren-numeral possessive
_YI_NOUN_PAREN_DE_PATTERN = re.compile(
    r'一[\u4e00-\u7683\u7685-\u9fff]{2,}\([A-Za-z0-9]+\)'
    r'的'
    r'([\u4e00-\u7683\u7685-\u9fff]{2,}(?:\([A-Za-z0-9]+\))?)'
)

_POSSESSIVE_VERB_DENYLIST = {
    '包括', '包含', '具有', '是', '為', '大於', '小於', '等於',
    '設置', '形成', '連接', '連結',
}


def _extract_supplementary_intros(text: str) -> list[tuple[str, str]]:
    """Extract bare-noun introductions from supplementary patterns.

    Returns (original_span, normalized_term) pairs, same contract as
    extract_introductions_tw's main loop.
    """
    results: list[tuple[str, str]] = []

    # F9: 透過Y連接/連結 — instrumental intro
    for m in _INSTRUMENTAL_PATTERN.finditer(text):
        noun = m.group(1)
        original = m.group(0)  # full matched span
        # Normalize: strip paren-numeral for the normalized form
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', noun)
        results.append((original, normalized))

    # F8: 相配合的Y — VP modifier intro
    # Scoped: Y must start with ordinal 第 OR contain paren-numeral
    for m in _VP_MODIFIER_PATTERN.finditer(text):
        noun = m.group(1)
        # Strip paren-numeral for normalized form
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', noun)
        # Scoping: Y must start with 第 (ordinal) OR original had paren-numeral
        has_numeral = '(' in noun
        has_ordinal = normalized.startswith('第')
        if not (has_numeral or has_ordinal):
            continue
        # Floor: normalized Y must be ≥3 CJK chars (rejects 圓形, 圓柱 shape descriptors)
        cjk_len = sum(1 for c in normalized if '\u4e00' <= c <= '\u9fff')
        if cjk_len < 3:
            continue
        results.append((m.group(0), normalized))

    # F7a: 形成於X的Y — locative intro (last 的NOUN before clause boundary)
    for pos in (i for i, ch in enumerate(text) if text[i:i + 3] == '形成於'):
        clause_start = pos + 3
        boundary = _CLAUSE_BOUNDARY_RE.search(text, clause_start)
        clause_end = boundary.start() if boundary else len(text)
        clause = text[clause_start:clause_end]
        # Find ALL 的NOUN in the clause, take the last
        last_noun = None
        last_original = None
        for dm in _DE_NOUN_RE.finditer(clause):
            last_noun = dm.group(1)
            last_original = text[clause_start + dm.start():clause_start + dm.end()]
        if last_noun is None:
            continue
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', last_noun)
        # Scoping: ≥3 CJK chars AND no ref prefix
        cjk_len = sum(1 for c in normalized if '\u4e00' <= c <= '\u9fff')
        if cjk_len < 3:
            continue
        if any(normalized.startswith(p) for p in _REF_PREFIX_SET):
            continue
        results.append((last_original, normalized))

    # F7b: 一V的Y — participial intro
    for m in _PARTICIPIAL_YI_DE_PATTERN.finditer(text):
        noun = m.group(1)
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', noun)
        has_numeral = '(' in noun
        has_ordinal = normalized.startswith('第')
        cjk_len = sum(1 for c in normalized if '\u4e00' <= c <= '\u9fff')
        if not (has_ordinal or has_numeral or cjk_len >= 3):
            continue
        results.append((m.group(0), normalized))

    # F7c: 的第Y — post-的 ordinal noun
    for m in _POST_DE_ORDINAL_PATTERN.finditer(text):
        noun = m.group(1)
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', noun)
        results.append((m.group(0), normalized))

    # F6: 具有/設置/形成 + Y — bare-after-verb intro
    for m in _BARE_AFTER_VERB_PATTERN.finditer(text):
        noun = m.group(1)
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', noun)
        results.append((m.group(0), normalized))

    # F5a: Ref-prefix possessive 所述X的Y (two variants)
    for pattern in (_REF_POSSESSIVE_WITH_NUM, _REF_POSSESSIVE_NO_NUM):
        for m in pattern.finditer(text):
            noun = m.group(1)
            normalized = re.sub(r'\([A-Za-z0-9]+\)', '', noun)
            cjk_len = sum(1 for c in normalized if '\u4e00' <= c <= '\u9fff')
            if cjk_len < 2:
                continue
            if normalized.startswith(('所述', '該', '前述')):
                continue
            # Check follower — reject if followed by content verb
            end_pos = m.end()
            follower = text[end_pos:end_pos + 2]
            if follower in _POSSESSIVE_VERB_DENYLIST:
                continue
            results.append((m.group(0), normalized))

    # F5b: 一X(N)的Y — intro with paren-numeral possessive
    for m in _YI_NOUN_PAREN_DE_PATTERN.finditer(text):
        noun = m.group(1)
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', noun)
        cjk_len = sum(1 for c in normalized if '\u4e00' <= c <= '\u9fff')
        if cjk_len < 2:
            continue
        if normalized.startswith(('所述', '該', '前述')):
            continue
        end_pos = m.end()
        follower = text[end_pos:end_pos + 2]
        if follower in _POSSESSIVE_VERB_DENYLIST:
            continue
        results.append((m.group(0), normalized))

    # Uniform trailing-verb cleanup for all supplementary captures
    cleaned: list[tuple[str, str]] = []
    for orig, norm in results:
        cleaned_norm = clean_noun_phrase_tw(norm)
        if cleaned_norm and len(cleaned_norm) >= 2:
            cleaned.append((orig, cleaned_norm))
    return cleaned


def extract_introductions_tw(
    claim: Claim,
    *,
    strict_qualifier_matching: bool = False,
) -> list[tuple[str, str]]:
    """Extract introductions from a TW claim as (original, normalized) pairs.

    ``original`` is the FULL intro span captured by ``_INTRO_PATTERN``,
    quantifier prefix included (e.g. ``一第一電極`` → original=``一第一電極``,
    ``複數齒輪`` → original=``複數齒輪``). Preserving the quantifier lets
    the walker's strict-plural escape hatch detect whether the intro was
    plural by inspecting the leading characters via
    ``full_ref_starts_with_plural``.

    ``normalized`` is the result of running ``normalize_candidate_intro``
    on the bare noun (group 1), which strips quantifiers and trailing
    verbs so it can be compared symmetrically against normalized
    reference terms.

    Post-processing (F3) repairs three classes of greedy over-capture:
      1. Reference-marker truncation/discard + re-scan
      2. Embedded 一 splitting at non-word-internal positions
      3. Paren-numeral variant registration
    """
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for m in _INTRO_PATTERN.finditer(claim.text):
        original = m.group(0)
        bare_noun = m.group(1)

        # F3 post-processing: may produce multiple candidates from one match
        candidates = _postprocess_intro_capture(bare_noun, m, claim.text)

        for candidate in candidates:
            normalized = normalize_candidate_intro(
                candidate,
                strict_qualifier_matching=strict_qualifier_matching,
            )
            if not normalized:
                continue
            if normalized not in seen:
                seen.add(normalized)
                pairs.append((original, normalized))

    # --- Supplementary patterns (bare-noun intros without 一 prefix) ---
    supplementary = _extract_supplementary_intros(claim.text)
    for orig, norm in supplementary:
        if norm not in seen:
            seen.add(norm)
            pairs.append((orig, norm))

    return pairs


def check_antecedent_basis(
    doc: TwPatentDocument,
    *,
    strict_plural_reference_matching: bool = False,
    strict_qualifier_matching: bool = False,
) -> list[dict]:
    """TW antecedent-basis BFS walker (Phase 8b, ADR-092 + ADR-095).

    Replaces the legacy regex-based check with a per-occurrence walker
    that mirrors the US walker's six-field finding shape:

        {
            "claim_id":       int,
            "term":           str,   # normalized noun (matching key)
            "reference_form": str,   # 該/所述/前述 + original noun
            "claim_text":     str,
            "suggested_match": dict | None,  # filled by Commit 5
            "cross_ref":      None,
        }

    Resolution algorithm:
      1. For each claim C, walk the full ancestor BFS chain
         (``get_ancestor_chain_tw``) per ADR-092.
      2. Collect introductions from every ancestor as a dict
         ``intros_by_term`` keyed on the normalized noun, with the
         shallowest (first-seen) ancestor claim id as the value.
      3. For each definite reference (該/所述/前述 + noun) in C, normalize
         via ``normalize_reference_term`` and look up the normalized term
         in ``intros_by_term``. If the term is absent, emit a finding.
      4. The strict_plural_reference_matching escape hatch (default
         False) additionally flags references that explicitly mark plural
         antecedence (該等/該些/...) when the matched intro was singular.

    Findings are deduped by ``(claim_id, term, reference_form)`` and
    sorted by ``(claim_id, term, reference_form)``.

    The walker is the data source: ``pipeline._run_tw_pipeline``
    populates ``AnalysisResult.antecedent_basis_issues`` with the return
    value, then ``to_report_data`` converts it into a CheckItem in the
    same way as US.
    """
    claims = doc.claims
    if not claims:
        return []

    issues: list[dict] = []

    for claim in claims:
        chain = get_ancestor_chain_tw(claim, claims)

        # Map normalized intro term → (shallowest ancestor id, BFS depth).
        # Iteration order (chain[0] = current claim @ depth 0, chain[1] =
        # nearest parent @ depth 1, ...) means setdefault preserves the
        # shallowest occurrence. Depth is later used by the did-you-mean
        # tiebreaker so when two candidates score identically the nearer
        # ancestor wins.
        intros_by_term: dict[str, tuple[int, int]] = {}
        for depth, ancestor in enumerate(chain):
            for _, normalized in extract_introductions_tw(
                ancestor,
                strict_qualifier_matching=strict_qualifier_matching,
            ):
                intros_by_term.setdefault(normalized, (ancestor.id, depth))

        # Dedup by normalized term within a claim — repeated greedy
        # captures of the same head noun (``該齒輪為金屬, 該齒輪設有齒``)
        # collapse to one finding. The displayable reference_form is
        # ``prefix + normalized_term`` so identical references print
        # identically across the report.
        #
        # Divergence from US walker: claims.py:254 keys dedup on the
        # raw two-tuple ``(term, reference_form)``. The TW walker uses
        # a single-key form on the *normalized* noun because the TW
        # regex captures multi-character noun spans greedily — the same
        # logical reference is captured with different trailing
        # fragments across occurrences (``該齒輪為``, ``該齒輪設``,
        # ``該齒輪所``), and a naive two-key dedup over those raw
        # fragments would inflate the finding count. Synthesizing a
        # canonical reference_form post-normalization (Option C from
        # the 2026-04-09 follow-up session) restores parity with the US
        # shape and is deferred to Phase 9, gated on a measured
        # baseline delta. See docs/architectural-decisions.md ADR-095
        # and the 2026-04-09 follow-up writeup for the decision trail.
        seen_terms: set[str] = set()
        for m in _REF_PATTERN_CAPTURE.finditer(claim.text):
            prefix = m.group("prefix")
            raw_noun = m.group("noun")
            if not raw_noun:
                continue

            full_ref = f"{prefix}{raw_noun}"
            normalized_term = normalize_reference_term(
                full_ref,
                strict_qualifier_matching=strict_qualifier_matching,
            )
            if not normalized_term:
                continue

            if normalized_term in seen_terms:
                continue
            seen_terms.add(normalized_term)

            reference_form = f"{prefix}{normalized_term}"

            # Resolution order:
            #   1. Exact normalized match against any ancestor intro.
            #   2. Paren-numeral asymmetry (F3 Rule 4): if the reference
            #      has NO trailing (...) but an intro has the same base
            #      noun WITH trailing (...), resolve. Guarded: if the
            #      reference itself has a paren numeral, it must match
            #      exactly (preserves L1/L2 typo detection).
            #   3. Longest-intro-prefix match — handles greedy regex
            #      captures that grabbed an in-claim verb past the head
            #      noun (e.g. captured ``控制器讀取`` vs intro 控制器).
            resolved_intro: str | None = None
            if normalized_term in intros_by_term:
                resolved_intro = normalized_term
            elif not re.search(r"\([^)]+\)$", normalized_term):
                # Reference has no paren numeral — try matching against
                # paren-stripped intro forms.
                for intro in intros_by_term:
                    stripped_intro = re.sub(r"\([^)]+\)$", "", intro)
                    if stripped_intro != intro and stripped_intro == normalized_term:
                        resolved_intro = intro
                        break
            if resolved_intro is None:
                best_len = 0
                for intro in intros_by_term:
                    if (
                        len(intro) >= 2
                        and len(intro) > best_len
                        and normalized_term.startswith(intro)
                    ):
                        best_len = len(intro)
                        resolved_intro = intro

            if resolved_intro is not None:
                # Number-neutral match satisfies the antecedent under
                # default semantics. Strict mode additionally requires
                # the reference's plurality to match the intro's.
                if not strict_plural_reference_matching:
                    continue
                if not detect_plural_reference(full_ref):
                    continue
                ancestor_id, _ = intros_by_term[resolved_intro]
                ancestor_claim = next(
                    (c for c in chain if c.id == ancestor_id), None
                )
                intro_was_plural = False
                if ancestor_claim is not None:
                    for original, normalized in extract_introductions_tw(
                        ancestor_claim,
                        strict_qualifier_matching=strict_qualifier_matching,
                    ):
                        if normalized != resolved_intro:
                            continue
                        if full_ref_starts_with_plural(original):
                            intro_was_plural = True
                            break
                if intro_was_plural:
                    continue

            # Did-you-mean layer (ADR-094): when neither exact match nor
            # longest-prefix fallback resolved the term, try character-
            # bigram Jaccard similarity against every ancestor intro. The
            # ordinal_guard pre-filter blocks pairs that differ only in
            # ordinal/polarity prefix (第一電極 vs 第二電極 score ~0.67 by
            # Jaccard but are intentionally distinct components).
            #
            # Tie-break: highest score wins; on ties the nearer ancestor
            # (smaller depth) wins; on remaining ties the dict insertion
            # order (source order within an ancestor) wins because dict
            # iteration is insertion-ordered in Python 3.7+.
            suggested_match: dict | None = None
            if resolved_intro is None:
                ref_tokens = tokenize_tw(normalized_term)
                best_score = 0.0
                best_depth: int | None = None
                for intro_term, (ancestor_id, depth) in intros_by_term.items():
                    if ordinal_guard(normalized_term, intro_term):
                        continue
                    score = jaccard(ref_tokens, tokenize_tw(intro_term))
                    if score < _DIDYOUMEAN_THRESHOLD:
                        continue
                    if (
                        score > best_score
                        or (
                            score == best_score
                            and (best_depth is None or depth < best_depth)
                        )
                    ):
                        best_score = score
                        best_depth = depth
                        suggested_match = {
                            "term": intro_term,
                            "claim_id": ancestor_id,
                        }

            # Self-suggest filter (round 3 fix): suppress suggestions
            # where the candidate term is byte-identical to the
            # normalized reference term. These are structurally
            # meaningless ("did you mean X? — yes, you wrote X") and
            # surface when the dedup layer can't catch them because
            # the displayed reference_form differs from the normalized
            # term. Architectural correctness fix, not a vocabulary
            # patch — universal across CJK.
            if (
                suggested_match is not None
                and suggested_match["term"] == normalized_term
            ):
                suggested_match = None

            issues.append(
                {
                    "claim_id": claim.id,
                    "term": normalized_term,
                    "reference_form": reference_form,
                    "claim_text": claim.text,
                    "suggested_match": suggested_match,
                    "cross_ref": None,
                }
            )

    issues.sort(key=lambda x: (x["claim_id"], x["term"], x["reference_form"]))
    return issues


def full_ref_starts_with_plural(text: str) -> bool:
    """True iff ``text`` begins with a plural quantifier marker.

    Helper for the strict_plural_reference_matching escape hatch. Kept
    module-level (not nested in the walker) so the import surface stays
    flat for tests.
    """
    return text.startswith(("複數", "多個", "數個", "複數個"))
