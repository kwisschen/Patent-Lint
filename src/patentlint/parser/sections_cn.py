# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""CN patent .docx section extraction — 五書模板 format."""

from __future__ import annotations

import re

from patentlint.models import CnPatentDocument, CnPatentType
from patentlint.parser.claims_cn import _MID_PARAGRAPH_CLAIM_BOUNDARY, parse_cn_claims_docx
from patentlint.parser.docx_loader import DocxSection
from patentlint.parser.detection import (
    HANGUL_REJECTION_RATIO,
    JP_KANA_REJECTION_RATIO,
    DetectionReason,
    DetectionResult,
)
from patentlint.parser.language import (
    cjk_ratio,
    hangul_ratio,
    jp_kana_ratio,
)

# ---------------------------------------------------------------------------
# Header matching patterns — match Word section header text to document parts
# ---------------------------------------------------------------------------

_HEADER_SPEC = re.compile(r"说明书(?!摘要|附图)")
_HEADER_CLAIMS = re.compile(r"权利要求书")
_HEADER_ABSTRACT = re.compile(r"说明书摘要|摘要(?!附图)")
_HEADER_ABSTRACT_DRAWING = re.compile(r"摘要附图")
_HEADER_DRAWINGS = re.compile(r"说明书附图")

# ---------------------------------------------------------------------------
# Spec sub-section header patterns — matched against body paragraph text
# ---------------------------------------------------------------------------

_SPEC_SUBSECTIONS = [
    ("technical_field", re.compile(r"^[\s\u3000]*技术领域[\s\u3000]*$")),
    ("background", re.compile(r"^[\s\u3000]*背景技术[\s\u3000]*$")),
    # R64 (2026-05-05) TW parity: 先前技术 alongside 背景技术 (both
    # treated as prior-art per CNIPA practice). Sub-headers under the
    # prior-art discussion (literature citations) map here too so
    # paragraphs in those subsections aren't dropped from numbering.
    ("background", re.compile(r"^[\s\u3000]*先前技术[\s\u3000]*$")),
    ("background", re.compile(r"^[\s\u3000]*先前技术文献[\s\u3000]*$")),
    ("background", re.compile(r"^[\s\u3000]*专利文献[\s\u3000]*$")),
    ("background", re.compile(r"^[\s\u3000]*非专利文献[\s\u3000]*$")),
    ("summary", re.compile(r"^[\s\u3000]*发明内容[\s\u3000]*$")),
    ("drawings_description", re.compile(r"^[\s\u3000]*附图说明[\s\u3000]*$")),
    ("detailed_description", re.compile(r"^[\s\u3000]*具体实施方式[\s\u3000]*$")),
]

# ---------------------------------------------------------------------------
# Paragraph numbering detection — user-added numbering in CN .docx is an error
# ---------------------------------------------------------------------------

_PARA_NUM_PATTERN = re.compile(r"^\[(\d{4})\]")

# ---------------------------------------------------------------------------
# INID cover-page markers — CNIPA publication exports (Google Patents .docx
# downloads, official publication copies) embed the title at (54)发明名称
# and the abstract at (57)摘要 on the INID cover page. Drafter-authoring
# files (五书模板) have no INID cover. Used as a fallback when the
# body-anchor / page-header tiers leave title or abstract empty.
# ---------------------------------------------------------------------------

_INID_TITLE_RE = re.compile(r"^\(54\)\s*(?:发明|实用新型|外观设计)名称\s*$")
_INID_ABSTRACT_RE = re.compile(r"^\(57\)\s*摘要\s*$")
_INID_CODE_RE = re.compile(r"^\(\d{2}\)")

# ---------------------------------------------------------------------------
# Body-anchor patterns — Phase 8c Tier 1 (ADR-109)
# ---------------------------------------------------------------------------
# Real CNIPA .docx downloads carry 五书 section titles as standalone body
# paragraphs, not in Word page headers. Examples seen in the 10-fixture
# corpus: '权\t利\t要\t求\t书\t1/2 页', '说\t明\t书\t摘要', bare
# '权利要求书'. The anchor regexes tolerate interior whitespace/tabs and
# an optional trailing 'N/M 页' page indicator.

_BA_COMPACT = re.compile(r"\s+")


def _compact(text: str) -> str:
    """Collapse all whitespace (including tabs + full-width U+3000)."""
    return _BA_COMPACT.sub("", text).strip()


