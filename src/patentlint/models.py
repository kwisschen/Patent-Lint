# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""PatentLint data models.

Pydantic models for structured patent analysis results.
These are designed to be shareable with the Agentic Patent Analyst project.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# Local copy of the structural-diagnostic helper (see
# analysis/utils.py for authoritative docs). Duplicated inline to avoid
# reaching into the analysis layer from the model layer and adding a new
# import dependency in the Pyodide bundle entrypoint.
def _dx(**kwargs: Any) -> dict[str, Any]:
    return {k: v for k, v in kwargs.items() if v is not None}


# Shape: '[N] → "word"\n              ' repeated. Parser surfaces the
# (location, phrase) pairs so CheckItem emit sites can hand them to the
# FlaggedTermList chip renderer. The location is int — paragraph or claim
# id depending on the emit site context.
_FORMATTED_PHRASE_RE = re.compile(r'\[(\d+)\]\s+→\s+"([^"]+)"')


def _parse_formatted_phrases(formatted: str, kind: str = "phrase") -> list[dict[str, Any]]:
    """Parse detect_restrictive_wording / detect_{restrictive_absolutes,indefinite_wording}_in_claims output
    into structured {location, token, kind} items. Deduplicates (location,
    token) pairs while preserving first-seen order. Used by the US spec +
    claims restrictiveWording emit sites in _to_us_report_data to populate
    details_params.flagged_phrases for the FlaggedTermList chip row."""
    if not formatted:
        return []
    seen: set[tuple[int, str]] = set()
    items: list[dict[str, Any]] = []
    for m in _FORMATTED_PHRASE_RE.finditer(formatted):
        loc = int(m.group(1))
        token = m.group(2)
        key = (loc, token.lower())
        if key in seen:
            continue
        seen.add(key)
        items.append({"location": loc, "token": token, "kind": kind})
    return items


class Jurisdiction(str, Enum):
    """Patent jurisdiction for analysis routing."""
    US = "US"
    CN = "CN"
    TW = "TW"
    EPC = "EPC"


class CnPatentType(str, Enum):
    """Chinese patent application type."""
    INVENTION = "INVENTION"           # 发明
    UTILITY_MODEL = "UTILITY_MODEL"   # 实用新型


class TwPatentType(str, Enum):
    """Taiwan patent application type."""
    INVENTION = "INVENTION"
    UTILITY_MODEL = "UTILITY_MODEL"


class Claim(BaseModel):
    """A single patent claim with metadata and dependency info.

    ``dependencies`` tracks statutory parent-claim references derived from
    the **preamble** form (``如請求項N所述的X...``). ``quoted_references``
    tracks 引用記載型式 body-embedded references (``一種Y，具備如請求項
    N所述的X``) — semantically incorporation-by-reference of claim N's
    sub-component definition, not a claim dependency. Keeping them in
    separate fields lets statutory checks (subject consistency, dependency
    format, multi-dep limits) key off ``dependencies`` while the antecedent
    walker's ancestor-chain can walk both so body-embedded references
    propagate intros for antecedent-basis resolution.
    """

    id: int
    text: str
    independent: bool
    multiple_dependent: bool = False
    method_claim: bool = False
    dependencies: list[int] = Field(default_factory=list)
    quoted_references: list[int] = Field(default_factory=list)


class FigureReference(BaseModel):
    """A figure reference (e.g., FIG. 2A) with numeric and optional alpha suffix."""

    number: int
    suffix: str = " "  # single char, space if no suffix

    @property
    def has_suffix(self) -> bool:
        return self.suffix.strip() != ""

    def __str__(self) -> str:
        return f"{self.number}{self.suffix if self.has_suffix else ''}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FigureReference):
            return NotImplemented
        return self.number == other.number and self.suffix == other.suffix

    def __hash__(self) -> int:
        return hash((self.number, self.suffix))


class ClaimWordingResult(BaseModel):
    """Result of claim wording analysis."""

    improper_claims: list[int] = Field(default_factory=list)
    formatted_phrases: str = ""


class SpecWordingResult(BaseModel):
    """Result of specification wording analysis."""

    flagged_paragraphs: list[int] = Field(default_factory=list)
    formatted_phrases: str = ""


class ReferenceNumeral(BaseModel):
    """A reference numeral extracted from patent text."""

    number: int  # e.g., 102
    element_name: str  # e.g., "base plate"
    occurrences: int = 0  # times it appears in spec text


class UnsupportedTerm(BaseModel):
    """A claim term not found in the specification."""

    claim_number: int
    phrase: str
    tiers_checked: list[str] = Field(default_factory=list)  # ["exact", "stemmed", "word_window"]
    # ADR-091: when the same (claim, phrase) is also flagged by the
    # antecedent-basis check, ``cross_ref`` is set to "antecedent" so the
    # frontend can render a hint line linking to the § 112(b) card.
    cross_ref: Optional[str] = None


class CnPatentDocument(BaseModel):
    """Parsed Chinese patent document (from CNIPA XML or .docx)."""
    patent_type: CnPatentType = CnPatentType.INVENTION
    title: str = ""
    technical_field: list[str] = Field(default_factory=list)
    background: list[str] = Field(default_factory=list)
    summary: list[str] = Field(default_factory=list)
    drawings_description: list[str] = Field(default_factory=list)
    detailed_description: list[str] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    abstract_text: str = ""
    abstract_char_count: int = 0
    paragraph_numbers: list[int] = Field(default_factory=list)
    figure_count: int = 0
    figure_refs: list[str] = Field(default_factory=list)
    has_paragraph_numbering: bool = False
    input_format: str = "docx"
    has_doc_page_fallback: bool = False
    # Per-section record of which section-ID fallback tier classified
    # each 五书 part of a .docx body (Phase 8c ADR-109, revised in
    # Stage 1.5 from a top-level str to a per-section dict). Keys are
    # ``"claims"``, ``"specification"``, and ``"abstract"``; values are
    # one of ``"body_anchor"``, ``"claim_density"``, ``"page_header"``,
    # or ``"none"``. A document can have mixed strategies (e.g., claims
    # via body_anchor, abstract via page_header fallback). For XML input
    # all three entries are ``"none"``. Empty default dict handles
    # pre-Phase-8c callers that still construct ``CnPatentDocument``
    # without populating this field (XML path).
    section_source_strategies: dict[str, str] = Field(default_factory=dict)
    # Canonical field-name keys (technical_field, background, summary,
    # drawings_description, detailed_description) in the order the parser
    # first encountered each section header in the document. First-occurrence
    # only. Empty list when no headers were found (XML path with no
    # <description>, or docx with no 五书 subsection headers). Consumed by
    # ``check_section_ordering`` to flag 专利法实施细则 §20 order violations
    # (Phase 9 #66; cite migrated from §17 in the 2023 revision effective
    # 2024-01-20).
    section_order: list[str] = Field(default_factory=list)


class SymbolEntry(BaseModel):
    """A symbol table entry (numeral + element name) for TW patents."""
    numeral: str
    name: str


