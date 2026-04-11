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

## TW Specification (說明書)

| Check | Reference | Severity | message_key | Description |
|-------|-----------|----------|-------------|-------------|
| Required sections | 專利法施行細則 §17 | AMEND / PASS | `check.tw.spec.requiredSections` | Required sections present (技術領域, 先前技術, 發明內容/新型內容, 實施方式) |
| Section ordering | 專利法施行細則 §17 | AMEND / PASS | `check.tw.spec.sectionOrdering` | Sections in prescribed order |
| Paragraph numbering format | 專利法施行細則 §17 | AMEND / PASS | `check.tw.spec.paragraphNumbering` | If present: 【NNNN】format, sequential, no gaps |
| Paragraph ending punctuation | 專利審查基準 | AMEND / PASS | `check.tw.spec.paragraphEnding` | Paragraphs end with valid Chinese punctuation (。！？) |
| Figure reference consistency | 專利審查基準 | VERIFY / PASS | `check.tw.spec.figureRefConsistency` | Figure references match between 圖式簡單說明 and 實施方式 |
| Patent type terminology | 專利審查基準 | VERIFY / PASS | `check.tw.spec.patentTypeTerminology` | 本發明 vs 本新型 consistency |
| Title requirements | 專利審查基準 | AMEND / PASS | `check.tw.spec.title` | Title concise, no trademarks or model numbers |
| Spec must not reference claims | 專利法施行細則 §17 | AMEND / PASS | `check.tw.spec.claimReference` | No 如請求項N所述 in specification |
| 符號說明 presence | 專利法施行細則 §17 | AMEND / PASS | `check.tw.spec.symbolTablePresence` | 符號說明 required when 圖式簡單說明 exists |
| 符號說明 vs spec consistency | 專利審查基準 | VERIFY / PASS | `check.tw.spec.symbolTableConsistency` | Symbols in 符號說明 appear in 實施方式 |

## TW Claims (申請專利範圍)

| Check | Reference | Severity | message_key | Description |
|-------|-----------|----------|-------------|-------------|
| Claims sequential | 專利審查基準 | AMEND / PASS | `check.tw.claims.sequential` | Claim numbers sequential from 1 |
| Dependency format | 專利法施行細則 §18 | AMEND / PASS | `check.tw.claims.dependencyFormat` | Dependencies use recognized format |
| Self-dependent | 專利法施行細則 §18 | AMEND / PASS | `check.tw.claims.selfDependent` | Claim does not depend on itself |
| Circular dependency | 專利法施行細則 §18 | AMEND / PASS | `check.tw.claims.circularDependency` | No circular dependency chains |
| Forward dependency | 專利法施行細則 §18 | AMEND / PASS | `check.tw.claims.forwardDependency` | Dependent claim only references preceding claims |
| Single sentence | 專利法施行細則 §18 | AMEND / PASS | `check.tw.claims.singleSentence` | Each claim has exactly one 。 at end |
| Reference numerals in parentheses | 專利法施行細則 §19 | VERIFY / PASS | `check.tw.claims.refNumeralParens` | Reference numerals enclosed in parentheses |
| Subject name consistency | 專利審查基準 | VERIFY / PASS | `check.tw.claims.subjectConsistency` | Dependent claim subject matches parent |
| Transition phrase detection | 專利法施行細則 §20 | VERIFY / PASS | `check.tw.claims.transitionPhrase` | Independent claims contain 其特徵在於 or equivalent |
| CN terminology flag | — | VERIFY / PASS | `check.tw.claims.cnTerminology` | Flags CNIPA terminology in TW document |
| Claims must not reference spec/drawings | 專利法施行細則 §19 | AMEND / PASS | `check.tw.claims.specDrawingRef` | No 如說明書所述, 如圖所示 in claims |
| Multi-multi dependency prohibited | 專利法施行細則 §18 | AMEND / PASS | `check.tw.claims.multiDepOnMultiDep` | Multi-dep cannot depend on another multi-dep |
| Multi-dep alternative form | 專利法施行細則 §18 | AMEND / PASS | `check.tw.claims.multiDepAlternative` | Multi-dep claims must use alternative form |
| Title vs claims subject | 專利審查基準 | VERIFY / PASS | `check.tw.claims.titleSubjectMatch` | 發明名稱/新型名稱 consistent with independent claim subjects |
| Claims vs 符號說明 consistency | 專利法施行細則 §19 | VERIFY / PASS | `check.tw.claims.symbolTableConsistency` | Numerals in claims undefined in 符號說明 (reverse direction not flagged; zero-numeral claims early-return PASS) |
| Antecedent basis (先行詞) | 專利審查基準 | VERIFY / PASS | `check.tw.claims.antecedentBasis` | BFS ancestor-chain walker with cycle protection; char-bigram Jaccard tokenization (threshold 0.40) with CJK ordinal guard pre-filter; did-you-mean suggestion layer on borderline misses; known limitations: semantic-disjunction intro regex, bigram Jaccard precision ceiling, multi-hop chain-walking gaps (Phase 9) |

## TW Abstract (摘要)

| Check | Reference | Severity | message_key | Description |
|-------|-----------|----------|-------------|-------------|
| Character count | 專利法施行細則 §21 | VERIFY / PASS | `check.tw.abstract.charCount` | Abstract within 250 characters |
| Title match | 專利審查基準 | VERIFY / PASS | `check.tw.abstract.titleMatch` | 發明名稱/新型名稱 appears in abstract |
| Commercial language | 專利法施行細則 §21 | AMEND / PASS | `check.tw.abstract.commercialLanguage` | No 商業性宣傳用語 (最優, 最佳, 世界領先, etc.) |
| Representative drawing | 專利法施行細則 §21 | VERIFY / PASS | `check.tw.abstract.representativeDrawing` | 代表圖 designation present when drawings exist |

## TW Cross-Reference

| Check | Reference | Severity | message_key | Description |
|-------|-----------|----------|-------------|-------------|
| 符號說明 vs 代表圖 consistency | 專利審查基準 | VERIFY / PASS | `check.tw.crossRef.symbolVsRepDrawing` | Symbols in 代表圖之符號簡單說明 match 符號說明 |
| Section header bracket format | 專利法施行細則 §17 | VERIFY / PASS | `check.tw.crossRef.bracketFormat` | Section headers use proper 【】brackets |

## TW Drawings (圖式)

| Check | Reference | Severity | message_key | Description |
|-------|-----------|----------|-------------|-------------|
| Figure count † | 專利審查基準 | PASS | `check.tw.drawings.figureCount` | Number of figures found |

---

**Total checks: 90** (33 US + 24 CN + 33 TW)

† Internal: not rendered as a CheckItem card in the web UI or PDF report. Used for stats aggregation and CLI output only.