# Compact-form anchor tokens. Matched after whitespace collapse.
_BA_CLAIMS_RE = re.compile(r"^权利要求书(?:\d+/\d+页)?$")
_BA_SPEC_RE = re.compile(r"^说明书(?:\d+/\d+页)?$")
_BA_ABSTRACT_RE = re.compile(r"^(?:说明书摘要|摘要)(?:\d+/\d+页)?$")
_BA_ABSTRACT_DRAWING_RE = re.compile(r"^(?:说明书)?摘要附图(?:\d+/\d+页)?$")
_BA_DRAWINGS_RE = re.compile(r"^(?:说明书)?附图(?:\d+/\d+页)?$")

# Doc-page structural token guard — never treat these short fragments as
# section anchors even if their compact form happens to prefix-match a
# 五书 name. (The XML <doc-page> content model is handled by xml_loader;
# this guard is defensive for any docx that happens to embed such text.)
_DOC_PAGE_GUARD_RE = re.compile(r"^doc-?page", re.IGNORECASE)


def _classify_body_anchor(text: str) -> str | None:
    """Classify a paragraph as one of the 五书 anchors, or None.

    Anchors are compared on the whitespace-compacted form so that
    real-world variants like '权\\t利\\t要\\t求\\t书\\t1/2 页' match
    the bare '权利要求书' token with an optional page indicator.
    """
    if not text:
        return None
    if _DOC_PAGE_GUARD_RE.match(text):
        return None
    compact = _compact(text)
    if not compact:
        return None
    # Order matters — more-specific patterns before their superstrings.
    if _BA_ABSTRACT_DRAWING_RE.match(compact):
        return "abstract_drawing"
    if _BA_ABSTRACT_RE.match(compact):
        return "abstract"
    if _BA_DRAWINGS_RE.match(compact):
        return "drawings"
    if _BA_CLAIMS_RE.match(compact):
        return "claims"
    if _BA_SPEC_RE.match(compact):
        return "specification"
    return None


# Claim-density tier — a contiguous run of paragraphs matching the CN
# claim-start pattern (typed prefix OR w:numPr-backfilled) is likely the
# claims section. Minimum density is 3 consecutive matches.
_CLAIM_START_RE = re.compile(r"^\s*\d+\s*[.．。、]")
_CLAIM_DENSITY_MIN = 3

# ---------------------------------------------------------------------------
# Figure reference patterns
# ---------------------------------------------------------------------------

_FIGURE_REF_PATTERN = re.compile(r"图\s*(\d+[a-zA-Z]?)")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _identify_section(header_text: str) -> str | None:
    """Identify which CN patent document part a Word section header corresponds to."""
    if not header_text:
        return None
    # Order matters: check more specific patterns before less specific
    if _HEADER_ABSTRACT_DRAWING.search(header_text):
        return "abstract_drawing"
    if _HEADER_ABSTRACT.search(header_text):
        return "abstract"
    if _HEADER_DRAWINGS.search(header_text):
        return "drawings"
    if _HEADER_CLAIMS.search(header_text):
        return "claims"
    if _HEADER_SPEC.search(header_text):
        return "specification"
    return None


def _merge_publication_continuations(paragraphs: list[str]) -> list[str]:
    """Merge orphan continuation paragraphs into their preceding [NNNN] paragraph.

    CNIPA publication exports (PDF→Word conversions) split logical
    paragraphs across multiple ``<w:p>`` elements at PDF column
    boundaries. The resulting paragraph list looks like::

        [0317]\\t作为示例而非限定，在本申请实施例中，可穿戴设备也可以称为穿戴式智能设备，
        是应用穿戴式技术对日常穿戴进行智能化设计...

    where the second entry is a continuation of the first with no
    ``[NNNN]`` numbering of its own. Drafter-authoring files do not
    fragment this way and do not use ``[NNNN]`` numbering at all, so
    this pass is a publication-only fixup.

    Gated on the presence of ``[NNNN]`` numbering: if no numbered
    paragraphs are found, the input is returned unchanged (drafter
    case). Orphan paragraphs before the first numbered paragraph are
    preserved as-is — they may be sub-section headers or pre-content
    prose that the subsection splitter will handle.
    """
    if not any(_PARA_NUM_PATTERN.match(p) for p in paragraphs):
        return list(paragraphs)

    merged: list[str] = []
    current: str | None = None

    for para in paragraphs:
        if _PARA_NUM_PATTERN.match(para):
            if current is not None:
                merged.append(current)
            current = para
            continue
        if _any_subsection_header(para):
            if current is not None:
                merged.append(current)
                current = None
            merged.append(para)
            continue
        if current is not None:
            current = current.rstrip() + para.lstrip()
        else:
            merged.append(para)

    if current is not None:
        merged.append(current)

    return merged