class TwPatentDocument(BaseModel):
    """Parsed Taiwan patent document (from TIPO .docx)."""
    patent_type: TwPatentType = TwPatentType.INVENTION
    title: str = ""
    technical_field: list[str] = Field(default_factory=list)
    prior_art: list[str] = Field(default_factory=list)
    disclosure: list[str] = Field(default_factory=list)
    drawings_description: list[str] = Field(default_factory=list)
    embodiment: list[str] = Field(default_factory=list)
    symbol_table: list[SymbolEntry] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    abstract_text: str = ""
    abstract_char_count: int = 0
    representative_drawing: str | None = None
    representative_drawing_symbols: list[SymbolEntry] = Field(default_factory=list)
    figure_refs: list[str] = Field(default_factory=list)
    paragraph_numbers: list[str] = Field(default_factory=list)
    has_paragraph_numbering: bool = False
    # Parallel list aligned with the concatenation of
    # (technical_field + prior_art + disclosure + drawings_description + embodiment),
    # carrying the 【NNNN】-format auto-numbering Word renders for each
    # body paragraph (or None if the paragraph isn't Word-auto-numbered).
    # Populated by ``extract_tw_sections`` when the loader supplies Word
    # numbering; empty when the pipeline received a non-docx input that
    # can't surface numbering metadata. Downstream checks surface this
    # value instead of a PatentLint-internal ordinal so flagged paragraphs
    # match the drafter's 【NNNN】 labels in Word.
    body_paragraph_word_numbers: list[str | None] = Field(default_factory=list)
    # Canonical field-name keys (technical_field, prior_art, disclosure,
    # drawings_description, embodiment, symbol_table) in the order the parser
    # first encountered each 【】bracket header. First-occurrence only. Empty
    # when no body-section headers were found. Consumed by
    # ``check_section_ordering`` to flag 專利法施行細則 §17 order violations
    # (Phase 9 #66).
    section_order: list[str] = Field(default_factory=list)
    # Canonical TIPO section names that appeared without the required 【】
    # brackets — either bare (先前技術 alone on a line) or in variant brackets
    # ([先前技術], 〔先前技術〕, (先前技術), （先前技術）). Populated by
    # ``extract_tw_sections``; consumed by ``check_bracket_format`` to surface
    # 專利法施行細則 §17 violations.
    bracketless_section_headers: list[str] = Field(default_factory=list)
    # True when an abstract heading (【摘要】 / 【發明摘要】 / 【新型摘要】)
    # was parsed. False when the drafter omitted the heading but the
    # parser still populated ``abstract_text`` via the 【中文】 text marker
    # or another fallback. Consumed by ``check_required_sections`` to
    # distinguish "摘要 content present because heading was there" from
    # "摘要 content recovered via fallback — 專利法 §25 第1項 violation".
    abstract_header_seen: bool = False
    # True when a claims heading (【申請專利範圍】 / 【發明申請專利範圍】 /
    # 【新型申請專利範圍】) was parsed. See ``abstract_header_seen``.
    claims_header_seen: bool = False
    # Diagnostic-only fields surfaced via check_required_sections to make
    # claims-parser failures self-diagnosing without needing the user's
    # actual draft. Set in extract_tw_sections.
    #   claims_section_paragraph_count: paragraphs accumulated into the
    #     claims section (after pre-processing). 0 when the header was
    #     seen but bracket-header reset dropped everything (issue #17
    #     class).
    #   claims_first_paragraph_starts_with_bracket: True when the first
    #     non-empty paragraph in the claims section starts with 【.
    #     Distinguishes unhandled bracket-label firm variants from
    #     standard formats without exposing claim content.
    #   unknown_bracket_headers_in_claims: count of 【...】 patterns that
    #     hit the unknown-header fallback inside the claims section.
    #     Non-zero = parser rejected something the drafter expected to
    #     work; combined with claims_section_paragraph_count=0, points
    #     directly at a missing firm-variant label pattern.
    claims_section_paragraph_count: int = 0
    claims_first_paragraph_starts_with_bracket: bool = False
    unknown_bracket_headers_in_claims: int = 0
    input_format: str = "docx"


class CheckItem(BaseModel):
    """Single check result for report rendering."""

    status: str  # "pass", "verify", or "amend"
    message: str  # English fallback
    message_key: str = ""  # i18n key for frontend
    details: str | None = None
    details_key: str | None = None
    details_params: dict[str, Any] | None = None
    reference: str | None = None
    # Structural diagnostic fingerprint surfaced in error-report emails so
    # the maintainer can identify walker parse paths without seeing claim
    # content. Values must be str / int / bool — no claim text, no nouns,
    # no verbs. Disclosed in Privacy §7 (error reports). Example:
    #   {"extraction_path": "fallthrough", "preamble_matched": False,
    #    "dep_subject_charlen": 13, "parent_subject_charlen": 3}
    diagnostics: dict[str, Any] | None = None


class ClaimTreeRow(BaseModel):
    """Single row in a claim tree table."""

    claim_id: int
    claim_type: str  # "Independent" or "Dependent"
    chain: str  # e.g., "3 ← 2 ← 1"
    claim_text: str = ""


class ClaimTreeGroup(BaseModel):
    """A group of claims (product or method) for tree display."""

    label: str  # "Product Claims" or "Method Claims"
    rows: list[ClaimTreeRow]


class ReportData(BaseModel):
    """Structured report data for template rendering."""

    jurisdiction: Jurisdiction = Jurisdiction.US
    patent_type: str | None = None

    # Summary stats
    paragraph_count: int
    total_claims: int
    independent_count: int
    dependent_count: int
    figure_count: int
    abstract_word_count: int

    # Check items grouped by section
    specification_checks: list[CheckItem]
    claims_checks: list[CheckItem]
    abstract_checks: list[CheckItem]
    drawings_checks: list[CheckItem]

    # Claim trees for the table
    claim_trees: list[ClaimTreeGroup]

    # Antecedent basis issues
    antecedent_basis_issues: list[dict] = Field(default_factory=list)

    # Phase 4 additions
    unsupported_terms: list[UnsupportedTerm] = Field(default_factory=list)

    # Document-level flags
    likely_patent: bool = True
    # Reason code describing why ``likely_patent`` was set the way it was
    # (see :class:`patentlint.parser.detection.DetectionReason`). Carries
    # forward to the frontend banner so copy can honestly describe what
    # the detector actually checked — content-missing vs. cross-script
    # vs. weak-signal. Default ``None`` keeps back-compat for constructors
    # that predate ADR-150.
    patent_detection_reason: str | None = None
    has_tracked_changes: bool = False
    has_scanned_fallback: bool = False

    # Issue #9 / ADR-082 revisit — set to True when the document looks
    # like a different supported jurisdiction than the one the user
    # selected (e.g., user picked US but uploaded a TW draft). The
    # frontend renders a soft-warning banner with a one-click "Switch
    # to [X]" button. ``suggested_jurisdiction`` carries the suggested
    # code ("US" / "CN" / "TW"). Both fields default to "no mismatch"
    # so existing constructors that predate the feature work unchanged.
    jurisdiction_mismatch: bool = False
    suggested_jurisdiction: str | None = None

    # Rubric grade (forwarded from AnalysisResult). Allows the PDF
    # template + frontend report to read the grade from a single
    # canonical surface.
    rubric_grade: RubricGrade | None = None

    @property
    def all_checks(self) -> list[CheckItem]:
        """Return a flat list of every CheckItem across all sections in
        declaration order. Useful for diagnostic scripts, snapshot
        comparisons, and cross-section analyses that don't care about
        section boundaries.
        """
        return (
            list(self.specification_checks)
            + list(self.claims_checks)
            + list(self.abstract_checks)
            + list(self.drawings_checks)
        )


