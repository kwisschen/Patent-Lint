# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""TW claims structural checks.

Nine pure functions checking Taiwan patent claim formatting
against TIPO rules (專利法施行細則 and 專利審查基準).
"""

from __future__ import annotations

import re

from patentlint.models import CheckItem, TwPatentDocument

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
