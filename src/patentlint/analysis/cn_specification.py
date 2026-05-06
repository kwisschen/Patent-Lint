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

# Canonical section order per 专利法实施细则 §20
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
    # R65 (2026-05-05) TW parity: bibliographic citation paragraphs.
    # CN drafters using cross-jurisdiction conventions list patent +
    # non-patent literature with `[专利文献N]` / `[非专利文献N]` labels;
    # citation entries are bibliographic references (e.g.
    # `美国专利第10256321号说明书`), not prose sentences. Drafters
    # conventionally omit trailing 。.
    re.compile(r"^\[(?:专利文献|非专利文献)\s*\d+\].*$"),
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
    subsections enumerated in 专利法实施细则 §20. When the drafter removes
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

    # 说明书 subsections per 专利法实施细则 §20
    required = ["technical_field", "background", "summary", "detailed_description"]
    for fname in required:
        paragraphs = getattr(cn_doc, fname)
        if not any(p.strip() for p in paragraphs):
            missing.append(_SECTION_NAMES_CN[fname])

    # Conditional: 附图说明 required when drawings are referenced in the body
    # (per 专利法实施细则 §20 第1款 第4项). ``figure_refs`` is populated by
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
            reference="专利法 §26 第1款、专利法实施细则 §20",
            diagnostics=_dx(
                missing_count=len(missing),
                first_missing=missing[0] if missing else None,
                missing_sections=missing[:10],
                input_format=getattr(cn_doc, "input_format", None),
                claims_strategy=cn_doc.section_source_strategies.get("claims") if hasattr(cn_doc, "section_source_strategies") else None,
                # Symmetry with TW (issue #17 follow-up): surface how many
                # claims the parser actually extracted, not just whether
                # the strategy detected them. claims_count=0 with a valid
                # claims_strategy would point at a downstream parsing
                # failure (e.g., unrecognized numbering format) rather
                # than a missing-section defect — same bug class TW saw
                # with bracket-label firm variants.
                claims_count=len(cn_doc.claims) if cn_doc.claims else 0,
            ),
        )]
    return [CheckItem(
        status="pass",
        message="All required sections are present.",
        message_key="check.cn.spec.requiredSections.pass",
        reference="专利法 §26 第1款、专利法实施细则 §20",
    )]


# ── Check 2 ──────────────────────────────────────────────────────────────


