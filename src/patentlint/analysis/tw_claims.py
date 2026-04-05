# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""TW claims structural checks.

Sixteen pure functions checking Taiwan patent claim formatting
against TIPO rules (專利法施行細則 and 專利審查基準).
"""

from __future__ import annotations

import re

from patentlint.models import CheckItem, SymbolEntry, TwPatentDocument

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
    """Compare reference numerals in claims against symbol_table entries."""
    if not doc.symbol_table:
        return [CheckItem(
            status="pass",
            message="Reference numerals in claims consistent with 符號說明.",
            message_key="check.tw.claims.symbolTableConsistency.pass",
            reference="專利審查基準",
        )]

    # Collect numerals from claims
    claim_numerals: set[str] = set()
    for claim in doc.claims:
        for m in _CLAIM_NUMERAL.finditer(claim.text):
            claim_numerals.add(m.group(1))

    # Collect numerals from symbol table
    symbol_numerals: set[str] = set()
    for entry in doc.symbol_table:
        # Handle ranges like "S21~S25" — extract individual numbers
        nums = re.findall(r"\d+", entry.numeral)
        symbol_numerals.update(nums)

    in_claims_not_table = claim_numerals - symbol_numerals
    in_table_not_claims = symbol_numerals - claim_numerals

    if in_claims_not_table or in_table_not_claims:
        parts = []
        if in_claims_not_table:
            parts.append(f"In claims but not 符號說明: {', '.join(sorted(in_claims_not_table))}")
        if in_table_not_claims:
            parts.append(f"In 符號說明 but not claims: {', '.join(sorted(in_table_not_claims))}")
        detail = "; ".join(parts)
        return [CheckItem(
            status="verify",
            message="Reference numerals in claims inconsistent with 符號說明.",
            message_key="check.tw.claims.symbolTableConsistency.verify",
            details=detail,
            details_key="details.tw.symbolTableConsistency",
            details_params={"detail": detail},
            reference="專利審查基準",
        )]

    return [CheckItem(
        status="pass",
        message="Reference numerals in claims consistent with 符號說明.",
        message_key="check.tw.claims.symbolTableConsistency.pass",
        reference="專利審查基準",
    )]


# ── Check 26 ─────────────────────────────────────────────────────────────

# Introduction: 一 + noun (2-8 CJK characters)
# Exclusion set extends phase7.md base pattern with conjunctions (及與和)
# and particles (之的) that act as noun boundaries in patent claims.
_INTRO_PATTERN = re.compile(r"一([^\s，。；：、及與和之的]{2,8})")

# Reference: 該/所述/前述 + noun (2-8 CJK characters)
_REF_PATTERN = re.compile(r"(?:該|所述|前述)([^\s，。；：、及與和之的]{2,8})")


def check_antecedent_basis(doc: TwPatentDocument) -> list[CheckItem]:
    """Check antecedent basis: 該/所述/前述 + noun needs matching 一 + noun in chain."""
    claims = doc.claims
    if not claims:
        return [CheckItem(
            status="pass",
            message="All referenced terms have antecedent basis.",
            message_key="check.tw.claims.antecedentBasis.pass",
            reference="專利審查基準",
        )]

    claims_by_id = {c.id: c for c in claims}

    def _collect_introductions(claim_id: int, visited: set[int] | None = None) -> set[str]:
        """Collect all 一+noun introductions from claim and its parent chain."""
        if visited is None:
            visited = set()
        if claim_id in visited:
            return set()
        visited.add(claim_id)
        claim = claims_by_id.get(claim_id)
        if not claim:
            return set()
        intros = set(_INTRO_PATTERN.findall(claim.text))
        for dep_id in claim.dependencies:
            intros |= _collect_introductions(dep_id, visited)
        return intros

    flagged_terms: set[str] = set()
    for claim in claims:
        intros = _collect_introductions(claim.id)
        refs = _REF_PATTERN.findall(claim.text)
        for ref_noun in refs:
            # Greedy regex may capture beyond the noun (e.g., "底座設有一凹槽"
            # instead of "底座"). Use 2-char prefix matching: Chinese nouns
            # are typically 2+ chars, so matching first 2 chars is sufficient.
            ref_head = ref_noun[:2]
            if not any(intro[:2] == ref_head for intro in intros):
                flagged_terms.add(ref_noun)

    if flagged_terms:
        sorted_terms = sorted(flagged_terms)
        return [CheckItem(
            status="verify",
            message=f"{len(sorted_terms)} term(s) may lack antecedent basis.",
            message_key="check.tw.claims.antecedentBasis.verify",
            details=", ".join(sorted_terms),
            details_key="details.tw.antecedentBasis",
            details_params={"count": str(len(sorted_terms))},
            reference="專利審查基準",
        )]

    return [CheckItem(
        status="pass",
        message="All referenced terms have antecedent basis.",
        message_key="check.tw.claims.antecedentBasis.pass",
        reference="專利審查基準",
    )]
