# PatentLint — Check Inventory

Complete inventory of every check implemented in PatentLint, organized by report section.

## Specification

| Check | Reference | Severity | message_key | Description |
|-------|-----------|----------|-------------|-------------|
| Tracked changes | — | AMEND | `check.spec.trackedChanges.amend` | Document contains tracked changes (revisions) |
| Restrictive wording | § 112(b) | VERIFY / PASS | `check.spec.restrictiveWording` | Restrictive wording in specification paragraphs |
| Paragraph sequential | § 608.01(p) | AMEND / PASS | `check.spec.paragraphSequential` / `check.spec.paragraphSequential.missing` | Paragraph numbers are sequential; no paragraph numbering found (patent documents only) |
| Paragraph ending | § 608.01(p) | AMEND / PASS | `check.spec.paragraphEnding` | Paragraphs have valid ending punctuation |
| Sequence listing | § 2422 | AMEND / PASS | `check.spec.sequenceListing` | SEQ ID NO referenced but no sequence listing statement |
| Cross-reference | § 608.01 | VERIFY / PASS | `check.spec.crossReference` | Cross-reference section cites related applications — verify completeness |
| Prior art citations | § 608.01(c) | VERIFY / PASS | `check.spec.priorArt` | Background section cites prior art — review characterizations |
| Required sections | § 608.01(a) | AMEND / PASS | `checks.required_sections_missing` / `checks.required_sections_pass` | Required sections per MPEP § 608.01(a) are present |
| Optional sections | § 608.01(a) | VERIFY | `checks.optional_section_missing` | Optional section not found (informational) |
| Drawings overview † | § 608.02 | VERIFY / PASS | `check.spec.drawings` | Composite drawings summary (figures count, sequential, prior art, single-figure) |

## Claims

| Check | Reference | Severity | message_key | Description |
|-------|-----------|----------|-------------|-------------|
| Restrictive wording | § 112(b) | VERIFY / PASS | `check.claims.restrictiveWording` | Restrictive or indefinite wording in claims |
| Claims sequential | § 608.01(m) | AMEND / PASS | `check.claims.sequential` | Claim numbers are sequential |
| Multiple dependents | § 608.01(n) | AMEND / PASS | `check.claims.multipleDependent` | Multiple-dependent claims found |
| Self-dependent | § 112(d) | AMEND / PASS | `check.claims.selfDependent` | Self-dependent claims found |
| Missing period | § 608.01(m) | AMEND | `claims.missingPeriod` | Per-claim: claim does not end with a period |
| Extra periods | § 608.01(m) | AMEND | `claims.extraPeriod` | Per-claim: claim has extra or misplaced periods |
| Wherein comma | § 608.01(m) | VERIFY | `claims.whereinComma` | Per-claim: incorrect comma around 'wherein' clause |
| Punctuation pass | § 608.01(m) | PASS | `claims.punctuationPass` | All claims have correct punctuation |
| Means-plus-function | § 112(f) | VERIFY / PASS | `check.claims.meansFunction` | Claims invoke 35 U.S.C. § 112(f) means-plus-function |
| Antecedent basis | § 112(b) | VERIFY / PASS | `check.claims.antecedentBasis` | Possible missing antecedent basis ("the X" without prior "a X") |
| Preamble consistency | § 608.01(m) / § 112(d) | AMEND / VERIFY / PASS | `checks.preamble_*` | Dependent claim preambles match independent claim entity type |
| Indefinite article | § 608.01(m) | AMEND | `checks.preamble_indefinite_article` | Dependent claim uses "A"/"An" instead of "The" |
| Transition phrase | § 112 | AMEND / PASS | `check.claims.missingTransition` / `check.claims.transitionsPresent` | Every independent claim has a transitional phrase |
| Jepson prior art | § 2129 | VERIFY | `claims.jepsonPriorArt` | Jepson format — preamble elements treated as admitted prior art |
| CRM non-transitory | § 101 | AMEND | `claims.crmNonTransitory` | Computer-readable medium missing 'non-transitory' qualifier |
| Markush transition | § 2117 | VERIFY | `claims.markushOpenTransition` | Markush group uses open-ended transition instead of 'consisting of' |
| Omnibus claim | § 112(b) | AMEND | `claims.omnibusClaim` | Claim references description/drawings without specific features |
| Special formats pass | — | PASS | `claims.specialFormatsPass` | No special claim format issues detected |
| Spec support | § 112(a) | VERIFY / PASS | `checks.spec_support_unsupported_terms` / `checks.spec_support_pass` | Claim terms found/not found in specification (3-tier matching) |
| Claims overview † | — | PASS | `check.claims.overview` | Summary: independent, dependent, and total claim counts |

## Brief Description of Drawings

| Check | Reference | Severity | message_key | Description |
|-------|-----------|----------|-------------|-------------|
| Single-figure labeling | § 608.02 | AMEND / PASS | `check.drawings.singleFigure` | Single-figure patent uses correct labeling ("The Figure") |
| Prior art references | § 608.02 | VERIFY / PASS | `check.drawings.priorArt` | Prior art references found in drawings description — verify figure labeling |
| Figures sequential | § 608.02 | AMEND / PASS | `check.drawings.sequential` | Figures are in sequential order |
| Figure count † | § 608.02 | PASS | `check.drawings.count` | Number of figures found |
| Cross-ref consistency | § 608.02 | VERIFY / PASS | `checks.figure_xref_*` | Figure references consistent between Brief Description and Detailed Description |

## Abstract

| Check | Reference | Severity | message_key | Description |
|-------|-----------|----------|-------------|-------------|
| Restrictive wording | § 608.01(b) | VERIFY / PASS | `check.abstract.restrictiveWording` | Restrictive or improper wording in abstract |
| Structure | § 608.01(b) | AMEND / PASS | `check.abstract.structure` | Abstract is single paragraph with valid ending |
| Implied phrases | § 608.01(b) | AMEND / PASS | `check.abstract.impliedPhrases` | Abstract contains 'disclosure' or 'provided' |
| Word count | § 608.01(b) | AMEND / PASS | `check.abstract.wordCount` | Abstract word count within 50–150 range |

---

**Total checks: 33** (10 Specification + 14 Claims + 5 Drawings + 4 Abstract)

† Internal: not rendered as a CheckItem card in the web UI. Used for stats aggregation, PDF report, and CLI output only.