def _any_subsection_header(para: str) -> bool:
    for _, pattern in _SPEC_SUBSECTIONS:
        if pattern.match(para):
            return True
    return False


def _split_spec_subsections(
    paragraphs: list[str],
) -> tuple[dict[str, list[str]], list[str]]:
    """Split specification paragraphs into sub-sections by header detection.

    Returns ``(subsections, section_order)``:

    * ``subsections`` — dict with keys: technical_field, background, summary,
      drawings_description, detailed_description. Each value is a list of
      paragraph strings (excluding the header line itself).
    * ``section_order`` — list of field-name keys in the order each header
      was first encountered in the document. First-occurrence only; repeated
      headers do not re-append. Feeds ``check_section_ordering``.

    Publication-format continuation merge runs first (Phase 9 #69) —
    orphan paragraphs from PDF-column fragmentation fold into their
    preceding ``[NNNN]`` paragraph before subsection classification.
    """
    paragraphs = _merge_publication_continuations(paragraphs)

    result: dict[str, list[str]] = {
        "technical_field": [],
        "background": [],
        "summary": [],
        "drawings_description": [],
        "detailed_description": [],
    }
    section_order: list[str] = []

    current_key: str | None = None
    for para in paragraphs:
        # Check if this paragraph is a sub-section header
        matched_key = None
        for key, pattern in _SPEC_SUBSECTIONS:
            if pattern.match(para):
                matched_key = key
                break

        if matched_key is not None:
            current_key = matched_key
            if matched_key not in section_order:
                section_order.append(matched_key)
            continue  # Skip the header line itself

        if current_key is not None:
            result[current_key].append(para)

    return result, section_order


def _detect_paragraph_numbering(paragraphs: list[str]) -> tuple[bool, list[int]]:
    """Detect user-added paragraph numbering in CN .docx paragraphs.

    Returns (has_numbering, list_of_numbers).
    """
    nums: list[int] = []
    for para in paragraphs:
        m = _PARA_NUM_PATTERN.match(para)
        if m:
            nums.append(int(m.group(1)))
    return len(nums) > 0, sorted(nums)


def _extract_inid_title_abstract(
    sections: list[DocxSection],
) -> tuple[str, list[str]]:
    """Fallback title + abstract extraction from INID cover page.

    CNIPA publication exports embed bibliographic metadata in a
    standardized INID (Internationally agreed Numbers for the
    Identification of Data) header that precedes the body text. The
    title follows the ``(54)发明名称`` marker; the abstract follows
    ``(57)摘要`` and runs until the next body anchor (权利要求书,
    说明书, 摘要附图, or another INID code line). Drafter-authoring
    五书模板 files have no INID cover, so this returns ``("", [])``
    for those — the primary body-anchor / page-header path owns that
    case.

    Used only when the primary tiers leave title or abstract empty.
    Does not override a non-empty title or abstract produced by the
    body-anchor / page-header tiers.
    """
    paras: list[str] = []
    for s in sections:
        paras.extend(s.paragraphs)

    title = ""
    abstract_paras: list[str] = []

    for i, p in enumerate(paras):
        if _INID_TITLE_RE.match(p.strip()):
            for j in range(i + 1, min(i + 5, len(paras))):
                candidate = paras[j].strip()
                if candidate:
                    title = candidate
                    break
            break

    in_abstract = False
    for p in paras:
        stripped = p.strip()
        if _INID_ABSTRACT_RE.match(stripped):
            in_abstract = True
            continue
        if not in_abstract:
            continue
        compact = _compact(stripped)
        if (
            _BA_CLAIMS_RE.match(compact)
            or _BA_SPEC_RE.match(compact)
            or _BA_ABSTRACT_DRAWING_RE.match(compact)
            or _BA_DRAWINGS_RE.match(compact)
        ):
            break
        if _INID_CODE_RE.match(stripped):
            break
        if stripped:
            abstract_paras.append(stripped)

    return title, abstract_paras


