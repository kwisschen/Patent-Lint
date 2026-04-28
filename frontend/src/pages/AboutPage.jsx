// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Check, Mail, ShieldCheck, Server, Github, Linkedin } from 'lucide-react'
import { useInView } from '../hooks/useInView'
import PageCTA from '../components/PageCTA'
import { useCountUp } from '../hooks/useCountUp'
import { JURISDICTION_COLORS } from '../lib/jurisdictionConfig'
import { composeEnterprise } from '../lib/feedback'
import { useFeedback } from '../components/FeedbackPicker'
import { TESTS_DISPLAY, CHECKS_DISPLAY, CHECKS_BY_JURISDICTION } from '../generated/stats'

function JurisdictionBadge({ code }) {
  return (
    <span
      className="inline-flex items-center justify-center w-6 h-6 rounded-full text-[9px] font-bold text-white shrink-0"
      style={{ backgroundColor: JURISDICTION_COLORS[code] }}
    >
      {code}
    </span>
  )
}

/* ────────────────────────────────────────────
   Section 1: Product Story
   ──────────────────────────────────────────── */
function ProductStory({ t }) {
  const [ref, isInView] = useInView()

  return (
    <section
      ref={ref}
      style={{
        opacity: isInView ? 1 : 0,
        transform: isInView ? 'translateY(0)' : 'translateY(24px)',
        transition: 'opacity 600ms ease, transform 600ms ease',
      }}
    >
      <h2 className="text-3xl font-bold text-foreground mb-6">
        {t('about.productTitle')}
      </h2>
      <p className="text-lg font-medium text-primary mb-4">
        {t('about.productTagline')}
      </p>
      <div className="space-y-4 text-muted-foreground leading-relaxed">
        <p>{t('about.productDesc1')}</p>
        <p>{t('about.productDesc2')}</p>
      </div>
    </section>
  )
}

/* ────────────────────────────────────────────
   Section 2: USPTO Comparison Table
   ──────────────────────────────────────────── */
// Row order follows CLAUDE.md § Check-ordering consistency invariant (7 canonical
// groups: spec structure → spec content → drawings → claims structure → claims
// cross-jurisdiction → claims §112 analysis → abstract). Within each marketing
// bucket (G1 = Formatting & Structure, G2 = USPTO Filing Format, G3 = Substantive
// Drafting), rows sort by that canonical sequence so readers see the same order
// they encounter in actual analysis results.
//
// G1/G3 placement is grounded in USPTO Patent Center's documented DOCX validation
// (DOCX_Feedback_Errors_and_Warnings.pdf + Sept 2025 User Guide): it catches
// period-ending, capitalization, single-sentence, numbering, multiple dependency,
// abstract word count, paragraph numbering, and section-heading detection — but
// performs NO semantic § 112 analysis, figure cross-reference, or paragraph-
// ending-punctuation checks. Items in G1 are shared; G3 is PatentLint-only.
const GROUP1_CHECKS = [
  // Spec structure
  'requiredSections', 'sectionHeaders', 'paraNumbering', 'specParaNumbering',
  // Claims structure (formatting half)
  'claimSequentiality', 'claimDependencies', 'claimPeriods',
  // Abstract structure
  'abstractWordCount', 'abstractStructure',
  // Filing extras
  'checkSequenceListing',
]

const GROUP2_CHECKS = [
  // Filing-format-specific checks (PDF / margins / typography) — outside the
  // canonical 7-group ordering; leave as-is.
  'pdfCompliance', 'marginCheck', 'fontSizeCheck', 'lineSpacing',
  'pageNumbering', 'headerFooter', 'filingReceipt',
]

const GROUP3_CHECKS = [
  // Spec structure (semantic)
  'specParaEndings',
  // Spec content (figure cross-reference)
  'figureCrossRef',
  // Drawings (MPEP § 608.02 semantic rules — USPTO doesn't check pre-submission)
  'figureSequential', 'singleFigure', 'priorArtLabeling',
  // Claims structure (substantive half)
  'transitionPhrase',
  // Claims cross-jurisdiction (restrictive wording family)
  'restrictiveWording', 'indefiniteTerms',
  // Claims §112 analysis
  'meansPlusFunction', 'antecedentBasis', 'specSupport', 'preambleConsistency',
  'checkJepsonPriorArt', 'checkCrmNonTransitory', 'checkMarkushTransition', 'checkOmnibusClaim',
  'whereinCommas', 'checkClaimPunctuation',
  // Abstract (substantive half)
  'legalPhrasesAbstract', 'impliedPhrases',
]

