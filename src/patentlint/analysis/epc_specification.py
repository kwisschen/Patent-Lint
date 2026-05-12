# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""EPC specification-level checks (G1 + G2 in the canonical 7-group order).

G1 (structure) — shipped:
  - check_required_sections_epc  — Art. 78(1) + Rule 41 + Rule 42(1) EPC
  - check_section_ordering_epc   — Rule 42(1) EPC canonical order
  - check_paragraph_numbering_epc — EPO Guidelines F-II § 4.5 (advisory)
  - check_paragraph_ending_epc   — drafting hygiene (REVIEW status)
  - check_title_required_epc     — Rule 41(2)(b) EPC

G2 (content) — pending:
  - check_figure_ref_consistency_epc — Rule 46(2)(h)
  - check_numeral_consistency_epc    — Rule 46(2)(h) + Rule 43(7)
  - check_claim_reference_in_spec_epc — Guidelines F-IV § 4.3

Each check returns a list of CheckItem dicts following the same shape as
the US / CN / TW jurisdictions. The walker-uncertainty hedge applies to
the antecedent + spec-support walkers (G6, separate module) — these G1
structural checks are FIX-status because the Rule 42(1) requirement is
unambiguous.
"""

from __future__ import annotations

import re

from patentlint.analysis.utils import _dx
from patentlint.models import CheckItem
from patentlint.parser.sections_epc import (
    _EPC_ANY_HEADER,
    extract_abstract_section_epc,
    extract_background_section_epc,
    extract_claims_section_epc,
    extract_detailed_description_section_epc,
    extract_drawings_description_section_epc,
    extract_summary_section_epc,
    extract_technical_field_section_epc,
    extract_title_epc,
)


# Canonical EPC description sub-section order per Rule 42(1) EPC.
# Index in this list is the canonical position; section_ordering check
# flags anything that violates monotonic-non-decreasing position.
_EPC_DESCRIPTION_ORDER = [
    "technical_field",       # Rule 42(1)(a)
    "background_art",        # Rule 42(1)(b)
    "summary",               # Rule 42(1)(c) — disclosure of invention
    "drawings_description",  # Rule 42(1)(d) — when drawings exist
    "detailed_description",  # Rule 42(1)(e) — embodiments / ways of carrying out
]


def check_title_required_epc(full_text: str) -> list[CheckItem]:
    """Verify a title is present per Rule 41(2)(b) EPC.

    Rule 41(2)(b) requires the request for grant to include the title of
    the invention. A draft missing a title fails this requirement. The
    title is identified as the text preceding the first recognised
    section header (same heuristic as the US extractor).
    """
    title = extract_title_epc(full_text)
    if not title:
        return [CheckItem(
            status="amend",
            message="Title missing — EPC Rule 41(2)(b) requires a title of the invention.",
            message_key="check.epc.spec.titleRequired.amend",
            reference="Rule 41(2)(b) EPC",
            diagnostics=_dx(title_charlen=0),
        )]
    # Sanity bound — a title shouldn't be a whole paragraph
    if len(title) > 500:
        return [CheckItem(
            status="verify",
            message="Title appears unusually long; verify it identifies the invention concisely.",
            message_key="check.epc.spec.titleRequired.verify",
            reference="Rule 41(2)(b) EPC",
            diagnostics=_dx(title_charlen=len(title)),
        )]
    return [CheckItem(
        status="pass",
        message="Title present per EPC Rule 41(2)(b).",
        message_key="check.epc.spec.titleRequired.pass",
        reference="Rule 41(2)(b) EPC",
    )]


def check_required_sections_epc(full_text: str) -> list[CheckItem]:
    """Verify required sections per Art. 78(1) + Rule 41 + Rule 42(1) EPC.

    Required at v1:
      - Title (Rule 41(2)(b))
      - Description (at least one Rule 42(1) sub-section detected)
      - Claims (Art. 78(1)(c))
      - Abstract (Art. 78(1)(e) + Rule 47)

    Brief Description of the Drawings is conditionally required when the
    draft contains drawings (Rule 46(2)(h) — the description shall briefly
    describe the figures). v1 detects drawings via the standalone heading
    presence; figure-text-anchored detection lands once the EPC fig-ref
    extractor ships in G2.
    """
    title_present = bool(extract_title_epc(full_text))
    background_present = bool(extract_background_section_epc(full_text))
    technical_field_present = bool(extract_technical_field_section_epc(full_text))
    summary_present = bool(extract_summary_section_epc(full_text))
    detailed_present = bool(extract_detailed_description_section_epc(full_text))
    drawings_desc_present = bool(extract_drawings_description_section_epc(full_text))
    claims_present = bool(extract_claims_section_epc(full_text))
    abstract_present = bool(extract_abstract_section_epc(full_text))

    description_present = any([
        technical_field_present,
        background_present,
        summary_present,
        detailed_present,
    ])

    section_results: dict[str, bool] = {
        "Title": title_present,
        "Description": description_present,
        "Claims": claims_present,
        "Abstract": abstract_present,
    }
    if drawings_desc_present:
        # Brief description of drawings being PRESENT is fine; the check
        # only flags it as missing when drawings exist but the section
        # is absent. v1 cannot reliably detect figure references yet,
        # so we only enforce when the heading is missing AND a drawings
        # heading was found upstream (handled by future G3 check).
        pass

    missing = [name for name, ok in section_results.items() if not ok]

    if missing:
        return [CheckItem(
            status="amend",
            message=f"Missing required sections per EPC Art. 78(1): {', '.join(missing)}.",
            message_key="check.epc.spec.requiredSections.amend",
            details=", ".join(missing),
            details_key="details.missingSections",
            details_params={
                "list": ", ".join(missing),
                "flagged_phrases": {
                    "items": [{"kind": "section", "token": s} for s in missing]
                },
            },
            reference="Art. 78(1) EPC; Rule 41(2)(b) EPC; Rule 42(1) EPC; Rule 47 EPC",
            diagnostics=_dx(
                missing_count=len(missing),
                missing_sections=missing,
                first_missing=missing[0],
            ),
        )]
    return [CheckItem(
        status="pass",
        message="Required sections per EPC Art. 78(1) + Rule 42(1) are present.",
        message_key="check.epc.spec.requiredSections.pass",
        reference="Art. 78(1) EPC; Rule 42(1) EPC",
    )]


def check_section_ordering_epc(full_text: str) -> list[CheckItem]:
    """Verify description sub-sections appear in Rule 42(1) EPC canonical order.

    Rule 42(1) lists the description sub-sections (a)–(e); EPC examiners
    flag drafts whose headers run out of order. We collect the start
    position of each detected sub-section header and check that the
    sequence is monotonically non-decreasing in canonical order.
    """
    starts: dict[str, int] = {}
    if (m := re.search(
        r"^[ \t]*(?:TECHNICAL\s+FIELD|FIELD\s+OF\s+THE\s+(?:INVENTION|DISCLOSURE))[ \t]*$",
        full_text, re.IGNORECASE | re.MULTILINE,
    )):
        starts["technical_field"] = m.start()
    if (m := re.search(
        r"^[ \t]*BACKGROUND(?:\s+(?:OF\s+(?:THE\s+)?)?(?:DISCLOSURE|INVENTION|ART))?[ \t]*$",
        full_text, re.IGNORECASE | re.MULTILINE,
    )):
        starts["background_art"] = m.start()
    if (m := re.search(
        r"^[ \t]*(?:BRIEF\s+)?SUMMARY(?:\s+OF\s+(?:THE\s+)?(?:INVENTION|DISCLOSURE))?[ \t]*$",
        full_text, re.IGNORECASE | re.MULTILINE,
    )):
        starts["summary"] = m.start()
    elif (m := re.search(
        r"^[ \t]*DISCLOSURE\s+OF\s+(?:THE\s+)?INVENTION[ \t]*$",
        full_text, re.IGNORECASE | re.MULTILINE,
    )):
        starts["summary"] = m.start()
    if (m := re.search(
        r"^[ \t]*(?:BRIEF\s+)?DESCRIPTION\s+OF\s+(?:THE\s+)?(?:DRAWINGS|FIGURES)[ \t]*$",
        full_text, re.IGNORECASE | re.MULTILINE,
    )):
        starts["drawings_description"] = m.start()
    if (m := re.search(
        r"^[ \t]*DETAILED\s+DESCRIPTION(?:\s+.*)?[ \t]*$",
        full_text, re.IGNORECASE | re.MULTILINE,
    )):
        starts["detailed_description"] = m.start()

    if len(starts) < 2:
        # Not enough sub-sections to evaluate ordering — pass through.
        return [CheckItem(
            status="pass",
            message="Section ordering check skipped (insufficient sub-sections to evaluate).",
            message_key="check.epc.spec.sectionOrdering.pass",
            reference="Rule 42(1) EPC",
        )]

    observed_order = sorted(starts.keys(), key=lambda k: starts[k])
    expected_position = {k: i for i, k in enumerate(_EPC_DESCRIPTION_ORDER)}
    canonical_subset = sorted(observed_order, key=lambda k: expected_position[k])

    if observed_order != canonical_subset:
        return [CheckItem(
            status="amend",
            message=(
                f"Description sub-sections out of EPC Rule 42(1) order. "
                f"Observed: {' → '.join(observed_order)}. "
                f"Expected: {' → '.join(canonical_subset)}."
            ),
            message_key="check.epc.spec.sectionOrdering.amend",
            reference="Rule 42(1) EPC",
            diagnostics=_dx(
                observed_order=observed_order,
                expected_order=canonical_subset,
            ),
        )]
    return [CheckItem(
        status="pass",
        message="Description sub-sections appear in Rule 42(1) EPC canonical order.",
        message_key="check.epc.spec.sectionOrdering.pass",
        reference="Rule 42(1) EPC",
    )]


def check_paragraph_numbering_epc(full_text: str) -> list[CheckItem]:
    """Advisory check on paragraph numbering (EPO Guidelines F-II § 4.5).

    EPC does NOT mandate sequential [0001]-style paragraph numbering the
    way US MPEP § 608.01(p) does. EPO Guidelines F-II § 4.5 mentions
    paragraph numbering as recommended for clarity but not required. v1
    emits a REVIEW-status advisory when paragraph numbers are present
    but non-sequential; absence of numbering is not flagged.
    """
    # Detect [0001]-style paragraph numbers
    numbers = [int(m.group(1)) for m in re.finditer(r"\[(\d{4})\]", full_text)]
    if not numbers:
        return [CheckItem(
            status="pass",
            message="No paragraph numbering detected — EPC does not mandate paragraph numbers.",
            message_key="check.epc.spec.paragraphNumbering.pass",
            reference="EPO Guidelines F-II § 4.5",
        )]
    # Check sequential
    expected = list(range(numbers[0], numbers[0] + len(numbers)))
    if numbers != expected:
        # Find the first non-sequential index
        first_gap = next(
            (i for i, (got, want) in enumerate(zip(numbers, expected)) if got != want),
            None,
        )
        return [CheckItem(
            status="verify",
            message=(
                f"Paragraph numbers detected but not strictly sequential. "
                f"Starting at [{numbers[0]:04d}], expected up to [{expected[-1]:04d}]; "
                f"found {len(numbers)} numbers ending at [{numbers[-1]:04d}]."
            ),
            message_key="check.epc.spec.paragraphNumbering.verify",
            reference="EPO Guidelines F-II § 4.5",
            diagnostics=_dx(
                total_numbers=len(numbers),
                first_number=numbers[0],
                last_number=numbers[-1],
                first_gap_index=first_gap,
            ),
        )]
    return [CheckItem(
        status="pass",
        message=f"Paragraph numbers sequential from [{numbers[0]:04d}] to [{numbers[-1]:04d}].",
        message_key="check.epc.spec.paragraphNumbering.pass",
        reference="EPO Guidelines F-II § 4.5",
    )]


def check_paragraph_ending_epc(full_text: str) -> list[CheckItem]:
    """Advisory check on paragraph-ending punctuation (drafting hygiene).

    No specific EPC rule mandates paragraph terminal punctuation. The
    check emits REVIEW status only and surfaces paragraphs whose final
    non-whitespace character isn't a standard terminator (. ! ? : ;).
    Operates on the description body only — the title and claims have
    their own conventions and are excluded.
    """
    from patentlint.parser.sections_epc import extract_description_section_epc

    description = extract_description_section_epc(full_text)
    if not description:
        return [CheckItem(
            status="pass",
            message="No description body extracted to check.",
            message_key="check.epc.spec.paragraphEnding.pass",
        )]
    paragraphs = [p.strip() for p in description.split("\n\n") if p.strip()]
    if not paragraphs:
        return [CheckItem(
            status="pass",
            message="No paragraphs to check.",
            message_key="check.epc.spec.paragraphEnding.pass",
        )]

    valid_endings = (".", "!", "?", ":", ";")
    flagged: list[int] = []
    for i, para in enumerate(paragraphs, start=1):
        # Skip standalone section headers
        if _EPC_ANY_HEADER.match(para):
            continue
        # Skip paragraphs that are just figure labels, claim numbers, etc.
        if re.fullmatch(r"\[\d+\]|FIG\.\s*\d+\w?|Fig\.\s*\d+\w?", para):
            continue
        if not para.endswith(valid_endings):
            flagged.append(i)

    if flagged:
        return [CheckItem(
            status="verify",
            message=(
                f"{len(flagged)} paragraph(s) end without standard terminal punctuation. "
                f"This is a drafting-hygiene advisory; no specific EPC rule mandates it."
            ),
            message_key="check.epc.spec.paragraphEnding.verify",
            details=", ".join(str(n) for n in flagged[:20]),
            diagnostics=_dx(
                flagged_count=len(flagged),
                total_paragraphs=len(paragraphs),
                first_flagged=flagged[0] if flagged else None,
            ),
        )]
    return [CheckItem(
        status="pass",
        message="All paragraphs end with standard terminal punctuation.",
        message_key="check.epc.spec.paragraphEnding.pass",
    )]


def run_g1_spec_structure_checks(full_text: str) -> list[CheckItem]:
    """Run all G1 spec-structure checks in canonical 7-group order.

    Order matches the documented seven-group emission discipline
    (CLAUDE.md § Check-ordering consistency invariant):
      1. requiredSections
      2. sectionOrdering
      3. paragraphNumbering
      4. paragraphEnding

    titleRequired emits in G2 (run_g2_spec_content_checks) per canonical
    bucket placement — title is a G2 SPEC_CONTENT check.
    """
    results: list[CheckItem] = []
    results.extend(check_required_sections_epc(full_text))
    results.extend(check_section_ordering_epc(full_text))
    results.extend(check_paragraph_numbering_epc(full_text))
    results.extend(check_paragraph_ending_epc(full_text))
    return results


# ---------------------------------------------------------------------------
# G2 (content) checks
# ---------------------------------------------------------------------------


# Spec-body references to claims, prohibited per EPO Guidelines F-IV § 4.3.
# Captures the common English forms EPC drafters slip into:
#   - "as claimed in claim 5"
#   - "according to claim 3"
#   - "in claim 7"
#   - "claim 2 specifies"
#   - "claims 1 to 5"
# Case-insensitive at match time so capitalization variants land too.
_EPC_CLAIM_REF_RE = re.compile(
    r"\b(?:"
    r"as\s+claimed\s+in\s+claims?\s+\d+"
    r"|according\s+to\s+claims?\s+\d+"
    r"|in\s+claims?\s+\d+(?:\s+to\s+\d+)?\s+(?:above|herein|specifies|recites|requires|provides|states)"
    r"|claims?\s+\d+(?:\s+to\s+\d+)?\s+(?:above|specifies|recites|requires|provides|states)"
    r"|recited\s+in\s+claims?\s+\d+"
    r"|set\s+forth\s+in\s+claims?\s+\d+"
    r")\b",
    re.IGNORECASE,
)


def check_figure_ref_consistency_epc(full_text: str) -> list[CheckItem]:
    """Verify figure references are consistent per Rule 46(2)(h) EPC.

    Rule 46(2)(h) requires the description to refer to each figure of the
    drawings; reuses the US figure-cross-reference helper, which extracts
    Fig./FIG./Figure references and compares the brief description of
    drawings against the detailed description body.
    """
    from patentlint.analysis.drawings import check_figure_cross_references
    from patentlint.parser.sections_epc import (
        extract_detailed_description_section_epc,
        extract_drawings_description_section_epc,
    )

    brief = extract_drawings_description_section_epc(full_text)
    detailed = extract_detailed_description_section_epc(full_text)
    results = check_figure_cross_references(brief, detailed)
    if not results:
        return [CheckItem(
            status="pass",
            message="No figure references detected — figure-reference consistency is vacuously satisfied.",
            message_key="check.epc.spec.figureRefConsistency.pass",
            reference="Rule 46(2)(h) EPC",
        )]
    # Re-key US `checks.figure_xref_*` (snake_case) into the EPC namespace
    # and override the reference. The US helper emits keys whose i18n
    # entries cite MPEP § 608.02; without the re-key, EPC-jurisdiction
    # users see MPEP text in their results.
    _XREF_KEY_MAP = {
        "checks.figure_xref_orphaned_brief": "check.epc.spec.figureRefConsistency.orphanedBrief.amend",
        "checks.figure_xref_orphaned_detailed": "check.epc.spec.figureRefConsistency.orphanedDetailed.amend",
        "checks.figure_xref_pass": "check.epc.spec.figureRefConsistency.pass",
    }
    re_keyed: list[CheckItem] = []
    for item in results:
        re_keyed.append(CheckItem(
            status=item.status,
            message=item.message,
            message_key=_XREF_KEY_MAP.get(item.message_key, item.message_key),
            details=item.details,
            details_key=item.details_key,
            details_params=item.details_params,
            reference="Rule 46(2)(h) EPC",
            diagnostics=item.diagnostics,
        ))
    return re_keyed


def check_numeral_consistency_epc(full_text: str) -> list[CheckItem]:
    """D1-style numeral consistency per Rule 43(7) EPC.

    Rule 43(7) EPC specifies reference signs in claims appear in
    parentheses and that they tie back to the description; reuses the US
    D1 detector for same-numeral / different-name conflicts in the spec
    body. The check fires when one numeral is paired with two or more
    disjoint element names (a typo / copy-paste bug signal).
    """
    from patentlint.analysis.specification import check_numeral_consistency
    from patentlint.parser.sections_epc import extract_description_section_epc

    description = extract_description_section_epc(full_text)
    results = check_numeral_consistency(description)
    re_keyed: list[CheckItem] = []
    for item in results:
        re_keyed.append(CheckItem(
            status=item.status,
            message=item.message,
            message_key=item.message_key.replace("check.spec.numeralConsistency", "check.epc.spec.numeralConsistency"),
            details=item.details,
            details_key=item.details_key,
            details_params=item.details_params,
            reference="Rule 43(7) EPC; Rule 46(2)(h) EPC",
            diagnostics=item.diagnostics,
        ))
    return re_keyed


def check_claim_reference_in_spec_epc(full_text: str) -> list[CheckItem]:
    """Flag spec text that references claims by number (Guidelines F-IV § 4.3).

    EPO examiners cite Guidelines F-IV § 4.3 against descriptions that
    contain phrases like "as claimed in claim 5" — the description must
    stand on its own and not rely on the claims for clarity. Detection
    runs on the extracted description body so that the title and claims
    themselves are not scanned.
    """
    from patentlint.parser.sections_epc import extract_description_section_epc

    description = extract_description_section_epc(full_text)
    if not description:
        return [CheckItem(
            status="pass",
            message="No description body to check.",
            message_key="check.epc.spec.claimReferenceInSpec.pass",
            reference="EPO Guidelines F-IV § 4.3",
        )]
    match = _EPC_CLAIM_REF_RE.search(description)
    if match:
        snippet = match.group()[:80]
        return [CheckItem(
            status="amend",
            message="Description references a specific claim — Guidelines F-IV § 4.3 requires the description to stand on its own.",
            message_key="check.epc.spec.claimReferenceInSpec.amend",
            details=snippet,
            details_key="details.epc.claimReferenceInSpec",
            details_params={"detail": snippet},
            reference="EPO Guidelines F-IV § 4.3",
            diagnostics=_dx(
                snippet_charlen=len(snippet),
                matched_phrase=match.group()[:80],
                match_position=match.start(),
                description_charlen=len(description),
            ),
        )]
    return [CheckItem(
        status="pass",
        message="No claim references found in description.",
        message_key="check.epc.spec.claimReferenceInSpec.pass",
        reference="EPO Guidelines F-IV § 4.3",
    )]


def run_g2_spec_content_checks(full_text: str) -> list[CheckItem]:
    """Run all G2 spec-content checks in canonical 7-group order.

      1. figureRefConsistency (idx 10)
      2. numeralConsistency (idx 15)
      3. titleRequired (idx 30) — emitted here, not in run_g1, to keep
         the spec_checks emission monotonic in canonical (group, idx)
      4. claimReferenceInSpec (idx 40)
    """
    results: list[CheckItem] = []
    results.extend(check_figure_ref_consistency_epc(full_text))
    results.extend(check_numeral_consistency_epc(full_text))
    results.extend(check_title_required_epc(full_text))
    results.extend(check_claim_reference_in_spec_epc(full_text))
    return results