def _extract_title(paragraphs: list[str]) -> str:
    """Extract invention title from spec paragraphs.

    The title appears before any sub-section header (技术领域, etc.).
    """
    for para in paragraphs:
        # Stop at first sub-section header
        for _, pattern in _SPEC_SUBSECTIONS:
            if pattern.match(para):
                return ""
        # Non-empty paragraph before any header is likely the title
        if para.strip():
            return para.strip()
    return ""


def _extract_figure_refs(text: str) -> list[str]:
    """Extract figure reference strings from text (e.g., '图1', '图2a')."""
    return [m.group(0) for m in _FIGURE_REF_PATTERN.finditer(text)]


def _count_figures_from_descriptions(paragraphs: list[str]) -> int:
    """Count distinct figure numbers referenced in drawings description paragraphs."""
    nums: set[str] = set()
    for para in paragraphs:
        for m in _FIGURE_REF_PATTERN.finditer(para):
            nums.add(m.group(1))
    return len(nums)


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------


_TW_BRACKET_HEADER_RE = re.compile(r"^【[^\d].+?】", re.MULTILINE)


def classify_document_cn(paragraphs: list[str]) -> DetectionResult:
    """Classify a .docx as CN patent or explain why it isn't.

    Layered decision (ADR-150):

    1. Cross-script rejection (ratio-based). JP kana or KO Hangul
       content above :data:`JP_KANA_REJECTION_RATIO` /
       :data:`HANGUL_REJECTION_RATIO` → reject with the specific
       reason code so the banner can explain what was detected.
       Ratios tolerate trace contamination (a stray middle dot in a
       real CN draft) without false-positive.
    2. TW 【】 bracket headers → reject as ``content_missing`` (the
       document looks like TW, not CN; the banner prompts the user
       to re-select jurisdiction without lying about what was found).
    3. Positive CN evidence: CN spec sub-section headers
       (技术领域 / 背景技术 / …) or 五书模板 boundary markers
       (权利要求书 / 说明书摘要).
    4. Numbered-claims fallback gated on CJK dominance ≥ 20% to
       disambiguate US drafts that embed CJK term callouts.
    """
    full_text = "\n".join(paragraphs)

    # --- Layer 1: Cross-script rejection (ratio-based) ---
    kana = jp_kana_ratio(full_text)
    hangul = hangul_ratio(full_text)
    if kana >= JP_KANA_REJECTION_RATIO:
        return (False, DetectionReason.CROSS_SCRIPT_JAPANESE)
    if hangul >= HANGUL_REJECTION_RATIO:
        return (False, DetectionReason.CROSS_SCRIPT_KOREAN)

    # --- Layer 2: TW 【】 section headers mean this isn't a CN draft ---
    # Not a cross-script issue — both are zh, just different jurisdictions.
    # Banner copy ("does not match CN spec patterns") is truthful.
    if _TW_BRACKET_HEADER_RE.search(full_text):
        return (False, DetectionReason.CONTENT_MISSING)

    # --- Layer 3: Positive CN evidence ---
    for para in paragraphs:
        stripped = para.strip()
        for _, pattern in _SPEC_SUBSECTIONS:
            if pattern.match(stripped):
                return (True, DetectionReason.PATENT_DETECTED)
        if stripped in ("权利要求书", "说明书摘要"):
            return (True, DetectionReason.PATENT_DETECTED)

    # --- Layer 4: Numbered-claims fallback (requires CJK dominance) ---
    if (
        len(re.findall(r"^\s*\d+[.．。]\s*", full_text, re.MULTILINE)) >= 3
        and cjk_ratio(full_text) >= 0.20
    ):
        return (True, DetectionReason.PATENT_DETECTED)

    return (False, DetectionReason.CONTENT_MISSING)


def detect_patent_document_cn(paragraphs: list[str]) -> bool:
    """Back-compat boolean wrapper around :func:`classify_document_cn`."""
    is_patent, _ = classify_document_cn(paragraphs)
    return is_patent


