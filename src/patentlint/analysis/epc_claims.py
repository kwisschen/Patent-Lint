# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""EPC claims-level checks (G4 + G5 + G6 in the canonical 7-group order).

G4 (structure) — shipped:
  - check_claims_sequential_epc       — Rule 43(5) EPC
  - check_dependency_format_epc       — Rule 43(4) EPC
  - check_self_dependent_epc          — basic logic
  - check_forward_dependency_epc      — Rule 43(4) EPC implied
  - check_single_sentence_per_claim_epc — Rule 43(4) + F-IV § 4.10
  - check_reference_signs_in_parens_epc — Rule 43(7) EPC
  - check_subject_consistency_epc     — Guidelines F-IV § 3.4
  - check_transition_phrase_epc       — Guidelines F-IV § 4.13

G5 (cross-jurisdiction / format guards) — pending:
  - check_claims_spec_reference_epc   — Rule 43(6) EPC
  - check_multi_dep_on_multi_dep_epc  — Rule 43(4) EPC
  - check_markush_format_epc          — Guidelines F-IV § 4.20
  - check_independent_claim_count_epc — Rule 43(2) + 43(3)
  - check_two_part_form_epc           — Rule 43(1) advisory

G6 (§ 112-equivalent, walker territory) — pending:
  - check_antecedent_basis_epc        — Art. 84 + Guidelines F-IV § 4.5
  - check_claim_punctuation_epc       — Guidelines F-IV § 4.10
  - check_restrictive_absolutes_epc   — Guidelines F-IV § 4.7
  - check_spec_support_epc            — Art. 84 (support)

