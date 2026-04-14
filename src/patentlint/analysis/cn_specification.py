# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""CN specification analysis checks.

Eight pure functions checking Chinese patent specification formatting
against CNIPA rules (专利法实施细则 and 审查指南).
"""

from __future__ import annotations

import re

from patentlint.models import CheckItem, CnPatentDocument

# Canonical section order per 专利法实施细则 §17
_CANONICAL_ORDER = [
    "technical_field",
    "background",
    "summary",
    "drawings_description",
    "detailed_description",
]

_SECTION_NAMES_CN = {
    "technical_field": "技术领域",
    "background": "背景技术",
    "summary": "发明内容",
    "drawings_description": "附图说明",
    "detailed_description": "具体实施方式",
}

_VALID_ENDINGS = frozenset("。！？：")


def _all_paragraphs(cn_doc: CnPatentDocument) -> list[str]:
    """Collect all spec paragraphs from the five body sections."""
    return (
        cn_doc.technical_field
        + cn_doc.background
        + cn_doc.summary
        + cn_doc.drawings_description
        + cn_doc.detailed_description
    )


def _all_spec_text(cn_doc: CnPatentDocument) -> str:
    """Join all spec paragraphs into a single string."""
    return "\n".join(_all_paragraphs(cn_doc))


# ── Check 1 ──────────────────────────────────────────────────────────────


def check_required_sections(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Check that the four mandatory spec sections are non-empty."""
    required = ["technical_field", "background", "summary", "detailed_description"]
    missing = []
    for field in required:
        paragraphs = getattr(cn_doc, field)
        if not any(p.strip() for p in paragraphs):
            missing.append(_SECTION_NAMES_CN[field])

    if missing:
        return [CheckItem(
            status="amend",
            message=f"Missing required sections: {', '.join(missing)}",
            message_key="check.cn.spec.requiredSections.amend",
            details=", ".join(missing),
            details_key="details.cn.requiredSections",
            details_params={"sections": ", ".join(missing)},
            reference="专利法实施细则 §17",
        )]
    return [CheckItem(
        status="pass",
        message="All required specification sections are present.",
        message_key="check.cn.spec.requiredSections.pass",
        reference="专利法实施细则 §17",
    )]


# ── Check 2 ──────────────────────────────────────────────────────────────


