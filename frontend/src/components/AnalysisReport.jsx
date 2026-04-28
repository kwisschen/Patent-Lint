// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
import { useState, useEffect, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import RubricHero from './RubricHero'
import SectionHealthBars from './SectionHealthBars'
import SummaryBar from './SummaryBar'
import TriagePanel from './TriagePanel'
import SectionPanel from './SectionPanel'
import ClaimTree from './ClaimTree'
import ClaimDiagram from './ClaimDiagram'
import AntecedentBasisCard from './AntecedentBasisCard'
import SpecSupportCard from './SpecSupportCard'
import Section112Container from './Section112Container'
import NonPatentBanner from './NonPatentBanner'
import TrackedChangesBanner from './TrackedChangesBanner'
import JurisdictionMismatchBanner from './JurisdictionMismatchBanner'
import { Button } from '@/components/ui/button'
import { FrostCard } from '@/components/ui/frost-card'
import { Download, RotateCcw, ShieldCheck } from 'lucide-react'
import { useNetworkMonitor } from '../hooks/useNetworkMonitor'
import { getJurisdictionConfig, JURISDICTION_COLORS } from '../lib/jurisdictionConfig'

const JURISDICTION_I18N = { US: 'jurisdiction.us', CN: 'jurisdiction.cn', TW: 'jurisdiction.tw' }

/**
 * Consolidate claims_checks to reduce visual noise:
 * 1. Remove redundant "Claims overview" CheckItem
 * 2. Group preamble noun-mismatch VERIFYs by root independent claim
 * 3. Replace individual antecedent basis CheckItems with one summary
 */
function consolidateClaimsChecks(checks) {
  if (!checks) return []

  const consolidated = []
  const nounMismatches = []
  const antecedentItems = []
  let hasAntecedentPass = false

  for (const check of checks) {
    if (check.message_key === 'check.claims.overview') {
      continue
    }
    if (check.message_key === 'checks.preamble_noun_mismatch') {
      nounMismatches.push(check)
    } else if (check.message_key?.startsWith('check.claims.antecedentBasis')) {
      if (check.status === 'pass') {
        hasAntecedentPass = true
      } else {
        antecedentItems.push(check)
      }
    } else {
      consolidated.push(check)
    }
  }

  if (nounMismatches.length > 0) {
    const byRoot = {}
    for (const nm of nounMismatches) {
      // Prefer structured details_params.parent (emitted by the walker since
      // Part A); fall back to regex on message text for older findings.
      const rootId = nm.details_params?.parent
        ?? nm.details?.match(/depends on claim (\d+)/)?.[1]
        ?? 'unknown'
      if (!byRoot[rootId]) byRoot[rootId] = { items: [] }
      byRoot[rootId].items.push(nm)
    }

    for (const [rootId, group] of Object.entries(byRoot)) {
      const first = group.items[0]
      const depNoun = first.details_params?.dependent
        ?? first.message.match(/preamble noun '([^']+)' differs/)?.[1]
        ?? '?'
      const parentNoun = first.details_params?.independent
        ?? first.message.match(/differs from parent claim '([^']+)'/)?.[1]
        ?? '?'
      const count = group.items.length
      // Collect the actual dep-claim IDs so the summary can name them
      // (user feedback: "1 个从属项与请求项 3 不同" was hiding WHICH dep).
      const depClaims = group.items
        .map(it => it.details_params?.claim)
        .filter(Boolean)
        .sort((a, b) => Number(a) - Number(b))

      consolidated.push({
        status: 'verify',
        message: `Preamble noun mismatch: ${count} dependent claim${count !== 1 ? 's' : ''} differ from Claim ${rootId}`,
        message_key: 'consolidation.nounMismatchSummary',
        details: `Parent: '${parentNoun}' — Dependents: '${depNoun}'`,
        details_key: 'details.preambleNounMismatchSummary',
        details_params: {
          count: String(count),
          rootId,
          dependent: depNoun,
          parent: parentNoun,
          depClaims: depClaims.join(', '),
        },
        // Forward the synthesized summary fields + the first underlying
        // walker item's diagnostics (charlens) so a Report click on
        // this consolidated row sends actually-useful pinpoint data.
        diagnostics: {
          summary_count: count,
          parent_claim_id: rootId,
          dependent_noun: depNoun,
          parent_noun: parentNoun,
          dependent_claims: depClaims.join(', '),
          ...(first?.diagnostics || {}),
        },
      })
    }
  }

  if (antecedentItems.length > 0) {
    const worst = antecedentItems.some(c => c.status === 'amend') ? 'amend' : 'verify'
    // Forward the rich diagnostic fingerprint from the underlying
    // walker emit so the Report button on this consolidated row sends
    // the same per-finding pinpoint data (term, did_you_mean, context
    // windows, etc.) as a direct report on the underlying card. Without
    // this, the consolidated row's report would carry only meta-fields
    // (check_key, jurisdiction, locale, build) — useless for triage.
    // Pick the amend item if present (richer payload from the actual
    // walker findings), else fall back to the first verify item.
    const sourceItem = antecedentItems.find(c => c.status === 'amend') || antecedentItems[0]
    consolidated.push({
      status: worst,
      message: 'Missing antecedent basis detected.',
      // message_key matches the chosen status so locale rendering and
      // citation lookup line up. Was always `.verify` even when status
      // was `.amend` — bug since this consolidation row was added.
      message_key: worst === 'amend'
        ? 'check.claims.antecedentBasis.amend'
        : 'check.claims.antecedentBasis.verify',
      details: 'See § 112 Analysis below for per-claim detail.',
      details_key: 'details.seeSection112',
      diagnostics: sourceItem?.diagnostics || null,
    })
  } else if (hasAntecedentPass) {
    consolidated.push({
      status: 'pass',
      message: 'No antecedent basis issues detected.',
      message_key: 'check.claims.antecedentBasis.pass',
    })
  }

  return consolidated
}

