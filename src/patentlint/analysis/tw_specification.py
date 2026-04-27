# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""TW specification analysis checks.

Ten pure functions checking Taiwan patent specification formatting
against TIPO rules (專利法施行細則 and 專利審查基準).
"""

from __future__ import annotations

import re

from patentlint.analysis.figure_refs import TW_PARSER
from patentlint.analysis.utils import _dx
from patentlint.models import CheckItem, TwPatentDocument, TwPatentType

# Canonical section order per 專利法施行細則 §17
_CANONICAL_ORDER = [
    "technical_field",
    "prior_art",
    "disclosure",
    "drawings_description",
    "embodiment",
    "symbol_table",
]

_SECTION_NAMES_TW = {
    "technical_field": "技術領域",
    "prior_art": "先前技術",
    "disclosure_invention": "發明內容",
    "disclosure_utility": "新型內容",
    "drawings_description": "圖式簡單說明",
    "embodiment": "實施方式",
    "symbol_table": "符號說明",
}

_VALID_ENDINGS = frozenset("。！？")

_TRADEMARK_RE = re.compile(r"[®™©]")
# Model-number pattern: ALL-CAPS alphanumeric tokens that look like product
# codes (XY-1234, ABC-12A). No IGNORECASE — lowercase hyphenated words like
# "foo-22" or "usb-30" are not model numbers. No `\b` word boundaries
# because TW titles often surround the code with CJK chars (一種XY-1234裝置),
# and CJK chars are Unicode word-chars in Python's regex engine, which
# defeats the boundary check. Use character-class lookbehind/ahead to
# guard against picking up codes that are embedded inside a longer Latin
# alphanumeric identifier.
_MODEL_NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9])"
    r"[A-Z]{2,}[- ]?\d{2,}[A-Z0-9\-]*"
    r"(?![A-Za-z0-9])"
)
# Spec-body references to claims (prohibited per 施行細則 §17). Introducing
# verb is not constrained — TIPO 偵錯系統 (Table 1 #20) accepts 如/依據/根據
# for dep-claim openers, so spec body may use any of them when referring
# back to a claim. Connective accepts either 所(述|記載|揭示|描述) or bare
# 之/的 (請求項N之X form). Distance-bounded (≤20 chars) to avoid FPs on
# cross-sentence co-occurrences.
_CLAIM_REF_RE = re.compile(
    r"請求項\s*\d+"
    r"(?:\s*(?:至|到|~|、|或)\s*(?:請求項\s*)?\d+)?"
    r"[^。]{0,20}?"
    r"(?:所(?:述|記載|揭示|描述)|[之的])"
)
_REF_NUMERAL_RE = re.compile(
    r"[(（]"                # require opening paren (ASCII or fullwidth)
    r"(\d{1,4}[a-zA-Z]?)"   # 1-4 digit + optional single letter suffix
    r"[)）]"                # require closing paren
)


def _all_spec_sections(doc: TwPatentDocument) -> list[str]:
    """Collect all spec paragraphs from body sections."""
    return (
        doc.technical_field
        + doc.prior_art
        + doc.disclosure
        + doc.drawings_description
        + doc.embodiment
    )


def _all_spec_text(doc: TwPatentDocument) -> str:
    """Join all spec paragraphs into a single string."""
    return "\n".join(_all_spec_sections(doc))


def _section_has_content(items: list) -> bool:
    """Check whether a section list has any non-empty content."""
    if not items:
        return False
    if isinstance(items[0], str):
        return any(p.strip() for p in items)
    # SymbolEntry list — non-empty means has content
    return True


# ── Check 1 ──────────────────────────────────────────────────────────────


def check_required_sections(doc: TwPatentDocument) -> list[CheckItem]:
    """Check that mandatory top-level TIPO filing sections are non-empty.

    Covers the three top-level components a TIPO application requires per
    專利法 §25 第1項 (摘要 / 說明書 / 申請專利範圍) plus the 說明書
    subsections enumerated in 專利法施行細則 §17. The 【發明說明書】 /
    【新型說明書】 wrapper header itself is intentionally not checked —
    when subsection headers (【技術領域】 etc.) carry the content, the
    specification is present in substance even if the wrapper divider is
    omitted.
    """
    missing = []

    # Top-level: 摘要 (required per 專利法 §25 第1項, format per §21).
    # Strict: the abstract HEADING must be present. The parser's 【中文】
    # text marker can populate ``abstract_text`` even when the drafter
    # omitted 【摘要】 / 【發明摘要】 / 【新型摘要】 — that is itself a
    # §25 violation, so we key off the header-seen flag rather than the
    # content field.
    if not doc.abstract_header_seen or not doc.abstract_text.strip():
        missing.append("摘要")

    # 說明書 subsections per 專利法施行細則 §17
    if not _section_has_content(doc.technical_field):
        missing.append("技術領域")
    if not _section_has_content(doc.prior_art):
        missing.append("先前技術")

    disclosure_name = (
        "新型內容" if doc.patent_type == TwPatentType.UTILITY_MODEL else "發明內容"
    )
    if not _section_has_content(doc.disclosure):
        missing.append(disclosure_name)

    if not _section_has_content(doc.embodiment):
        missing.append("實施方式")

    # Conditional: 圖式簡單說明 + 符號說明 are required when drawings exist
    # (per 施行細則 §17 第1款 第5項 + 第7項). Use ``figure_refs`` (parsed
    # from spec body) as the canonical signal that figures exist —
    # mirrors CN's approach at cn_specification.py and is robust to
    # the case where a user removes both 圖式簡單說明 AND 符號說明
    # while keeping figure references in 實施方式.
    drawings_exist = bool(doc.figure_refs) or _section_has_content(doc.drawings_description)
    if drawings_exist:
        if not _section_has_content(doc.drawings_description):
            missing.append("圖式簡單說明")
        if not _section_has_content(doc.symbol_table):
            missing.append("符號說明")

    # Top-level: 申請專利範圍 (required per 專利法 §25 第1項, format per §18).
    # Strict: the claims HEADING must be present. Future parser fallbacks
    # (numbering-pattern recovery) would otherwise mask a missing-header
    # defect; key off the header-seen flag, not the content field.
    if not doc.claims_header_seen or not doc.claims:
        missing.append("申請專利範圍")

    if missing:
        return [CheckItem(
            status="amend",
            message=f"Missing required sections: {', '.join(missing)}",
            message_key="check.tw.spec.requiredSections.amend",
            details=", ".join(missing),
            details_key="details.tw.requiredSections",
            details_params={
                "sections": ", ".join(missing),
                "flagged_phrases": {
                    "items": [{"kind": "section", "token": s} for s in missing]
                },
            },
            reference="專利法 §25 第1項、專利法施行細則 §17",
            diagnostics=_dx(
                missing_count=len(missing),
                first_missing=missing[0] if missing else None,
                missing_sections=missing[:10],
                total_required=len(missing) + (5 - len(missing)) if len(missing) <= 5 else len(missing),
                abstract_header_seen=getattr(doc, "abstract_header_seen", None),
                claims_header_seen=getattr(doc, "claims_header_seen", None),
            ),
        )]
    return [CheckItem(
        status="pass",
        message="All required sections are present.",
        message_key="check.tw.spec.requiredSections.pass",
        reference="專利法 §25 第1項、專利法施行細則 §17",
    )]


# ── Check 2 ──────────────────────────────────────────────────────────────


def check_section_ordering(doc: TwPatentDocument) -> list[CheckItem]:
    """Verify sections appear in prescribed TIPO order.

    Reads ``doc.section_order`` — the list of canonical body-section keys
    in the order the parser first encountered each 【】bracket header. A
    non-increasing canonical-index sequence indicates the drafter placed
    sections out of the 專利法施行細則 §17 order. Empty ``section_order``
    (no bracket headers found) passes vacuously.
    """
    canonical_index = {name: idx for idx, name in enumerate(_CANONICAL_ORDER)}
    indices = [
        canonical_index[s] for s in doc.section_order if s in canonical_index
    ]
    is_sorted = all(indices[i] < indices[i + 1] for i in range(len(indices) - 1))

    if not is_sorted:
        return [CheckItem(
            status="amend",
            message="Specification sections are not in the required order.",
            message_key="check.tw.spec.sectionOrdering.amend",
            details_key="details.tw.sectionOrdering",
            reference="專利法施行細則 §17",
            diagnostics=_dx(
                sections_seen=len(indices),
                total_canonical_sections=len(_CANONICAL_ORDER),
                section_order_actual=list(doc.section_order)[:10],
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
        message_key="check.tw.spec.sectionOrdering.pass",
        reference="專利法施行細則 §17",
    )]


# ── Check 3 ──────────────────────────────────────────────────────────────


def check_paragraph_numbering(doc: TwPatentDocument) -> list[CheckItem]:
    """Check paragraph numbering format when present (optional per §17)."""
    if not doc.has_paragraph_numbering:
        return [CheckItem(
            status="pass",
            message="Paragraph numbering is absent (optional per 施行細則 §17).",
            message_key="check.tw.spec.paragraphNumbering.pass",
            reference="專利法施行細則 §17",
        )]

    nums = doc.paragraph_numbers
    if not nums:
        return [CheckItem(
            status="pass",
            message="Paragraph numbering correct.",
            message_key="check.tw.spec.paragraphNumbering.pass",
            reference="專利法施行細則 §17",
        )]

    # Verify 4-digit format
    four_digit_re = re.compile(r"^\d{4}$")
    bad_format = [n for n in nums if not four_digit_re.match(n)]
    if bad_format:
        examples_str = ", ".join(bad_format[:5])
        return [CheckItem(
            status="amend",
            message=f"{len(bad_format)} paragraph(s) use non-[NNNN] format.",
            message_key="check.tw.spec.paragraphNumbering.amendFormat",
            details_key="details.tw.paragraphNumbering",
            details_params={"count": len(bad_format), "examples": examples_str},
            reference="專利法施行細則 §17",
            diagnostics=_dx(
                flagged_count=len(bad_format),
                total_paragraphs=len(nums),
                findings=[
                    {"raw_value": n[:32], "charlen": len(n), "is_digits": n.isdigit()}
                    for n in bad_format[:5]
                ],
            ),
        )]

    # Check sequential
    int_nums = [int(n) for n in nums]
    for i in range(1, len(int_nums)):
        if int_nums[i] != int_nums[i - 1] + 1:
            return [CheckItem(
                status="amend",
                message=f"Paragraph numbering has a gap: [{nums[i - 1]}] is followed by [{nums[i]}].",
                message_key="check.tw.spec.paragraphNumbering.amendGap",
                details_key="details.tw.paragraphNumbering",
                details_params={"prev": nums[i - 1], "next": nums[i]},
                reference="專利法施行細則 §17",
                diagnostics=_dx(
                    gap_size=int_nums[i] - int_nums[i - 1],
                    total_paragraphs=len(nums),
                    prev_value=nums[i - 1],
                    next_value=nums[i],
                    gap_position=i,
                    is_backward=int_nums[i] < int_nums[i - 1],
                ),
            )]

    return [CheckItem(
        status="pass",
        message="Paragraph numbering is correct.",
        message_key="check.tw.spec.paragraphNumbering.pass",
        reference="專利法施行細則 §17",
    )]


# ── Check 4 ──────────────────────────────────────────────────────────────


_BRACKET_SUBHEADING = re.compile(r"^\[.+\]$")
_SYMBOL_TABLE_ENTRY = re.compile(
    r"^[A-Za-z0-9~\-]+\s*(?:[‧·.…：:\t]\s*[‧·.…]*\s*|\s{2,}).+"
)
# JP-translation-style numbered sub-claim marker in the disclosure body,
# e.g. `[1]一種蓋組件...，` / `[2]如所述[1]記載的蓋組件...`. When a paragraph
# starts with this marker, the sub-claim body may legitimately span multiple
# Word paragraphs (intermediate lines ending with ，/、/；, closing line with 。).
_BRACKET_CLAIM_MARKER = re.compile(r"^\[\d+\]")


def _is_skip_paragraph_ending(text: str) -> bool:
    """Check if paragraph should be excluded from ending punctuation check."""
    # Half-width bracket sub-headings: [第一實施例]
    if _BRACKET_SUBHEADING.match(text):
        return True
    # Symbol table entry patterns: numeral + separator + name
    if _SYMBOL_TABLE_ENTRY.match(text):
        return True
    return False


def check_paragraph_ending(doc: TwPatentDocument) -> list[CheckItem]:
    """Check each specification paragraph ends with valid Chinese punctuation.

    Excludes 符號說明 section, half-width bracket sub-headings, and
    symbol table entry patterns from the check.

    Relaxed sections (發明內容, 圖式簡單說明, 實施方式) also treat
    JP-translation-style `[N]`-numbered sub-claim groups as single logical
    units — intermediate continuation paragraphs are skipped and only the
    closing paragraph of the unit (the one that ends with valid punctuation)
    is validated. A unit is opened by a paragraph starting with `[<digit>+]`
    that lacks a valid ending, and closed by the first subsequent paragraph
    that ends with valid punctuation (or by a new heading/section boundary).
    """
    # Relaxed endings for 圖式簡單說明, 發明內容/新型內容, 實施方式
    # (semicolons and colons allowed for enumerations and step descriptions)
    _RELAXED_VALID = _VALID_ENDINGS | frozenset("；：")

    def _has_valid_ending_tw(text: str, relaxed: bool) -> bool:
        endings = _RELAXED_VALID if relaxed else _VALID_ENDINGS
        if text[-1] in endings:
            return True
        # Allow "；以及" and "；及" endings (penultimate list item)
        if relaxed and (text.endswith("；以及") or text.endswith("；及")):
            return True
        return False

    # Only check body sections, NOT 符號說明.
    # Strict (。！？ only) for 技術領域 and 先前技術.
    # Relaxed (+ ；：) for 發明內容, 圖式簡單說明, 實施方式.
    sections_to_check = [
        (doc.technical_field, False),
        (doc.prior_art, False),
        (doc.disclosure, True),
        (doc.drawings_description, True),
        (doc.embodiment, True),
    ]
    # Parallel word-numbers aligned with the same concatenation order used
    # by sections_to_check. Populated by extract_tw_sections for .docx
    # input; may be empty for other input paths (XML, legacy callers), in
    # which case the check falls back to an internal ordinal.
    word_numbers = doc.body_paragraph_word_numbers

    bad_paragraphs: list[int | str] = []
    bad_findings: list[dict] = []
    ordinal = 0
    for section_paras, relaxed in sections_to_check:
        in_claim_unit = False
        for para in section_paras:
            stripped = para.strip()
            if not stripped:
                continue
            ordinal += 1
            if _is_skip_paragraph_ending(stripped):
                # Full-bracket subheadings reset any open claim unit.
                if _BRACKET_SUBHEADING.match(stripped):
                    in_claim_unit = False
                continue
            has_valid = _has_valid_ending_tw(stripped, relaxed)
            if relaxed and _BRACKET_CLAIM_MARKER.match(stripped):
                # Start of an [N]-numbered sub-claim group.
                in_claim_unit = not has_valid
                if not has_valid:
                    continue  # unit continues into subsequent paragraphs
            elif relaxed and in_claim_unit:
                # Continuation paragraph inside an open [N] unit.
                if has_valid:
                    in_claim_unit = False
                continue
            if not has_valid:
                # Prefer the Word 【NNNN】 auto-number when the drafter's
                # file carried it; fall back to the internal ordinal
                # otherwise so XML/legacy paths still produce useful output.
                #
                # Continuation paragraphs (Word paragraphs that lack
                # ``w:numPr`` because they wrap inside a single logical
                # 【NNNN】 paragraph) carry word_number=None. Walk backward
                # to the most recent non-None value so the flagged label
                # matches the 【NNNN】 the drafter sees in Word — not an
                # internal ordinal that shifts on subsection boundaries.
                label: int | str = ordinal
                resolved_wn: str | None = None
                idx = ordinal - 1
                while idx >= 0 and idx < len(word_numbers):
                    candidate = word_numbers[idx]
                    if candidate is not None:
                        resolved_wn = candidate
                        break
                    idx -= 1
                if resolved_wn is not None:
                    label = resolved_wn
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
            message_key="check.tw.spec.paragraphEnding.verify",
            details=f"{len(bad_paragraphs)} paragraphs",
            details_key="details.tw.paragraphEnding",
            details_params={"count": len(bad_paragraphs), "paragraphs": bad_paragraphs},
            reference="專利審查基準",
            diagnostics=_dx(
                flagged_count=len(bad_paragraphs),
                total_paragraphs_scanned=ordinal,
                findings=bad_findings,
            ),
        )]
    return [CheckItem(
        status="pass",
        message="All paragraphs have valid ending punctuation.",
        message_key="check.tw.spec.paragraphEnding.pass",
        reference="專利審查基準",
    )]


# ── Check 5 ──────────────────────────────────────────────────────────────


def check_figure_ref_consistency(doc: TwPatentDocument) -> list[CheckItem]:
    """Compare figure references between 圖式簡單說明 and 實施方式."""
    drawings_text = "\n".join(doc.drawings_description)
    embodiment_text = "\n".join(doc.embodiment)

    if not drawings_text.strip():
        return [CheckItem(
            status="pass",
            message="No 圖式簡單說明 to check.",
            message_key="check.tw.spec.figureRefConsistency.pass",
            reference="專利審查基準",
        )]

    drawings_figs = TW_PARSER.extract(drawings_text).ids
    embodiment_figs = TW_PARSER.extract(embodiment_text).ids

    # Collapse sub-figure suffixes onto the parent figure number so that
    # 圖12, 圖12(A), 圖12A all compare as figure 12. Without this, a drawings
    # section listing 圖12(A) and 圖12(B) would not match an embodiment
    # reference to bare 圖12, and the old ``_to_int_safe`` filter silently
    # dropped suffix IDs from the rendered mismatch list.
    def _parent_num(fid: str) -> int | None:
        m = re.match(r"(\d+)", fid)
        return int(m.group(1)) if m else None

    drawings_parents = {p for p in (_parent_num(f) for f in drawings_figs) if p is not None}
    embodiment_parents = {p for p in (_parent_num(f) for f in embodiment_figs) if p is not None}

    only_drawings = sorted(drawings_parents - embodiment_parents)
    only_embodiment = sorted(embodiment_parents - drawings_parents)

    if only_drawings or only_embodiment:
        return [CheckItem(
            status="amend",
            message="Figure references differ between 圖式簡單說明 and 實施方式.",
            message_key="check.tw.spec.figureRefConsistency.amend",
            details_key="details.tw.figureRefConsistency",
            details_params={
                "figure_ref_inconsistency": {
                    "only_drawings": only_drawings,
                    "only_embodiment": only_embodiment,
                    "jurisdiction": "tw",
                },
            },
            reference="專利審查基準",
            diagnostics=_dx(
                only_drawings_count=len(only_drawings),
                only_embodiment_count=len(only_embodiment),
                total_drawings=len(drawings_parents),
                total_embodiment=len(embodiment_parents),
                only_drawings_sample=only_drawings[:10],
                only_embodiment_sample=only_embodiment[:10],
            ),
        )]

    return [CheckItem(
        status="pass",
        message="Figure references are consistent across sections.",
        message_key="check.tw.spec.figureRefConsistency.pass",
        reference="專利審查基準",
    )]


# ── Check 6 ──────────────────────────────────────────────────────────────


def check_patent_type_terminology(doc: TwPatentDocument) -> list[CheckItem]:
    """Flag 本發明 / 此發明 / 本新型 / 此新型 used against declared patent type.

    Per TIPO 偵錯系統 Table 1 #18: 新型內容 and 實施方式 must not contain
    「本發明」or「此發明」when filed as 新型 (and symmetrically for 發明).
    """
    text = _all_spec_text(doc)

    # Forbidden terms per direction. TIPO lists 本 and 此 prefixes.
    if doc.patent_type == TwPatentType.INVENTION:
        forbidden = ("本新型", "此新型")
    elif doc.patent_type == TwPatentType.UTILITY_MODEL:
        forbidden = ("本發明", "此發明")
    else:
        forbidden = ()

    hits = [term for term in forbidden if term in text]
    if hits:
        primary = hits[0]
        return [CheckItem(
            status="verify",
            message=f"Patent type terminology mismatch: {', '.join(hits)}.",
            message_key="check.tw.spec.patentTypeTerminology.verify",
            details=f"Patent type mismatch: {primary}",
            details_key="details.tw.patentTypeTerminology",
            details_params={"term": primary},
            reference="專利審查基準",
            diagnostics=_dx(
                patent_type=(
                    "invention"
                    if doc.patent_type == TwPatentType.INVENTION
                    else "utility_model"
                ),
                mismatched_term_count=len(hits),
                mismatched_term_codepoint=ord("本"),
                mismatched_terms=hits[:10],
                first_match_position=text.find(hits[0]) if hits else None,
                spec_charlen=len(text),
            ),
        )]

    return [CheckItem(
        status="pass",
        message="Patent type terminology is consistent.",
        message_key="check.tw.spec.patentTypeTerminology.pass",
        reference="專利審查基準",
    )]


# ── Check 7 ──────────────────────────────────────────────────────────────


def check_title(doc: TwPatentDocument) -> list[CheckItem]:
    """Check title for prohibited content (no character limit for TW)."""
    title = doc.title
    if not title.strip():
        return [CheckItem(
            status="amend",
            message="Title is missing.",
            message_key="check.tw.spec.title.amendMissing",
            details_key="details.tw.titleMissing",
            details="",
            reference="專利審查基準",
            diagnostics=_dx(
                reason_code="missing",
                title_charlen=0,
                title_raw_charlen=len(doc.title),
                title_is_whitespace=bool(doc.title and not doc.title.strip()),
            ),
        )]

    items: list[dict] = []
    tm_match = _TRADEMARK_RE.search(title)
    if tm_match:
        items.append({"kind": "trademark", "token": tm_match.group()})
    model_match = _MODEL_NUMBER_RE.search(title)
    if model_match:
        items.append({"kind": "model", "token": model_match.group()})

    if items:
        return [CheckItem(
            status="amend",
            message="Title contains prohibited content.",
            message_key="check.tw.spec.title.amendContent",
            details_key="details.tw.title",
            details_params={"title_prohibited_items": {"items": items}},
            reference="專利審查基準",
            diagnostics=_dx(
                reason_code="prohibited_content",
                flagged_count=len(items),
                title_charlen=len(title),
                flagged_kinds=[it.get("kind") for it in items],
                tokens_sample=[(it.get("token") or "")[:32] for it in items[:5]],
            ),
        )]

    return [CheckItem(
        status="pass",
        message="Title meets requirements.",
        message_key="check.tw.spec.title.pass",
        reference="專利審查基準",
    )]


# ── Check 8 ──────────────────────────────────────────────────────────────


def check_spec_claim_reference(doc: TwPatentDocument) -> list[CheckItem]:
    """Flag specification text that references specific claims."""
    text = _all_spec_text(doc)
    match = _CLAIM_REF_RE.search(text)

    if match:
        snippet = match.group()[:50]
        return [CheckItem(
            status="amend",
            message="Specification references a specific claim.",
            message_key="check.tw.spec.claimReference.amend",
            details=snippet,
            details_key="details.tw.claimReference",
            details_params={"detail": snippet},
            reference="專利法施行細則 §17",
            diagnostics=_dx(
                hit_count=1,
                snippet_charlen=len(snippet),
                matched_phrase=match.group()[:80],
                match_position=match.start(),
                spec_text_charlen=len(text),
            ),
        )]

    return [CheckItem(
        status="pass",
        message="No claim references found in specification.",
        message_key="check.tw.spec.claimReference.pass",
        reference="專利法施行細則 §17",
    )]


# ── Check 9 ──────────────────────────────────────────────────────────────


def check_symbol_table_presence(doc: TwPatentDocument) -> list[CheckItem]:
    """Check 符號說明 presence when drawings exist."""
    if _section_has_content(doc.drawings_description) and not _section_has_content(doc.symbol_table):
        return [CheckItem(
            status="amend",
            message="符號說明 section missing but 圖式簡單說明 is present.",
            message_key="check.tw.spec.symbolTablePresence.amend",
            details_key="details.tw.symbolTablePresence",
            reference="專利法施行細則 §17",
            diagnostics=_dx(
                reason_code="missing_with_drawings_present",
                drawings_section_paragraphs=len(doc.drawings_description),
                symbol_table_entries=len(doc.symbol_table) if doc.symbol_table else 0,
                drawings_section_charlen=sum(len(p) for p in doc.drawings_description),
            ),
        )]

    return [CheckItem(
        status="pass",
        message="符號說明 section present.",
        message_key="check.tw.spec.symbolTablePresence.pass",
        reference="專利法施行細則 §17",
    )]


# ── Check 10 ─────────────────────────────────────────────────────────────


def check_symbol_table_consistency(doc: TwPatentDocument) -> list[CheckItem]:
    """Compare 符號說明 entries against 實施方式 text."""
    if not doc.symbol_table:
        return [CheckItem(
            status="pass",
            message="No 符號說明 to check.",
            message_key="check.tw.spec.symbolTableConsistency.pass",
            reference="專利審查基準",
        )]

    embodiment_text = "\n".join(doc.embodiment)

    # Check defined but unreferenced
    unreferenced = []
    for entry in doc.symbol_table:
        # For range numerals (e.g., S21~S25, 3001~3010), check if any
        # component appears in the text
        parts = re.split(r"[~\-]", entry.numeral)
        found = any(p in embodiment_text for p in parts if p.strip())
        if not found:
            unreferenced.append(entry.numeral)

    # Check reference numerals in embodiment not defined in symbol_table
    # Build set of all individual numerals covered by symbol_table entries
    defined_numerals: set[str] = set()
    for entry in doc.symbol_table:
        defined_numerals.add(entry.numeral)
        # Also add individual parts of range numerals
        for part in re.split(r"[~\-]", entry.numeral):
            part = part.strip()
            if part:
                defined_numerals.add(part)
    embodiment_numerals = set(_REF_NUMERAL_RE.findall(embodiment_text))
    undefined = sorted(embodiment_numerals - defined_numerals)

    if unreferenced or undefined:
        return [CheckItem(
            status="verify",
            message="符號說明 entries inconsistent with 實施方式.",
            message_key="check.tw.spec.symbolTableConsistency.verify",
            details_key="details.tw.symbolTableConsistency",
            details_params={
                "symbol_table_inconsistency": {
                    "unreferenced": sorted(unreferenced)[:10],
                    "undefined": sorted(undefined)[:10],
                },
            },
            reference="專利審查基準",
            diagnostics=_dx(
                unreferenced_count=len(unreferenced),
                undefined_count=len(undefined),
                total_table_entries=len(doc.symbol_table),
                unreferenced_sample=[(n or "")[:32] for n in sorted(unreferenced)[:5]],
                undefined_sample=[(n or "")[:32] for n in sorted(undefined)[:5]],
            ),
        )]

    return [CheckItem(
        status="pass",
        message="符號說明 entries consistent with specification.",
        message_key="check.tw.spec.symbolTableConsistency.pass",
        reference="專利審查基準",
    )]


# ── Check 11 ─────────────────────────────────────────────────────────────

# Taiwanese indigenous peoples terminology (per TIPO 偵錯系統 Table 1 #19,
# grounded in 原住民族傳統智慧創作保護條例). TIPO's PDF fig 31 shows example
# hits (魯凱族, 部落, 阿美族, 卑南族, 達悟族) but doesn't publish its full
# trigger list. The list below covers 原住民族委員會's 16 officially-
# recognized peoples (high confidence — statutory indigenous status under
# 原住民族基本法) plus the two generic terms TIPO surfaced in examples.
#
# NOT INCLUDED: the 10 unrecognized Pingpu peoples (阿立昆族, 貓霧拺族,
# 巴賽族, 洪雅族, 噶哈巫族, 凱達格蘭族, 拍瀑拉族, 巴宰族, 猴猴族,
# 道卡斯族) — they lack statutory indigenous status and their names
# overlap more with ordinary usage, raising FP risk. If TIPO's real
# trigger list is confirmed to include these, the tuple can be extended.
# 雅美族 (older colonial-era name) and 達悟族 (modern official name) both
# included since they name the same people and either can appear in drafts.
# Advisory VERIFY — flags for drafter review; not a hard violation.
_TW_INDIGENOUS_TERMS = (
    # 16 officially-recognized indigenous peoples
    "阿美族", "泰雅族", "排灣族", "布農族", "卑南族", "魯凱族", "鄒族",
    "賽夏族", "雅美族", "達悟族", "邵族", "噶瑪蘭族", "太魯閣族",
    "撒奇萊雅族", "賽德克族", "拉阿魯哇族", "卡那卡那富族",
    # Generic terms TIPO's advisory surfaces
    "原住民", "部落",
)


def check_indigenous_terms(doc: TwPatentDocument) -> list[CheckItem]:
    """Flag indigenous peoples terminology for drafter review.

    Per TIPO 偵錯系統 Table 1 #19 + 原住民族傳統智慧創作保護條例 — TIPO's
    system surfaces indigenous-peoples references so applicants can verify
    their filing doesn't conflict with protected traditional creations.
    Advisory (VERIFY) rather than a hard rule violation.
    """
    text = _all_spec_text(doc)
    hits = sorted({term for term in _TW_INDIGENOUS_TERMS if term in text})

    if hits:
        return [CheckItem(
            status="verify",
            message=f"Indigenous terminology found: {', '.join(hits)}.",
            message_key="check.tw.spec.indigenousTerms.verify",
            details=", ".join(hits),
            details_key="details.tw.indigenousTerms",
            details_params={
                "count": len(hits),
                "terms": hits,
                "flagged_phrases": {
                    "items": [{"kind": "term", "token": t} for t in hits]
                },
            },
            reference="原住民族傳統智慧創作保護條例",
            diagnostics=_dx(
                flagged_count=len(hits),
                first_hit_charlen=len(hits[0]) if hits else None,
                hit_terms=hits[:10],
                total_terms_scanned=len(_TW_INDIGENOUS_TERMS),
            ),
        )]
    return [CheckItem(
        status="pass",
        message="No indigenous terminology references found.",
        message_key="check.tw.spec.indigenousTerms.pass",
        reference="原住民族傳統智慧創作保護條例",
    )]