def check_section_ordering(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Verify sections appear in canonical CNIPA order."""
    present = []
    for idx, field in enumerate(_CANONICAL_ORDER):
        paragraphs = getattr(cn_doc, field)
        if any(p.strip() for p in paragraphs):
            present.append(idx)

    is_sorted = all(present[i] < present[i + 1] for i in range(len(present) - 1))

    if not is_sorted:
        return [CheckItem(
            status="amend",
            message="Specification sections are not in the required order.",
            message_key="check.cn.spec.sectionOrdering.amend",
            details_key="details.cn.sectionOrdering",
            reference="专利法实施细则 §17",
        )]
    return [CheckItem(
        status="pass",
        message="Specification sections are in the correct order.",
        message_key="check.cn.spec.sectionOrdering.pass",
        reference="专利法实施细则 §17",
    )]


# ── Check 3 ──────────────────────────────────────────────────────────────


def check_paragraph_numbering(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Check paragraph numbering rules (XML: sequential; docx: none allowed)."""
    if cn_doc.input_format == "xml":
        nums = cn_doc.paragraph_numbers
        if nums:
            for i in range(1, len(nums)):
                if nums[i] != nums[i - 1] + 1:
                    return [CheckItem(
                        status="amend",
                        message=f"Paragraph numbering has a gap: paragraph {nums[i - 1]} is followed by {nums[i]}.",
                        message_key="check.cn.spec.paragraphNumbering.amendXmlGap",
                        details_key="details.cn.paragraphNumberingXml",
                        details_params={"prev": nums[i - 1], "next": nums[i]},
                        reference="审查指南",
                    )]
            # Check for duplicates
            if len(set(nums)) != len(nums):
                return [CheckItem(
                    status="amend",
                    message="Duplicate paragraph numbers detected.",
                    message_key="check.cn.spec.paragraphNumbering.amendXmlDuplicate",
                    details_key="details.cn.paragraphNumberingXml",
                    reference="审查指南",
                )]
    elif cn_doc.input_format == "docx":
        if cn_doc.has_paragraph_numbering:
            return [CheckItem(
                status="amend",
                message="Manual paragraph numbering found in .docx — CNIPA forbids this.",
                message_key="check.cn.spec.paragraphNumbering.amendDocx",
                details_key="details.cn.paragraphNumberingDocx",
                reference="审查指南",
            )]

    return [CheckItem(
        status="pass",
        message="Paragraph numbering is correct.",
        message_key="check.cn.spec.paragraphNumbering.pass",
        reference="审查指南",
    )]


# ── Check 4 ──────────────────────────────────────────────────────────────


def check_paragraph_ending(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Check each paragraph ends with valid Chinese punctuation."""
    bad_count = 0
    for para in _all_paragraphs(cn_doc):
        stripped = para.strip()
        if not stripped:
            continue
        last_char = stripped[-1]
        if last_char not in _VALID_ENDINGS:
            bad_count += 1

    if bad_count:
        return [CheckItem(
            status="amend",
            message=f"{bad_count} paragraph(s) have invalid ending punctuation.",
            message_key="check.cn.spec.paragraphEnding.amend",
            details=f"{bad_count} paragraphs",
            details_key="details.cn.paragraphEnding",
            details_params={"count": str(bad_count)},
            reference="审查指南",
        )]
    return [CheckItem(
        status="pass",
        message="All paragraphs have valid ending punctuation.",
        message_key="check.cn.spec.paragraphEnding.pass",
        reference="审查指南",
    )]


# ── Check 5 ──────────────────────────────────────────────────────────────

_FIGURE_REF_RE = re.compile(r"图\s*(\d+)")


def check_figure_reference_consistency(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Compare figure references between 附图说明 and 具体实施方式."""
    drawings_text = "\n".join(cn_doc.drawings_description)
    detail_text = "\n".join(cn_doc.detailed_description)

    if not drawings_text.strip() and not detail_text.strip():
        return [CheckItem(
            status="pass",
            message="No drawings sections to check.",
            message_key="check.cn.spec.figureRefConsistency.pass",
            reference="审查指南",
        )]

    drawings_figs = set(_FIGURE_REF_RE.findall(drawings_text))
    detail_figs = set(_FIGURE_REF_RE.findall(detail_text))

    only_drawings = sorted(drawings_figs - detail_figs, key=int)
    only_detail = sorted(detail_figs - drawings_figs, key=int)

    if only_drawings or only_detail:
        return [CheckItem(
            status="verify",
            message="Figure references differ between 附图说明 and 具体实施方式.",
            message_key="check.cn.spec.figureRefConsistency.verify",
            details_key="details.cn.figureRefConsistency",
            details_params={
                "figure_ref_inconsistency": {
                    "only_drawings": [int(x) for x in only_drawings],
                    "only_embodiment": [int(x) for x in only_detail],
                    "jurisdiction": "cn",
                },
            },
            reference="审查指南",
        )]

    return [CheckItem(
        status="pass",
        message="Figure references are consistent across sections.",
        message_key="check.cn.spec.figureRefConsistency.pass",
        reference="审查指南",
    )]


# ── Check 6 ──────────────────────────────────────────────────────────────


def check_patent_type_terminology(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Flag mixed 本发明 / 本实用新型 usage."""
    text = _all_spec_text(cn_doc)
    has_invention = "本发明" in text
    has_utility = "本实用新型" in text

    if has_invention and has_utility:
        # Determine minority term
        inv_count = text.count("本发明")
        util_count = text.count("本实用新型")
        minority = "本实用新型" if inv_count >= util_count else "本发明"
        return [CheckItem(
            status="verify",
            message="Mixed patent type terminology found.",
            message_key="check.cn.spec.patentTypeTerminology.verify",
            details=f"Minority term: {minority}",
            details_key="details.cn.patentTypeTerminology",
            details_params={"term": minority},
            reference="审查指南",
        )]

    return [CheckItem(
        status="pass",
        message="Patent type terminology is consistent.",
        message_key="check.cn.spec.patentTypeTerminology.pass",
        reference="审查指南",
    )]


# ── Check 7 ──────────────────────────────────────────────────────────────

_CJK_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")
_TRADEMARK_RE = re.compile(r"[®™©]")
_COMMERCIAL_PATTERN = re.compile(
    r"[A-Z0-9]{2,}-\d{2,}|(?:Model|型号)",
    re.IGNORECASE,
)


def check_title(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Check title length and prohibited content."""
    title = cn_doc.title
    if not title.strip():
        return [CheckItem(
            status="amend",
            message="Title is missing.",
            message_key="check.cn.spec.title.amendMissing",
            details_key="details.cn.titleMissing",
            details="",
            reference="审查指南 第一部分第一章",
        )]

    results: list[CheckItem] = []

    # Length check
    cjk_count = len(_CJK_CHAR_RE.findall(title))
    if cjk_count > 25:
        results.append(CheckItem(
            status="amend",
            message=f"Title has {cjk_count} Chinese characters (max 25).",
            message_key="check.cn.spec.title.amendLength",
            details_key="details.cn.titleLength",
            details_params={"count": cjk_count},
            reference="审查指南 第一部分第一章",
        ))

    # Content check
    items: list[dict] = []
    tm_match = _TRADEMARK_RE.search(title)
    if tm_match:
        items.append({"kind": "trademark", "token": tm_match.group()})
    comm_match = _COMMERCIAL_PATTERN.search(title)
    if comm_match:
        items.append({"kind": "commercial", "token": comm_match.group()})

    if items:
        results.append(CheckItem(
            status="amend",
            message="Title contains prohibited content.",
            message_key="check.cn.spec.title.amendContent",
            details_key="details.cn.titleContent",
            details_params={"title_prohibited_items": {"items": items}},
            reference="审查指南 第一部分第一章",
        ))

    if not results:
        results.append(CheckItem(
            status="pass",
            message="Title is acceptable.",
            message_key="check.cn.spec.title.pass",
            reference="审查指南 第一部分第一章",
        ))

    return results


# ── Check 8 ──────────────────────────────────────────────────────────────

_CLAIM_REF_RE = re.compile(r"如权利要求\s*\d+[\s\S]*?所述")


def check_spec_claim_reference(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Flag specification text that references specific claims."""
    text = _all_spec_text(cn_doc)
    match = _CLAIM_REF_RE.search(text)

    if match:
        snippet = match.group()[:50]
        return [CheckItem(
            status="amend",
            message="Specification references a specific claim number.",
            message_key="check.cn.spec.claimReference.amend",
            details=snippet,
            details_key="details.cn.specClaimReference",
            details_params={"detail": snippet},
            reference="专利法实施细则 §17",
        )]

    return [CheckItem(
        status="pass",
        message="No claim references found in specification.",
        message_key="check.cn.spec.claimReference.pass",
        reference="专利法实施细则 §17",
    )]