export default function AnalysisReport({ data, filename, onDownloadPdf, onReset, onSwitchJurisdiction, downloading, onShowProveIt, pyodideReady }) {
  const { t } = useTranslation()
  const { active: networkActive } = useNetworkMonitor()

  // Non-patent document gate
  const isNonPatent = data.likely_patent === false
  const [showResults, setShowResults] = useState(!isNonPatent)

  // Tracked changes gate
  const hasTrackedChanges = data.has_tracked_changes === true
  const [dismissedTracked, setDismissedTracked] = useState(false)

  // Jurisdiction-mismatch gate (Issue #9 / ADR-082 revisit). Renders
  // before the NonPatent banner because a mismatch is the more useful
  // diagnosis when both fire (mismatch implies the NonPatent trigger
  // was caused by running the wrong-jurisdiction pipeline). When the
  // user clicks Switch, App.jsx re-runs analysis on the same file
  // under the suggested jurisdiction — the component remounts with
  // fresh data so this state resets implicitly.
  const hasJurisdictionMismatch = data.jurisdiction_mismatch === true && Boolean(data.suggested_jurisdiction)
  const [dismissedMismatch, setDismissedMismatch] = useState(false)

  // Stagger cascade for summary cards
  const [mounted, setMounted] = useState(false)
  useEffect(() => {
    const timer = setTimeout(() => setMounted(true), 50)
    return () => clearTimeout(timer)
  }, [])

  // Sticky action bar entrance
  const [barVisible, setBarVisible] = useState(false)
  useEffect(() => {
    const timer = setTimeout(() => setBarVisible(true), 300)
    return () => clearTimeout(timer)
  }, [])

  // Green dot mount pulse
  const [dotPulsed, setDotPulsed] = useState(false)
  useEffect(() => {
    if (pyodideReady) {
      const timer = setTimeout(() => setDotPulsed(true), 100)
      return () => clearTimeout(timer)
    }
  }, [pyodideReady])

  const jConfig = getJurisdictionConfig(data.jurisdiction)

  // --- Rubric grade helpers (per-section pill rendering) ---
  // section_grades is keyed by RubricSection enum values: "specification",
  // "drawings", "claims", "antecedent_spec_support", "abstract".
  const sectionGradeFor = (sectionId) => {
    return data.rubric_grade?.section_grades?.find((sg) => sg.section === sectionId) || null
  }
  // Standard US 12-tier letter map (no A+, matches rubric.py letter_for_score).
  const letterFromScore = (sg) => {
    if (!sg || !sg.applicable) return null
    const s = sg.score
    if (s >= 93) return 'A'
    if (s >= 90) return 'A-'
    if (s >= 87) return 'B+'
    if (s >= 83) return 'B'
    if (s >= 80) return 'B-'
    if (s >= 77) return 'C+'
    if (s >= 73) return 'C'
    if (s >= 70) return 'C-'
    if (s >= 67) return 'D+'
    if (s >= 63) return 'D'
    if (s >= 60) return 'D-'
    return 'F'
  }

  const consolidatedData = useMemo(() => ({
    ...data,
    specification_checks: jConfig.filterInternalSpecChecks
      ? (data.specification_checks || []).filter(
          (c) => c.message_key !== 'check.spec.drawings'
        )
      : data.specification_checks || [],
    claims_checks: jConfig.consolidateClaimsChecks
      ? consolidateClaimsChecks(data.claims_checks)
      : data.claims_checks || [],
    drawings_checks: jConfig.filterInternalDrawingsChecks
      ? (data.drawings_checks || []).filter(
          (c) => c.message_key !== 'check.drawings.count'
        )
      : data.drawings_checks || [],
  }), [data, jConfig])

  const hasAntecedentIssues = data.antecedent_basis_issues?.length > 0
  const hasUnsupportedTerms = data.unsupported_terms?.length > 0

  const cascadeDelay = (i) => ({
    opacity: mounted ? 1 : 0,
    transform: mounted ? 'translateY(0) scale(1)' : 'translateY(20px) scale(0.95)',
    transition: `opacity 400ms var(--ease-bounce) ${i * 100}ms, transform 400ms var(--ease-bounce) ${i * 100}ms`,
  })

  if (hasJurisdictionMismatch && !dismissedMismatch) {
    return (
      <JurisdictionMismatchBanner
        selectedJurisdiction={data.jurisdiction}
        suggestedJurisdiction={data.suggested_jurisdiction}
        onSwitch={() => {
          if (onSwitchJurisdiction) {
            onSwitchJurisdiction(data.suggested_jurisdiction)
          }
        }}
        onDismiss={() => {
          setDismissedMismatch(true)
          // Banner-stack discipline: dismissing the Mismatch banner
          // means the user has acknowledged the document is from a
          // different jurisdiction and chose to view results under the
          // originally-selected pipeline. The NonPatent banner that
          // would otherwise fire next describes the same observation
          // reframed (the selected jurisdiction's markers are absent
          // BECAUSE the doc is from another jurisdiction) for
          // content_missing / weak_signal reasons — suppress it.
          // For cross_script_japanese / cross_script_korean keep
          // NonPatent: it surfaces an orthogonal script-level warning
          // (e.g., "this looks Japanese") that the Mismatch banner
          // didn't address.
          const reason = data.patent_detection_reason || 'content_missing'
          if (reason === 'content_missing' || reason === 'weak_signal') {
            setShowResults(true)
          }
          // Always reset cascade — if NonPatent still fires next, its
          // dismiss handler will redo it; the extra setState calls
          // are cheap and the unused mount/bar timers don't render.
          setMounted(false)
          setBarVisible(false)
          setTimeout(() => setMounted(true), 50)
          setTimeout(() => setBarVisible(true), 300)
        }}
      />
    )
  }

  if (!showResults) {
    return (
      <NonPatentBanner
        jurisdiction={data.jurisdiction}
        reason={data.patent_detection_reason || 'content_missing'}
        onShowResults={() => {
          setShowResults(true)
          // Reset cascade so results animate in fresh
          setMounted(false)
          setBarVisible(false)
          setTimeout(() => setMounted(true), 50)
          setTimeout(() => setBarVisible(true), 300)
        }}
      />
    )
  }

  if (hasTrackedChanges && !dismissedTracked) {
    return (
      <TrackedChangesBanner
        onAnalyzeAgain={onReset}
        onShowResults={() => {
          setDismissedTracked(true)
          // Reset cascade so results animate in fresh
          setMounted(false)
          setBarVisible(false)
          setTimeout(() => setMounted(true), 50)
          setTimeout(() => setBarVisible(true), 300)
        }}
      />
    )
  }

  return (
    <div className="space-y-5">
      {filename && (
        <FrostCard tier="resting" className="flex items-center justify-between gap-3 px-4 py-3">
          <p className="min-w-0 text-sm text-muted-foreground truncate">{t('analysis.label')}: {filename}</p>
          {data.jurisdiction && (
            <span
              className="whitespace-nowrap rounded-full px-3 py-1 text-xs font-semibold tracking-wide shrink-0"
              style={{
                background: `linear-gradient(135deg, ${JURISDICTION_COLORS[data.jurisdiction]}, ${JURISDICTION_COLORS[data.jurisdiction]}cc)`,
                color: '#fff',
                boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.2), 0 1px 3px rgba(0,0,0,0.2)',
              }}
            >
              {t(JURISDICTION_I18N[data.jurisdiction])}
            </span>
          )}
        </FrostCard>
      )}

      {/* Hero: rubric grade letter + score + status legend (replaces
          finding-count hero per the scoring repositioning). */}
      <div style={cascadeDelay(0)}>
        <RubricHero data={consolidatedData} animate={mounted} />
      </div>
      <div style={cascadeDelay(1)}>
        <SectionHealthBars data={consolidatedData} animate={mounted} />
      </div>
      <div style={cascadeDelay(2)}>
        <SummaryBar data={consolidatedData} animate={mounted} />
      </div>
      {jConfig.showClaimTree && data.claim_trees?.length > 0 && (
        <div style={cascadeDelay(3)}>
          <ClaimDiagram claimTrees={data.claim_trees} />
        </div>
      )}
      <div style={cascadeDelay(4)}>
        <TriagePanel data={consolidatedData} />
      </div>

      <div className="space-y-3" style={cascadeDelay(5)}>
        <SectionPanel
          title={t(jConfig.specSectionKey)}
          checks={consolidatedData.specification_checks}
          defaultOpen
          jurisdiction={data.jurisdiction}
          grade={sectionGradeFor('specification')?.score != null ? letterFromScore(sectionGradeFor('specification')) : null}
          applicable={sectionGradeFor('specification')?.applicable !== false}
        />
        <SectionPanel
          title={t(jConfig.drawingsSectionKey)}
          checks={consolidatedData.drawings_checks}
          defaultOpen
          jurisdiction={data.jurisdiction}
          grade={sectionGradeFor('drawings')?.score != null ? letterFromScore(sectionGradeFor('drawings')) : null}
          applicable={sectionGradeFor('drawings')?.applicable !== false}
        />
        <SectionPanel
          title={t(jConfig.claimsSectionKey)}
          checks={consolidatedData.claims_checks}
          defaultOpen
          jurisdiction={data.jurisdiction}
          grade={sectionGradeFor('claims')?.score != null ? letterFromScore(sectionGradeFor('claims')) : null}
          applicable={sectionGradeFor('claims')?.applicable !== false}
        >
          {jConfig.showClaimTree && (
            <>
              <Section112Container
                hasAntecedentIssues={hasAntecedentIssues}
                hasUnsupportedTerms={hasUnsupportedTerms}
                antecedentBasisIssues={data.antecedent_basis_issues}
                unsupportedTerms={data.unsupported_terms}
                claimTrees={data.claim_trees}
                jurisdiction={data.jurisdiction}
              />

              <ClaimTree claimTrees={data.claim_trees} />
            </>
          )}
        </SectionPanel>
        <SectionPanel
          title={t(jConfig.abstractSectionKey)}
          checks={consolidatedData.abstract_checks}
          defaultOpen
          jurisdiction={data.jurisdiction}
          grade={sectionGradeFor('abstract')?.score != null ? letterFromScore(sectionGradeFor('abstract')) : null}
          applicable={sectionGradeFor('abstract')?.applicable !== false}
        />
      </div>

      {/* Spacer so content isn't hidden behind sticky bar */}
      <div className="h-28" />

      {/* Single-row action bar with security status */}
      <div
        className="fixed bottom-0 left-0 right-0 z-40 border-t border-[var(--frost-elevated-border)] frost-blur-md bg-background/85 supports-[backdrop-filter]:bg-background/60 transition-transform duration-[var(--motion-duration-base)] shadow-[var(--frost-elevated-shadow)]"
        style={{
          transform: barVisible ? 'translateY(0)' : 'translateY(100%)',
          transitionTimingFunction: 'var(--ease-smooth)',
        }}
      >
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          {/* Left: action buttons */}
          <div className="flex items-center gap-2">
            <Button className="no-print" onClick={onDownloadPdf} disabled={downloading}>
              <Download className="h-4 w-4" />
              {downloading ? t('button.generating') : t('button.downloadPdf')}
            </Button>
            <Button variant="outline" onClick={onReset}>
              <RotateCcw className="h-4 w-4" />
              {t('button.newAnalysis')}
            </Button>
          </div>

          {/* Right: security status */}
          {pyodideReady && (
            <div className="flex items-center gap-3 text-xs">
              <div className="flex items-center gap-1.5 text-green-600 dark:text-green-400">
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>{t('security.results.badge')}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span
                  className={`w-2 h-2 rounded-full transition-colors duration-75 ${networkActive ? 'bg-red-500' : 'bg-green-500'} ${dotPulsed ? '' : 'network-dot-pulse'}`}
                />
                <span className={`transition-colors duration-75 ${
                  networkActive ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400'
                }`}>
                  {networkActive ? t('security.results.networkActive') : t('security.results.networkIdle')}
                </span>
              </div>
              <button
                onClick={() => onShowProveIt?.()}
                className="text-xs underline underline-offset-2 text-gray-500 hover:text-gray-700 dark:hover:text-gray-400 transition-colors"
              >
                {t('security.results.howItWorks')}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
