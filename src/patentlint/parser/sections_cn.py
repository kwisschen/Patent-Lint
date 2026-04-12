# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""CN patent .docx section extraction — 五書模板 format."""

from __future__ import annotations

import re

from patentlint.models import CnPatentDocument, CnPatentType
from patentlint.parser.claims_cn import parse_cn_claims_docx
from patentlint.parser.docx_loader import DocxSection

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
    ("summary", re.compile(r"^[\s\u3000]*发明内容[\s\u3000]*$")),
    ("drawings_description", re.compile(r"^[\s\u3000]*附图说明[\s\u3000]*$")),
    ("detailed_description", re.compile(r"^[\s\u3000]*具体实施方式[\s\u3000]*$")),
]

# ---------------------------------------------------------------------------
# Paragraph numbering detection — user-added numbering in CN .docx is an error
# ---------------------------------------------------------------------------

_PARA_NUM_PATTERN = re.compile(r"^\[(\d{4})\]")

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


def _split_spec_subsections(paragraphs: list[str]) -> dict[str, list[str]]:
    """Split specification paragraphs into sub-sections by header detection.

    Returns a dict with keys: technical_field, background, summary,
    drawings_description, detailed_description. Each value is a list of
    paragraph strings (excluding the header line itself).
    """
    result: dict[str, list[str]] = {
        "technical_field": [],
        "background": [],
        "summary": [],
        "drawings_description": [],
        "detailed_description": [],
    }

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
            continue  # Skip the header line itself

        if current_key is not None:
            result[current_key].append(para)

    return result


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


def detect_patent_document_cn(paragraphs: list[str]) -> bool:
    """Heuristic check for whether a CN .docx appears to be a patent specification.

    Returns True if patent indicators are found, False otherwise.
    OR logic — returns True on first match.
    """
    for para in paragraphs:
        stripped = para.strip()

        # 1. CN spec sub-section header (技术领域, 背景技术, etc.)
        for _, pattern in _SPEC_SUBSECTIONS:
            if pattern.match(stripped):
                return True

        # 2. 五書模板 boundary markers
        if stripped in ("权利要求书", "说明书摘要"):
            return True

    # 3. Numbered claims: 3+ lines starting with Arabic numeral + period variant
    full_text = "\n".join(paragraphs)
    if len(re.findall(r"^\s*\d+[.．。]\s*", full_text, re.MULTILINE)) >= 3:
        return True

    return False


def _collect_by_page_header(
    sections: list[DocxSection],
) -> tuple[list[str], list[str], list[str], list[bool]]:
    """Tier 4 (legacy) — classify sections by Word page-header text.

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
    """Tier 1 — walk flattened paragraphs, classify by body-anchor scan.

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

    Phase 8c (ADR-109) — three-tier section-ID fallback chain:

    1. **Tier 1 body_anchor** — flatten paragraphs across Word sections
       and classify by standalone 五书 markers (权利要求书, 说明书, etc.).
       Primary tier; fires for real CNIPA downloads.
    2. **Tier 2 claim_density** — if no structural anchor is found, scan
       for runs of ≥3 consecutive claim-start paragraphs. Recovers the
       claims span when body anchors have been stripped.
    3. **Tier 3 page_header** — legacy Word-page-header mapping. Last
       resort; fires for 五书模板 Word exports where section titles live
       in page headers rather than body paragraphs.

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

    # Backfill synthetic N. prefixes on numPr claims (ADR-109).
    claims_paragraphs = _backfill_numpr_prefixes(claims_paragraphs, claims_numpr_flags)

    # Split specification into sub-sections
    subsections = _split_spec_subsections(spec_paragraphs)

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
    )
