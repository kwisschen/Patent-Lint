# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""CN claims analysis checks.

Twelve pure functions checking Chinese patent claim formatting
against CNIPA rules (专利法实施细则 and 审查指南).
"""

from __future__ import annotations

import re

from patentlint.models import CheckItem, CnPatentDocument

# ── Check 9 ──────────────────────────────────────────────────────────────


def check_claims_sequential(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Verify claim IDs are 1, 2, 3, ... N with no gaps."""
    claims = cn_doc.claims
    if not claims:
        return [CheckItem(
            status="pass",
            message="No claims to check.",
            message_key="check.cn.claims.sequential.pass",
            reference="审查指南",
        )]

    for i, claim in enumerate(claims):
        expected = i + 1
        if claim.id != expected:
            detail = f"expected {expected}, found {claim.id}"
            return [CheckItem(
                status="amend",
                message=f"Claim numbering is not sequential: {detail}.",
                message_key="check.cn.claims.sequential.amend",
                details=detail,
                details_key="details.cn.claimsSequential",
                details_params={"detail": detail},
                reference="审查指南",
            )]

    return [CheckItem(
        status="pass",
        message="Claim numbers are sequential.",
        message_key="check.cn.claims.sequential.pass",
        reference="审查指南",
    )]


# ── Check 10 ─────────────────────────────────────────────────────────────

_DEP_FORMAT_SINGLE = re.compile(r"如权利要求\s*\d+[\s\S]*?所述的")
_DEP_FORMAT_MULTI = re.compile(
    r"如权利要求\s*\d+[\s\S]*?中\s*任[一意]\s*项\s*所述的"
)