function CheckMark({ active, isPatentLint }) {
  if (!active) {
    return <span className="inline-flex justify-center text-muted-foreground/40">—</span>
  }
  return (
    <Check
      size={18}
      className={`inline-block ${isPatentLint ? 'text-green-600 dark:text-green-400' : 'text-muted-foreground'}`}
      strokeWidth={2.5}
    />
  )
}

// CN table: same canonical 7-group ordering within each tbody as US + TW.
// Single-column "what PatentLint covers" framing (no public CNIPA pre-filing
// debug system to compare against — CNIPA's WORD转XML编辑器 is filing-format
// only). Total 32 checks per CHECKS.md row count (excluding the † informational
// figureCount row, which by US/TW convention also doesn't appear in the
// marketing table).
const CN_SPEC_CHECKS = [
  // G1 spec structure
  'trackedChanges',                  // FIX (no statute — drafting hygiene)
  'requiredSections',                // 专利法实施细则 §17
  'sectionOrdering',                 // 专利法实施细则 §17
  'paragraphNumbering',              // 审查指南
  'paragraphEnding',                 // 审查指南
  // G2 spec content
  'figureRefConsistency',            // 审查指南
  'patentTypeTerminology',           // 审查指南
  'titleRequirements',               // 审查指南 第一部分第一章
  'specClaimReference',              // 专利法实施细则 §17
]

const CN_CLAIMS_CHECKS = [
  // G4 claims structure
  'claimsSequential',                // 审查指南
  'dependencyFormat',                // 专利法实施细则 §22
  'independentPreamble',             // 审查指南 §3.1.1 canonical (advisory)
  'selfDependent',                   // 专利法实施细则 §22
  'forwardDependency',               // 专利法实施细则 §22
  'dependentOrdering',               // 审查指南 第二部分第二章
  'singleSentence',                  // 审查指南 第二部分第二章
  'refNumeralParens',                // 审查指南
  'subjectNameConsistency',          // 审查指南 第二部分第二章
  'transitionPhrase',                // 审查指南
  // G5 claims cross-jurisdiction
  'cnTwTerminology',                 // — (PatentLint guard against TIPO leakage)
  'claimsSpecReference',             // 审查指南 第二部分第二章
  'multiMultiDependency',            // 专利法实施细则 §22
  'connectionRelationships',         // 审查指南 §3.2.1 + 专利法 §26.4
  // G6 claims §112-equivalent (引用基础 + 说明书支持)
  'antecedentBasis',                 // 审查指南 第二部分第二章 §3.2.2
  'specSupport',                     // 专利法 §26 第4款 + 审查指南 §3.2.1 (ADR-151)
  'omnibus',                         // 审查指南 第二部分第二章 §3.3
  'markushOpenTransition',           // 审查指南 第二部分第十章 §9.3
]

const CN_ABSTRACT_CHECKS = [
  // G7 abstract
  'abstractCharCount',               // 专利法实施细则 §23
  'titleInAbstract',                 // 审查指南
  'commercialLanguage',              // 专利法实施细则 §23
]

const CN_DRAWINGS_CHECKS = [
  // G3 drawings (figureCount † informational row excluded by US/TW convention)
  'priorArt',                        // 审查指南 第一部分第一章 §4.2
  'figuresSequential',               // 审查指南
]