def _collect_by_page_header(
    sections: list[DocxSection],
) -> tuple[list[str], list[str], list[str], list[bool]]:
    """Drafter-authoring tier — classify Word sections by page-header text.

    This is the tier the CNIPA 五书模板 (drafter-authoring template)
    exercises: the template is a single .docx with 5 Word sections whose
    page headers are set to 说明书摘要 / 摘要附图 / 权利要求书 / 说明书 /
    说明书附图 (verified 2026-04-19 against
    ``docs/WORD转XML编辑器五书模板文件.docx`` + WORD转XML编辑器 user
    manual §3.3.1). Historically labeled "Tier 4 / legacy / last resort"
    because the 10-fixture real corpus all came from Google Patents
    publication exports (which carry page-less body anchors instead of
    true Word page headers), so the page-header tier rarely fired in
    corpus dogfood. The naming was reverse-calibrated against a publication
    corpus; the authoring reality is the opposite — page-header is the
    primary drafter tier, body-anchor is the publication-recovery tier.

    Returns (spec_paragraphs, claims_paragraphs, abstract_paragraphs,
    claims_numpr_flags). Any tier may return empty lists if its heuristic
    does not fire.
    """
    spec: list[str] = []
    claims: list[str] = []
    claims_numpr: list[bool] = []
    abstract: list[str] = []

    for section in sections:
        doc_part = _identify_section(section.header_text)
        if doc_part == "specification":
            spec = list(section.paragraphs)
        elif doc_part == "claims":
            claims = list(section.paragraphs)
            claims_numpr = list(section.numpr_flags) if section.numpr_flags else [False] * len(claims)
        elif doc_part == "abstract":
            abstract = list(section.paragraphs)
    return spec, claims, abstract, claims_numpr


def _collect_by_body_anchor(
    sections: list[DocxSection],
) -> tuple[list[str], list[str], list[str], list[bool], int]:
    """Publication-recovery tier — walk flat paragraphs, classify by body anchors.

    Fires on Google-Patents-downloaded CNIPA publication exports where
    the 五书 part delimiters sit as standalone body paragraphs (often
    with pagination suffixes like ``1/3 页``) rather than true Word page
    headers. Drafter-authoring .docx files use the page-header tier
    instead; this tier exists to recover section structure from the
    PDF→Word publication pipeline artifact. The ``(?:\\d+/\\d+页)?`` suffix
    tolerance in the anchor regexes is publication-specific.

    Returns (spec, claims, abstract, claims_numpr_flags, anchors_found_count).
    Anchors recognized: 权利要求书, 说明书, 说明书摘要/摘要,
    说明书附图, 摘要附图, and the spec sub-section headers (技术领域 etc.)
    which implicitly mark the start of the specification.
    """
    spec: list[str] = []
    claims: list[str] = []
    claims_numpr: list[bool] = []
    abstract: list[str] = []

    # Flatten paragraphs + numPr flags across all Word sections.
    flat_paras: list[str] = []
    flat_numpr: list[bool] = []
    for section in sections:
        flags = section.numpr_flags or [False] * len(section.paragraphs)
        # Guard against mismatched lengths (older callers).
        if len(flags) != len(section.paragraphs):
            flags = [False] * len(section.paragraphs)
        flat_paras.extend(section.paragraphs)
        flat_numpr.extend(flags)

    current: str | None = None
    anchor_count = 0
    seen_anchors: set[str] = set()

    for para, has_numpr in zip(flat_paras, flat_numpr, strict=True):
        anchor = _classify_body_anchor(para)
        # Spec sub-section headers (技术领域 etc.) are an implicit
        # spec anchor — they only appear inside the specification.
        sub_match = False
        for _, pat in _SPEC_SUBSECTIONS:
            if pat.match(para):
                sub_match = True
                break

        if anchor is not None:
            if anchor not in seen_anchors:
                anchor_count += 1
                seen_anchors.add(anchor)
            if anchor == "claims":
                current = "claims"
                continue  # skip the anchor paragraph itself
            if anchor == "specification":
                current = "specification"
                continue
            if anchor == "abstract":
                current = "abstract"
                continue
            if anchor in ("drawings", "abstract_drawing"):
                # Transition out of claims/spec; we don't aggregate
                # these separately here (drawings_description is derived
                # from the spec sub-section).
                current = None
                continue

        if sub_match:
            # Spec sub-section header implies we're in the specification.
            # It also counts as an implicit "specification" anchor for
            # the ≥2-distinct-anchors promotion gate (real CNIPA
            # downloads have a 权利要求书 heading but no standalone
            # 说明书 heading — the spec is identified by its sub-sections).
            if "specification" not in seen_anchors:
                seen_anchors.add("specification")
                anchor_count += 1
            current = "specification"

        if current == "claims":
            claims.append(para)
            claims_numpr.append(has_numpr)
        elif current == "specification":
            spec.append(para)
        elif current == "abstract":
            abstract.append(para)

    return spec, claims, abstract, claims_numpr, anchor_count