def check_dependency_format(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Check dependent claims use the 如权利要求N所述的 format."""
    dependents = [c for c in cn_doc.claims if not c.independent]
    if not dependents:
        return [CheckItem(
            status="pass",
            message="No dependent claims to check.",
            message_key="check.cn.claims.dependencyFormat.pass",
            reference="专利法实施细则 §22",
        )]

    bad_count = 0
    for claim in dependents:
        if claim.multiple_dependent:
            if not _DEP_FORMAT_MULTI.search(claim.text):
                bad_count += 1
        else:
            if not _DEP_FORMAT_SINGLE.search(claim.text):
                bad_count += 1

    if bad_count:
        return [CheckItem(
            status="amend",
            message=f"{bad_count} dependent claim(s) lack proper dependency format.",
            message_key="check.cn.claims.dependencyFormat.amend",
            details=f"{bad_count} claims",
            details_key="details.cn.dependencyFormat",
            details_params={"count": str(bad_count)},
            reference="专利法实施细则 §22",
        )]

    return [CheckItem(
        status="pass",
        message="All dependent claims use proper dependency format.",
        message_key="check.cn.claims.dependencyFormat.pass",
        reference="专利法实施细则 §22",
    )]


# ── Check 11 ─────────────────────────────────────────────────────────────


def check_self_dependent(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Check if any claim depends on itself."""
    bad = [c.id for c in cn_doc.claims if c.id in c.dependencies]

    if bad:
        claims_str = ", ".join(str(i) for i in bad)
        return [CheckItem(
            status="amend",
            message=f"Self-dependent claims found: {claims_str}.",
            message_key="check.cn.claims.selfDependent.amend",
            details=claims_str,
            details_key="details.cn.selfDependent",
            details_params={"claims": claims_str},
            reference="专利法实施细则 §22",
        )]

    return [CheckItem(
        status="pass",
        message="No self-dependent claims.",
        message_key="check.cn.claims.selfDependent.pass",
        reference="专利法实施细则 §22",
    )]


# ── Check 12 ─────────────────────────────────────────────────────────────


def check_forward_dependency(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Check if any claim depends on a higher-numbered claim."""
    bad = [c.id for c in cn_doc.claims if any(d > c.id for d in c.dependencies)]

    if bad:
        claims_str = ", ".join(str(i) for i in bad)
        return [CheckItem(
            status="amend",
            message=f"Forward-referencing claims found: {claims_str}.",
            message_key="check.cn.claims.forwardDependency.amend",
            details=claims_str,
            details_key="details.cn.forwardDependency",
            details_params={"claims": claims_str},
            reference="专利法实施细则 §22",
        )]

    return [CheckItem(
        status="pass",
        message="No forward-referencing dependencies.",
        message_key="check.cn.claims.forwardDependency.pass",
        reference="专利法实施细则 §22",
    )]


# ── Check 13 ─────────────────────────────────────────────────────────────


def check_single_sentence(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Each claim must have exactly one 。 at the end."""
    bad_count = 0
    for claim in cn_doc.claims:
        text = claim.text.strip()
        period_count = text.count("。")
        if period_count != 1 or not text.endswith("。"):
            bad_count += 1

    if bad_count:
        return [CheckItem(
            status="amend",
            message=f"{bad_count} claim(s) have invalid sentence structure.",
            message_key="check.cn.claims.singleSentence.amend",
            details=f"{bad_count} claims",
            details_key="details.cn.singleSentence",
            details_params={"count": str(bad_count)},
            reference="审查指南 第二部分第二章",
        )]

    return [CheckItem(
        status="pass",
        message="All claims are single sentences ending with 。.",
        message_key="check.cn.claims.singleSentence.pass",
        reference="审查指南 第二部分第二章",
    )]


# ── Check 14 ─────────────────────────────────────────────────────────────

# CJK char followed by optional space then 2-4 digits, not in parentheses
_BARE_NUMERAL = re.compile(
    r"(?<!\()(?<=[\u4e00-\u9fff])\s?\d{2,4}(?!\))"
)


def check_reference_numeral_parentheses(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Find reference numerals in claims not enclosed in parentheses."""
    bad_count = 0
    for claim in cn_doc.claims:
        if _BARE_NUMERAL.search(claim.text):
            bad_count += 1

    if bad_count:
        return [CheckItem(
            status="verify",
            message=f"{bad_count} claim(s) have unparenthesized reference numerals.",
            message_key="check.cn.claims.refNumeralParens.verify",
            details=f"{bad_count} claims",
            details_key="details.cn.refNumeralParens",
            details_params={"count": str(bad_count)},
            reference="审查指南",
        )]

    return [CheckItem(
        status="pass",
        message="All reference numerals in claims are parenthesized.",
        message_key="check.cn.claims.refNumeralParens.pass",
        reference="审查指南",
    )]


# ── Check 15 ─────────────────────────────────────────────────────────────

# Extract subject name: text after the last 所述的 (or 的) before 。
_SUBJECT_RE = re.compile(r"所述的(.+?)(?:[，,]|$)")
_LEADING_QUANTIFIER = re.compile(r"^(?:一种|一个|该|所述|所述的)\s*")


def _extract_subject(claim_text: str) -> str:
    """Extract the subject name from a claim — text after last 所述的 before comma/end."""
    match = _SUBJECT_RE.search(claim_text)
    if match:
        return match.group(1).strip()
    return ""


def _normalize_subject(subject: str) -> str:
    """Strip leading quantifiers for comparison."""
    return _LEADING_QUANTIFIER.sub("", subject).strip()


def check_subject_name_consistency(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Check dependent claim subjects match their parent claim subjects."""
    claims_by_id = {c.id: c for c in cn_doc.claims}
    dependents = [c for c in cn_doc.claims if not c.independent]

    if not dependents:
        return [CheckItem(
            status="pass",
            message="No dependent claims to check.",
            message_key="check.cn.claims.subjectConsistency.pass",
            reference="审查指南 第二部分第二章",
        )]

    bad_count = 0
    for claim in dependents:
        dep_subject = _extract_subject(claim.text)
        if not dep_subject or not claim.dependencies:
            continue
        parent_id = claim.dependencies[0]
        parent = claims_by_id.get(parent_id)
        if not parent:
            continue
        # For independent parent, extract the subject from preamble
        # (text before 其特征在于 or before first ，)
        parent_text = parent.text
        preamble_match = re.search(r"[.．。]\s*(.+?)(?:，|,|其特征)", parent_text)
        if preamble_match:
            parent_subject = preamble_match.group(1).strip()
        else:
            parent_subject = ""

        if (dep_subject and parent_subject
                and _normalize_subject(dep_subject) != _normalize_subject(parent_subject)):
            bad_count += 1

    if bad_count:
        return [CheckItem(
            status="verify",
            message=f"{bad_count} dependent claim(s) have inconsistent subject names.",
            message_key="check.cn.claims.subjectConsistency.verify",
            details=f"{bad_count} claims",
            details_key="details.cn.subjectConsistency",
            details_params={"count": str(bad_count)},
            reference="审查指南 第二部分第二章",
        )]

    return [CheckItem(
        status="pass",
        message="Dependent claim subject names are consistent.",
        message_key="check.cn.claims.subjectConsistency.pass",
        reference="审查指南 第二部分第二章",
    )]


# ── Check 16 ─────────────────────────────────────────────────────────────

_TRANSITION_PHRASES = re.compile(r"其特征在于|其特征是|其改进在于")


def check_transition_phrase(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Check independent claims contain a characterizing transition."""
    independents = [c for c in cn_doc.claims if c.independent]
    if not independents:
        return [CheckItem(
            status="pass",
            message="No independent claims to check.",
            message_key="check.cn.claims.transitionPhrase.pass",
            reference="审查指南",
        )]

    bad_count = 0
    for claim in independents:
        if not _TRANSITION_PHRASES.search(claim.text):
            bad_count += 1

    if bad_count:
        return [CheckItem(
            status="verify",
            message=f"{bad_count} independent claim(s) lack a transition phrase.",
            message_key="check.cn.claims.transitionPhrase.verify",
            details=f"{bad_count} claims",
            details_key="details.cn.transitionPhrase",
            details_params={"count": str(bad_count)},
            reference="审查指南",
        )]

    return [CheckItem(
        status="pass",
        message="All independent claims contain a transition phrase.",
        message_key="check.cn.claims.transitionPhrase.pass",
        reference="审查指南",
    )]


# ── Check 17 ─────────────────────────────────────────────────────────────

_TW_TERMS = re.compile(r"请求项|請求項")


def check_tw_terminology(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Scan claims for Taiwan-specific terminology."""
    for claim in cn_doc.claims:
        if _TW_TERMS.search(claim.text):
            return [CheckItem(
                status="verify",
                message="Taiwan-specific terminology found in claims.",
                message_key="check.cn.claims.twTerminology.verify",
                details_key="details.cn.twTerminology",
                reference="",
            )]

    return [CheckItem(
        status="pass",
        message="No Taiwan-specific terminology found.",
        message_key="check.cn.claims.twTerminology.pass",
        reference="",
    )]


# ── Check 18 ─────────────────────────────────────────────────────────────

_SPEC_REF = re.compile(r"如说明书|如图|参见说明书|参见图|参照说明书|参照附图")


def check_claims_spec_reference(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Check if claims reference the specification or drawings for scope."""
    bad_count = 0
    for claim in cn_doc.claims:
        if _SPEC_REF.search(claim.text):
            bad_count += 1

    if bad_count:
        return [CheckItem(
            status="amend",
            message=f"{bad_count} claim(s) reference the specification or drawings.",
            message_key="check.cn.claims.specReference.amend",
            details=f"{bad_count} claims",
            details_key="details.cn.claimsSpecReference",
            details_params={"count": str(bad_count)},
            reference="审查指南 第二部分第二章",
        )]

    return [CheckItem(
        status="pass",
        message="No claims reference the specification or drawings.",
        message_key="check.cn.claims.specReference.pass",
        reference="审查指南 第二部分第二章",
    )]


# ── Check 19 ─────────────────────────────────────────────────────────────


def check_multi_multi_dependency(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Find claims that multiply-depend on another multiple-dependent claim."""
    multi_dep_ids = {c.id for c in cn_doc.claims if c.multiple_dependent}
    bad = []
    for claim in cn_doc.claims:
        if claim.multiple_dependent:
            if any(d in multi_dep_ids for d in claim.dependencies):
                bad.append(claim.id)

    if bad:
        claims_str = ", ".join(str(i) for i in bad)
        return [CheckItem(
            status="amend",
            message=f"Multiple-dependent claim(s) depend on other multiple-dependent claims: {claims_str}.",
            message_key="check.cn.claims.multiMultiDep.amend",
            details=claims_str,
            details_key="details.cn.multiMultiDep",
            details_params={"claims": claims_str},
            reference="专利法实施细则 §22",
        )]

    return [CheckItem(
        status="pass",
        message="No chained multiple dependencies.",
        message_key="check.cn.claims.multiMultiDep.pass",
        reference="专利法实施细则 §22",
    )]


# ── Check 20 ─────────────────────────────────────────────────────────────


def check_dependent_ordering(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Check dependents of each independent claim appear consecutively."""
    claims = cn_doc.claims
    if not claims:
        return [CheckItem(
            status="pass",
            message="No claims to check.",
            message_key="check.cn.claims.dependentOrdering.pass",
            reference="审查指南 第二部分第二章",
        )]

    # Build map: for each independent claim, find the last position of
    # any dependent that references it (directly or transitively via chain).
    # Then check no dependent of an earlier independent appears after a later
    # independent.

    # Find independent claim positions
    indep_positions = []
    for i, c in enumerate(claims):
        if c.independent:
            indep_positions.append(i)

    if len(indep_positions) < 2:
        return [CheckItem(
            status="pass",
            message="Dependent claim ordering is correct.",
            message_key="check.cn.claims.dependentOrdering.pass",
            reference="审查指南 第二部分第二章",
        )]

    # For each independent claim, find the "group boundary" — the position
    # of the next independent claim. Any dependent that references the
    # earlier independent but appears after the next independent is out of order.
    claims_by_id = {c.id: c for c in claims}

    def root_independent(claim_id: int, visited: set | None = None) -> int | None:
        """Trace dependency chain to find the root independent claim."""
        if visited is None:
            visited = set()
        if claim_id in visited:
            return None
        visited.add(claim_id)
        c = claims_by_id.get(claim_id)
        if not c:
            return None
        if c.independent:
            return c.id
        if c.dependencies:
            return root_independent(c.dependencies[0], visited)
        return None

    # Check: after each independent claim, all claims until the next
    # independent should depend (transitively) on the current or a
    # preceding independent claim, not on a later one.
    for idx in range(len(indep_positions) - 1):
        current_indep_pos = indep_positions[idx]
        next_indep_pos = indep_positions[idx + 1]

        # Check claims after next_indep_pos to see if any reference
        # the current independent
        current_indep_id = claims[current_indep_pos].id
        for j in range(next_indep_pos + 1, len(claims)):
            c = claims[j]
            if not c.independent:
                root = root_independent(c.id)
                if root == current_indep_id:
                    return [CheckItem(
                        status="amend",
                        message="Dependent claims are not grouped with their independent claim.",
                        message_key="check.cn.claims.dependentOrdering.amend",
                        details_key="details.cn.dependentOrdering",
                        reference="审查指南 第二部分第二章",
                    )]

    return [CheckItem(
        status="pass",
        message="Dependent claim ordering is correct.",
        message_key="check.cn.claims.dependentOrdering.pass",
        reference="审查指南 第二部分第二章",
    )]
