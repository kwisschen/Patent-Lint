# PatentLint — Check Inventory

Complete inventory of every check implemented in PatentLint, organized by report section.

## Specification

| Check | Reference | Severity | message_key | Description |
|-------|-----------|----------|-------------|-------------|
| Tracked changes | — | FIX | `check.spec.trackedChanges.amend` | Document contains tracked changes (revisions) |
| Title requirements | MPEP § 606, § 608.01 | FIX / REVIEW / PASS | `check.spec.title` | Title ≤500 chars, no trademarks/model numbers; advisory warning if >15 words |
| Restrictive wording | § 112(b), MPEP § 2111.01(II) | REVIEW / PASS | `check.spec.restrictiveWording` | MPEP 2111.01(II) narrowing language in spec paragraphs: always / never / must / solely / every / required / essential / critical / vital / necessary / imperative / indispensable (Phase 9 #72b) |
| Paragraph sequential | § 608.01(p) | FIX / PASS | `check.spec.paragraphSequential` / `check.spec.paragraphSequential.missing` | Paragraph numbers are sequential; no paragraph numbering found (patent documents only) |
| Paragraph ending | § 608.01(p) | REVIEW / PASS | `check.spec.paragraphEnding` | Paragraphs have valid ending punctuation (formatting hygiene; §608.01(p) governs numbering, not termination) |
| Sequence listing | § 2422 | FIX / PASS | `check.spec.sequenceListing` | SEQ ID NO referenced but no sequence listing statement |
| Cross-reference | § 608.01 | REVIEW / PASS | `check.spec.crossReference` | Cross-reference section cites related applications — verify completeness |
| Prior art citations | § 608.01(c) | REVIEW / PASS | `check.spec.priorArt` | Background section cites prior art — review characterizations |
| Required sections | § 608.01(a) | FIX / PASS | `checks.required_sections_missing` / `checks.required_sections_pass` | Required sections per MPEP § 608.01(a) are present |
| Optional sections | § 608.01(a) | REVIEW | `checks.optional_section_missing` | Optional section not found (informational) |
| Scope-limiting wording | MPEP § 2111; Phillips v. AWH 415 F.3d 1303 | REVIEW / PASS | `check.spec.scopeLimitWording` | "the (present) invention" / "this invention" in spec body — scope-limit risk under Phillips claim construction |
| Reference numeral consistency (D1) | MPEP § 608.01(g) | FIX / PASS | `check.spec.numeralConsistency` | Same reference numeral used with multiple disjoint element names — drafter typo / copy-paste error |
| Drawings overview † | § 608.02 | REVIEW / PASS | `check.spec.drawings` | Composite drawings summary (figures count, sequential, prior art, single-figure) |

## Claims

| Check | Reference | Severity | message_key | Description |
|-------|-----------|----------|-------------|-------------|
| Restrictive absolutes | § 2173.01 | REVIEW / PASS | `check.claims.restrictiveAbsolutes` | Absolute terms (must, always, never, etc.) |
| Indefinite wording | § 2173.05(b) | REVIEW / PASS | `check.claims.indefiniteWording` | Relative/indefinite terms (may, substantially, generally, etc.) |
| Claims sequential | § 608.01(m) | FIX / PASS | `check.claims.sequential` | Claim numbers are sequential |
| Multiple dependents | § 608.01(n) | REVIEW / PASS | `check.claims.multipleDependent` | Multiple-dependent claims found — fee + chain reminder |
| Chained multi-dep | § 112(e) | FIX / PASS | `check.claims.chainedMultiDep` | Multi-dep claim depending on another multi-dep claim |
| Self-dependent | § 112(d) | FIX / PASS | `check.claims.selfDependent` | Self-dependent claims found |
| Missing period | § 608.01(m) | FIX | `claims.missingPeriod` | Per-claim: claim does not end with a period |
| Extra periods | § 608.01(m) | FIX | `claims.extraPeriod` | Per-claim: claim has extra or misplaced periods |
| Wherein comma | § 608.01(m) | REVIEW | `claims.whereinComma` | Per-claim: incorrect comma around 'wherein' clause |
| Punctuation pass | § 608.01(m) | PASS | `claims.punctuationPass` | All claims have correct punctuation |
| Means-plus-function | § 112(f) | REVIEW / PASS | `check.claims.meansFunction` | Claims invoke 35 U.S.C. § 112(f) means-plus-function |
| Antecedent basis | § 112(b) | FIX / PASS | `check.claims.antecedentBasis` | Possible missing antecedent basis ("the X" without prior "a X") |
| Preamble consistency | § 608.01(m) / § 112(d) | FIX / REVIEW / PASS | `checks.preamble_*` | Dependent claim preambles match independent claim entity type |
| Indefinite article | § 608.01(m) | FIX | `checks.preamble_indefinite_article` | Dependent claim uses "A"/"An" instead of "The" |
| Transition phrase | § 112 | FIX / PASS | `check.claims.missingTransition` / `check.claims.transitionsPresent` | Every independent claim has a transitional phrase |
| Jepson prior art | § 2129 | REVIEW | `claims.jepsonPriorArt` | Jepson format — preamble elements treated as admitted prior art |
| CRM non-transitory | § 101 | FIX | `claims.crmNonTransitory` | Computer-readable medium missing 'non-transitory' qualifier |
| Markush transition | § 2117 | FIX | `claims.markushOpenTransition` | Markush group uses open-ended transition instead of 'consisting of' (improper Markush = substantive rejection on the merits per MPEP § 2117) |
| Omnibus claim | § 112(b) | FIX | `claims.omnibusClaim` | Claim references description/drawings without specific features |
| Special formats pass | — | PASS | `claims.specialFormatsPass` | No special claim format issues detected |
| Spec support | § 112(a) | FIX / PASS | `checks.spec_support_unsupported_terms` / `checks.spec_support_pass` | Claim terms found/not found in specification (3-tier matching) |
| Claims overview † | — | PASS | `check.claims.overview` | Summary: independent, dependent, and total claim counts |

## Brief Description of Drawings

| Check | Reference | Severity | message_key | Description |
|-------|-----------|----------|-------------|-------------|
| Single-figure labeling | § 608.02 | FIX / PASS | `check.drawings.singleFigure` | Single-figure patent uses correct labeling ("The Figure") |
| Prior art references | § 608.02 | REVIEW / PASS | `check.drawings.priorArt` | Prior art references found in drawings description — verify figure labeling |
| Figures sequential | § 608.02 | FIX / PASS | `check.drawings.sequential` | Figures are in sequential order |
| Figure count † | § 608.02 | PASS | `check.drawings.count` | Number of figures found |
| Cross-ref consistency | § 608.02 | FIX / PASS | `checks.figure_xref_*` | Figure references consistent between Brief Description and Detailed Description |

## Abstract

| Check | Reference | Severity | message_key | Description |
|-------|-----------|----------|-------------|-------------|
| Legal phraseology | § 608.01(b) | REVIEW / PASS | `check.abstract.legalPhraseology` | Claim-style legal phraseology (means, said, comprising, wherein, thereof, the same) |
| Merit language | § 608.01(b) | REVIEW / PASS | `check.abstract.meritLanguage` | Purported-merit or self-referential language (novel, innovative, present invention, etc.) |
| Structure | § 608.01(b) | FIX / PASS | `check.abstract.structure` | Abstract is single paragraph with valid ending |
| Implied phrases | § 608.01(b) | FIX / PASS | `check.abstract.impliedPhrases` | Abstract contains 'disclosure' or 'provided' |
| Word count | § 608.01(b) | FIX / PASS | `check.abstract.wordCount` | Abstract word count within 50–150 range |

---

**Total US checks: 40** (10 Specification + 21 Claims + 4 Drawings + 5 Abstract; † summary rows excluded)

† Internal: not rendered as a CheckItem card in the web UI or PDF report. Used for stats aggregation and CLI output only.

---

## CN Specification (说明书)

| Check | Reference | Severity | message_key | Description |
|-------|-----------|----------|-------------|-------------|
| Tracked changes | — | FIX | `check.cn.spec.trackedChanges.amend` | Document contains tracked changes (revisions) |
| Required sections | 专利法实施细则 §20 | FIX / PASS | `check.cn.spec.requiredSections` | Required sections present (技术领域, 背景技术, 发明内容, 具体实施方式) |
| Section ordering | 专利法实施细则 §20 | FIX / PASS | `check.cn.spec.sectionOrdering` | Sections in prescribed order |
| Paragraph numbering | 审查指南 | FIX / PASS | `check.cn.spec.paragraphNumbering` | XML: sequential `<p num>` tags; docx: `[NNNN]` format present |
| Paragraph ending | 审查指南 | REVIEW / PASS | `check.cn.spec.paragraphEnding` | Paragraphs end with Chinese punctuation (。！？) (formatting hygiene; not literal in 实施细则 or 审查指南) |
| Figure ref consistency | 审查指南 | FIX / PASS | `check.cn.spec.figureRefConsistency` | Figure references match between 附图说明 and 具体实施方式 |
| Patent type terminology | 审查指南 | REVIEW / PASS | `check.cn.spec.patentTypeTerminology` | 本发明 vs 本实用新型 consistency |
| Title requirements | 审查指南 第一部分第一章 | FIX / PASS | `check.cn.spec.title` | Title ≤25 CJK chars, no trademarks/model numbers |
| Spec must not reference claims | 专利法实施细则 §20 | FIX / PASS | `check.cn.spec.claimReference` | No 如权利要求N所述 in specification |
| Reference numeral consistency (D1) | 专利法实施细则 §21 第2款; 审查指南 §3.3.1 | FIX / PASS | `check.cn.spec.numeralConsistency` | Same drawing reference (附图标记) used with multiple disjoint component names — 同一附图标记应当指代同一构件 |

## CN Claims (权利要求)

| Check | Reference | Severity | message_key | Description |
|-------|-----------|----------|-------------|-------------|
| Claims sequential | 审查指南 | FIX / PASS | `check.cn.claims.sequential` | Claim numbers sequential from 1 |
| Dependency format | 专利法实施细则 §25 | FIX / PASS | `check.cn.claims.dependencyFormat` | Dependencies use 如权利要求N所述的 format |
| Independent claim preamble | 审查指南 §3.1.1 (canonical form) | REVIEW / PASS | `check.cn.claims.independentPreamble` | Advisory: independent claims typically open with 一种 (statute requires subject-matter name, not literal 一种) |
| Self-dependent | 专利法实施细则 §25 | FIX / PASS | `check.cn.claims.selfDependent` | Claim does not depend on itself |
| Forward dependency | 专利法实施细则 §25 | FIX / PASS | `check.cn.claims.forwardDependency` | No references to later claims |
| Single sentence | 审查指南 第二部分第二章 | FIX / PASS | `check.cn.claims.singleSentence` | Each claim is one sentence ending with 。 |
| Reference numeral parentheses | 审查指南 | REVIEW / PASS | `check.cn.claims.refNumeralParens` | Reference numerals in parentheses, e.g. (101) |
| Subject name consistency | 审查指南 第二部分第二章 | REVIEW / PASS | `check.cn.claims.subjectConsistency` | Dependent claim subject matches parent |
| Transition phrase | 审查指南 | REVIEW / PASS | `check.cn.claims.transitionPhrase` | Independent claims contain 其特征在于 |
| TW terminology | — | FIX / PASS | `check.cn.claims.twTerminology` | Flags 请求项 (TIPO) vs 权利要求 (CNIPA) — jurisdictional contamination = filing-fatal |
| Claims must not reference spec/drawings | 审查指南 第二部分第二章 | FIX / PASS | `check.cn.claims.specReference` | No references to 说明书 or 附图 in claims |
| Multi-dep on multi-dep | 专利法实施细则 §25 第3款 | FIX / PASS | `check.cn.claims.multiMultiDep` | Multi-dep claim cannot reference another multi-dep |
| Dependent claim ordering | 审查指南 第二部分第二章 | FIX / PASS | `check.cn.claims.dependentOrdering` | Dependents grouped after their independent claim |
| Component connection relationships | 审查指南 §3.2.1 + 专利法 §26.4 | REVIEW / PASS | `check.cn.claims.connectionRelationships` | Independent device/system claims must describe how their listed components connect (carve-outs: method, CRM, MPF, composition) |
| Antecedent basis (引用基础) | 审查指南 第二部分第二章 §3.2.2 | FIX / PASS | `check.cn.claims.antecedentBasis` | BFS ancestor-chain walker with cycle protection; char-bigram Jaccard tokenization with CJK ordinal guard pre-filter; did-you-mean suggestion layer on borderline misses |
| Specification support (说明书支持) | 专利法 §26 第4款 + 审查指南 第二部分第二章 §3.2.1 | FIX / PASS | `check.cn.claims.specSupport` | 3-tier match (aggressively-normalized exact → raw exact → ±30-char CJK bigram window) for every claim intro against technical_field + summary + detailed_description (背景技术 excluded per §2.2.3 — prior-art context, not disclosure). Inventory hygiene: paren + bare-numeral reference strip, leading preposition strip (于/到/在/自/由/从/向/对), mid-phrase reference-prefix recovery, conjunction split including disjunctive 或 (X或Y → X, Y), length cap 12, existential-verb leading reject (设有/装有/配置有/设置有), CN-drafting trailing-token strip (之间/位于/构成/设置 etc.), tw_contamination skip (该等/该些 parser artifacts not double-reported) |
| Omnibus claim | 审查指南 第二部分第二章 §3.3 | FIX / PASS | `check.cn.claims.omnibus` | Claim references 说明书/附图 without reciting specific technical features |
| Markush open transition | 审查指南 第二部分第十章 §9.3 | FIX / PASS | `check.cn.claims.markushOpenTransition` | Markush group uses 包括/具有/含有 instead of 组成的 (closed transition) — improper Markush = substantive rejection per §9.3 |

## CN Abstract (摘要)

| Check | Reference | Severity | message_key | Description |
|-------|-----------|----------|-------------|-------------|
| Character count | 专利法实施细则 §26 | FIX / PASS | `check.cn.abstract.charCount` | Abstract ≤300 Chinese characters |
| Title match | 审查指南 | REVIEW / PASS | `check.cn.abstract.titleMatch` | 发明名称 appears in abstract (compound titles split on 以及/及/和/与 — `passCompound` when all halves ≥2 CJK chars appear, Phase 9 #72a) |
| Commercial language | 专利法实施细则 §26 | FIX / PASS | `check.cn.abstract.commercialLanguage` | No 最优, 最佳, 世界领先, etc. |

## CN Drawings (附图)

| Check | Reference | Severity | message_key | Description |
|-------|-----------|----------|-------------|-------------|
| Figure count † | 审查指南 | PASS | `check.cn.drawings.figureCount` | Number of figures found |
| Prior art references | 审查指南 第一部分第一章 §4.2 | REVIEW / PASS | `check.cn.drawings.priorArt` | Prior-art references found in 附图说明 — verify figure labeling |
| Figures sequential | 审查指南 | FIX / PASS | `check.cn.drawings.figuresSequential` | Figure numbers form a contiguous 1..N set (sub-figure suffixes collapsed) |

---

## TW Specification (說明書)

| Check | Reference | Severity | message_key | Description |
|-------|-----------|----------|-------------|-------------|
| Required sections | 專利法施行細則 §17 | FIX / PASS | `check.tw.spec.requiredSections` | Required sections present (技術領域, 先前技術, 發明內容/新型內容, 實施方式) |
| Section ordering | 專利法施行細則 §17 | FIX / PASS | `check.tw.spec.sectionOrdering` | Sections in prescribed order |
| Paragraph numbering format | 專利法施行細則 §17 | FIX / PASS | `check.tw.spec.paragraphNumbering` | If present: 【NNNN】format, sequential, no gaps |
| Paragraph ending punctuation | 專利審查基準 | REVIEW / PASS | `check.tw.spec.paragraphEnding` | Paragraphs end with valid Chinese punctuation (。！？) (formatting hygiene; not literal in 施行細則 or 審查基準) |
| Figure reference consistency | 專利審查基準 | FIX / PASS | `check.tw.spec.figureRefConsistency` | Figure references match between 圖式簡單說明 and 實施方式 |
| Patent type terminology | 專利審查基準 | REVIEW / PASS | `check.tw.spec.patentTypeTerminology` | 本發明 vs 本新型 consistency |
| Title requirements | 專利審查基準 | FIX / PASS | `check.tw.spec.title` | Title concise, no trademarks or model numbers |
| Spec must not reference claims | 專利法施行細則 §17 | FIX / PASS | `check.tw.spec.claimReference` | No 如請求項N所述 in specification |
| Reference symbol consistency (D1) | 專利法施行細則 §19 第2款 | FIX / PASS | `check.tw.spec.numeralConsistency` | Same reference symbol used with multiple disjoint element names — 同一代表符號應指稱同一元件 |
| 符號說明 presence | 專利法施行細則 §17 | FIX / PASS | `check.tw.spec.symbolTablePresence` | 符號說明 required when 圖式簡單說明 exists |
| 符號說明 numeral coverage (D3) | 專利法施行細則 §19 第2款 | FIX / PASS | `check.tw.spec.symbolTableCoverage` | All reference symbols used in spec body must be declared in 符號說明 |
| 符號說明 vs spec consistency | 專利審查基準 | REVIEW / PASS | `check.tw.spec.symbolTableConsistency` | Symbols in 符號說明 appear in 實施方式 |
| Indigenous terminology | 原住民族傳統智慧創作保護條例 | REVIEW / PASS | `check.tw.spec.indigenousTerms` | Indigenous peoples terms flagged for drafter review |

## TW Claims (申請專利範圍)

| Check | Reference | Severity | message_key | Description |
|-------|-----------|----------|-------------|-------------|
| Claims sequential | 專利審查基準 | FIX / PASS | `check.tw.claims.sequential` | Claim numbers sequential from 1 |
| Dependency format | 專利法施行細則 §18 | FIX / PASS | `check.tw.claims.dependencyFormat` | Dependencies use recognized format |
| Independent claim preamble | 專利審查基準 + TIPO 偵錯系統 #20 | REVIEW / PASS | `check.tw.claims.independentPreamble` | Advisory: independent claims typically open with 一種 (statute requires subject-matter name, not literal 一種) |
| Self-dependent | 專利法施行細則 §18 | FIX / PASS | `check.tw.claims.selfDependent` | Claim does not depend on itself |
| Circular dependency | 專利法施行細則 §18 | FIX / PASS | `check.tw.claims.circularDependency` | No circular dependency chains |
| Forward dependency | 專利法施行細則 §18 | FIX / PASS | `check.tw.claims.forwardDependency` | Dependent claim only references preceding claims |
| Single sentence | 專利法施行細則 §18 | FIX / PASS | `check.tw.claims.singleSentence` | Each claim has exactly one 。 at end |
| Reference numerals in parentheses | 專利法施行細則 §19 第3款 | FIX / PASS | `check.tw.claims.refNumeralParens` | Reference numerals enclosed in parentheses — §19 第3款 mandates parens when numerals are used |
| Subject name consistency | 專利審查基準 | REVIEW / PASS | `check.tw.claims.subjectConsistency` | Dependent claim subject matches parent |
| Transition phrase detection | 專利法施行細則 §20 | REVIEW / PASS | `check.tw.claims.transitionPhrase` | Independent claims contain 其特徵在於 or equivalent |
| CN terminology flag | — | FIX / PASS | `check.tw.claims.cnTerminology` | Flags CNIPA terminology in TW document — jurisdictional contamination = filing-fatal |
| Claims must not reference spec/drawings | 專利法施行細則 §19 | FIX / PASS | `check.tw.claims.specDrawingRef` | No 如說明書所述, 如圖所示 in claims |
| Multi-multi dependency prohibited | 專利法施行細則 §18 | FIX / PASS | `check.tw.claims.multiDepOnMultiDep` | Multi-dep cannot depend on another multi-dep |
| Multi-dep alternative form | 專利法施行細則 §18 | FIX / PASS | `check.tw.claims.multiDepAlternative` | Multi-dep claims must use alternative form |
| Title vs claims subject | 專利審查基準 | REVIEW / PASS | `check.tw.claims.titleSubjectMatch` | 發明名稱/新型名稱 consistent with independent claim subjects |
| Claims vs 符號說明 consistency | 專利法施行細則 §19 | REVIEW / PASS | `check.tw.claims.symbolTableConsistency` | Numerals in claims undefined in 符號說明 (reverse direction not flagged; zero-numeral claims early-return PASS) |
| Antecedent basis (先行詞) | 專利審查基準 | REVIEW / PASS | `check.tw.claims.antecedentBasis` | BFS ancestor-chain walker with cycle protection; char-bigram Jaccard tokenization (threshold 0.40) with CJK ordinal guard pre-filter; did-you-mean suggestion layer on borderline misses; known limitations: semantic-disjunction intro regex, bigram Jaccard precision ceiling, multi-hop chain-walking gaps (Phase 9) |
| Specification support (說明書支持) | 專利法 §26 第3項 | FIX / PASS | `check.tw.claims.specSupport` | 4-tier match (symbol-table whitelist + representative-drawing symbols → aggressively-normalized exact → raw exact → ±30-char CJK bigram window) for every claim intro against technical_field + prior_art + disclosure + embodiment. Inventory-level hygiene: TIPO §19 trailing parenthetical reference numerals stripped, leading preposition strip (於/到/在/自/由), mid-phrase reference-prefix recovery, conjunction split (X及Y → X, Y), length cap 12, leading-verb + interior clause-marker reject (ADR-138) |
| Component connection relationships | 專利審查基準 §2.4 | REVIEW / PASS | `check.tw.claims.connectionRelationships` | Independent apparatus/system claims must describe how their listed components are arranged (carve-outs: method, CRM, MPF, composition) |

## TW Abstract (摘要)

| Check | Reference | Severity | message_key | Description |
|-------|-----------|----------|-------------|-------------|
| Character count | 專利法施行細則 §21 | FIX / PASS | `check.tw.abstract.charCount` | Abstract within 250 characters — §21 hard limit |
| Title match | 專利審查基準 | REVIEW / PASS | `check.tw.abstract.titleMatch` | 發明名稱/新型名稱 appears in abstract (compound titles split on 以及/及/和/與 — `passCompound` when all halves ≥2 CJK chars appear, Phase 9 #72a) |
| Commercial language | 專利法施行細則 §21 | FIX / PASS | `check.tw.abstract.commercialLanguage` | No 商業性宣傳用語 (最優, 最佳, 世界領先, etc.) |
| Representative drawing | 專利法施行細則 §21 | REVIEW / PASS | `check.tw.abstract.representativeDrawing` | 代表圖 designation present when drawings exist |

## TW Cross-Reference

| Check | Reference | Severity | message_key | Description |
|-------|-----------|----------|-------------|-------------|
| 符號說明 vs 代表圖 consistency | 專利審查基準 | REVIEW / PASS | `check.tw.crossRef.symbolVsRepDrawing` | Symbols in 代表圖之符號簡單說明 match 符號說明 |
| Section header bracket format | 專利法施行細則 §17 | FIX / PASS | `check.tw.crossRef.bracketFormat` | Section headers use proper 【】brackets — §17 strict bracket format |

## TW Drawings (圖式)

| Check | Reference | Severity | message_key | Description |
|-------|-----------|----------|-------------|-------------|
| Figure count † | 專利審查基準 | PASS | `check.tw.drawings.figureCount` | Number of figures found |
| Figures sequential | 專利審查基準 | FIX / PASS | `check.tw.drawings.figuresSequential` | Figure numbers form a contiguous 1..N set (sub-figure suffixes collapsed) |

---

**Total checks: 109** (40 US + 32 CN + 37 TW; † summary rows excluded)

† Internal: not rendered as a CheckItem card in the web UI or PDF report. Used for stats aggregation and CLI output only.

---

## Pre-analysis gate — jurisdiction detection

Before any check runs, every upload passes through a jurisdiction-aware document-type detector. When the detector rejects an input as "not a [selected jurisdiction] patent," the frontend renders `NonPatentBanner` with a "Show Results Anyway" bypass button — the detector is advisory, not a hard gate.

| Jurisdiction | Detector | Accepts | Rejects |
|---|---|---|---|
| US | `sections.py::detect_patent_document` | English section headers (CLAIMS, ABSTRACT, DETAILED DESCRIPTION, …) OR English claim preamble (`1. A/An/The ...`); east-asian-script ratio ≤ 5% | CJK (CN/TW/JP), Hangul (KO), German / French / Spanish / other Latin-script foreign patents |
| CN | `sections_cn.py::detect_patent_document_cn` | CN sub-section headers (技术领域, 背景技术, 发明内容, 附图说明, 具体实施方式), 五书 body-anchor markers (权利要求书, 说明书摘要), or 3+ numbered-claim lines with ≥ 20% CJK ratio | TW 【】 bracket headers, JP kana, KO Hangul, US / other Latin-script foreign patents |
| TW | `sections_tw.py::detect_patent_document_tw` | 【】 fullwidth bracket headers, 請求項 claims keyword, or 3+ 【NNNN】 paragraph numbers | JP kana, KO Hangul, CN Simplified (uses 权利要求 not 請求項; [NNNN] ASCII brackets not 【NNNN】) |

See ADR-134 for the full rationale and `src/patentlint/parser/language.py` for the shared CJK / Hangul / kana classifiers.
