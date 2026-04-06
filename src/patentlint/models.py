# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""PatentLint data models.

Pydantic models for structured patent analysis results.
These are designed to be shareable with the Agentic Patent Analyst project.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Jurisdiction(str, Enum):
    """Patent jurisdiction for analysis routing."""
    US = "US"
    CN = "CN"
    TW = "TW"


class CnPatentType(str, Enum):
    """Chinese patent application type."""
    INVENTION = "INVENTION"           # 发明
    UTILITY_MODEL = "UTILITY_MODEL"   # 实用新型


class TwPatentType(str, Enum):
    """Taiwan patent application type."""
    INVENTION = "INVENTION"
    UTILITY_MODEL = "UTILITY_MODEL"


class Claim(BaseModel):
    """A single patent claim with metadata and dependency info."""

    id: int
    text: str
    independent: bool
    multiple_dependent: bool = False
    method_claim: bool = False
    dependencies: list[int] = Field(default_factory=list)


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
    input_format: str = "docx"


class CheckItem(BaseModel):
    """Single check result for report rendering."""

    status: str  # "pass", "verify", or "amend"
    message: str  # English fallback
    message_key: str = ""  # i18n key for frontend
    details: str | None = None
    details_key: str | None = None
    details_params: dict[str, str] | None = None
    reference: str | None = None


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
    has_tracked_changes: bool = False
    has_scanned_fallback: bool = False