def _collect_by_claim_density(
    sections: list[DocxSection],
) -> tuple[list[str], list[bool]]:
    """Tier 3 — find the densest contiguous run of claim-start paragraphs.

    Only returns the claims span; spec/abstract detection requires a
    structural anchor and is not recoverable from pure density.
    """
    flat_paras: list[str] = []
    flat_numpr: list[bool] = []
    for section in sections:
        flags = section.numpr_flags or [False] * len(section.paragraphs)
        if len(flags) != len(section.paragraphs):
            flags = [False] * len(section.paragraphs)
        flat_paras.extend(section.paragraphs)
        flat_numpr.extend(flags)

    best_start = -1
    best_end = -1
    best_len = 0
    i = 0
    while i < len(flat_paras):
        # A paragraph is claim-like if it has a typed N. prefix OR
        # w:numPr auto-numbering.
        if _CLAIM_START_RE.match(flat_paras[i]) or flat_numpr[i]:
            j = i
            # Extend run — include continuation (non-claim-start) paragraphs
            # between claim starts, but the run is bounded by the last
            # claim-start + 1 (we don't know where it ends without an anchor).
            last_claim_start = i
            starts = 1
            j = i + 1
            while j < len(flat_paras):
                if _CLAIM_START_RE.match(flat_paras[j]) or flat_numpr[j]:
                    last_claim_start = j
                    starts += 1
                    j += 1
                    continue
                # Allow a small gap of continuation paragraphs, but abort
                # on a clear spec anchor or long stretch of non-claim text.
                if _classify_body_anchor(flat_paras[j]) is not None:
                    break
                sub_hit = any(pat.match(flat_paras[j]) for _, pat in _SPEC_SUBSECTIONS)
                if sub_hit:
                    break
                j += 1
            if starts >= _CLAIM_DENSITY_MIN and starts > best_len:
                best_start = i
                best_end = last_claim_start + 1
                best_len = starts
            i = j + 1
        else:
            i += 1

    if best_start < 0:
        return [], []
    return flat_paras[best_start:best_end], flat_numpr[best_start:best_end]


def _presplit_mid_paragraph(
    paragraphs: list[str], numpr_flags: list[bool]
) -> tuple[list[str], list[bool]]:
    """Split continuation paragraphs on embedded mid-paragraph claim
    boundaries BEFORE the numPr backfill runs.

    Real CNIPA filings sometimes pack two claims into one Word paragraph
    (continuation paragraph whose body text embeds ``…。 4 .根据…``).
    Without pre-splitting, ``_backfill_numpr_prefixes`` sees this as a
    single continuation paragraph and its counter fails to increment;
    subsequent numPr claims then get mis-numbered.

    Reuses ``_MID_PARAGRAPH_CLAIM_BOUNDARY`` from ``claims_cn`` — same
    regex that R20 (``574e850``) applied at parse time. Running it here
    lets the backfill counter reset via the existing typed-prefix
    branch on the second chunk.
    """
    out_paras: list[str] = []
    out_flags: list[bool] = []
    for para, np_flag in zip(paragraphs, numpr_flags, strict=True):
        split = _MID_PARAGRAPH_CLAIM_BOUNDARY.sub(
            lambda m: "\n" + m.group(0).lstrip(), para
        )
        if "\n" not in split:
            out_paras.append(para)
            out_flags.append(np_flag)
            continue
        chunks = [c.strip() for c in split.split("\n") if c.strip()]
        for i, chunk in enumerate(chunks):
            out_paras.append(chunk)
            # Only the first chunk inherits the original numPr flag.
            # Subsequent chunks start with a typed prefix and must not
            # double-trigger the backfill counter.
            out_flags.append(np_flag if i == 0 else False)
    return out_paras, out_flags