def check_section_ordering(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Verify sections appear in canonical CNIPA order.

    Reads ``cn_doc.section_order`` — the list of canonical field-name keys
    in the order the parser first encountered each header. A non-increasing
    canonical-index sequence indicates the drafter placed sections out of
    the 专利法实施细则 §20 order (e.g., reusing an MPEP-ordered spec without
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
            reference="专利法实施细则 §20",
            diagnostics=_dx(
                sections_seen=len(indices),
                total_canonical_sections=len(_CANONICAL_ORDER),
                section_order_actual=list(cn_doc.section_order)[:10],
                canonical_order=list(_CANONICAL_ORDER)[:10],
                first_disorder_at=next(
                    (i for i in range(len(indices) - 1) if indices[i] >= indices[i + 1]),
                    None,
                ),
            ),
        )]
    return [CheckItem(
        status="pass",
        message="Specification sections are in the correct order.",
        message_key="check.cn.spec.sectionOrdering.pass",
        reference="专利法实施细则 §20",
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
                        duplicate_sample=duplicates[:10],
                        first_duplicate=duplicates[0] if duplicates else None,
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
                            prev_value=nums[i - 1],
                            next_value=nums[i],
                            gap_position=i,
                            is_backward=nums[i] < nums[i - 1],
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
                    total_paragraphs=len(cn_doc.paragraph_numbers) if cn_doc.paragraph_numbers else None,
                    sample_numbers=[str(n) for n in (cn_doc.paragraph_numbers or [])[:5]],
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
    bad_findings: list[dict] = []
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
            if len(bad_findings) < 5:
                bad_findings.append({
                    "paragraph_label": label,
                    "last_char_codepoint": ord(stripped[-1]),
                    "last_30_chars": stripped[-30:],
                    "relaxed_section": relaxed,
                })

    if bad_paragraphs:
        paras_str = ", ".join(str(n) for n in bad_paragraphs)
        return [CheckItem(
            status="verify",
            message=f"{len(bad_paragraphs)} paragraph(s) have invalid ending punctuation (paragraphs: {paras_str}).",
            message_key="check.cn.spec.paragraphEnding.verify",
            details=f"{len(bad_paragraphs)} paragraphs",
            details_key="details.cn.paragraphEnding",
            details_params={"count": len(bad_paragraphs), "paragraphs": bad_paragraphs},
            reference="审查指南",
            diagnostics=_dx(
                flagged_count=len(bad_paragraphs),
                total_paragraphs_scanned=ordinal,
                findings=bad_findings,
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
            status="amend",
            message="Figure references differ between 附图说明 and 具体实施方式.",
            message_key="check.cn.spec.figureRefConsistency.amend",
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
                only_drawings_sample=[int(x) for x in only_drawings[:10]],
                only_embodiment_sample=[int(x) for x in only_detail[:10]],
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
                minority_term=minority,
                minority_count=min(inv_count, util_count),
                majority_count=max(inv_count, util_count),
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
                title_raw_charlen=len(cn_doc.title),
                title_is_whitespace=bool(cn_doc.title and not cn_doc.title.strip()),
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
                title_charlen=len(title),
                first_30_chars=title[:30],
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
                flagged_kinds=[it.get("kind") for it in items],
                tokens_sample=[(it.get("token") or "")[:32] for it in items[:5]],
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

# Spec-text references to claims (prohibited per 专利法实施细则 §20 —
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
        # Build per-finding samples directly from the spec text.
        sample_findings: list[dict] = []
        scan_ord = 0
        for para in _all_paragraphs(cn_doc):
            stripped = para.strip()
            if not stripped:
                continue
            scan_ord += 1
            if scan_ord not in bad_paragraphs:
                continue
            m = _CLAIM_REF_RE.search(stripped)
            if not m:
                continue
            sample_findings.append({
                "paragraph_ordinal": scan_ord,
                "matched_phrase": m.group(0)[:80],
            })
            if len(sample_findings) >= 5:
                break
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
            reference="专利法实施细则 §20",
            diagnostics=_dx(
                flagged_count=len(bad_paragraphs),
                total_paragraphs_scanned=ordinal,
                findings=sample_findings,
            ),
        )]

    return [CheckItem(
        status="pass",
        message="No claim references found in specification.",
        message_key="check.cn.spec.claimReference.pass",
        reference="专利法实施细则 §20",
    )]


# ── D1 reference numeral consistency (CN) ──────────────────────────────
# 专利法实施细则 §21 第2款 + 审查指南 §3.3.1 — 同一附图标记应当指代同一构件.
# Same numeral must designate the same element. Different elements
# require different numerals. Same name with different numerals is
# permitted (multiple instances).
#
# Mirrors the US implementation in specification.py but uses CJK regex
# patterns and char-level (not word-level) content overlap detection.

# CJK noun + numeral pattern. Captures a 2-8 CJK-char noun phrase
# followed by a 2-4 digit numeral with optional letter suffix
# (e.g., "外殼102" / "壳体100" / "传感器120a"). Non-greedy on the
# noun span so we capture the SHORTEST plausible head noun.
_CN_REFNUM_AFTER_NOUN = re.compile(
    r"(?P<noun>[一-鿿]{2,8})\s*(?P<num>\d{2,4}[a-z]?)"
    r"(?![\d.%])",  # not followed by another digit, decimal, or % unit
)
# Parenthetical: 外壳(102) / 壳体（100）
_CN_REFNUM_PARENS = re.compile(
    r"(?P<noun>[一-鿿]{2,8})\s*[(（](?P<num>\d{2,4}[a-z]?)[)）]"
)

# Reference-form prefixes to strip from CJK names before D1 comparison.
# These are statutory reference markers (该/所述/前述), not part of the
# element name itself. Without stripping, "该外壳" and "外壳" would
# appear as different names.
_CN_REF_PREFIXES = ("该等", "所述的", "所述", "前述", "该", "本", "其")
# Ordinal prefixes also strippable for D1 comparison — "第一外壳" and
# "外壳" are the same head noun for D1 purposes (different INSTANCES
# with their own numerals is the legitimate D2 case which D1 ignores).
_CN_ORDINAL_RE = re.compile(r"^第[一二三四五六七八九十百零0-9]+")
# Common quantifiers that may lead a captured noun phrase
_CN_LEADING_QUANTIFIERS = ("多个", "复数个", "复数", "至少一个", "至少一", "一个", "一种", "一对")
# Leading verbs/particles/prepositions that creep into the captured noun
# from compound sentences. After prefix/ordinal/quantifier strip these
# are still iterated off as long as the residual remains ≥2 CJK chars.
# Both Trad + Simp variants included so the helpers work for both.
_CN_LEADING_VERBS_PARTICLES = (
    "之", "至", "由", "将", "將", "盖", "蓋", "介", "经", "經",
    "自", "于", "於", "在", "向", "对", "對", "较", "較", "因",
    "为", "為", "及", "并", "並", "以", "從", "从", "或",
)
# Single-CJK-char words that creep in as "names" (verbs, particles, etc.)
# When a captured head noun reduces to one of these after stripping,
# discard it as a real D1 candidate.
_CN_NOISE_SINGLE_CHARS = frozenset({"于", "以", "对", "时", "中", "上", "下", "内", "外"})

# Measurement / process / chemistry-context indicators. If a captured
# head noun ENDS WITH or CONTAINS any of these, the numeral is almost
# certainly a measurement value (含量为 10 / 浓度为 5wt% / etc.) rather
# than a reference numeral. Exclude from D1 detection. Empirically tuned
# against CN chemistry/biology fixtures (CN117427144B / CN120266060A)
# where the regex pulled hundreds of process-context phrases as "names"
# for measurement numerals.
_CN_PROCESS_CONTEXT_TAILS = (
    # Measurement-equals / preference-equals (Simp + Trad)
    "为", "為",
    "优选", "更优选", "进而优选", "特别优选",
    "優選", "更優選", "進而優選", "特別優選",
    "上限", "下限", "含量", "浓度", "濃度", "比例", "用量",
    # Process verbs (Simp + Trad)
    "加入", "溶于", "搅拌", "攪拌", "加热", "加熱",
    "离心", "離心", "冷却", "冷卻", "升温", "升溫", "降温", "降溫",
    "冷却至", "冷卻至", "加热至", "加熱至", "搅拌至", "攪拌至",
    "冲洗", "沖洗", "培养", "培養", "反应", "反應",
    "蒸馏", "蒸餾", "过滤", "過濾", "干燥", "乾燥", "混合",
    "包括", "包含", "构成", "構成",
    "对比例", "對比例",
    # Measurement context — physical-property nouns (Simp + Trad)
    "厚度", "直径", "直徑", "长度", "長度", "宽度", "寬度",
    "高度", "深度", "重量", "质量", "質量",
    "波长", "波長", "频率", "頻率", "温度", "溫度",
    "压力", "壓力", "速度", "电压", "電壓", "电流", "電流", "功率",
    "时间", "時間", "次数", "次數",
    # Chemistry continuation — connector words that creep into the tail
    "并在", "並在", "并且", "並且", "与", "與", "及", "以及",
)
_CN_PROCESS_CONTEXT_TOKENS = (
    "含量", "浓度", "濃度", "比例", "用量", "上限", "下限",
    "优选", "優選",
    "加热搅拌", "加熱攪拌", "氮气冲洗", "氮氣沖洗",
    "对比例", "對比例", "加入",
    # Frequently mixed-case measurement units that shouldn't anchor
    # reference numerals
    "重量份至", "重量份",
)
# Chemistry compound suffixes — captured names ending in these are
# almost certainly chemicals listed by weight/concentration in
# chemistry/biology patents, not reference numerals to physical
# elements. Empirically tuned against CN120266060A / CN117427144B.
_CN_CHEMISTRY_SUFFIXES = (
    "烯", "酸", "醇", "酮", "醚", "胺", "盐", "酯",
    "烷", "烃", "糖", "苷", "蛋白", "肽", "酶",
    "氢", "氧化物", "化合物", "树脂", "聚合物",
    "腈", "醛", "酐", "肼",  # additional chemistry suffixes
    # Common chemical-element radicals — captured noun ending in these
    # is usually a chemical compound mention, not a reference numeral
    "钠", "钾", "钙", "镁", "铁", "铝", "铜", "锌", "锂",
)


def _cn_is_measurement_context(name: str) -> bool:
    """True if the captured noun phrase looks like measurement / process
    context (chemistry/biology drafting), not a reference numeral.
    """
    if name.endswith(_CN_PROCESS_CONTEXT_TAILS):
        return True
    if name.endswith(_CN_CHEMISTRY_SUFFIXES):
        return True
    return any(tok in name for tok in _CN_PROCESS_CONTEXT_TOKENS)


def _cn_d1_head_noun(raw: str) -> str:
    """Strip reference-form prefixes + ordinals + quantifiers from a
    captured CJK noun phrase to get the bare head noun for D1 dedup."""
    s = raw.strip()
    # Strip leading reference-form prefix
    for p in _CN_REF_PREFIXES:
        if s.startswith(p):
            s = s[len(p):]
            break
    # Strip leading ordinal
    m = _CN_ORDINAL_RE.match(s)
    if m:
        s = s[m.end():]
    # Strip leading quantifier
    for q in _CN_LEADING_QUANTIFIERS:
        if s.startswith(q):
            s = s[len(q):]
            break
    # Iteratively strip leading single-char verbs/particles. Stops as
    # soon as residual would drop below 2 CJK chars or first char isn't
    # in the strip set.
    while s and len(s) >= 3 and s[0] in _CN_LEADING_VERBS_PARTICLES:
        s = s[1:]
    if len(s) < 2:
        return ""
    if s in _CN_NOISE_SINGLE_CHARS:
        return ""
    if _cn_is_measurement_context(s):
        return ""
    return s


def _cn_extract_numeral_name_pairs(text: str) -> list[tuple[int, str]]:
    """Return per-occurrence (numeral, head_noun) pairs from CN spec text."""
    pairs: list[tuple[int, str]] = []
    seen_spans: set[tuple[int, int]] = set()
    for pattern in [_CN_REFNUM_AFTER_NOUN, _CN_REFNUM_PARENS]:
        for m in pattern.finditer(text):
            span = (m.start(), m.end())
            if span in seen_spans:
                continue
            seen_spans.add(span)
            num_str = m.group("num").rstrip("abcdefghijklmnopqrstuvwxyz")
            if not num_str:
                continue
            num = int(num_str)
            if len(num_str) >= 5:
                continue
            head = _cn_d1_head_noun(m.group("noun"))
            if not head:
                continue
            pairs.append((num, head))
    return pairs


def _cn_content_chars(name: str) -> set[str]:
    """For CJK strings, content "words" are individual CJK characters.
    Two names share content iff they share at least one CJK char."""
    return {c for c in name if "一" <= c <= "鿿"}


def _cn_names_form_real_d1_conflict(names: list[str]) -> bool:
    """At least one pair of names shares NO CJK char → real conflict."""
    if len(names) < 2:
        return False
    char_sets = [_cn_content_chars(n) for n in names]
    for i in range(len(char_sets)):
        if not char_sets[i]:
            continue
        for j in range(i + 1, len(char_sets)):
            if not char_sets[j]:
                continue
            if not (char_sets[i] & char_sets[j]):
                return True
    return False


def check_numeral_consistency_cn(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """D1 — flag reference numerals appearing with multiple disjoint
    element names in CN specifications.

    Statutory: 专利法实施细则 §21 第2款 + 审查指南 §3.3.1 —
    同一附图标记应当指代同一构件.

    Same precision filters as US D1: ≥3 total occurrences, ≥2 per name,
    and at least one disjoint pair of CJK-char sets.
    """
    spec_text = _all_spec_text(cn_doc)
    if not spec_text:
        return [CheckItem(
            status="pass",
            message="无附图标记一致性问题（说明书为空）。",
            message_key="check.cn.spec.numeralConsistency.pass",
            reference="专利法实施细则 §21 第2款",
        )]

    pairs = _cn_extract_numeral_name_pairs(spec_text)
    if not pairs:
        return [CheckItem(
            status="pass",
            message="未检测到附图标记。",
            message_key="check.cn.spec.numeralConsistency.pass",
            reference="专利法实施细则 §21 第2款",
        )]

    by_num_counts: dict[int, Counter] = {}
    by_num_total: Counter = Counter()
    for num, name in pairs:
        by_num_counts.setdefault(num, Counter())[name] += 1
        by_num_total[num] += 1

    by_num: dict[int, list[str]] = {}
    for num, name_counts in by_num_counts.items():
        if by_num_total[num] < 3:
            continue
        seen: list[str] = []
        seen_set: set[str] = set()
        for raw_num, raw_name in pairs:
            if raw_num != num or raw_name in seen_set:
                continue
            if name_counts[raw_name] < 2:
                continue
            seen_set.add(raw_name)
            seen.append(raw_name)
        if seen:
            by_num[num] = seen

    conflicts = [
        (num, names)
        for num, names in sorted(by_num.items())
        if len(names) > 1 and _cn_names_form_real_d1_conflict(names)
    ]

    if not conflicts:
        return [CheckItem(
            status="pass",
            message="附图标记与所指代构件名称一致。",
            message_key="check.cn.spec.numeralConsistency.pass",
            reference="专利法实施细则 §21 第2款",
        )]

    sample = conflicts[:8]
    extra = max(0, len(conflicts) - 8)
    findings = [
        {"numeral": num, "names": names[:5]}
        for num, names in sample
    ]
    return [CheckItem(
        status="amend",
        message=f"{len(conflicts)} 个附图标记被用于指代多个不同的构件名称。",
        message_key="check.cn.spec.numeralConsistency.amend",
        details_key="details.cn.numeralConsistency",
        details_params={
            "count": len(conflicts),
            "findings": findings,
            "extra": extra,
        },
        reference="专利法实施细则 §21 第2款",
        diagnostics=_dx(
            conflict_count=len(conflicts),
            sample_numerals=[num for num, _ in sample],
            max_names_per_numeral=max(len(names) for _, names in conflicts),
        ),
    )]
