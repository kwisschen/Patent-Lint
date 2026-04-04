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

**Total US checks: 33** (10 Specification + 14 Claims + 5 Drawings + 4 Abstract)

† Internal: not rendered as a CheckItem card in the web UI or PDF report. Used for stats aggregation and CLI output only.

---

## CN Specification (说明书)

| Check | Reference | Severity | message_key | Description |
|-------|-----------|----------|-------------|-------------|
| Required sections | 专利法实施细则 §17 | AMEND / PASS | `check.cn.spec.requiredSections` | Required sections present (技术领域, 背景技术, 发明内容, 具体实施方式) |
| Section ordering | 专利法实施细则 §17 | AMEND / PASS | `check.cn.spec.sectionOrdering` | Sections in prescribed order |
| Paragraph numbering | 审查指南 | AMEND / PASS | `check.cn.spec.paragraphNumbering` | XML: sequential `<p num>` tags; docx: `[NNNN]` format present |
| Paragraph ending | 审查指南 | AMEND / PASS | `check.cn.spec.paragraphEnding` | Paragraphs end with Chinese punctuation (。！？) |
| Figure ref consistency | 审查指南 | VERIFY / PASS | `check.cn.spec.figureRefConsistency` | Figure references match between 附图说明 and 具体实施方式 |
| Patent type terminology | 审查指南 | VERIFY / PASS | `check.cn.spec.patentTypeTerminology` | 本发明 vs 本实用新型 consistency |
| Title requirements | 审查指南 第一部分第一章 | AMEND / PASS | `check.cn.spec.title` | Title ≤25 CJK chars, no trademarks/model numbers |
| Spec must not reference claims | 专利法实施细则 §17 | AMEND / PASS | `check.cn.spec.claimReference` | No 如权利要求N所述 in specification |

## CN Claims (权利要求)

| Check | Reference | Severity | message_key | Description |
|-------|-----------|----------|-------------|-------------|
| Claims sequential | 审查指南 | AMEND / PASS | `check.cn.claims.sequential` | Claim numbers sequential from 1 |
| Dependency format | 专利法实施细则 §22 | AMEND / PASS | `check.cn.claims.dependencyFormat` | Dependencies use 如权利要求N所述的 format |
| Self-dependent | 专利法实施细则 §22 | AMEND / PASS | `check.cn.claims.selfDependent` | Claim does not depend on itself |
| Forward dependency | 专利法实施细则 §22 | AMEND / PASS | `check.cn.claims.forwardDependency` | No references to later claims |
| Single sentence | 审查指南 第二部分第二章 | AMEND / PASS | `check.cn.claims.singleSentence` | Each claim is one sentence ending with 。 |
| Reference numeral parentheses | 审查指南 | VERIFY / PASS | `check.cn.claims.refNumeralParens` | Reference numerals in parentheses, e.g. (101) |
| Subject name consistency | 审查指南 第二部分第二章 | VERIFY / PASS | `check.cn.claims.subjectConsistency` | Dependent claim subject matches parent |
| Transition phrase | 审查指南 | VERIFY / PASS | `check.cn.claims.transitionPhrase` | Independent claims contain 其特征在于 |
| TW terminology | — | VERIFY / PASS | `check.cn.claims.twTerminology` | Flags 请求项 (TIPO) vs 权利要求 (CNIPA) |
| Claims must not reference spec/drawings | 审查指南 第二部分第二章 | AMEND / PASS | `check.cn.claims.specDrawingRef` | No references to 说明书 or 附图 in claims |
| Multi-dep on multi-dep | 专利法实施细则 §22 | AMEND / PASS | `check.cn.claims.multiDepOnMultiDep` | Multi-dep claim cannot reference another multi-dep |
| Dependent claim ordering | 审查指南 第二部分第二章 | AMEND / PASS | `check.cn.claims.dependentOrdering` | Dependents grouped after their independent claim |

## CN Abstract (摘要)

| Check | Reference | Severity | message_key | Description |
|-------|-----------|----------|-------------|-------------|
| Character count | 专利法实施细则 §23 | AMEND / PASS | `check.cn.abstract.charCount` | Abstract ≤300 Chinese characters |
| Title match | 审查指南 | VERIFY / PASS | `check.cn.abstract.titleMatch` | 发明名称 appears in abstract |
| Commercial language | 专利法实施细则 §23 | AMEND / PASS | `check.cn.abstract.commercialLanguage` | No 最优, 最佳, 世界领先, etc. |

## CN Drawings (附图)

| Check | Reference | Severity | message_key | Description |
|-------|-----------|----------|-------------|-------------|
| Figure count † | 审查指南 | PASS | `check.cn.drawings.figureCount` | Number of figures found |

---

**Total checks: 57** (33 US + 24 CN)

† Internal: not rendered as a CheckItem card in the web UI or PDF report. Used for stats aggregation and CLI output only.