def _backfill_numpr_prefixes(paragraphs: list[str], numpr_flags: list[bool]) -> list[str]:
    """Prepend synthetic 'N. ' claim numbers to numPr paragraphs that
    lack a typed prefix.

    Mirrors ``load_docx_tw``'s behavior (ADR-109). The counter is
    incremented for each claim start observed — either a typed-prefix
    paragraph or a numPr paragraph. Continuation paragraphs (no typed
    prefix, no numPr) are left untouched so the downstream claim parser
    attaches them to the preceding claim.
    """
    if not paragraphs:
        return paragraphs
    out: list[str] = []
    counter = 0
    for para, has_numpr in zip(paragraphs, numpr_flags, strict=True):
        typed = _CLAIM_START_RE.match(para)
        if typed:
            # Let the parser read the embedded number directly.
            out.append(para)
            counter = int(re.match(r"\s*(\d+)", para).group(1))
            continue
        if has_numpr:
            counter += 1
            out.append(f"{counter}. {para}")
            continue
        out.append(para)
    return out


def extract_cn_sections_from_docx(sections: list[DocxSection]) -> CnPatentDocument:
    """Extract CN patent document structure from Word sections.

    Phase 8c (ADR-109) — three-tier section-ID fallback chain. The tier
    ordering (body_anchor tried first, page_header only if body_anchor
    fails) was reverse-calibrated against the 10-fixture Google-Patents-
    publication corpus and is NOT the authoring-format order. Verified
    2026-04-19 against the CNIPA 五书模板 + WORD转XML编辑器 user manual
    §3.3.1: drafter-authoring files use page_header to delimit 五书
    parts. Real CNIPA publication exports use body_anchor (with
    pagination suffixes) instead. Both tiers must remain; swap priority
    only if a user-demand signal shows drafter-authoring files fail to
    parse due to spurious body-anchor matches (not observed to date).

    1. **Tier 1 body_anchor** — flatten paragraphs across Word sections
       and classify by standalone 五书 markers (权利要求书, 说明书, etc.).
       Fires for Google-Patents-downloaded publication exports where the
       五书 titles appear as body paragraphs (often with ``N/M 页``
       pagination suffixes).
    2. **Tier 2 claim_density** — if no structural anchor is found, scan
       for runs of ≥3 consecutive claim-start paragraphs. Recovers the
       claims span when body anchors have been stripped.
    3. **Tier 3 page_header** — Word-page-header mapping. Fires for
       CNIPA 五书模板 drafter-authoring files where the five parts are
       delimited by Word section page headers (the ``说明书摘要`` /
       ``摘要附图`` / ``权利要求书`` / ``说明书`` / ``说明书附图`` headers
       specified in the official template).

    Stage 1 shipped a fourth `template_substyle` tier but it never fired
    on the real 10-fixture corpus or the two synthetic parity pairs;
    deleted in Stage 1.5 rather than "implicitly covered" (same
    rationalization that let Phase 8b's `用` exclusion rot).

    The winning tier is recorded per-section on
    ``CnPatentDocument.section_source_strategies``, keyed by
    ``"claims"`` / ``"specification"`` / ``"abstract"``. A document can
    have mixed strategies (e.g., claims via body_anchor, abstract via
    page_header fallback).
    """
    # --- Run tiers ---
    ba_spec, ba_claims, ba_abstract, ba_numpr, ba_anchor_count = _collect_by_body_anchor(sections)
    ph_spec, ph_claims, ph_abstract, ph_numpr = _collect_by_page_header(sections)

    strategies: dict[str, str] = {
        "claims": "none",
        "specification": "none",
        "abstract": "none",
    }
    spec_paragraphs: list[str]
    claims_paragraphs: list[str]
    claims_numpr_flags: list[bool]
    abstract_paragraphs: list[str]

    if ba_anchor_count >= 2 and ba_claims:
        spec_paragraphs = ba_spec
        claims_paragraphs = ba_claims
        claims_numpr_flags = ba_numpr
        abstract_paragraphs = ba_abstract
        if ba_claims:
            strategies["claims"] = "body_anchor"
        if ba_spec:
            strategies["specification"] = "body_anchor"
        if ba_abstract:
            strategies["abstract"] = "body_anchor"
    elif ph_claims or ph_spec:
        # Page-header branch — fires for 五书模板 Word exports where
        # section titles live in page headers.
        spec_paragraphs = ph_spec
        claims_paragraphs = ph_claims
        claims_numpr_flags = ph_numpr
        abstract_paragraphs = ph_abstract
        if ph_claims:
            strategies["claims"] = "page_header"
        if ph_spec:
            strategies["specification"] = "page_header"
        if ph_abstract:
            strategies["abstract"] = "page_header"
    else:
        # Tier 3 — claim-density heuristic recovers claims only.
        cd_claims, cd_numpr = _collect_by_claim_density(sections)
        if cd_claims:
            spec_paragraphs = ba_spec  # best-effort (may be empty)
            claims_paragraphs = cd_claims
            claims_numpr_flags = cd_numpr
            abstract_paragraphs = ba_abstract
            strategies["claims"] = "claim_density"
            if ba_spec:
                strategies["specification"] = "body_anchor"
            if ba_abstract:
                strategies["abstract"] = "body_anchor"
        else:
            spec_paragraphs = []
            claims_paragraphs = []
            claims_numpr_flags = []
            abstract_paragraphs = []

    # Pre-split continuation paragraphs that embed a mid-paragraph claim
    # boundary, BEFORE the numPr backfill runs. Without this, the backfill
    # counter drifts on sibling numPr claims that follow the embedded
    # boundary, producing duplicate claim IDs downstream.
    claims_paragraphs, claims_numpr_flags = _presplit_mid_paragraph(
        claims_paragraphs, claims_numpr_flags
    )

    # Backfill synthetic N. prefixes on numPr claims (ADR-109).
    claims_paragraphs = _backfill_numpr_prefixes(claims_paragraphs, claims_numpr_flags)

    # Split specification into sub-sections
    subsections, section_order = _split_spec_subsections(spec_paragraphs)

    # Extract title (before first sub-section header)
    title = _extract_title(spec_paragraphs)

    # Detect user-added paragraph numbering (should not exist in CN .docx)
    all_spec_paras: list[str] = []
    for paras in subsections.values():
        all_spec_paras.extend(paras)
    has_numbering, para_nums = _detect_paragraph_numbering(all_spec_paras)

    # Parse claims
    claims_text = "\n".join(claims_paragraphs)
    claims = parse_cn_claims_docx(claims_text)

    # Abstract
    abstract_text = "\n".join(abstract_paragraphs).strip()

    # INID cover-page fallback (publication docs). Fires only when the
    # primary tiers left title or abstract empty — drafter files never
    # have an INID cover, so this is a no-op for them.
    if not title or not abstract_text:
        inid_title, inid_abstract = _extract_inid_title_abstract(sections)
        if not title and inid_title:
            title = inid_title
        if not abstract_text and inid_abstract:
            abstract_paragraphs = inid_abstract
            abstract_text = "\n".join(abstract_paragraphs).strip()

    abstract_char_count = len(
        abstract_text.replace("\n", "").replace(" ", "").replace("\u3000", "")
    )

    # Figure references from detailed description and drawings description
    detail_text = "\n".join(subsections["detailed_description"])
    drawings_desc_text = "\n".join(subsections["drawings_description"])
    all_refs_text = detail_text + "\n" + drawings_desc_text
    figure_refs = _extract_figure_refs(all_refs_text)
    figure_count = _count_figures_from_descriptions(subsections["drawings_description"])

    # Patent type heuristic: count 本实用新型 vs 本发明 in body text
    body_text = " ".join(all_spec_paras)
    if body_text.count("本实用新型") > body_text.count("本发明"):
        patent_type = CnPatentType.UTILITY_MODEL
    else:
        patent_type = CnPatentType.INVENTION

    return CnPatentDocument(
        patent_type=patent_type,
        title=title,
        technical_field=subsections["technical_field"],
        background=subsections["background"],
        summary=subsections["summary"],
        drawings_description=subsections["drawings_description"],
        detailed_description=subsections["detailed_description"],
        claims=claims,
        abstract_text=abstract_text,
        abstract_char_count=abstract_char_count,
        paragraph_numbers=para_nums,
        figure_count=figure_count,
        figure_refs=figure_refs,
        has_paragraph_numbering=has_numbering,
        input_format="docx",
        has_doc_page_fallback=False,
        section_source_strategies=strategies,
        section_order=section_order,
    )
