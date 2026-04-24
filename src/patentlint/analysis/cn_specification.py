# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""CN specification analysis checks.

Eight pure functions checking Chinese patent specification formatting
against CNIPA rules (专利法实施细则 and 审查指南).
"""

from __future__ import annotations

import re
from collections import Counter

from patentlint.analysis.utils import _dx
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

_VALID_ENDINGS = frozenset("。！？")  # strict: 技术领域 / 背景技术

# Manual [NNNN] bracket prefix at the head of a CN spec paragraph. Separately
# flagged as forbidden by ``check_paragraph_numbering``, but when present it
# is the only identifier the drafter can visually locate in Word, so the
# paragraph-ending check surfaces it as the paragraph label so the two flags
# don't contradict each other.
_PARA_NUM_PREFIX_RE = re.compile(r"^\[(\d{4})\]")

# Bare figure-caption paragraph (e.g. 图1, 图4A, 图5C). Drafters insert
# these below figure images in 附图说明 / 具体实施方式 without trailing
# punctuation; they are captions, not prose.
_FIGURE_CAPTION_RE = re.compile(r"^\s*图\s*\d+[A-Za-z]?\s*$")

# Non-prose structural markers commonly found in CN spec body paragraphs
# (especially chemistry / pharma filings). These are not sentences and
# shouldn't be held to the 。！？ / ；： ending rule:
#
#   [化N] / [表N] / [式N]   formula / table / equation labels
#   [short label]            bracketed section name (e.g. [实施例1], [LWR])
#   ＜...＞ / 〈...〉        angle-bracketed section marker
#   (...) / （...）         paren-wrapped sub-section marker (allows 1-level
#                            nesting such as (鎓盐化合物(1)))
#   "实施例" / similar       bare section header words on their own line
#   [NNNN] alone             bare paragraph number with no content
#
# Patterns strip any leading [NNNN] prefix first, then inspect the
# remaining body for a recognized non-prose shape.
_NON_PROSE_BODY_PATTERNS = (
    # [化N] / [表N] / [式N] with optional content after
    re.compile(r"^\[(?:化|表|式)\s*\d+[A-Za-z]?\s*\].*$"),
    # Any bracketed label ≤20 CJK/Latin chars (e.g. [实施例1], [LWR])
    re.compile(r"^\[[^\]]{1,20}\]\s*$"),
    # Angle-bracketed section marker
    re.compile(r"^[＜〈<][^＞〉>]+[＞〉>]\s*$"),
    # Paren-wrapped (1-level nesting allowed) — (鎓盐化合物) / (鎓盐化合物(1))
    re.compile(r"^\([^)]*(?:\([^)]*\)[^)]*)*\)\s*$"),
    re.compile(r"^（[^）]*(?:（[^）]*）[^）]*)*）\s*$"),
    # Empty body after stripping [NNNN] prefix — standalone para-number
    # placeholder with no content is a structural marker.
    re.compile(r"^$"),
)
_PARA_NUM_STRIP_RE = re.compile(r"^\[\d{4}\][\s　\t]*")


def _is_skip_paragraph_ending_cn(text: str) -> bool:
    """Paragraphs excluded from the ending-punctuation check.

    Skips bare figure captions (``图N``) and non-prose structural markers
    (formula / table / equation labels, angle-bracketed section headers,
    paren-wrapped sub-section markers, bare ``[NNNN]`` placeholders).
    Chemistry and pharma CN specs rely heavily on these shapes for
    embedded 化学式 / 表 / 式 labeling, and flagging them as prose-ending
    violations floods the report with non-actionable items (~200/doc on
    CN120266060A).
    """
    if _FIGURE_CAPTION_RE.match(text):
        return True
    body = _PARA_NUM_STRIP_RE.sub("", text).strip()
    return any(p.match(body) for p in _NON_PROSE_BODY_PATTERNS)


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
    """Check that mandatory top-level CNIPA filing sections are non-empty.

    Covers the three top-level components a CNIPA application requires per
    专利法 §26 第1款 (说明书 / 摘要 / 权利要求书) plus the 说明书
    subsections enumerated in 专利法实施细则 §17. When the drafter removes
    a 五书 header, the corresponding field extracts empty (or in some
    cases is silently recovered by a parser fallback tier — see below).

    **Strict header detection.** ``cn_doc.section_source_strategies``
    records which parser tier resolved each top-level part:

    * ``"body_anchor"`` / ``"page_header"`` — a real 五书 heading
      (``权利要求书`` / ``说明书摘要`` / ``说明书`` / page-header
      equivalent) was parsed in the document.
    * ``"claim_density"`` — claims were RECOVERED from a contiguous run
      of ``N. ...`` claim-start paragraphs because no ``权利要求书``
      anchor was found. This is parser robustness for malformed
      publications, but for a draft check it MUST be flagged: the
      drafter omitted the required heading.
    * ``"none"`` — no source resolved that part.

    For 摘要 we additionally accept the publication-format INID
    fallback (``(57)摘要`` cover page) by checking ``abstract_text``
    when strategies are silent — a downloaded publication is a valid
    input, and flagging the (57)摘要-only path would be a false
    positive against the publication-checking workflow.
    """
    missing: list[str] = []
    strategies = cn_doc.section_source_strategies or {}
    valid_anchor = {"body_anchor", "page_header"}

    # Top-level: 摘要 (required per 专利法 §26, format per §23). Content
    # alone is the gate: when a body 说明书摘要 anchor is present, the
    # parser populates ``abstract_text`` from the scoped paragraphs;
    # when the body anchor is missing, the publication-format INID
    # fallback ((57)摘要) may populate it. An empty ``abstract_text``
    # means no source resolved abstract content at all → flag.
    if not cn_doc.abstract_text or not cn_doc.abstract_text.strip():
        missing.append("摘要")

    # 说明书 subsections per 专利法实施细则 §17
    required = ["technical_field", "background", "summary", "detailed_description"]
    for fname in required:
        paragraphs = getattr(cn_doc, fname)
        if not any(p.strip() for p in paragraphs):
            missing.append(_SECTION_NAMES_CN[fname])

    # Conditional: 附图说明 required when drawings are referenced in the body
    # (per 专利法实施细则 §17 第1款 第4项). ``figure_refs`` is populated by
    # ``_extract_figure_refs`` from the 具体实施方式 + 附图说明 text, so any
    # 图N reference in the body forces this requirement.
    if cn_doc.figure_refs and not any(p.strip() for p in cn_doc.drawings_description):
        missing.append(_SECTION_NAMES_CN["drawings_description"])

    # Top-level: 权利要求书 (required per 专利法 §26, format per §22).
    # Strict: require a real heading. claim_density recovery is parser
    # robustness, not a substitute for the 权利要求书 anchor — flag.
    claims_anchor = strategies.get("claims") in valid_anchor
    if not claims_anchor or not cn_doc.claims:
        missing.append("权利要求书")

    if missing:
        return [CheckItem(
            status="amend",
            message=f"Missing required sections: {', '.join(missing)}",
            message_key="check.cn.spec.requiredSections.amend",
            details=", ".join(missing),
            details_key="details.cn.requiredSections",
            details_params={
                "sections": ", ".join(missing),
                "flagged_phrases": {
                    "items": [{"kind": "section", "token": s} for s in missing]
                },
            },
            reference="专利法 §26 第1款、专利法实施细则 §17",
            diagnostics=_dx(
                missing_count=len(missing),
            ),
        )]
    return [CheckItem(
        status="pass",
        message="All required sections are present.",
        message_key="check.cn.spec.requiredSections.pass",
        reference="专利法 §26 第1款、专利法实施细则 §17",
    )]


# ── Check 2 ──────────────────────────────────────────────────────────────


def check_section_ordering(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Verify sections appear in canonical CNIPA order.

    Reads ``cn_doc.section_order`` — the list of canonical field-name keys
    in the order the parser first encountered each header. A non-increasing
    canonical-index sequence indicates the drafter placed sections out of
    the 专利法实施细则 §17 order (e.g., reusing an MPEP-ordered spec without
    reordering). Empty ``section_order`` (no headers found, or XML with no
    ``<description>``) passes vacuously.
    """
    canonical_index = {name: idx for idx, name in enumerate(_CANONICAL_ORDER)}
    indices = [
        canonical_index[s] for s in cn_doc.section_order if s in canonical_index
    ]
    is_sorted = all(indices[i] < indices[i + 1] for i in range(len(indices) - 1))

    if not is_sorted:
        return [CheckItem(
            status="amend",
            message="Specification sections are not in the required order.",
            message_key="check.cn.spec.sectionOrdering.amend",
            details_key="details.cn.sectionOrdering",
            reference="专利法实施细则 §17",
            diagnostics=_dx(
                sections_seen=len(indices),
            ),
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
            # Duplicate detection runs BEFORE gap detection — a pattern like
            # [1, 2, 2, 3] otherwise fires .amendXmlGap with prev==next and
            # the .amendXmlDuplicate key becomes unreachable.
            counts = Counter(nums)
            duplicates = sorted(n for n, c in counts.items() if c > 1)
            if duplicates:
                dup_str = ", ".join(str(n) for n in duplicates)
                return [CheckItem(
                    status="amend",
                    message=f"Duplicate paragraph numbers detected: paragraphs {dup_str}.",
                    message_key="check.cn.spec.paragraphNumbering.amendXmlDuplicate",
                    details_key="details.cn.paragraphNumberingXml",
                    details_params={"count": len(duplicates), "paragraphs": duplicates},
                    reference="审查指南",
                    diagnostics=_dx(
                        reason_code="duplicate",
                        duplicate_count=len(duplicates),
                        total_paragraphs=len(nums),
                    ),
                )]
            for i in range(1, len(nums)):
                if nums[i] != nums[i - 1] + 1:
                    return [CheckItem(
                        status="amend",
                        message=f"Paragraph numbering has a gap: paragraph {nums[i - 1]} is followed by {nums[i]}.",
                        message_key="check.cn.spec.paragraphNumbering.amendXmlGap",
                        details_key="details.cn.paragraphNumberingXml",
                        details_params={"prev": nums[i - 1], "next": nums[i]},
                        reference="审查指南",
                        diagnostics=_dx(
                            reason_code="gap",
                            gap_size=nums[i] - nums[i - 1],
                            total_paragraphs=len(nums),
                        ),
                    )]
    elif cn_doc.input_format == "docx":
        if cn_doc.has_paragraph_numbering:
            return [CheckItem(
                status="amend",
                message="Manual paragraph numbering found in .docx — CNIPA forbids this.",
                message_key="check.cn.spec.paragraphNumbering.amendDocx",
                details_key="details.cn.paragraphNumberingDocx",
                reference="审查指南",
                diagnostics=_dx(
                    reason_code="manual_docx_numbering",
                ),
            )]

    return [CheckItem(
        status="pass",
        message="Paragraph numbering is correct.",
        message_key="check.cn.spec.paragraphNumbering.pass",
        reference="审查指南",
    )]


# ── Check 4 ──────────────────────────────────────────────────────────────


def check_paragraph_ending(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Check each paragraph ends with valid Chinese punctuation.

    Strict (。！？) applies to 技术领域 and 背景技术 per CNIPA practice.
    Relaxed (+ ；：) applies to 发明内容, 附图说明, and 具体实施方式 where
    enumerations and step descriptions legitimately end with ； or ：.
    Mirrors the TIPO-aligned implementation in ``tw_specification``.

    Bare figure-caption paragraphs (``图1``, ``图4A``, …) are skipped since
    they are captions, not prose. Prefers the manually-added ``[NNNN]``
    bracket prefix as the paragraph label when present so the drafter can
    locate the flagged paragraph in Word by the exact identifier they
    typed; falls back to an internal ordinal counter otherwise.
    """
    _RELAXED_VALID = _VALID_ENDINGS | frozenset("；：")
    sections_to_check = [
        (cn_doc.technical_field, False),
        (cn_doc.background, False),
        (cn_doc.summary, True),
        (cn_doc.drawings_description, True),
        (cn_doc.detailed_description, True),
    ]

    bad_paragraphs: list[int | str] = []
    ordinal = 0
    # Continuation paragraphs (Word paragraphs that wrap inside a single
    # logical [NNNN] unit) lack the typed [NNNN] prefix. Carry the most
    # recently seen [NNNN] forward so flagged continuations report the
    # number the drafter sees in Word, not an internal ordinal that
    # shifts on subsection boundaries.
    last_para_num: str | None = None
    for section_paras, relaxed in sections_to_check:
        for para in section_paras:
            stripped = para.strip()
            if not stripped:
                continue
            ordinal += 1
            m = _PARA_NUM_PREFIX_RE.match(stripped)
            if m:
                last_para_num = m.group(1)
            if _is_skip_paragraph_ending_cn(stripped):
                continue
            endings = _RELAXED_VALID if relaxed else _VALID_ENDINGS
            if stripped[-1] in endings:
                continue
            # Allow ；以及 / ；及 penultimate list items in relaxed sections
            # (mirror TW allowance for list-cap endings).
            if relaxed and (stripped.endswith("；以及") or stripped.endswith("；及")):
                continue
            if last_para_num is not None:
                label: int | str = f"[{last_para_num}]"
            else:
                label = ordinal
            bad_paragraphs.append(label)

    if bad_paragraphs:
        paras_str = ", ".join(str(n) for n in bad_paragraphs)
        return [CheckItem(
            status="amend",
            message=f"{len(bad_paragraphs)} paragraph(s) have invalid ending punctuation (paragraphs: {paras_str}).",
            message_key="check.cn.spec.paragraphEnding.amend",
            details=f"{len(bad_paragraphs)} paragraphs",
            details_key="details.cn.paragraphEnding",
            details_params={"count": len(bad_paragraphs), "paragraphs": bad_paragraphs},
            reference="审查指南",
            diagnostics=_dx(
                flagged_count=len(bad_paragraphs),
                total_paragraphs_scanned=ordinal,
            ),
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
            diagnostics=_dx(
                only_drawings_count=len(only_drawings),
                only_embodiment_count=len(only_detail),
                total_drawings=len(drawings_figs),
                total_detail=len(detail_figs),
            ),
        )]

    return [CheckItem(
        status="pass",
        message="Figure references are consistent across sections.",
        message_key="check.cn.spec.figureRefConsistency.pass",
        reference="审查指南",
    )]


# ── Check 6 ──────────────────────────────────────────────────────────────


def check_patent_type_terminology(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Flag mixed 本发明/此发明 vs 本实用新型/此实用新型 usage.

    Per 审查指南 第一部分第二章 §2.1.2 (and TIPO 偵錯系統 Table 1 #18
    parallel): 本发明 terminology is only permitted in invention filings;
    本实用新型 only in utility-model filings. 此发明 and 此实用新型 are
    less-common variants of the same concept and also violate.

    CN patent_type is inferred heuristically (whichever term dominates the
    spec body), so we can't gate on a declared type as TIPO does. Fall back
    to the mixed-usage signal: if BOTH families appear, something is
    inconsistent — flag whichever is the minority.
    """
    text = _all_spec_text(cn_doc)
    invention_terms = ("本发明", "此发明")
    utility_terms = ("本实用新型", "此实用新型")
    inv_count = sum(text.count(t) for t in invention_terms)
    util_count = sum(text.count(t) for t in utility_terms)

    if inv_count and util_count:
        # Determine minority family to surface the likely error
        if inv_count >= util_count:
            minority = next(
                (t for t in utility_terms if t in text), utility_terms[0]
            )
        else:
            minority = next(
                (t for t in invention_terms if t in text), invention_terms[0]
            )
        return [CheckItem(
            status="verify",
            message="Mixed patent type terminology found.",
            message_key="check.cn.spec.patentTypeTerminology.verify",
            details=f"Minority term: {minority}",
            details_key="details.cn.patentTypeTerminology",
            details_params={"term": minority},
            reference="审查指南",
            diagnostics=_dx(
                invention_count=inv_count,
                utility_count=util_count,
            ),
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
            diagnostics=_dx(
                reason_code="missing",
                title_charlen=0,
            ),
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
            diagnostics=_dx(
                reason_code="length",
                cjk_count=cjk_count,
                threshold=25,
                overage=cjk_count - 25,
            ),
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
            diagnostics=_dx(
                reason_code="prohibited_content",
                flagged_count=len(items),
                title_charlen=len(title),
            ),
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

# Spec-text references to claims (prohibited per 专利法实施细则 §17 —
# the specification must not describe the invention by reference to the
# claims). The introducing verb is not constrained: CN drafters use
# 根据/如/按照/依照/依据 + 权利要求N + 所述, or bare 权利要求N所述.
# Distance-bounded to keep `所述` within 20 chars of `权利要求N`, avoiding
# FPs on unrelated co-occurrences across sentences.
_CLAIM_REF_RE = re.compile(r"权利要求\s*\d+[^所。]{0,20}所述")


def check_spec_claim_reference(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Flag specification text that references specific claims."""
    bad_paragraphs: list[int] = []
    first_snippet = ""
    ordinal = 0
    for para in _all_paragraphs(cn_doc):
        stripped = para.strip()
        if not stripped:
            continue
        ordinal += 1
        match = _CLAIM_REF_RE.search(stripped)
        if match:
            bad_paragraphs.append(ordinal)
            if not first_snippet:
                first_snippet = match.group()[:50]

    if bad_paragraphs:
        paras_str = ", ".join(str(n) for n in bad_paragraphs)
        return [CheckItem(
            status="amend",
            message=f"Specification references claims in {len(bad_paragraphs)} paragraph(s) (paragraphs: {paras_str}).",
            message_key="check.cn.spec.claimReference.amend",
            details=first_snippet,
            details_key="details.cn.specClaimReference",
            details_params={
                "count": len(bad_paragraphs),
                "paragraphs": bad_paragraphs,
                "snippet": first_snippet,
            },
            reference="专利法实施细则 §17",
            diagnostics=_dx(
                flagged_count=len(bad_paragraphs),
                total_paragraphs_scanned=ordinal,
            ),
        )]

    return [CheckItem(
        status="pass",
        message="No claim references found in specification.",
        message_key="check.cn.spec.claimReference.pass",
        reference="专利法实施细则 §17",
    )]