function CnCheckTable({ t }) {
  const [cnRef1, cnInView1] = useInView()
  const [cnRef2, cnInView2] = useInView()
  const [cnRef3, cnInView3] = useInView()
  const [cnRef4, cnInView4] = useInView()

  const renderCnGroup = (ref, inView, titleKey, checks, delay) => (
    <tbody
      ref={ref}
      style={{
        opacity: inView ? 1 : 0,
        transform: inView ? 'translateY(0)' : 'translateY(16px)',
        transition: `opacity 500ms ease ${delay}ms, transform 500ms ease ${delay}ms`,
      }}
    >
      <tr>
        <td
          colSpan={2}
          className="pt-6 pb-2 px-2 sm:px-4 text-xs sm:text-sm font-semibold text-muted-foreground uppercase tracking-wider"
        >
          {t(titleKey)}
        </td>
      </tr>
      {checks.map((key) => (
        <tr
          key={key}
          className="border-b border-border/50 hover:bg-muted/50 transition-colors border-l-2 border-l-green-200 dark:border-l-green-800"
        >
          <td className="px-2 py-2 sm:px-4 sm:py-2.5 text-xs sm:text-sm text-foreground">
            {t(`about.cnChecks.${key}`)}
          </td>
          <td className="px-2 py-2 sm:px-4 sm:py-2.5 text-center sm:w-40">
            <CheckMark active isPatentLint />
          </td>
        </tr>
      ))}
    </tbody>
  )

  return (
    <div className="frost-card">
      <table className="w-full text-left">
        <thead>
          <tr className="border-b border-border bg-muted/30">
            <th className="px-2 py-2 sm:px-4 sm:py-3 text-xs sm:text-sm font-semibold text-foreground">
              {t('about.uspto.colCheck')}
            </th>
            <th className="px-2 py-2 sm:px-4 sm:py-3 text-xs sm:text-sm font-semibold text-foreground text-center whitespace-nowrap sm:w-40">
              {t('about.uspto.colPatentLint')}
            </th>
          </tr>
        </thead>
        {renderCnGroup(cnRef1, cnInView1, 'about.cnGroups.specification', CN_SPEC_CHECKS, 0)}
        {renderCnGroup(cnRef2, cnInView2, 'about.cnGroups.claims', CN_CLAIMS_CHECKS, 150)}
        {renderCnGroup(cnRef3, cnInView3, 'about.cnGroups.abstract', CN_ABSTRACT_CHECKS, 300)}
        {renderCnGroup(cnRef4, cnInView4, 'about.cnGroups.drawings', CN_DRAWINGS_CHECKS, 450)}
      </table>
    </div>
  )
}

const US_FEATURE_KEYS = ['claimTree', 'specAbstract', 'specSupport']
const CN_FEATURE_KEYS = ['claimTree', 'specAbstract', 'dualPipeline']
const TW_FEATURE_KEYS = ['claimTree', 'specAbstract', 'symbolTable']

const FEATURE_ACCENT = {
  US: {
    border: 'border-l-blue-200 dark:border-l-blue-800',
    glow: 'rgba(37, 99, 235, 0.18)',
    sheen: 'rgba(96, 165, 250, 0.22)',
  },
  CN: {
    border: 'border-l-red-200 dark:border-l-red-800',
    glow: 'rgba(220, 38, 38, 0.18)',
    sheen: 'rgba(248, 113, 113, 0.22)',
  },
  TW: {
    border: 'border-l-teal-200 dark:border-l-teal-800',
    glow: 'rgba(13, 148, 136, 0.18)',
    sheen: 'rgba(45, 212, 191, 0.22)',
  },
}