Walker checks (antecedentBasis + specSupport) ship as REVIEW status at v1
per locked decision; ADR-154-style promotion to FIX only after FP rate
is measured on real EPC corpus.
"""

from __future__ import annotations

import re

from patentlint.analysis.utils import _dx
from patentlint.models import CheckItem, Claim


# Transitional phrases recognised in EPC drafts. "comprising" / "comprises"
# is the open-ended form; "consisting of" is closed; "consisting essentially
# of" is partly-open (Guidelines F-IV § 4.13).
_EPC_TRANSITION_RE = re.compile(
    r"\b(?:"
    r"compris(?:e|es|ing|ed)"
    r"|consist(?:s|ing|ed)\s+(?:essentially\s+)?of"
    r"|character(?:i[sz]ed)\s+(?:in\s+that|by)"
    r"|including"
    r"|containing"
    r")\b",
    re.IGNORECASE,
)


def check_claims_sequential_epc(claims: list[Claim]) -> list[CheckItem]:
    """Verify claims are numbered consecutively per Rule 43(5) EPC."""
    if not claims:
        return [CheckItem(
            status="pass",
            message="No claims to check.",
            message_key="check.epc.claims.sequential.pass",
            reference="Rule 43(5) EPC",
        )]
    ids = [c.id for c in claims]
    gaps: list[int] = []
    for i in range(1, len(ids)):
        if ids[i] - ids[i - 1] != 1:
            for missing in range(ids[i - 1] + 1, ids[i]):
                gaps.append(missing)
    if ids[0] != 1:
        gaps = list(range(1, ids[0])) + gaps

    if gaps:
        return [CheckItem(
            status="amend",
            message=f"Claims are not sequentially numbered. Missing claim(s): {', '.join(str(g) for g in gaps)}.",
            message_key="check.epc.claims.sequential.amend",
            details=", ".join(str(g) for g in gaps),
            reference="Rule 43(5) EPC",
            diagnostics=_dx(
                missing_count=len(gaps),
                missing_numbers=gaps,
                first_missing=gaps[0] if gaps else None,
                total_claims=len(claims),
            ),
        )]
    return [CheckItem(
        status="pass",
        message="Claims numbered consecutively per Rule 43(5) EPC.",
        message_key="check.epc.claims.sequential.pass",
        reference="Rule 43(5) EPC",
    )]


def check_dependency_format_epc(claims: list[Claim]) -> list[CheckItem]:
    """Verify dependent claims explicitly reference their parent per Rule 43(4) EPC.

    Any dependent claim (independent=False) with an empty dependency list
    indicates the parser failed to find a "claim N" reference — likely a
    malformed preamble. The parser already classifies via the dep-ref
    regex, so this check guards the contract: dependent ⇒ has parent(s).
    """
    bad = [c.id for c in claims if not c.independent and not c.dependencies]
    if bad:
        return [CheckItem(
            status="amend",
            message=(
                f"Claim(s) {', '.join(str(i) for i in bad)} look dependent but "
                f"do not explicitly reference a parent claim — Rule 43(4) EPC "
                f"requires explicit reference (e.g., 'according to claim N')."
            ),
            message_key="check.epc.claims.dependencyFormat.amend",
            details=", ".join(str(i) for i in bad),
            reference="Rule 43(4) EPC",
            diagnostics=_dx(
                flagged_count=len(bad),
                flagged_claim_id=bad[0] if bad else None,
            ),
        )]
    return [CheckItem(
        status="pass",
        message="All dependent claims explicitly reference a parent claim.",
        message_key="check.epc.claims.dependencyFormat.pass",
        reference="Rule 43(4) EPC",
    )]


def check_self_dependent_epc(claims: list[Claim]) -> list[CheckItem]:
    """Verify no claim depends on itself.

    The parser already drops self-references as a noise guard, but the
    check confirms the post-parse contract: claim N never appears in its
    own dependency list. A non-empty list here would indicate a parser
    regression rather than a drafter mistake.
    """
    bad = [c.id for c in claims if c.id in c.dependencies]
    if bad:
        return [CheckItem(
            status="amend",
            message=f"Self-dependent claim(s): {', '.join(str(i) for i in bad)}.",
            message_key="check.epc.claims.selfDependent.amend",
            details=", ".join(str(i) for i in bad),
            reference="Rule 43(4) EPC",
            diagnostics=_dx(flagged_count=len(bad), flagged_claim_id=bad[0]),
        )]
    return [CheckItem(
        status="pass",
        message="No self-dependent claims.",
        message_key="check.epc.claims.selfDependent.pass",
        reference="Rule 43(4) EPC",
    )]


def check_forward_dependency_epc(claims: list[Claim]) -> list[CheckItem]:
    """Verify no claim depends on a higher-numbered claim (Rule 43(4) EPC implied).

    EPC drafting convention is that dependent claims refer to earlier-
    numbered claims only. A forward reference (claim 3 depending on
    claim 5) is a typo / restructuring leftover.
    """
    bad = [c.id for c in claims if any(d > c.id for d in c.dependencies)]
    if bad:
        return [CheckItem(
            status="amend",
            message=f"Forward-referencing claim(s): {', '.join(str(i) for i in bad)}.",
            message_key="check.epc.claims.forwardDependency.amend",
            details=", ".join(str(i) for i in bad),
            reference="Rule 43(4) EPC",
            diagnostics=_dx(
                flagged_count=len(bad),
                flagged_claim_id=bad[0],
            ),
        )]
    return [CheckItem(
        status="pass",
        message="No forward dependencies.",
        message_key="check.epc.claims.forwardDependency.pass",
        reference="Rule 43(4) EPC",
    )]


def check_single_sentence_per_claim_epc(claims: list[Claim]) -> list[CheckItem]:
    """Verify each claim is a single sentence per Rule 43(4) + F-IV § 4.10.

    A claim contains multiple sentences if it has more than one
    period-ended segment in its body. Common drafting hygiene: drafters
    sometimes split a long claim into two sentences when they should be
    one via semicolons or commas. The check tolerates "e.g.", "i.e.",
    "etc." by ignoring them. REVIEW status (Guidelines F-IV § 4.10 is
    a strong but not absolute requirement).
    """
    bad: list[int] = []
    abbrev_re = re.compile(r"\b(e\.g\.|i\.e\.|etc\.|cf\.|et\s+al\.)", re.IGNORECASE)
    for c in claims:
        body = c.text
        # Mask abbreviations before counting sentences so "e.g." doesn't
        # inflate the period count.
        masked = abbrev_re.sub("ABBR", body)
        # Count strong terminators followed by a space-and-capital or EOF.
        # We require a SPACE after the period because end-of-claim "." is
        # legitimate.
        sentence_endings = re.findall(r"\.\s+[A-Z]", masked)
        if len(sentence_endings) >= 1:
            # At least one sentence-boundary inside the body indicates
            # multi-sentence structure.
            bad.append(c.id)
    if bad:
        return [CheckItem(
            status="verify",
            message=(
                f"Claim(s) {', '.join(str(i) for i in bad)} appear to contain "
                f"multiple sentences — Guidelines F-IV § 4.10 prefers one "
                f"sentence per claim."
            ),
            message_key="check.epc.claims.singleSentence.verify",
            details=", ".join(str(i) for i in bad),
            reference="Rule 43(4) EPC; EPO Guidelines F-IV § 4.10",
            diagnostics=_dx(
                flagged_count=len(bad),
                flagged_claim_id=bad[0],
            ),
        )]
    return [CheckItem(
        status="pass",
        message="All claims are single sentences per Guidelines F-IV § 4.10.",
        message_key="check.epc.claims.singleSentence.pass",
        reference="Rule 43(4) EPC; EPO Guidelines F-IV § 4.10",
    )]


_BARE_NUMERAL_IN_CLAIM = re.compile(
    r"(?<![\(\d\.\-])"          # not preceded by an open-paren / digit / dot / dash
    r"\b(\d{1,4}[a-zA-Z]?)\b"   # bare 1-4 digit token (optional alpha suffix)
    r"(?![\)\d])"               # not followed by close-paren or another digit
)


def check_reference_signs_in_parens_epc(claims: list[Claim]) -> list[CheckItem]:
    """Verify reference signs in claims appear in parentheses per Rule 43(7) EPC.

    Rule 43(7): "If the European patent application contains drawings,
    the technical features mentioned in the claims shall preferably, if
    the intelligibility of the claim can thereby be increased, be
    followed by reference signs relating to these features, placed in
    parentheses."

    The check fires when a claim contains bare numerals (1-4 digit
    tokens not already enclosed in parentheses). Year mentions (4-digit
    >= 1900) are excluded because date references are not reference
    signs. v1 uses a tight conservative pattern; refinement via
    real-corpus signal will follow.
    """
    flagged: list[dict] = []
    for c in claims:
        # Strip parenthesised content so "(10)" doesn't match
        stripped = re.sub(r"\([^()]*\)", "", c.text)
        for m in _BARE_NUMERAL_IN_CLAIM.finditer(stripped):
            token = m.group(1)
            # Year exclusion: 4-digit numbers 1900-2099
            if len(token) == 4 and token.isdigit() and 1900 <= int(token) <= 2099:
                continue
            # Claim-number reference like "claim 1" is legitimate prose
            before = stripped[max(0, m.start() - 8):m.start()].lower()
            if "claim" in before:
                continue
            flagged.append({"claim_id": c.id, "token": token})
    if flagged:
        # Only emit when we have at least one finding per claim — collapse
        # duplicates for the message.
        flagged_claims = sorted({f["claim_id"] for f in flagged})
        return [CheckItem(
            status="verify",
            message=(
                f"Claim(s) {', '.join(str(i) for i in flagged_claims)} contain "
                f"bare numeral(s) not in parentheses — Rule 43(7) EPC prefers "
                f"reference signs to be parenthesised."
            ),
            message_key="check.epc.claims.refSignsInParens.verify",
            details=", ".join(str(i) for i in flagged_claims),
            reference="Rule 43(7) EPC",
            diagnostics=_dx(
                flagged_count=len(flagged),
                flagged_claim_id=flagged_claims[0] if flagged_claims else None,
                sample_tokens=[f["token"] for f in flagged[:5]],
            ),
        )]
    return [CheckItem(
        status="pass",
        message="Reference signs in claims are properly parenthesised.",
        message_key="check.epc.claims.refSignsInParens.pass",
        reference="Rule 43(7) EPC",
    )]


def _claim_subject(claim_text: str) -> str:
    """Return the subject noun(s) of a claim from its preamble.

    Heuristic: text between the leading article (A / An / The) and the
    first comma or "comprising" / "according to" boundary. Lower-cased
    for comparison. Returns empty string if no subject can be extracted.
    """
    # Strip leading article
    m = re.match(
        r"^\s*(?:A|An|The)\s+(.+?)(?=,|\s+comprising|\s+according to|\s+characteri[sz]ed|\s+wherein|$)",
        claim_text.strip(),
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return ""
    return m.group(1).strip().lower()


def check_subject_consistency_epc(claims: list[Claim]) -> list[CheckItem]:
    """Verify dependent claim subjects match their parent per Guidelines F-IV § 3.4.

    A dependent claim's preamble subject should match the parent claim
    (e.g., parent "An apparatus comprising..."; dep "The apparatus of
    claim 1, wherein..." — match). Mismatches like dep "The method of
    claim 1" pointing to apparatus parent are real drafting errors.
    REVIEW status — extraction is heuristic and FP on edge phrasings.
    """
    by_id = {c.id: c for c in claims}
    bad: list[int] = []
    for c in claims:
        if c.independent or not c.dependencies:
            continue
        dep_subject = _claim_subject(c.text)
        if not dep_subject:
            continue
        # Match against ANY parent (multi-dep need at least one match)
        any_match = False
        for parent_id in c.dependencies:
            parent = by_id.get(parent_id)
            if not parent:
                continue
            parent_subject = _claim_subject(parent.text)
            if not parent_subject:
                continue
            # Match if the dep subject head noun appears in the parent subject
            # (or vice versa) — very loose to keep FP rate low at v1.
            dep_head = dep_subject.split()[0] if dep_subject.split() else ""
            parent_head = parent_subject.split()[0] if parent_subject.split() else ""
            if dep_head and parent_head and (dep_head == parent_head or dep_head in parent_subject or parent_head in dep_subject):
                any_match = True
                break
        if not any_match:
            bad.append(c.id)
    if bad:
        return [CheckItem(
            status="verify",
            message=(
                f"Claim(s) {', '.join(str(i) for i in bad)} may have a subject "
                f"that does not match the parent claim — verify per Guidelines F-IV § 3.4."
            ),
            message_key="check.epc.claims.subjectConsistency.verify",
            details=", ".join(str(i) for i in bad),
            reference="EPO Guidelines F-IV § 3.4",
            diagnostics=_dx(
                flagged_count=len(bad),
                flagged_claim_id=bad[0],
            ),
        )]
    return [CheckItem(
        status="pass",
        message="Dependent-claim subjects match their parents.",
        message_key="check.epc.claims.subjectConsistency.pass",
        reference="EPO Guidelines F-IV § 3.4",
    )]


def check_transition_phrase_epc(claims: list[Claim]) -> list[CheckItem]:
    """Verify independent claims use an EPC-recognised transitional phrase.

    Guidelines F-IV § 4.13 recognises:
      - "comprising" / "comprises" / "including" / "containing" (open-ended)
      - "consisting of" (closed)
      - "consisting essentially of" (partly open)
      - "characterised in that" / "characterised by" (two-part form)
    Independent claims missing any of these are flagged for review.
    """
    bad: list[int] = []
    for c in claims:
        if not c.independent:
            continue
        if not _EPC_TRANSITION_RE.search(c.text):
            bad.append(c.id)
    if bad:
        return [CheckItem(
            status="verify",
            message=(
                f"Independent claim(s) {', '.join(str(i) for i in bad)} appear to lack "
                f"an EPC-recognised transitional phrase (comprising / consisting of / "
                f"characterised in that). Verify per Guidelines F-IV § 4.13."
            ),
            message_key="check.epc.claims.transitionPhrase.verify",
            details=", ".join(str(i) for i in bad),
            reference="EPO Guidelines F-IV § 4.13",
            diagnostics=_dx(
                flagged_count=len(bad),
                flagged_claim_id=bad[0],
            ),
        )]
    return [CheckItem(
        status="pass",
        message="All independent claims use an EPC-recognised transitional phrase.",
        message_key="check.epc.claims.transitionPhrase.pass",
        reference="EPO Guidelines F-IV § 4.13",
    )]


# ---------------------------------------------------------------------------
# G5 (cross-jurisdiction / format guards) checks
# ---------------------------------------------------------------------------


# Rule 43(6) EPC: claims must not reference description / drawings by
# paragraph or figure number. Common English forms drafters slip in:
#   - "see paragraph [0010]"
#   - "as described in paragraph 10"
#   - "with reference to Fig. 5"        ← in claim body, NOT as ref sign
#   - "as shown in Figure 3"
# The ref-signs-in-parens convention (Rule 43(7)) means a parenthesised
# "(see Fig. 5)" is acceptable; bare prose references like "shown in
# Fig. 5" inside a claim body are not.
_CLAIM_SPEC_REF_RE = re.compile(
    r"\b("
    r"see\s+paragraph\s+\[?\d+\]?"
    r"|as\s+(?:described|shown|illustrated|set\s+forth)\s+in\s+(?:paragraph|Figure|FIG\.?|Fig\.?)\s+\[?\d+\]?"
    r"|with\s+reference\s+to\s+(?:paragraph|Figure|FIG\.?|Fig\.?)\s+\[?\d+\]?"
    r"|in\s+paragraph\s+\[?\d+\]?"
    r")\b",
    re.IGNORECASE,
)


# Markush group format detection. EPC accepts the same "selected from the
# group consisting of A, B, and C" form as US. Guidelines F-IV § 4.20
# requires the closed-group format; "selected from A, B, or C" (without
# "the group consisting of") is technically incorrect.
_MARKUSH_GOOD_RE = re.compile(
    r"selected\s+from\s+(?:the\s+)?group\s+consisting\s+of\b",
    re.IGNORECASE,
)
_MARKUSH_BAD_RE = re.compile(
    r"selected\s+from\s+(?!(?:the\s+)?group\s+consisting\s+of)"
    r"(?:[\w\s,]+?)\s+(?:or|and)\b",
    re.IGNORECASE,
)


# Rule 43(1) two-part form: preamble + characterising portion. Detection
# looks for either "characterised in that" or "characterised by"
# anywhere in an independent claim. Advisory only — Rule 43(1) is
# "where appropriate", not mandatory.
_TWO_PART_RE = re.compile(
    r"\bcharacter(?:i[sz]ed)\s+(?:in\s+that|by)\b",
    re.IGNORECASE,
)


def check_claims_spec_reference_epc(claims: list[Claim]) -> list[CheckItem]:
    """Verify claims do not reference description / drawings per Rule 43(6) EPC.

    A claim that says "see paragraph [0010]" or "as shown in Fig. 5"
    violates Rule 43(6), which requires claims to be self-contained.
    Parenthesised reference signs per Rule 43(7) are fine; the check
    runs on text with parenthesised content stripped.
    """
    flagged: list[int] = []
    for c in claims:
        stripped = re.sub(r"\([^()]*\)", "", c.text)
        if _CLAIM_SPEC_REF_RE.search(stripped):
            flagged.append(c.id)
    if flagged:
        return [CheckItem(
            status="amend",
            message=(
                f"Claim(s) {', '.join(str(i) for i in flagged)} reference description "
                f"or drawings — Rule 43(6) EPC requires claims to be self-contained."
            ),
            message_key="check.epc.claims.specReference.amend",
            details=", ".join(str(i) for i in flagged),
            reference="Rule 43(6) EPC",
            diagnostics=_dx(
                flagged_count=len(flagged),
                flagged_claim_id=flagged[0],
            ),
        )]
    return [CheckItem(
        status="pass",
        message="No claim references description or drawings.",
        message_key="check.epc.claims.specReference.pass",
        reference="Rule 43(6) EPC",
    )]


def check_multi_dep_on_multi_dep_epc(claims: list[Claim]) -> list[CheckItem]:
    """Verify multi-dependent claims do not depend on other multi-dependent claims.

    Rule 43(4) EPC permits multi-dependent claims but does not allow
    a multi-dependent claim to depend on another multi-dependent claim
    (chained multi-dep). This mirrors the US MPEP § 608.01(n) prohibition.
    """
    by_id = {c.id: c for c in claims}
    bad: list[int] = []
    for c in claims:
        if not c.multiple_dependent:
            continue
        # Check whether any parent is itself multi-dep
        for parent_id in c.dependencies:
            parent = by_id.get(parent_id)
            if parent and parent.multiple_dependent:
                bad.append(c.id)
                break
    if bad:
        return [CheckItem(
            status="amend",
            message=(
                f"Claim(s) {', '.join(str(i) for i in bad)} are multi-dependent claims "
                f"that depend on another multi-dependent claim — Rule 43(4) EPC prohibits this."
            ),
            message_key="check.epc.claims.multiDepOnMultiDep.amend",
            details=", ".join(str(i) for i in bad),
            reference="Rule 43(4) EPC",
            diagnostics=_dx(
                flagged_count=len(bad),
                flagged_claim_id=bad[0],
            ),
        )]
    return [CheckItem(
        status="pass",
        message="No multi-dependent claim depends on another multi-dependent claim.",
        message_key="check.epc.claims.multiDepOnMultiDep.pass",
        reference="Rule 43(4) EPC",
    )]


def check_markush_format_epc(claims: list[Claim]) -> list[CheckItem]:
    """Verify Markush group format per Guidelines F-IV § 4.20.

    EPO accepts "selected from the group consisting of A, B, and C"
    (closed Markush). Forms like "selected from A, B, or C" without the
    "group consisting of" phrasing are technically open-ended and
    flagged for review.
    """
    bad: list[int] = []
    for c in claims:
        if _MARKUSH_BAD_RE.search(c.text) and not _MARKUSH_GOOD_RE.search(c.text):
            bad.append(c.id)
    if bad:
        return [CheckItem(
            status="verify",
            message=(
                f"Claim(s) {', '.join(str(i) for i in bad)} use a Markush-style "
                f"alternative that may need the closed 'selected from the group "
                f"consisting of' form per Guidelines F-IV § 4.20."
            ),
            message_key="check.epc.claims.markushFormat.verify",
            details=", ".join(str(i) for i in bad),
            reference="EPO Guidelines F-IV § 4.20",
            diagnostics=_dx(
                flagged_count=len(bad),
                flagged_claim_id=bad[0],
            ),
        )]
    return [CheckItem(
        status="pass",
        message="Markush groups (if any) use the closed format.",
        message_key="check.epc.claims.markushFormat.pass",
        reference="EPO Guidelines F-IV § 4.20",
    )]


def check_independent_claim_count_epc(claims: list[Claim]) -> list[CheckItem]:
    """Advisory check on independent claim count per Rule 43(2) EPC.

    Rule 43(2) limits a European patent application to one independent
    claim per category (product / process / apparatus / use) unless one
    of the four Rule 43(3) exceptions applies:
      (a) interrelated products
      (b) different uses of a product or apparatus
      (c) alternative solutions to a particular problem
    Detection of the exceptions is high-FP risk, so v1 emits a REVIEW
    advisory when more than one independent claim exists in any single
    category, with no attempt to identify which Rule 43(3) exception
    might apply.
    """
    independents = [c for c in claims if c.independent]
    if len(independents) <= 1:
        return [CheckItem(
            status="pass",
            message="Single independent claim — Rule 43(2) EPC satisfied.",
            message_key="check.epc.claims.independentClaimCount.pass",
            reference="Rule 43(2) EPC",
        )]
    # Crude category split: method vs non-method
    methods = sum(1 for c in independents if c.method_claim)
    non_methods = len(independents) - methods
    if methods > 1 or non_methods > 1:
        return [CheckItem(
            status="verify",
            message=(
                f"Found {len(independents)} independent claims ({methods} method, "
                f"{non_methods} non-method). Rule 43(2) EPC limits to one "
                f"independent claim per category unless a Rule 43(3) exception "
                f"applies (interrelated products / different uses / alternative "
                f"solutions). Verify."
            ),
            message_key="check.epc.claims.independentClaimCount.verify",
            reference="Rule 43(2) EPC; Rule 43(3) EPC",
            diagnostics=_dx(
                independent_count=len(independents),
                method_count=methods,
                non_method_count=non_methods,
            ),
        )]
    return [CheckItem(
        status="pass",
        message="Independent claim count per category satisfies Rule 43(2) EPC.",
        message_key="check.epc.claims.independentClaimCount.pass",
        reference="Rule 43(2) EPC",
    )]


def check_two_part_form_epc(claims: list[Claim]) -> list[CheckItem]:
    """Advisory check on Rule 43(1) two-part form (where appropriate).

    Rule 43(1) recommends — but does not require — the two-part form
    (preamble + "characterised in that" + characterising portion) for
    independent claims defining an invention over closest prior art.
    Detection looks for the phrase in any independent claim. Status
    'pass' when ≥1 independent claim uses two-part form; 'verify' when
    no independent claim does (advisory: drafter may want to consider
    it). Never 'amend' — Rule 43(1) is conditional.
    """
    independents = [c for c in claims if c.independent]
    if not independents:
        return [CheckItem(
            status="pass",
            message="No independent claims to check for two-part form.",
            message_key="check.epc.claims.twoPartForm.pass",
            reference="Rule 43(1) EPC",
        )]
    has_two_part = any(_TWO_PART_RE.search(c.text) for c in independents)
    if has_two_part:
        return [CheckItem(
            status="pass",
            message="At least one independent claim uses the two-part form per Rule 43(1) EPC.",
            message_key="check.epc.claims.twoPartForm.pass",
            reference="Rule 43(1) EPC",
        )]
    return [CheckItem(
        status="verify",
        message=(
            "No independent claim uses the two-part form (preamble + "
            "'characterised in that'). Rule 43(1) EPC recommends this form "
            "where appropriate; verify whether the closest prior art warrants it."
        ),
        message_key="check.epc.claims.twoPartForm.verify",
        reference="Rule 43(1) EPC",
        diagnostics=_dx(independent_count=len(independents)),
    )]


def run_g5_claims_cross_jurisdiction_checks(claims: list[Claim]) -> list[CheckItem]:
    """Run all G5 claims-cross-jurisdiction checks.

      1. claimsSpecReference
      2. multiDepOnMultiDep
      3. markushFormat
      4. independentClaimCount (advisory)
      5. twoPartForm (advisory)
    """
    results: list[CheckItem] = []
    results.extend(check_claims_spec_reference_epc(claims))
    results.extend(check_multi_dep_on_multi_dep_epc(claims))
    results.extend(check_markush_format_epc(claims))
    results.extend(check_independent_claim_count_epc(claims))
    results.extend(check_two_part_form_epc(claims))
    return results


def run_g4_claims_structure_checks(claims: list[Claim]) -> list[CheckItem]:
    """Run all G4 claims-structure checks in canonical 7-group order.

      1. claimsSequential
      2. dependencyFormat
      3. selfDependent
      4. forwardDependency
      5. singleSentencePerClaim
      6. refSignsInParens
      7. subjectConsistency
      8. transitionPhrase
    """
    results: list[CheckItem] = []
    results.extend(check_claims_sequential_epc(claims))
    results.extend(check_dependency_format_epc(claims))
    results.extend(check_self_dependent_epc(claims))
    results.extend(check_forward_dependency_epc(claims))
    results.extend(check_single_sentence_per_claim_epc(claims))
    results.extend(check_reference_signs_in_parens_epc(claims))
    results.extend(check_subject_consistency_epc(claims))
    results.extend(check_transition_phrase_epc(claims))
    return results