class AnalysisResult(BaseModel):
    """Aggregates all analysis findings into a single structured result.

    Replaces the original 20+ parameter displayAnalysisResults method.
    Serializes directly to JSON via Pydantic.
    """

    # Specification
    jurisdiction: Jurisdiction = Jurisdiction.US
    patent_type: str | None = None
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
    contains_prior_art_in_drawings: bool = False
    single_figure: bool = False
    wrong_label_for_single_figure: bool = False

    # Claims
    claims: list[Claim] = Field(default_factory=list)
    improper_claims: list[int] = Field(default_factory=list)
    improper_claim_phrases_formatted: str = ""
    independent_claims_count: int = 0
    dependent_claims_count: int = 0
    claims_sequential: bool = True
    last_sequential_claim: int = 0
    punctuation_checks: list[CheckItem] = Field(default_factory=list)
    multiple_dependent_claims: list[int] = Field(default_factory=list)
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

    # CN check results (populated by _run_cn_pipeline, empty for US)
    cn_specification_checks: list[CheckItem] = Field(default_factory=list)
    cn_claims_checks: list[CheckItem] = Field(default_factory=list)
    cn_abstract_checks: list[CheckItem] = Field(default_factory=list)
    cn_drawings_checks: list[CheckItem] = Field(default_factory=list)

    # TW check results (populated by _run_tw_pipeline, empty for US/CN)
    tw_specification_checks: list[CheckItem] = Field(default_factory=list)
    tw_claims_checks: list[CheckItem] = Field(default_factory=list)
    tw_abstract_checks: list[CheckItem] = Field(default_factory=list)
    tw_drawings_checks: list[CheckItem] = Field(default_factory=list)

    # Document-level flags
    likely_patent: bool = True
    has_scanned_fallback: bool = False

    # Abstract
    abstract_word_count: int = 0
    abstract_structure_good: bool = True
    abstract_has_implied_phrase: bool = False
    improper_abstract_phrases_formatted: str = ""

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
            likely_patent=self.likely_patent,
            has_scanned_fallback=self.has_scanned_fallback,
        )

    def _to_tw_report_data(self) -> ReportData:
        """Build ReportData for TW jurisdiction from pre-computed check lists."""
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
            likely_patent=self.likely_patent,
        )

    def _to_us_report_data(self) -> ReportData:
        """Build ReportData for US jurisdiction from flat analysis fields."""
        # --- Specification checks ---
        spec_checks: list[CheckItem] = []

        if self.has_tracked_changes:
            spec_checks.append(CheckItem(
                status="amend",
                message="Document contains tracked changes (revisions). Accept or reject all changes before filing.",
                message_key="check.spec.trackedChanges.amend",
            ))

        if self.improper_spec_paragraphs:
            spec_checks.append(CheckItem(
                status="verify",
                message="Restrictive wording found in specification paragraphs.",
                message_key="check.spec.restrictiveWording.verify",
                details=f"Paragraphs: {self.improper_spec_paragraphs}",
                details_key="details.restrictiveWordingSpec",
                details_params={"list": str(self.improper_spec_paragraphs)},
            ))
        else:
            spec_checks.append(CheckItem(
                status="pass",
                message="No restrictive wording found in specification.",
                message_key="check.spec.restrictiveWording.pass",
            ))

        if self.paragraph_count == 0 and self.likely_patent:
            spec_checks.append(CheckItem(
                status="amend",
                message="No paragraph numbering found in specification.",
                message_key="check.spec.paragraphSequential.missing",
                details_key="details.paragraphNumberingMissing",
            ))
        elif not self.paragraphs_sequential:
            spec_checks.append(CheckItem(
                status="amend",
                message="Paragraph numbers are not sequential.",
                message_key="check.spec.paragraphSequential.amend",
                details=f"First gap at position {self.last_sequential_paragraph}",
                details_key="details.firstGapParagraph",
                details_params={"position": str(self.last_sequential_paragraph)},
            ))
        else:
            spec_checks.append(CheckItem(
                status="pass",
                message="Paragraph numbers are sequential.",
                message_key="check.spec.paragraphSequential.pass",
            ))

        if self.missing_ending_paragraphs:
            spec_checks.append(CheckItem(
                status="amend",
                message="Paragraphs with invalid or missing ending punctuation.",
                message_key="check.spec.paragraphEnding.amend",
                details=f"Paragraphs: {self.missing_ending_paragraphs}",
                details_key="details.paragraphEnding",
                details_params={"list": str(self.missing_ending_paragraphs)},
            ))
        else:
            spec_checks.append(CheckItem(
                status="pass",
                message="All paragraphs have valid ending punctuation.",
                message_key="check.spec.paragraphEnding.pass",
            ))

        if self.sequence_listing_mismatch:
            spec_checks.append(CheckItem(
                status="amend",
                message="SEQ ID NO referenced but no sequence listing statement found.",
                message_key="check.spec.sequenceListing.amend",
                details_key="details.sequenceListingFix",
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
            ))
        else:
            spec_checks.append(CheckItem(
                status="pass",
                message="No prior art citations found in background.",
                message_key="check.spec.priorArt.pass",
            ))

        # Required sections checks (Issue #2)
        for rc in self.required_sections_checks:
            spec_checks.append(rc)

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
        ))

        # --- Claims checks ---
        claims_checks: list[CheckItem] = []

        if self.improper_claims:
            claims_checks.append(CheckItem(
                status="verify",
                message="Restrictive or indefinite wording found in claims.",
                message_key="check.claims.restrictiveWording.verify",
                details=f"Claims: {self.improper_claims}",
                details_key="details.restrictiveWordingClaims",
                details_params={"list": str(self.improper_claims)},
            ))
        else:
            claims_checks.append(CheckItem(
                status="pass",
                message="No restrictive or indefinite wording found in claims.",
                message_key="check.claims.restrictiveWording.pass",
            ))

        if not self.claims_sequential:
            claims_checks.append(CheckItem(
                status="amend",
                message="Claim numbers are not sequential.",
                message_key="check.claims.sequential.amend",
                details=f"First gap at position {self.last_sequential_claim}",
                details_key="details.firstGapClaim",
                details_params={"position": str(self.last_sequential_claim)},
            ))
        else:
            claims_checks.append(CheckItem(
                status="pass",
                message="Claim numbers are sequential.",
                message_key="check.claims.sequential.pass",
            ))

        if self.multiple_dependent_claims:
            claims_checks.append(CheckItem(
                status="amend",
                message="Multiple-dependent claims found.",
                message_key="check.claims.multipleDependent.amend",
                details=f"Claims: {self.multiple_dependent_claims}",
                details_key="details.multipleDependentClaims",
                details_params={"list": str(self.multiple_dependent_claims)},
            ))
        else:
            claims_checks.append(CheckItem(
                status="pass",
                message="No multiple-dependent claims.",
                message_key="check.claims.multipleDependent.pass",
            ))

        if self.self_dependent_claims:
            claims_checks.append(CheckItem(
                status="amend",
                message="Self-dependent claims found.",
                message_key="check.claims.selfDependent.amend",
                details=f"Claims: {self.self_dependent_claims}",
                details_key="details.selfDependentClaims",
                details_params={"list": str(self.self_dependent_claims)},
            ))
        else:
            claims_checks.append(CheckItem(
                status="pass",
                message="No self-dependent claims.",
                message_key="check.claims.selfDependent.pass",
            ))

        # Claim punctuation checks
        for pc in self.punctuation_checks:
            claims_checks.append(pc)

        if self.means_plus_function_claims:
            claims_checks.append(CheckItem(
                status="verify",
                message="Claims may invoke 35 U.S.C. § 112(f) means-plus-function.",
                message_key="check.claims.meansFunction.verify",
                details=f"Claims: {self.means_plus_function_claims}",
                details_key="details.meansFunctionClaims",
                details_params={"list": str(self.means_plus_function_claims)},
            ))
        else:
            claims_checks.append(CheckItem(
                status="pass",
                message="No means-plus-function language detected.",
                message_key="check.claims.meansFunction.pass",
            ))

        if self.antecedent_basis_issues:
            unique_terms = sorted(set(item["term"] for item in self.antecedent_basis_issues))
            claims_checks.append(CheckItem(
                status="verify",
                message="Possible missing antecedent basis found.",
                message_key="check.claims.antecedentBasis.verify",
                details=f"Terms: {', '.join(unique_terms)}",
                details_key="details.antecedentBasisTerms",
                details_params={"list": ", ".join(unique_terms)},
            ))
        else:
            claims_checks.append(CheckItem(
                status="pass",
                message="No antecedent basis issues detected.",
                message_key="check.claims.antecedentBasis.pass",
            ))

        # Preamble consistency checks
        for pc in self.preamble_checks:
            claims_checks.append(pc)

        # Transition phrase checks
        for tc in self.transition_checks:
            claims_checks.append(tc)

        # Special claim format checks
        for sc in self.special_format_checks:
            claims_checks.append(sc)

        # Spec support checks
        if self.unsupported_terms:
            unique_phrases = sorted(set(ut.phrase for ut in self.unsupported_terms))
            claims_checks.append(CheckItem(
                status="verify",
                message="Claim terms not found in specification.",
                message_key="checks.spec_support_unsupported_terms",
                details=f"Terms: {', '.join(unique_phrases[:10])}",
                details_key="details.specSupportUnsupported",
                details_params={"count": str(len(unique_phrases))},
            ))
        else:
            claims_checks.append(CheckItem(
                status="pass",
                message="All claim terms found in specification.",
                message_key="checks.spec_support_pass",
            ))

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
        abstract_checks: list[CheckItem] = []

        if self.improper_abstract_phrases_formatted:
            abstract_checks.append(CheckItem(
                status="verify",
                message="Restrictive or improper wording found in abstract.",
                message_key="check.abstract.restrictiveWording.verify",
                details=self.improper_abstract_phrases_formatted.strip(),
                details_key="details.restrictiveWordingAbstract",
                details_params={"text": self.improper_abstract_phrases_formatted.strip()},
            ))
        else:
            abstract_checks.append(CheckItem(
                status="pass",
                message="No restrictive or improper wording found in abstract.",
                message_key="check.abstract.restrictiveWording.pass",
            ))

        if not self.abstract_structure_good:
            abstract_checks.append(CheckItem(
                status="amend",
                message="Abstract has extra paragraphs or invalid ending.",
                message_key="check.abstract.structure.amend",
                details_key="details.abstractStructureFix",
            ))
        else:
            abstract_checks.append(CheckItem(
                status="pass",
                message="Abstract is a single paragraph with valid ending.",
                message_key="check.abstract.structure.pass",
            ))

        if self.abstract_has_implied_phrase:
            abstract_checks.append(CheckItem(
                status="amend",
                message="Abstract contains implied phrases ('disclosure' or 'provided').",
                message_key="check.abstract.impliedPhrases.amend",
                details_key="details.abstractImpliedPhrasesFix",
            ))
        else:
            abstract_checks.append(CheckItem(
                status="pass",
                message="No implied phrases found in abstract.",
                message_key="check.abstract.impliedPhrases.pass",
            ))

        wc = self.abstract_word_count
        if wc < 50 or wc > 150:
            abstract_checks.append(CheckItem(
                status="amend",
                message=f"Abstract word count ({wc}) is outside the 50\u2013150 range.",
                message_key="check.abstract.wordCount.amend",
                details_key="details.abstractWordCountFix",
            ))
        else:
            abstract_checks.append(CheckItem(
                status="pass",
                message=f"Abstract word count ({wc}) is within the 50\u2013150 range.",
                message_key="check.abstract.wordCount.pass",
            ))

        # --- Drawings checks ---
        drawings_checks: list[CheckItem] = []

        if self.single_figure and self.wrong_label_for_single_figure:
            drawings_checks.append(CheckItem(
                status="amend",
                message="Single-figure patent uses 'FIG. 1' instead of 'The Figure'.",
                message_key="check.drawings.singleFigure.amend",
                details_key="details.singleFigureFix",
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
            ))
        else:
            drawings_checks.append(CheckItem(
                status="pass",
                message="Figures are in sequential order.",
                message_key="check.drawings.sequential.pass",
            ))

        drawings_checks.append(CheckItem(
            status="pass",
            message=f"{self.figures_count} figure(s) found.",
            message_key="check.drawings.count",
            details_params={"count": str(self.figures_count)},
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
            has_tracked_changes=self.has_tracked_changes,
        )