function JurisdictionFeatureBlock({ t, jurisdiction, cardKeys }) {
  const [ref, inView] = useInView()
  const prefix = `${jurisdiction.toLowerCase()}Features`
  const accent = FEATURE_ACCENT[jurisdiction] ?? FEATURE_ACCENT.US

  return (
    <div
      ref={ref}
      className="mb-8"
      style={{
        opacity: inView ? 1 : 0,
        transform: inView ? 'translateY(0)' : 'translateY(16px)',
        transition: 'opacity 500ms ease, transform 500ms ease',
      }}
    >
      <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-4">
        {t(`about.${prefix}.title`)}
      </h3>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {cardKeys.map((key, i) => (
          <div
            key={key}
            className={`feature-card frost-card frost-card-interactive p-4 border-l-2 ${accent.border}`}
            style={{
              '--feature-glow': accent.glow,
              '--feature-sheen': accent.sheen,
              opacity: inView ? 1 : 0,
              transform: inView ? 'translateY(0)' : 'translateY(14px)',
              transition: `opacity 600ms var(--ease-smooth) ${i * 120}ms, transform 600ms var(--ease-smooth) ${i * 120}ms, box-shadow 260ms var(--ease-smooth), border-color 260ms var(--ease-smooth)`,
            }}
          >
            <div className="feature-card__sheen" aria-hidden="true" />
            <div className="text-sm font-semibold text-foreground mb-2 relative">
              {t(`about.${prefix}.${key}.title`)}
            </div>
            <div className="text-xs text-muted-foreground leading-relaxed relative">
              {t(`about.${prefix}.${key}.description`)}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// TW table: two marketing buckets (Shared / PatentLint-only).
// Within each bucket rows sort by the canonical 7-group document order.
//
// AUTHORITATIVE SOURCE for TIPO coverage: "專利申請文件輔助偵錯系統 —
// 功能介紹與使用指南" (2023.5.30 版, 專利行政企劃組 助理審查官 劉克群).
// Table 1 lists 20 documented check families — each check below is mapped
// to the specific TIPO item number it corresponds to. G1 is direct evidence
// from that table, not inference.
const TW_GROUP1_CHECKS = [
  // G2 spec-content
  'figureRefConsistency',        // TIPO #4  (實施方式圖號 vs 圖式簡單說明)
  'patentTypeTerminology',       // TIPO #18 (新型 內容/實施方式 用「本發明」「此發明」)
  'symbolVsRepDrawing',          // TIPO #1/#2/#16 (符號說明 vs 代表圖符號簡單說明)
  'symbolTableConsistency',      // TIPO #3  (新型內容/實施方式 vs 符號說明/代表圖符號簡單說明)
  'tipoIndigenous',              // TIPO #19 (原住民相關用語)
  // G4 claims-structure
  'selfDependent',               // TIPO #5  (附屬項未依附在前 — self-dep 分支)
  'circularDependency',          // TIPO #5  (附屬項未依附在前 — circular 分支)
  'forwardDependency',           // TIPO #5  (附屬項未依附在前 — forward 分支)
  'singleSentence',              // TIPO #8  (獨立項/附屬項未以單句為之)
  'refNumeralParens',            // TIPO #9  (構件符號未全部置於括號內)
  'subjectConsistency',          // TIPO #10 (附屬項標的名稱 vs 所依附請求項標的名稱)
  'dependencyFormat',            // TIPO #20 (附屬項開頭「如」「依據」「根據」)
  'independentPreamble',         // TIPO #20 (獨立項「一種」開頭)
  // G5 claims-cross-jurisdiction
  'cnTerminology',               // TIPO #17 (附屬項開頭使用「權利要求」)
  'multiDepOnMultiDep',          // TIPO #6  (多項附屬項直接/間接依附多項附屬項)
  'multiDepAlternative',         // TIPO #7  (多項附屬項未以選擇式為之)
  'titleSubjectMatch',           // TIPO #15 (新型名稱 vs 請求項標的名稱)
  'claimsSymbolTableConsistency',// TIPO #13 (申請專利範圍 vs 符號說明/代表圖符號簡單說明)
  'connectionRelationships',     // TIPO #14 (獨立項主要構件連結/對應關係)
  // G6 claims §112-equivalent
  'antecedentBasis',             // TIPO #11 + #12 (先行詞 + 不當依附)
]

const TW_GROUP3_CHECKS = [
  // G1 spec-structure
  'requiredSections', 'sectionOrdering', 'paragraphNumbering', 'paragraphEnding', 'bracketFormat',
  // G2 spec-content
  'title', 'claimReference', 'symbolTablePresence',
  // G3 drawings
  'figuresSequential',
  // G4 claims-structure
  'sequential', 'transitionPhrase',
  // G5 claims-cross-jurisdiction
  'specDrawingRef',
  // G6 claims §26 第3項 semantic walker analysis
  'specSupport',
  // G7 abstract
  'charCount', 'titleMatch', 'commercialLanguage', 'representativeDrawing',
]

function TwComparisonTable({ t }) {
  const [ref1, inView1] = useInView()
  const [ref3, inView3] = useInView()

  const renderGroup = (ref, inView, titleKey, checks, tipo, patentlint, highlight, delay) => (
    <tbody
      ref={ref}
      style={{
        opacity: inView ? 1 : 0,
        transform: inView ? 'translateY(0)' : 'translateY(16px)',
        transition: `opacity 500ms ease ${delay}ms, transform 500ms ease ${delay}ms`,
      }}
    >
      <tr>
        <td
          colSpan={3}
          className="pt-6 pb-2 px-2 sm:px-4 text-xs sm:text-sm font-semibold text-muted-foreground uppercase tracking-wider"
        >
          {t(titleKey)}
        </td>
      </tr>
      {checks.map((key) => (
        <tr
          key={key}
          className={`border-b border-border/50 hover:bg-muted/50 transition-colors ${
            highlight ? 'border-l-2 border-l-green-200 dark:border-l-green-800' : ''
          }`}
        >
          <td className="px-2 py-2 sm:px-4 sm:py-2.5 text-xs sm:text-sm text-foreground">
            {t(`about.twChecks.${key}`)}
          </td>
          <td className="px-2 py-2 sm:px-4 sm:py-2.5 text-center sm:w-40">
            <CheckMark active={tipo} isPatentLint={false} />
          </td>
          <td className="px-2 py-2 sm:px-4 sm:py-2.5 text-center sm:w-40">
            <CheckMark active={patentlint} isPatentLint={true} />
          </td>
        </tr>
      ))}
    </tbody>
  )

  return (
    <div className="frost-card">
      <table className="w-full text-left">
        <thead>
          <tr className="border-b border-border bg-muted/30">
            <th className="px-2 py-2 sm:px-4 sm:py-3 text-xs sm:text-sm font-semibold text-foreground">
              {t('about.uspto.colCheck')}
            </th>
            <th className="px-2 py-2 sm:px-4 sm:py-3 text-xs sm:text-sm font-semibold text-foreground text-center whitespace-nowrap sm:w-40">
              {t('about.tw.colTipo')}
            </th>
            <th className="px-2 py-2 sm:px-4 sm:py-3 text-xs sm:text-sm font-semibold text-foreground text-center whitespace-nowrap sm:w-40">
              {t('about.uspto.colPatentLint')}
            </th>
          </tr>
        </thead>
        {renderGroup(ref1, inView1, 'about.tw.group1Title', TW_GROUP1_CHECKS, true, true, false, 0)}
        {renderGroup(ref3, inView3, 'about.tw.group3Title', TW_GROUP3_CHECKS, false, true, true, 150)}
      </table>
      <p className="text-xs text-muted-foreground italic px-2 py-3">
        {t('about.twTableFootnote')}
      </p>
    </div>
  )
}

function UsComparisonTable({ t }) {
  const [ref1, inView1] = useInView()
  const [ref2, inView2] = useInView()
  const [ref3, inView3] = useInView()

  const renderGroup = (ref, inView, titleKey, checks, uspto, patentlint, highlight, delay) => (
    <tbody
      ref={ref}
      style={{
        opacity: inView ? 1 : 0,
        transform: inView ? 'translateY(0)' : 'translateY(16px)',
        transition: `opacity 500ms ease ${delay}ms, transform 500ms ease ${delay}ms`,
      }}
    >
      <tr>
        <td
          colSpan={3}
          className="pt-6 pb-2 px-2 sm:px-4 text-xs sm:text-sm font-semibold text-muted-foreground uppercase tracking-wider"
        >
          {t(titleKey)}
        </td>
      </tr>
      {checks.map((key) => (
        <tr
          key={key}
          className={`border-b border-border/50 hover:bg-muted/50 transition-colors ${
            highlight ? 'border-l-2 border-l-green-200 dark:border-l-green-800' : ''
          }`}
        >
          <td className="px-2 py-2 sm:px-4 sm:py-2.5 text-xs sm:text-sm text-foreground">
            {t(`about.uspto.check.${key}`)}
          </td>
          <td className="px-2 py-2 sm:px-4 sm:py-2.5 text-center sm:w-40">
            <CheckMark active={uspto} isPatentLint={false} />
          </td>
          <td className="px-2 py-2 sm:px-4 sm:py-2.5 text-center sm:w-40">
            <CheckMark active={patentlint} isPatentLint={true} />
          </td>
        </tr>
      ))}
    </tbody>
  )

  return (
    <div className="frost-card">
      <table className="w-full text-left">
        <thead>
          <tr className="border-b border-border bg-muted/30">
            <th className="px-2 py-2 sm:px-4 sm:py-3 text-xs sm:text-sm font-semibold text-foreground">
              {t('about.uspto.colCheck')}
            </th>
            <th className="px-2 py-2 sm:px-4 sm:py-3 text-xs sm:text-sm font-semibold text-foreground text-center whitespace-nowrap sm:w-40">
              {t('about.uspto.colUSPTO')}
            </th>
            <th className="px-2 py-2 sm:px-4 sm:py-3 text-xs sm:text-sm font-semibold text-foreground text-center whitespace-nowrap sm:w-40">
              {t('about.uspto.colPatentLint')}
            </th>
          </tr>
        </thead>
        {renderGroup(ref1, inView1, 'about.uspto.group1Title', GROUP1_CHECKS, true, true, false, 0)}
        {renderGroup(ref2, inView2, 'about.uspto.group2Title', GROUP2_CHECKS, true, false, false, 150)}
        {renderGroup(ref3, inView3, 'about.uspto.group3Title', GROUP3_CHECKS, false, true, true, 300)}
      </table>
      <p className="text-xs text-muted-foreground italic px-2 py-3">
        {t('about.tableFootnote')}
      </p>
    </div>
  )
}

function ComparisonTable({ t }) {
  const [activeTab, setActiveTab] = useState('US')

  return (
    <section>
      <div className="text-center mb-8">
        <div
          className="flex items-center justify-center gap-1 rounded-lg p-1 mb-4 w-fit mx-auto ring-1"
          style={{
            backgroundImage: 'var(--frost-resting-bg)',
            boxShadow: 'var(--frost-resting-inner-light)',
            borderColor: 'var(--frost-resting-border)',
          }}
          role="radiogroup"
          aria-label={t('jurisdiction.label')}
        >
          {['US', 'CN', 'TW'].map((j) => (
            <button
              key={j}
              role="radio"
              aria-checked={activeTab === j}
              onClick={() => setActiveTab(j)}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                activeTab === j
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <JurisdictionBadge code={j} />
              {t(`jurisdiction.${j.toLowerCase()}`)}
            </button>
          ))}
        </div>
        <h2 className="text-3xl font-bold text-foreground mb-2">
          {t(activeTab === 'CN' ? 'about.cnTitle' : activeTab === 'TW' ? 'about.twTitle' : 'about.usptoTitle')}
        </h2>
        <p className="text-muted-foreground">
          {t(
            activeTab === 'CN' ? 'about.cnSubtitle' : activeTab === 'TW' ? 'about.twSubtitle' : 'about.usptoSubtitle',
            { count: CHECKS_BY_JURISDICTION[activeTab] }
          )}
        </p>
      </div>

      {activeTab === 'US' && (
        <>
          <JurisdictionFeatureBlock t={t} jurisdiction="US" cardKeys={US_FEATURE_KEYS} />
          <UsComparisonTable t={t} />
        </>
      )}
      {activeTab === 'CN' && (
        <>
          <JurisdictionFeatureBlock t={t} jurisdiction="CN" cardKeys={CN_FEATURE_KEYS} />
          <CnCheckTable t={t} />
        </>
      )}
      {activeTab === 'TW' && (
        <>
          <JurisdictionFeatureBlock t={t} jurisdiction="TW" cardKeys={TW_FEATURE_KEYS} />
          <TwComparisonTable t={t} />
        </>
      )}
    </section>
  )
}

/* ────────────────────────────────────────────
   Section 3a: Stats Cards
   ──────────────────────────────────────────── */
function StatCard({ value, suffix, label, delay }) {
  const [ref, inView] = useInView()
  const count = useCountUp(value, 800, inView)

  return (
    <div
      ref={ref}
      className="frost-card frost-card-interactive p-6 text-center"
      style={{
        opacity: inView ? 1 : 0,
        transform: inView ? undefined : 'translateY(16px)',
        transition: `opacity 400ms ease ${delay}ms, transform 400ms ease ${delay}ms`,
      }}
    >
      <div className="text-3xl font-bold text-foreground">
        {count}{suffix}
      </div>
      <div className="text-sm text-muted-foreground mt-1">{label}</div>
    </div>
  )
}

function StatsGrid({ t }) {
  const { i18n } = useTranslation()
  const localeCount = (i18n.options.supportedLngs || []).filter((l) => l !== 'cimode').length
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
      <StatCard value={TESTS_DISPLAY} suffix="+" label={t('about.stats.tests')} delay={0} />
      <StatCard value={CHECKS_DISPLAY} suffix="+" label={t('about.stats.checks')} delay={100} />
      <StatCard value={localeCount} suffix="" label={t('about.stats.languages')} delay={200} />
      <StatCard value={0} suffix="" label={t('about.stats.cloudRequests')} delay={300} />
    </div>
  )
}

/* ────────────────────────────────────────────
   Section 3b: Architecture Diagram
   ──────────────────────────────────────────── */
const BROWSER_NODES = [
  { id: 'react', label: 'React Frontend', tipKey: 'about.arch.tip.react' },
  { id: 'pyodide', label: 'Pyodide / WebAssembly', tipKey: 'about.arch.tip.pyodide' },
  { id: 'patentlint', labelKey: 'about.arch.node.analysisEngine', tipKey: null },
  { id: 'pdfmake', labelKey: 'about.arch.node.pdfReport', tipKey: 'about.arch.tip.pdfmake' },
]

const OPTIONAL_NODES_LEFT = [
  { id: 'fastapi', label: 'FastAPI', tipKey: 'about.arch.tip.fastapi' },
  { id: 'cli', label: 'CLI', tipKey: 'about.arch.tip.cli' },
]

const OPTIONAL_NODES_RIGHT = [
  { id: 'weasyprint', label: 'weasyprint', tipKey: 'about.arch.tip.weasyprint' },
]

function ArchNode({ label, tipKey, t }) {
  const [hovered, setHovered] = useState(false)
  const tip = tipKey ? t(tipKey) : null

  return (
    <div className="relative flex flex-col items-center">
      <div
        className={`px-4 py-2 rounded-lg border text-sm font-medium transition-all duration-200 cursor-default select-none ${
          hovered
            ? 'border-primary scale-[1.02] shadow-md text-foreground'
            : 'border-border text-foreground bg-card'
        }`}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        {label}
      </div>
      {tip && hovered && (
        <div className="absolute top-full mt-2 px-3 py-1.5 text-xs text-muted-foreground bg-muted rounded shadow-lg whitespace-nowrap z-10">
          {tip}
        </div>
      )}
    </div>
  )
}

function ArchitectureDiagram({ t }) {
  const [ref, inView] = useInView()
  const nodeH = 40
  const gap = 12
  const step = nodeH + gap
  const railX = 12
  const stubLen = 16
  const dotR = 3

  const browserRailHeight = (BROWSER_NODES.length - 1) * step
  const totalDrawDelay = 500

  const { sendFeedback } = useFeedback()
  const handleEnterpriseClick = (e) => {
    e.preventDefault()
    sendFeedback(composeEnterprise(t))
  }

  return (
    <div ref={ref} className="mt-12">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Browser group */}
        <div className="border-l-4 border-l-green-600 dark:border-l-green-500 pl-6 py-4">
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-4">
            {t('about.arch.browser')}
          </h3>
          <div className="relative" style={{ paddingLeft: railX + stubLen + 8 }}>
            {/* Rail + stubs SVG */}
            <svg
              className="absolute left-0 top-0 pointer-events-none"
              width={railX + stubLen + 4}
              height={browserRailHeight + nodeH}
              style={{ overflow: 'visible' }}
            >
              {/* Vertical rail */}
              <line
                x1={railX} y1={nodeH / 2} x2={railX} y2={browserRailHeight + nodeH / 2}
                stroke="var(--color-green-600, #16a34a)"
                strokeWidth="2"
                strokeDasharray={browserRailHeight + nodeH}
                strokeDashoffset={inView ? 0 : browserRailHeight + nodeH}
                style={{ transition: `stroke-dashoffset 1300ms ease ${totalDrawDelay}ms` }}
              />
              {/* Horizontal stubs + junction dots */}
              {BROWSER_NODES.map((_, i) => {
                const cy = i * step + nodeH / 2
                const drawDelay = totalDrawDelay + 300 + i * 250
                return (
                  <g key={i}>
                    <line
                      x1={railX} y1={cy} x2={railX + stubLen} y2={cy}
                      stroke="var(--color-green-600, #16a34a)"
                      strokeWidth="2"
                      strokeDasharray={stubLen}
                      strokeDashoffset={inView ? 0 : stubLen}
                      style={{ transition: `stroke-dashoffset 650ms ease ${drawDelay}ms` }}
                    />
                    <circle
                      cx={railX} cy={cy} r={dotR}
                      fill="var(--color-green-600, #16a34a)"
                      style={{
                        opacity: inView ? 1 : 0,
                        transform: inView ? 'scale(1)' : 'scale(0)',
                        transformOrigin: `${railX}px ${cy}px`,
                        transition: `opacity 300ms ease ${drawDelay}ms, transform 500ms var(--ease-bounce) ${drawDelay}ms`,
                      }}
                    />
                  </g>
                )
              })}
            </svg>
            {/* Nodes */}
            <div className="flex flex-col" style={{ gap: `${gap}px` }}>
              {BROWSER_NODES.map((node) => (
                <div key={node.id} style={{ height: nodeH }} className="flex items-center">
                  <ArchNode label={node.labelKey ? t(node.labelKey) : node.label} tipKey={node.tipKey} t={t} />
                </div>
              ))}
            </div>
            <div className="flex items-center gap-1.5 mt-4 text-xs text-green-600 dark:text-green-400">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>{t('about.arch.zeroBadge')}</span>
            </div>
          </div>
        </div>

        {/* Optional group */}
        <div className="border-l-4 border-l-slate-400/40 dark:border-l-slate-500/30 pl-6 py-4">
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-4">
            {t('about.arch.optional')}
          </h3>
          <div className="space-y-6">
            {[
              { left: 'FastAPI', leftTip: 'about.arch.tip.fastapi', right: 'weasyprint', rightTip: 'about.arch.tip.weasyprint', delay: 1000 },
              { left: 'CLI', leftTip: 'about.arch.tip.cli', right: 'weasyprint', rightTip: 'about.arch.tip.weasyprint', delay: 1300 },
            ].map(({ left, leftTip, right, rightTip, delay }, idx) => (
              <div key={idx} className="flex items-center gap-3">
                <ArchNode label={left} tipKey={leftTip} t={t} />
                <svg width="40" height="16" className="shrink-0" style={{ overflow: 'visible' }}>
                  <line
                    x1="2" y1="8" x2="34" y2="8"
                    stroke="currentColor" strokeWidth="1.5" className="text-slate-400 dark:text-slate-500"
                    strokeDasharray="5 4"
                    strokeDashoffset={inView ? 0 : 36}
                    style={{ transition: `stroke-dashoffset 1000ms ease ${delay}ms` }}
                  />
                  <circle cx="2" cy="8" r={dotR - 1} className="fill-slate-400 dark:fill-slate-500"
                    style={{ opacity: inView ? 1 : 0, transition: `opacity 300ms ease ${delay}ms` }}
                  />
                  <polygon points="32,4 38,8 32,12" className="fill-slate-400 dark:fill-slate-500"
                    style={{ opacity: inView ? 1 : 0, transition: `opacity 300ms ease ${delay + 500}ms` }}
                  />
                </svg>
                <ArchNode label={right} tipKey={rightTip} t={t} />
              </div>
            ))}
          </div>
          <div className="flex items-center gap-1.5 mt-4 text-xs text-muted-foreground">
            <Server className="w-3.5 h-3.5" />
            <span>{t('about.arch.selfHostBadge')}</span>
          </div>
          <a
            href="#"
            onClick={handleEnterpriseClick}
            className="inline-flex items-center gap-1 mt-3 text-sm text-primary underline underline-offset-4 hover:text-primary/80"
          >
            {t('security.tech.contactEnterprise')}
          </a>
        </div>
      </div>
    </div>
  )
}

/* ────────────────────────────────────────────
   Section 4: Builder Story
   ──────────────────────────────────────────── */
function BuilderStory({ t }) {
  const [ref, inView] = useInView()

  const links = [
    { href: 'mailto:kwisschen@gmail.com', icon: Mail, label: 'Email' },
    { href: 'https://github.com/kwisschen', icon: Github, label: 'GitHub' },
    { href: 'https://linkedin.com/in/kwisschen', icon: Linkedin, label: 'LinkedIn' },
  ]

  return (
    <section
      ref={ref}
      style={{
        opacity: inView ? 1 : 0,
        transform: inView ? 'translateY(0)' : 'translateY(24px)',
        transition: 'opacity 600ms ease, transform 600ms ease',
      }}
    >
      <h2 className="text-3xl font-bold text-foreground mb-6">
        {t('about.builderTitle')}
      </h2>
      <div className="space-y-4 text-muted-foreground leading-relaxed">
        <p>{t('about.builderPain')}</p>
        <p>{t('about.builderDesc1')}</p>
        <p>{t('about.builderDesc2')}</p>
        <p>{t('about.builderSister')}</p>
      </div>
      <div className="flex flex-wrap gap-3 mt-8">
        {links.map(({ href, icon: Icon, label }) => (
          <a
            key={label}
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full border border-border text-sm font-medium text-foreground bg-card hover:shadow-md transition-all duration-200"
            style={{ transitionTimingFunction: 'var(--ease-bounce)' }}
            onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-2px)' }}
            onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)' }}
          >
            <Icon size={16} />
            {label}
          </a>
        ))}
      </div>
    </section>
  )
}

/* ────────────────────────────────────────────
   Main About Page
   ──────────────────────────────────────────── */
export default function AboutPage() {
  const { t } = useTranslation()
  useEffect(() => { window.scrollTo(0, 0) }, [])

  return (
    <div className="w-full max-w-5xl mx-auto px-4 py-16 space-y-24">
      <ProductStory t={t} />
      <ComparisonTable t={t} />
      <section>
        <StatsGrid t={t} />
        <ArchitectureDiagram t={t} />
      </section>
      <BuilderStory t={t} />
      <PageCTA />
    </div>
  )
}