class RubricSection(str, Enum):
    """The 5 weighted rubric sections (jurisdiction-uniform).

    See ``patentlint.rubric`` for the scoring logic + section weights.
    """

    SPECIFICATION = "specification"
    DRAWINGS = "drawings"
    CLAIMS = "claims"
    ANTECEDENT_SPEC_SUPPORT = "antecedent_spec_support"
    ABSTRACT = "abstract"


class SectionGrade(BaseModel):
    """Per-section grading result."""

    section: RubricSection
    weight: int  # original section weight (pre-renormalization)
    effective_weight: float  # post-renormalization (when N/A sections drop out)
    score: int  # 0-100
    fix_count: int = 0
    review_count: int = 0
    pass_count: int = 0
    applicable: bool = True  # False = N/A (e.g., no drawings)


class CompletenessGap(BaseModel):
    """Reason a draft fails the completeness gate (no grade emitted)."""

    missing_sections: list[str] = Field(default_factory=list)


class ImpactItem(BaseModel):
    """An unaddressed finding ranked by score-impact-if-resolved."""

    message_key: str
    section: RubricSection
    status: str  # "amend" or "verify"
    delta: int  # points the overall score would rise


class RubricGrade(BaseModel):
    """Top-level scoring result for an analysis run.

    When ``completeness_gap`` is set, the draft is incomplete and
    ``score`` / ``letter`` are placeholders — the UI surfaces a
    "draft incomplete" state instead of the grade.
    """

    rubric_version: str = "1.0"
    score: int = 0  # 0-100 weighted overall (post-gate)
    letter: str = "F"  # A / A- / B+ / B / B- / C+ / C / D / F (or "—" when ungraded)
    cap_reason: str | None = None  # e.g., "1 FIX caps grade at B-"
    section_grades: list[SectionGrade] = Field(default_factory=list)
    impact_list: list[ImpactItem] = Field(default_factory=list)
    completeness_gap: CompletenessGap | None = None

    @property
    def is_complete(self) -> bool:
        return self.completeness_gap is None


