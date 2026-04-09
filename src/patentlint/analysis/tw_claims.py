# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""TW claims structural checks.

Sixteen pure functions checking Taiwan patent claim formatting
against TIPO rules (專利法施行細則 and 專利審查基準).
"""

from __future__ import annotations

import re

from patentlint.models import CheckItem, Claim, TwPatentDocument

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

# Phase 8b walker noun-character boundary set. Extends the phase7.md base
# pattern with conjunctions (及與和) and particles (之的) that act as noun
# boundaries in TW patent claims, plus 該 (literary determiner — never a
# noun morpheme) so consecutive references like ``該控制器讀取該感測器``
# split into two captures instead of one greedy span. The 2-16 character
# window captures legitimate compound patent nouns like
# 高頻基板用樹脂組成物 that the previous {2,8} cap truncated mid-word.
_NOUN_CHARS = r"[^\s，。；：、及與和之的該]{2,16}"

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
_INTRO_MULTI_QUANTIFIERS = (
    "至少一個", "至少一",
    "一個", "一種", "一對",
    "複數個", "多個", "數個",
    "複數",
)
_INTRO_PATTERN = re.compile(
    r"(?:" + "|".join(_INTRO_MULTI_QUANTIFIERS) + r"|(?<!第)一)"
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
        # as a stray. Same for 前 (start of 前述). Risk: 場所/研究所 end
        # in 所 — false positive is rare in claim language.
        "所", "前",
    ),
    key=len,
    reverse=True,
))

# ADR-095 Rule 2: leading quantifiers (stripped from both sides).
# Ordered longest-first so 至少一個 is stripped as a single token before
# 至少一 is stripped.
_LEADING_QUANTIFIER_DENYLIST: tuple[str, ...] = tuple(sorted(
    (
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
        # Verbs
        "設有", "包含", "包括", "具有", "含有", "具備",
        "係為", "係於",
        "為", "是", "係",
        # Reference-form prefixes (multi-char)
        "所述", "前述", "該等", "該些",
    ),
    key=len,
    reverse=True,
))


def clean_noun_phrase_tw(text: str) -> str:
    """Strip trailing verbs and conjunction fragments from a TW reference term.

    Two-phase cleanup:

    1. Interior-verb truncation — find the first occurrence of any
       ``_INTERIOR_VERB_BOUNDARIES`` token and cut everything from that
       position onward. Recovers ``底座`` from greedy regex captures
       like ``底座設有一孔洞``.

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

    # Phase 1: interior-verb truncation. Find the EARLIEST verb-boundary
    # occurrence so multi-verb texts cut at the first verb only.
    earliest_idx: int | None = None
    for verb in _INTERIOR_VERB_BOUNDARIES:
        idx = text.find(verb)
        if idx > 1:  # require ≥2 chars before the verb
            if earliest_idx is None or idx < earliest_idx:
                earliest_idx = idx
    current = text[:earliest_idx] if earliest_idx is not None else text

    # Phase 2: trailing-verb stripping (iterative).
    # Safety bound to prevent pathological iteration.
    for _ in range(16):
        stripped = False
        for verb in _TRAILING_VERB_DENYLIST:
            if current.endswith(verb) and len(current) > len(verb):
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


def normalize_reference_term(text: str) -> str:
    """Normalize a flagged reference term for antecedent matching.

    Composes: strip_reference_form_prefix → clean_noun_phrase_tw →
    strip_leading_quantifier. The reference-form strip runs first so
    that a term like 該第一電極 loses its 該 marker and the walker's
    comparison sees 第一電極.
    """
    t = strip_reference_form_prefix(text)
    t = clean_noun_phrase_tw(t)
    t = strip_leading_quantifier(t)
    return t


def normalize_candidate_intro(text: str) -> str:
    """Normalize an introduction candidate for antecedent matching.

    Composes: clean_noun_phrase_tw → strip_leading_quantifier. No
    reference-form prefix strip because intros do not carry 該/所述/前述
    markers.
    """
    t = clean_noun_phrase_tw(text)
    t = strip_leading_quantifier(t)
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


def extract_introductions_tw(claim: Claim) -> list[tuple[str, str]]:
    """Extract introductions from a TW claim as (original, normalized) pairs.

    Returns the bare noun captured after the quantifier (e.g.
    ``一第一電極`` → original=``第一電極``, normalized=
    ``normalize_candidate_intro("第一電極")``). Both fields are surfaced
    so the walker can present the writer's original phrasing in
    diagnostic output while keeping the normalized form for matching.
    """
    pairs: list[tuple[str, str]] = []
    for m in _INTRO_PATTERN.finditer(claim.text):
        original = m.group(1)
        normalized = normalize_candidate_intro(original)
        if normalized:
            pairs.append((original, normalized))
    return pairs


def check_antecedent_basis(
    doc: TwPatentDocument,
    *,
    strict_plural_reference_matching: bool = False,
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

        # Map normalized intro term → shallowest ancestor claim id.
        # Iteration order (chain[0] = current claim, chain[1] = nearest
        # parent, ...) means setdefault preserves the shallowest.
        intros_by_term: dict[str, int] = {}
        for ancestor in chain:
            for _, normalized in extract_introductions_tw(ancestor):
                intros_by_term.setdefault(normalized, ancestor.id)

        # Dedup by normalized term within a claim — repeated greedy
        # captures of the same head noun (``該齒輪為金屬, 該齒輪設有齒``)
        # collapse to one finding. The displayable reference_form is
        # ``prefix + normalized_term`` so identical references print
        # identically across the report.
        seen_terms: set[str] = set()
        for m in _REF_PATTERN_CAPTURE.finditer(claim.text):
            prefix = m.group("prefix")
            raw_noun = m.group("noun")
            if not raw_noun:
                continue

            full_ref = f"{prefix}{raw_noun}"
            normalized_term = normalize_reference_term(full_ref)
            if not normalized_term:
                continue

            if normalized_term in seen_terms:
                continue
            seen_terms.add(normalized_term)

            reference_form = f"{prefix}{normalized_term}"

            # Resolution order:
            #   1. Exact normalized match against any ancestor intro.
            #   2. Longest-intro-prefix match — handles greedy regex
            #      captures that grabbed an in-claim verb past the head
            #      noun (e.g. captured ``控制器讀取`` vs intro 控制器).
            resolved_intro: str | None = None
            if normalized_term in intros_by_term:
                resolved_intro = normalized_term
            else:
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
                ancestor_id = intros_by_term[resolved_intro]
                ancestor_claim = next(
                    (c for c in chain if c.id == ancestor_id), None
                )
                intro_was_plural = False
                if ancestor_claim is not None:
                    for original, normalized in extract_introductions_tw(
                        ancestor_claim
                    ):
                        if normalized != resolved_intro:
                            continue
                        if full_ref_starts_with_plural(original):
                            intro_was_plural = True
                            break
                if intro_was_plural:
                    continue

            issues.append(
                {
                    "claim_id": claim.id,
                    "term": normalized_term,
                    "reference_form": reference_form,
                    "claim_text": claim.text,
                    "suggested_match": None,
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