class AnalysisResult(BaseModel):
    """Aggregates all analysis findings into a single structured result.

    Replaces the original 20+ parameter displayAnalysisResults method.
    Serializes directly to JSON via Pydantic.
    """

    # Specification
    jurisdiction: Jurisdiction = Jurisdiction.US
    patent_type: str | None = None
    title: str = ""
    has_tracked_changes: bool = False
    paragraph_count: int = 0
    improper_spec_paragraphs: list[int] = Field(default_factory=list)
    improper_spec_phrases_formatted: str = ""
    paragraphs_sequential: bool = True
    last_sequential_paragraph: int = 0
    missing_ending_paragraphs: list[int] = Field(default_factory=list)
    sequence_listing_mismatch: bool = False
    cross_reference_text: str = ""
    cross_reference_citations: str = ""
    prior_art_citations: str = ""

    # Drawings
    figures_count: int = 0
    figures_sequential: bool = True
    figures_missing: list[int] = Field(default_factory=list)
    contains_prior_art_in_drawings: bool = False
    single_figure: bool = False
    wrong_label_for_single_figure: bool = False

    # Claims
    claims: list[Claim] = Field(default_factory=list)
    restrictive_absolute_claims: list[int] = Field(default_factory=list)
    restrictive_absolute_phrases_formatted: str = ""
    indefinite_wording_claims: list[int] = Field(default_factory=list)
    indefinite_wording_phrases_formatted: str = ""
    independent_claims_count: int = 0
    dependent_claims_count: int = 0
    claims_sequential: bool = True
    last_sequential_claim: int = 0
    punctuation_checks: list[CheckItem] = Field(default_factory=list)
    multiple_dependent_claims: list[int] = Field(default_factory=list)
    chained_multi_dep_claims: list[int] = Field(default_factory=list)
    self_dependent_claims: list[int] = Field(default_factory=list)
    means_plus_function_claims: list[int] = Field(default_factory=list)
    antecedent_basis_issues: list[dict] = Field(default_factory=list)
    preamble_checks: list[CheckItem] = Field(default_factory=list)
    transition_checks: list[CheckItem] = Field(default_factory=list)
    special_format_checks: list[CheckItem] = Field(default_factory=list)
    unsupported_terms: list[UnsupportedTerm] = Field(default_factory=list)

    # Drawings — reference numerals
    reference_numerals: list[ReferenceNumeral] = Field(default_factory=list)

    # Issue #2 & #3 — required sections + figure cross-references
    required_sections_checks: list[CheckItem] = Field(default_factory=list)
    figure_xref_checks: list[CheckItem] = Field(default_factory=list)

    # Scope-limit wording (US, MPEP § 2111 + Phillips v. AWH). Single-element
    # list (one summary CheckItem); kept as a list for parity with other
    # check-bundle fields and future-proof against multi-emit changes.
    scope_limit_checks: list[CheckItem] = Field(default_factory=list)

    # Reference numeral consistency D1 (US, MPEP § 608.01(g)). Same shape
    # as scope_limit_checks. Detects same-numeral / different-name conflicts.
    numeral_consistency_checks: list[CheckItem] = Field(default_factory=list)

    # CN check results (populated by _run_cn_pipeline, empty for US)
    cn_specification_checks: list[CheckItem] = Field(default_factory=list)
    cn_claims_checks: list[CheckItem] = Field(default_factory=list)
    cn_abstract_checks: list[CheckItem] = Field(default_factory=list)
    cn_drawings_checks: list[CheckItem] = Field(default_factory=list)
    # CN per-claim lists for omnibus + Markush open-transition detection
    # (CheckItem summary already sits inside ``cn_claims_checks`` above;
    # these ID lists support report-data forwarding + cross-tooling).
    cn_omnibus_claims: list[int] = Field(default_factory=list)
    cn_markush_open_claims: list[int] = Field(default_factory=list)

    # TW check results (populated by _run_tw_pipeline, empty for US/CN)
    tw_specification_checks: list[CheckItem] = Field(default_factory=list)
    tw_claims_checks: list[CheckItem] = Field(default_factory=list)
    tw_abstract_checks: list[CheckItem] = Field(default_factory=list)
    tw_drawings_checks: list[CheckItem] = Field(default_factory=list)

    # EPC check results (populated by _run_epc_pipeline, empty for other
    # jurisdictions). v1 ships English specs only; the
    # jurisdiction-mismatch detector gates DE / FR EPC input upstream.
    epc_specification_checks: list[CheckItem] = Field(default_factory=list)
    epc_claims_checks: list[CheckItem] = Field(default_factory=list)
    epc_abstract_checks: list[CheckItem] = Field(default_factory=list)
    epc_drawings_checks: list[CheckItem] = Field(default_factory=list)

    # Document-level flags
    likely_patent: bool = True
    patent_detection_reason: str | None = None
    has_scanned_fallback: bool = False

    # Issue #9 / ADR-082 revisit — see ReportData.jurisdiction_mismatch.
    jurisdiction_mismatch: bool = False
    suggested_jurisdiction: str | None = None

    # Abstract
    abstract_word_count: int = 0
    # Raw abstract text — populated for US runs from the parser's
    # ``abstract_section``. CN/TW carry their abstract text on
    # ``CnPatentDocument`` / ``TwPatentDocument`` (the doc-level model)
    # rather than here, so ``abstract_text`` on ``AnalysisResult`` is
    # US-only by current convention. Diagnostic emit sites in
    # ``_to_us_report_data`` (e.g., the abstract.structure.amend chip)
    # read from this field; the previous version assumed it existed
    # and crashed when ``abstract_structure_good`` was False (b447ab6
    # / 1c35b54 ADR-145 sweep regression — see fix landed alongside
    # the ADR-082 revisit).
    abstract_text: str = ""
    abstract_structure_good: bool = True
    abstract_has_implied_phrase: bool = False
    abstract_implied_phrases: list[str] = Field(default_factory=list)
    abstract_legal_phraseology_formatted: str = ""
    abstract_legal_phraseology_items: list[str] = Field(default_factory=list)
    abstract_merit_language_formatted: str = ""
    abstract_merit_language_items: list[str] = Field(default_factory=list)

    # Rubric grade (populated by pipelines via patentlint.rubric.compute_rubric_grade
    # after all checks emit). None until the grading pass runs.
    rubric_grade: RubricGrade | None = None

    @property
    def total_claims(self) -> int:
        return self.independent_claims_count + self.dependent_claims_count

    def to_report_data(self) -> ReportData:
        """Transform flat analysis fields into structured report data.

        This is a presentation adapter — it does not change any existing
        fields or behavior.
        """
        if self.jurisdiction == Jurisdiction.CN:
            return self._to_cn_report_data()
        if self.jurisdiction == Jurisdiction.TW:
            return self._to_tw_report_data()
        if self.jurisdiction == Jurisdiction.EPC:
            return self._to_epc_report_data()
        return self._to_us_report_data()

    def _build_claim_trees(self) -> list[ClaimTreeGroup]:
        """Build claim tree groups from self.claims."""
        from patentlint.analysis.claims import get_dependency_chain

        product_rows: list[ClaimTreeRow] = []
        method_rows: list[ClaimTreeRow] = []

        for claim in self.claims:
            chain = get_dependency_chain(claim, self.claims)
            chain_display = chain.replace(" \u2192 ", " \u2190 ")
            claim_type = "Independent" if claim.independent else "Dependent"
            row = ClaimTreeRow(
                claim_id=claim.id,
                claim_type=claim_type,
                chain=chain_display,
                claim_text=claim.text,
            )
            if claim.method_claim:
                method_rows.append(row)
            else:
                product_rows.append(row)

        all_rows = product_rows + method_rows
        if not all_rows:
            return []

        if self.jurisdiction != Jurisdiction.US:
            return [ClaimTreeGroup(label="Claims", rows=all_rows)]

        claim_trees: list[ClaimTreeGroup] = []
        if product_rows:
            claim_trees.append(ClaimTreeGroup(label="Apparatus Claims", rows=product_rows))
        if method_rows:
            claim_trees.append(ClaimTreeGroup(label="Method Claims", rows=method_rows))
        return claim_trees

    def _to_cn_report_data(self) -> ReportData:
        """Build ReportData for CN jurisdiction from pre-computed check lists."""
        return ReportData(
            jurisdiction=self.jurisdiction,
            patent_type=self.patent_type,
            paragraph_count=self.paragraph_count,
            total_claims=self.total_claims,
            independent_count=self.independent_claims_count,
            dependent_count=self.dependent_claims_count,
            figure_count=self.figures_count,
            abstract_word_count=self.abstract_word_count,
            specification_checks=list(self.cn_specification_checks),
            claims_checks=list(self.cn_claims_checks),
            abstract_checks=list(self.cn_abstract_checks),
            drawings_checks=list(self.cn_drawings_checks),
            claim_trees=self._build_claim_trees(),
            antecedent_basis_issues=self.antecedent_basis_issues,
            unsupported_terms=self.unsupported_terms,
            likely_patent=self.likely_patent,
            patent_detection_reason=self.patent_detection_reason,
            has_tracked_changes=self.has_tracked_changes,
            has_scanned_fallback=self.has_scanned_fallback,
            jurisdiction_mismatch=self.jurisdiction_mismatch,
            suggested_jurisdiction=self.suggested_jurisdiction,
            rubric_grade=self.rubric_grade,
        )

    def _to_tw_report_data(self) -> ReportData:
        """Build ReportData for TW jurisdiction from pre-computed check lists.

        Phase 8b: ``antecedent_basis_issues`` carries the walker's
        per-occurrence findings (used by the Section112 frontend card);
        the summary CheckItem is already inside ``tw_claims_checks``,
        synthesized by the pipeline alongside the walker call.
        """
        return ReportData(
            jurisdiction=self.jurisdiction,
            patent_type=self.patent_type,
            paragraph_count=self.paragraph_count,
            total_claims=self.total_claims,
            independent_count=self.independent_claims_count,
            dependent_count=self.dependent_claims_count,
            figure_count=self.figures_count,
            abstract_word_count=self.abstract_word_count,
            specification_checks=list(self.tw_specification_checks),
            claims_checks=list(self.tw_claims_checks),
            abstract_checks=list(self.tw_abstract_checks),
            drawings_checks=list(self.tw_drawings_checks),
            claim_trees=self._build_claim_trees(),
            antecedent_basis_issues=self.antecedent_basis_issues,
            unsupported_terms=self.unsupported_terms,
            likely_patent=self.likely_patent,
            patent_detection_reason=self.patent_detection_reason,
            has_tracked_changes=self.has_tracked_changes,
            jurisdiction_mismatch=self.jurisdiction_mismatch,
            suggested_jurisdiction=self.suggested_jurisdiction,
            rubric_grade=self.rubric_grade,
        )

    def _to_epc_report_data(self) -> ReportData:
        """Build ReportData for EPC jurisdiction from pre-computed check lists.

        v1 ships English specs only; ``antecedent_basis_issues`` and
        ``unsupported_terms`` are populated by the walker port once Sessions
        8-9 of the implementation plan land. At scaffolding stage all check
        lists are empty.
        """
        return ReportData(
            jurisdiction=self.jurisdiction,
            patent_type=self.patent_type,
            paragraph_count=self.paragraph_count,
            total_claims=self.total_claims,
            independent_count=self.independent_claims_count,
            dependent_count=self.dependent_claims_count,
            figure_count=self.figures_count,
            abstract_word_count=self.abstract_word_count,
            specification_checks=list(self.epc_specification_checks),
            claims_checks=list(self.epc_claims_checks),
            abstract_checks=list(self.epc_abstract_checks),
            drawings_checks=list(self.epc_drawings_checks),
            claim_trees=self._build_claim_trees(),
            antecedent_basis_issues=self.antecedent_basis_issues,
            unsupported_terms=self.unsupported_terms,
            likely_patent=self.likely_patent,
            patent_detection_reason=self.patent_detection_reason,
            has_tracked_changes=self.has_tracked_changes,
            jurisdiction_mismatch=self.jurisdiction_mismatch,
            suggested_jurisdiction=self.suggested_jurisdiction,
            rubric_grade=self.rubric_grade,
        )

    def _to_us_report_data(self) -> ReportData:
        """Build ReportData for US jurisdiction from flat analysis fields.

        Emission order follows the Phase 10C document-order invariant (see
        CLAUDE.md "Check-ordering consistency invariant"):
          1. Spec structure: tracked_changes → required_sections
             → paragraph_numbering → paragraph_ending
          2. Spec content: sequence_listing → cross_reference → prior_art
             → spec restrictive_wording → drawing_overview
        """
        # --- Specification checks ---
        spec_checks: list[CheckItem] = []

        # --- Group 1: Spec structure ---
        if self.has_tracked_changes:
            spec_checks.append(CheckItem(
                status="amend",
                message="Document contains tracked changes (revisions). Accept or reject all changes before filing.",
                message_key="check.spec.trackedChanges.amend",
                diagnostics=_dx(
                    reason_code="tracked_changes_present",
                    total_paragraphs=self.paragraph_count,
                    total_claims=self.total_claims,
                ),
            ))

        # Required sections checks (Issue #2) — moved to front of spec-structure
        # group per the document-order invariant (was mid-list; TW/CN already
        # emit these first).
        for rc in self.required_sections_checks:
            spec_checks.append(rc)

        if self.paragraph_count == 0 and self.likely_patent:
            spec_checks.append(CheckItem(
                status="amend",
                message="No paragraph numbering found in specification.",
                message_key="check.spec.paragraphSequential.missing",
                details_key="details.paragraphNumberingMissing",
                diagnostics=_dx(
                    reason_code="no_paragraph_numbering",
                    paragraph_count=self.paragraph_count,
                    likely_patent=self.likely_patent,
                    total_claims=self.total_claims,
                ),
            ))
        elif not self.paragraphs_sequential:
            spec_checks.append(CheckItem(
                status="amend",
                message="Paragraph numbers are not sequential.",
                message_key="check.spec.paragraphSequential.amend",
                details=f"First gap at position {self.last_sequential_paragraph}",
                details_key="details.firstGapParagraph",
                details_params={"position": str(self.last_sequential_paragraph)},
                diagnostics=_dx(
                    first_gap_position=self.last_sequential_paragraph,
                    total_paragraphs=self.paragraph_count,
                ),
            ))
        else:
            spec_checks.append(CheckItem(
                status="pass",
                message="Paragraph numbers are sequential.",
                message_key="check.spec.paragraphSequential.pass",
            ))

        if self.missing_ending_paragraphs:
            spec_checks.append(CheckItem(
                status="verify",
                message="Paragraphs with invalid or missing ending punctuation.",
                message_key="check.spec.paragraphEnding.verify",
                details=f"Paragraphs: {self.missing_ending_paragraphs}",
                details_key="details.paragraphEnding",
                details_params={"list": str(self.missing_ending_paragraphs)},
                diagnostics=_dx(
                    flagged_count=len(self.missing_ending_paragraphs),
                    total_paragraphs=self.paragraph_count,
                    flagged_paragraphs_sample=self.missing_ending_paragraphs[:10],
                    first_flagged_paragraph=self.missing_ending_paragraphs[0] if self.missing_ending_paragraphs else None,
                ),
            ))
        else:
            spec_checks.append(CheckItem(
                status="pass",
                message="All paragraphs have valid ending punctuation.",
                message_key="check.spec.paragraphEnding.pass",
            ))

        # --- Group 2: Spec content ---
        # Reference numeral consistency D1 (US, MPEP § 608.01(g)) emits
        # first in SPEC_CONTENT — same canonical position (idx 15) as
        # CN/TW so users see refnum-checks early regardless of jurisdiction.
        for nc in self.numeral_consistency_checks:
            spec_checks.append(nc)

        from patentlint.analysis.specification import check_title as _check_us_title
        spec_checks.extend(_check_us_title(self.title))

        if self.sequence_listing_mismatch:
            spec_checks.append(CheckItem(
                status="amend",
                message="SEQ ID NO referenced but no sequence listing statement found.",
                message_key="check.spec.sequenceListing.amend",
                details_key="details.sequenceListingFix",
                diagnostics=_dx(
                    reason_code="missing_sequence_statement",
                    paragraph_count=self.paragraph_count,
                ),
            ))
        else:
            spec_checks.append(CheckItem(
                status="pass",
                message="No sequence listing mismatch.",
                message_key="check.spec.sequenceListing.pass",
            ))

        if self.cross_reference_citations:
            spec_checks.append(CheckItem(
                status="verify",
                message="Cross-reference section cites related applications.",
                message_key="check.spec.crossReference.verify",
                details=self.cross_reference_citations,
                details_key="details.crossReferenceCitations",
                details_params={"text": self.cross_reference_citations},
                diagnostics=_dx(
                    citation_charlen=len(self.cross_reference_citations),
                    citation_excerpt=self.cross_reference_citations[:60],
                ),
            ))
        else:
            spec_checks.append(CheckItem(
                status="pass",
                message="No cross-reference citations found.",
                message_key="check.spec.crossReference.pass",
            ))

        if self.prior_art_citations:
            spec_checks.append(CheckItem(
                status="verify",
                message="Background section cites prior art.",
                message_key="check.spec.priorArt.verify",
                details=self.prior_art_citations,
                details_key="details.priorArtCitations",
                details_params={"text": self.prior_art_citations},
                diagnostics=_dx(
                    citation_charlen=len(self.prior_art_citations),
                    citation_excerpt=self.prior_art_citations[:60],
                ),
            ))
        else:
            spec_checks.append(CheckItem(
                status="pass",
                message="No prior art citations found in background.",
                message_key="check.spec.priorArt.pass",
            ))

        # Spec restrictive wording belongs to spec-content (not spec-structure)
        # per the document-order invariant — was #2 in the legacy order.
        if self.improper_spec_paragraphs:
            spec_items = _parse_formatted_phrases(
                self.improper_spec_phrases_formatted, kind="phrase"
            )
            spec_checks.append(CheckItem(
                status="verify",
                message="Restrictive wording found in specification paragraphs.",
                message_key="check.spec.restrictiveWording.verify",
                details=f"Paragraphs: {self.improper_spec_paragraphs}",
                details_key="details.restrictiveWordingSpec",
                details_params={
                    "list": str(self.improper_spec_paragraphs),
                    "flagged_phrases": {"items": spec_items},
                } if spec_items else {"list": str(self.improper_spec_paragraphs)},
                diagnostics=_dx(
                    flagged_paragraph_count=len(self.improper_spec_paragraphs),
                    flagged_phrase_count=len(spec_items) or None,
                    flagged_paragraphs_sample=self.improper_spec_paragraphs[:5] or None,
                    flagged_phrases_sample=[
                        {"location": it.get("location"), "token": (it.get("token") or "")[:80], "kind": it.get("kind")}
                        for it in spec_items[:5]
                    ] or None,
                ),
            ))
        else:
            spec_checks.append(CheckItem(
                status="pass",
                message="No restrictive wording found in specification.",
                message_key="check.spec.restrictiveWording.pass",
            ))

        # Scope-limit wording (US, MPEP § 2111 + Phillips v. AWH).
        # Sits next to restrictive-wording in the spec-content group —
        # both are drafting hygiene checks operating on spec body text.
        # Distinct from restrictiveWording: that targets MPEP § 2173.01
        # absolutes; this targets Phillips claim-construction risk.
        for sc in self.scope_limit_checks:
            spec_checks.append(sc)

        # Drawings overview in specification section
        has_drawing_issue = (
            (self.single_figure and self.wrong_label_for_single_figure)
            or self.contains_prior_art_in_drawings
            or not self.figures_sequential
        )
        spec_checks.append(CheckItem(
            status="verify" if has_drawing_issue else "pass",
            message="Drawings overview.",
            message_key="check.spec.drawings",
            details=f"{self.figures_count} figure(s) found.",
            details_key="details.figureCount",
            details_params={"count": str(self.figures_count)},
            diagnostics=_dx(
                figure_count=self.figures_count,
                has_drawing_issue=has_drawing_issue,
                single_figure=self.single_figure,
                wrong_label_for_single_figure=self.wrong_label_for_single_figure,
                contains_prior_art_in_drawings=self.contains_prior_art_in_drawings,
                figures_sequential=self.figures_sequential,
            ) if has_drawing_issue else None,
        ))

        # --- Claims checks ---
        # Emission order follows the canonical claims sequence (ADR-149):
        #   G4 claims-structure: sequential → multipleDependent → selfDependent
        #     → transition_phrase
        #   G5 claims cross-jurisdiction: restrictive_wording
        #   G6 claims §112 analysis: meansFunction → antecedentBasis
        #     → spec_support → preamble_checks → special_formats → punctuation
        #   end: overview (summary)
        claims_checks: list[CheckItem] = []

        # --- G4: Claims structure ---
        if not self.claims_sequential:
            claims_checks.append(CheckItem(
                status="amend",
                message="Claim numbers are not sequential.",
                message_key="check.claims.sequential.amend",
                details=f"First gap at position {self.last_sequential_claim}",
                details_key="details.firstGapClaim",
                details_params={"position": str(self.last_sequential_claim)},
                diagnostics=_dx(
                    first_gap_position=self.last_sequential_claim,
                    total_claims=self.total_claims,
                    has_independent=any(c.independent for c in self.claims),
                    independent_count=sum(1 for c in self.claims if c.independent),
                ),
            ))
        else:
            claims_checks.append(CheckItem(
                status="pass",
                message="Claim numbers are sequential.",
                message_key="check.claims.sequential.pass",
            ))

        if self.multiple_dependent_claims:
            claims_checks.append(CheckItem(
                status="verify",
                message="Multiple-dependent claims found — review fees and chained-multi rule (MPEP § 608.01(n); § 112(e)).",
                message_key="check.claims.multipleDependent.verify",
                details=f"Claims: {self.multiple_dependent_claims}",
                details_key="details.multipleDependentClaims",
                details_params={"list": str(self.multiple_dependent_claims)},
                diagnostics=_dx(
                    flagged_count=len(self.multiple_dependent_claims),
                    total_claims=len(self.claims),
                    flagged_claim_id=self.multiple_dependent_claims[0] if self.multiple_dependent_claims else None,
                    findings=[
                        {"claim_id": cid, "preamble": (next((c.text for c in self.claims if c.id == cid), "") or "")[:80]}
                        for cid in self.multiple_dependent_claims[:5]
                    ],
                ),
            ))
        else:
            claims_checks.append(CheckItem(
                status="pass",
                message="No multiple-dependent claims.",
                message_key="check.claims.multipleDependent.pass",
            ))

        # § 112(e) chained-multi prohibition — a multi-dep claim cannot depend
        # on another multi-dep claim. Unlike the informational multipleDependent
        # check, this is a real rule violation (FIX).
        if self.chained_multi_dep_claims:
            claims_checks.append(CheckItem(
                status="amend",
                message="Multi-dependent claim depends on another multi-dependent claim (§ 112(e) / MPEP § 608.01(n)).",
                message_key="check.claims.chainedMultiDep.amend",
                details=f"Claims: {self.chained_multi_dep_claims}",
                details_key="details.chainedMultiDepClaims",
                details_params={"list": str(self.chained_multi_dep_claims)},
                diagnostics=_dx(
                    flagged_count=len(self.chained_multi_dep_claims),
                    total_claims=len(self.claims),
                    flagged_claim_id=self.chained_multi_dep_claims[0] if self.chained_multi_dep_claims else None,
                    findings=[
                        {"claim_id": cid, "preamble": (next((c.text for c in self.claims if c.id == cid), "") or "")[:80]}
                        for cid in self.chained_multi_dep_claims[:5]
                    ],
                ),
            ))
        else:
            claims_checks.append(CheckItem(
                status="pass",
                message="No chained multiple-dependent claims.",
                message_key="check.claims.chainedMultiDep.pass",
            ))

        if self.self_dependent_claims:
            claims_checks.append(CheckItem(
                status="amend",
                message="Self-dependent claims found.",
                message_key="check.claims.selfDependent.amend",
                details=f"Claims: {self.self_dependent_claims}",
                details_key="details.selfDependentClaims",
                details_params={"list": str(self.self_dependent_claims)},
                diagnostics=_dx(
                    flagged_count=len(self.self_dependent_claims),
                    total_claims=len(self.claims),
                    flagged_claim_id=self.self_dependent_claims[0] if self.self_dependent_claims else None,
                    findings=[
                        {"claim_id": cid, "preamble": (next((c.text for c in self.claims if c.id == cid), "") or "")[:80]}
                        for cid in self.self_dependent_claims[:5]
                    ],
                ),
            ))
        else:
            claims_checks.append(CheckItem(
                status="pass",
                message="No self-dependent claims.",
                message_key="check.claims.selfDependent.pass",
            ))

        for tc in self.transition_checks:
            claims_checks.append(tc)

        # --- G5: Claims cross-jurisdiction ---
        # Split into two category-specific checks (MPEP § 2173.01 restrictive
        # absolutes vs MPEP § 2173.05(b) indefinite/relative wording) so users
        # see category-appropriate titles and chips — avoids the confusion of
        # "can" appearing under a card titled "restrictive absolutes".
        if self.restrictive_absolute_claims:
            restrictive_items = _parse_formatted_phrases(
                self.restrictive_absolute_phrases_formatted, kind="phrase"
            )
            claims_checks.append(CheckItem(
                status="verify",
                message="Restrictive absolutes found in claims.",
                message_key="check.claims.restrictiveAbsolutes.verify",
                details=f"Claims: {self.restrictive_absolute_claims}",
                details_key="details.restrictiveAbsolutesClaims",
                details_params={
                    "list": str(self.restrictive_absolute_claims),
                    "flagged_phrases": {"items": restrictive_items},
                } if restrictive_items else {"list": str(self.restrictive_absolute_claims)},
                diagnostics=_dx(
                    flagged_claim_count=len(self.restrictive_absolute_claims),
                    flagged_phrase_count=len(restrictive_items) or None,
                    flagged_claims_sample=self.restrictive_absolute_claims[:5] or None,
                    flagged_phrases_sample=[
                        {"location": it.get("location"), "token": (it.get("token") or "")[:80], "kind": it.get("kind")}
                        for it in restrictive_items[:5]
                    ] or None,
                ),
            ))
        else:
            claims_checks.append(CheckItem(
                status="pass",
                message="No restrictive absolutes found in claims.",
                message_key="check.claims.restrictiveAbsolutes.pass",
            ))

        if self.indefinite_wording_claims:
            indefinite_items = _parse_formatted_phrases(
                self.indefinite_wording_phrases_formatted, kind="phrase"
            )
            claims_checks.append(CheckItem(
                status="verify",
                message="Indefinite or relative wording found in claims.",
                message_key="check.claims.indefiniteWording.verify",
                details=f"Claims: {self.indefinite_wording_claims}",
                details_key="details.indefiniteWordingClaims",
                details_params={
                    "list": str(self.indefinite_wording_claims),
                    "flagged_phrases": {"items": indefinite_items},
                } if indefinite_items else {"list": str(self.indefinite_wording_claims)},
                diagnostics=_dx(
                    flagged_claim_count=len(self.indefinite_wording_claims),
                    flagged_phrase_count=len(indefinite_items) or None,
                    flagged_claims_sample=self.indefinite_wording_claims[:5] or None,
                    flagged_phrases_sample=[
                        {"location": it.get("location"), "token": (it.get("token") or "")[:80], "kind": it.get("kind")}
                        for it in indefinite_items[:5]
                    ] or None,
                ),
            ))
        else:
            claims_checks.append(CheckItem(
                status="pass",
                message="No indefinite or relative wording found in claims.",
                message_key="check.claims.indefiniteWording.pass",
            ))

        # --- G6: Claims § 112 analysis ---
        if self.means_plus_function_claims:
            claims_checks.append(CheckItem(
                status="verify",
                message="Claims may invoke 35 U.S.C. § 112(f) means-plus-function.",
                message_key="check.claims.meansFunction.verify",
                details=f"Claims: {self.means_plus_function_claims}",
                details_key="details.meansFunctionClaims",
                details_params={"list": str(self.means_plus_function_claims)},
                diagnostics=_dx(
                    flagged_count=len(self.means_plus_function_claims),
                    total_claims=len(self.claims),
                    flagged_claim_id=self.means_plus_function_claims[0] if self.means_plus_function_claims else None,
                    findings=[
                        {"claim_id": cid, "preamble": (next((c.text for c in self.claims if c.id == cid), "") or "")[:80]}
                        for cid in self.means_plus_function_claims[:5]
                    ],
                ),
            ))
        else:
            claims_checks.append(CheckItem(
                status="pass",
                message="No means-plus-function language detected.",
                message_key="check.claims.meansFunction.pass",
            ))

        if self.antecedent_basis_issues:
            from patentlint.diagnostic_extractors import extract_antecedent_basis
            issue_count = len(self.antecedent_basis_issues)
            ab_claim_ids = sorted({item["claim_id"] for item in self.antecedent_basis_issues})
            claim_count = len(ab_claim_ids)
            claims_checks.append(CheckItem(
                status="amend",
                message="Possible missing antecedent basis found.",
                message_key="check.claims.antecedentBasis.amend",
                details=f"{issue_count} issues across {claim_count} claims",
                details_key="details.antecedentBasisTerms",
                details_params={"count": str(issue_count), "claims": str(claim_count)},
                diagnostics=extract_antecedent_basis(self.antecedent_basis_issues, len(self.claims)),
            ))
        else:
            claims_checks.append(CheckItem(
                status="pass",
                message="No antecedent basis issues detected.",
                message_key="check.claims.antecedentBasis.pass",
            ))

        if self.unsupported_terms:
            from patentlint.diagnostic_extractors import extract_spec_support
            unique_phrases = sorted(set(ut.phrase for ut in self.unsupported_terms))
            claims_checks.append(CheckItem(
                status="amend",
                message="Claim terms not found in specification.",
                message_key="checks.spec_support_unsupported_terms",
                details=f"Terms: {', '.join(unique_phrases[:10])}",
                details_key="details.specSupportUnsupported",
                details_params={"count": str(len(unique_phrases))},
                diagnostics=extract_spec_support(
                    self.unsupported_terms,
                    total_claims=len(self.claims),
                ),
            ))
        else:
            claims_checks.append(CheckItem(
                status="pass",
                message="All claim terms found in specification.",
                message_key="checks.spec_support_pass",
            ))

        for pc in self.preamble_checks:
            claims_checks.append(pc)

        for sc in self.special_format_checks:
            claims_checks.append(sc)

        for pc in self.punctuation_checks:
            claims_checks.append(pc)

        # --- End summary ---
        claims_checks.append(CheckItem(
            status="pass",
            message="Claims overview.",
            message_key="check.claims.overview",
            details=(
                f"{self.independent_claims_count} independent, "
                f"{self.dependent_claims_count} dependent, "
                f"{self.total_claims} total"
            ),
            details_key="details.claimsOverview",
            details_params={
                "independent": str(self.independent_claims_count),
                "dependent": str(self.dependent_claims_count),
                "total": str(self.total_claims),
            },
        ))

        # --- Abstract checks ---
        # Emission order follows canonical G7 sequence (ADR-149):
        #   word_count → restrictive_wording → implied_phrases → structure
        abstract_checks: list[CheckItem] = []

        wc = self.abstract_word_count
        if wc < 50 or wc > 150:
            abstract_checks.append(CheckItem(
                status="amend",
                message=f"Abstract word count ({wc}) is outside the 50–150 range.",
                message_key="check.abstract.wordCount.amend",
                details_key="details.abstractWordCountFix",
                diagnostics=_dx(
                    word_count=wc,
                    lower_threshold=50,
                    upper_threshold=150,
                    reason_code="below" if wc < 50 else "above",
                ),
            ))
        else:
            abstract_checks.append(CheckItem(
                status="pass",
                message=f"Abstract word count ({wc}) is within the 50–150 range.",
                message_key="check.abstract.wordCount.pass",
            ))

        # Split into two § 608.01(b) subcategories (legal phraseology vs
        # purported-merit language) so each chip appears under a card whose
        # title accurately describes what it flags.
        def _dedupe(tokens: list[str]) -> list[str]:
            seen: set[str] = set()
            out: list[str] = []
            for t in tokens:
                k = t.lower()
                if k in seen:
                    continue
                seen.add(k)
                out.append(t)
            return out

        if self.abstract_legal_phraseology_formatted:
            unique_legal = _dedupe(self.abstract_legal_phraseology_items)
            abstract_checks.append(CheckItem(
                status="verify",
                message="Legal phraseology found in abstract.",
                message_key="check.abstract.legalPhraseology.verify",
                details=self.abstract_legal_phraseology_formatted.strip(),
                details_key="details.legalPhraseologyAbstract",
                details_params={
                    "text": self.abstract_legal_phraseology_formatted.strip(),
                    "flagged_phrases": {
                        "items": [{"kind": "phrase", "token": p} for p in unique_legal]
                    },
                } if unique_legal else {"text": self.abstract_legal_phraseology_formatted.strip()},
                diagnostics=_dx(
                    flagged_phrases_charlen=len(self.abstract_legal_phraseology_formatted),
                    flagged_phrase_count=len(unique_legal) or None,
                    flagged_phrases_sample=[(p or "")[:80] for p in unique_legal[:5]] or None,
                ),
            ))
        else:
            abstract_checks.append(CheckItem(
                status="pass",
                message="No legal phraseology found in abstract.",
                message_key="check.abstract.legalPhraseology.pass",
            ))

        if self.abstract_merit_language_formatted:
            unique_merit = _dedupe(self.abstract_merit_language_items)
            abstract_checks.append(CheckItem(
                status="verify",
                message="Merit or self-referential language found in abstract.",
                message_key="check.abstract.meritLanguage.verify",
                details=self.abstract_merit_language_formatted.strip(),
                details_key="details.meritLanguageAbstract",
                details_params={
                    "text": self.abstract_merit_language_formatted.strip(),
                    "flagged_phrases": {
                        "items": [{"kind": "phrase", "token": p} for p in unique_merit]
                    },
                } if unique_merit else {"text": self.abstract_merit_language_formatted.strip()},
                diagnostics=_dx(
                    flagged_phrases_charlen=len(self.abstract_merit_language_formatted),
                    flagged_phrase_count=len(unique_merit) or None,
                    flagged_phrases_sample=[(p or "")[:80] for p in unique_merit[:5]] or None,
                ),
            ))
        else:
            abstract_checks.append(CheckItem(
                status="pass",
                message="No merit or self-referential language found in abstract.",
                message_key="check.abstract.meritLanguage.pass",
            ))

        if self.abstract_has_implied_phrase:
            phrases = list(self.abstract_implied_phrases)
            abstract_checks.append(CheckItem(
                status="amend",
                message="Abstract contains implied phrases ('disclosure' or 'provided').",
                message_key="check.abstract.impliedPhrases.amend",
                details_key="details.abstractImpliedPhrasesFix",
                details_params={
                    "phrases": ", ".join(f'"{p}"' for p in phrases),
                    "flagged_phrases": {
                        "items": [{"kind": "phrase", "token": p} for p in phrases]
                    },
                } if phrases else None,
                diagnostics=_dx(
                    reason_code="implied_phrase_detected",
                    flagged_phrase_count=len(phrases) or None,
                    flagged_phrases_sample=[(p or "")[:80] for p in phrases[:5]] or None,
                ),
            ))
        else:
            abstract_checks.append(CheckItem(
                status="pass",
                message="No implied phrases found in abstract.",
                message_key="check.abstract.impliedPhrases.pass",
            ))

        if not self.abstract_structure_good:
            abstract_checks.append(CheckItem(
                status="amend",
                message="Abstract has extra paragraphs or invalid ending.",
                message_key="check.abstract.structure.amend",
                details_key="details.abstractStructureFix",
                diagnostics=_dx(
                    reason_code="bad_structure",
                    abstract_word_count=self.abstract_word_count,
                    abstract_charlen=len(self.abstract_text or ""),
                    last_char_codepoint=ord((self.abstract_text or "X")[-1]) if (self.abstract_text or "").strip() else None,
                ),
            ))
        else:
            abstract_checks.append(CheckItem(
                status="pass",
                message="Abstract is a single paragraph with valid ending.",
                message_key="check.abstract.structure.pass",
            ))

        # --- Drawings checks ---
        # Emission order follows the canonical Group 3 sequence (ADR-149):
        #   figure_count → single_figure → prior_art → figures_sequential
        #   → figure_xref
        # Matches CN + TW pipeline ordering (Phase 10C 8cf18af).
        drawings_checks: list[CheckItem] = []

        drawings_checks.append(CheckItem(
            status="pass",
            message=f"{self.figures_count} figure(s) found.",
            message_key="check.drawings.count",
            details_params={"count": str(self.figures_count)},
        ))

        if self.single_figure and self.wrong_label_for_single_figure:
            drawings_checks.append(CheckItem(
                status="amend",
                message="Single-figure patent uses 'FIG. 1' instead of 'The Figure'.",
                message_key="check.drawings.singleFigure.amend",
                details_key="details.singleFigureFix",
                diagnostics=_dx(
                    reason_code="wrong_single_figure_label",
                    figure_count=self.figures_count,
                ),
            ))
        elif self.single_figure:
            drawings_checks.append(CheckItem(
                status="pass",
                message="Single-figure patent correctly labeled.",
                message_key="check.drawings.singleFigure.pass",
            ))

        if self.contains_prior_art_in_drawings:
            drawings_checks.append(CheckItem(
                status="verify",
                message="Prior art references found in drawings description.",
                message_key="check.drawings.priorArt.verify",
                details_key="details.drawingsPriorArt",
                diagnostics=_dx(
                    reason_code="prior_art_reference_in_drawings",
                    figure_count=self.figures_count,
                ),
            ))
        else:
            drawings_checks.append(CheckItem(
                status="pass",
                message="No prior art references in drawings description.",
                message_key="check.drawings.priorArt.pass",
            ))

        if not self.figures_sequential:
            drawings_checks.append(CheckItem(
                status="amend",
                message="Figures are not in sequential order.",
                message_key="check.drawings.sequential.amend",
                details_key="details.figuresSequentialFix",
                details_params={"figure_list": self.figures_missing},
                diagnostics=_dx(
                    missing_count=len(self.figures_missing) if self.figures_missing else 0,
                    total_figures=self.figures_count,
                    missing_figures=self.figures_missing[:10] if self.figures_missing else None,
                    first_missing=self.figures_missing[0] if self.figures_missing else None,
                ),
            ))
        else:
            drawings_checks.append(CheckItem(
                status="pass",
                message="Figures are in sequential order.",
                message_key="check.drawings.sequential.pass",
            ))

        # Figure cross-reference checks (Issue #3)
        for fc in self.figure_xref_checks:
            drawings_checks.append(fc)

        return ReportData(
            jurisdiction=self.jurisdiction,
            paragraph_count=self.paragraph_count,
            total_claims=self.total_claims,
            independent_count=self.independent_claims_count,
            dependent_count=self.dependent_claims_count,
            figure_count=self.figures_count,
            abstract_word_count=self.abstract_word_count,
            specification_checks=spec_checks,
            claims_checks=claims_checks,
            abstract_checks=abstract_checks,
            drawings_checks=drawings_checks,
            claim_trees=self._build_claim_trees(),
            antecedent_basis_issues=self.antecedent_basis_issues,
            unsupported_terms=self.unsupported_terms,
            likely_patent=self.likely_patent,
            patent_detection_reason=self.patent_detection_reason,
            has_tracked_changes=self.has_tracked_changes,
            jurisdiction_mismatch=self.jurisdiction_mismatch,
            suggested_jurisdiction=self.suggested_jurisdiction,
            rubric_grade=self.rubric_grade,
        )
