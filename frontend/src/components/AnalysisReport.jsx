// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
import { useState, useEffect, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import HealthDonut from './HealthDonut'
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
import { Button } from '@/components/ui/button'
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
      const rootMatch = nm.details?.match(/depends on claim (\d+)/)
      const rootId = rootMatch ? rootMatch[1] : 'unknown'
      if (!byRoot[rootId]) byRoot[rootId] = { items: [], message: nm.message }
      byRoot[rootId].items.push(nm)
    }

    for (const [rootId, group] of Object.entries(byRoot)) {
      const first = group.items[0]
      const nounMatch = first.message.match(/preamble noun '([^']+)' differs from parent claim '([^']+)'/)
      const depNoun = nounMatch ? nounMatch[1] : '?'
      const parentNoun = nounMatch ? nounMatch[2] : '?'
      const count = group.items.length

      consolidated.push({
        status: 'verify',
        message: `Preamble noun mismatch: ${count} dependent claim${count !== 1 ? 's' : ''} differ from Claim ${rootId}`,
        message_key: 'consolidation.nounMismatchSummary',
        details: `Parent: '${parentNoun}' — Dependents: '${depNoun}'`,
        details_key: 'details.preambleNounMismatchSummary',
        details_params: { count: String(count), rootId, dependent: depNoun, parent: parentNoun },
      })
    }
  }

  if (antecedentItems.length > 0) {
    const worst = antecedentItems.some(c => c.status === 'amend') ? 'amend' : 'verify'
    consolidated.push({
      status: worst,
      message: 'Missing antecedent basis detected.',
      message_key: 'check.claims.antecedentBasis.verify',
      details: 'See § 112 Analysis below for per-claim detail.',
      details_key: 'details.seeSection112',
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

export default function AnalysisReport({ data, filename, onDownloadPdf, onReset, downloading, onShowProveIt, pyodideReady }) {
  const { t } = useTranslation()
  const { active: networkActive } = useNetworkMonitor()

  // Non-patent document gate
  const isNonPatent = data.likely_patent === false
  const [showResults, setShowResults] = useState(!isNonPatent)

  // Tracked changes gate
  const hasTrackedChanges = data.has_tracked_changes === true
  const [dismissedTracked, setDismissedTracked] = useState(false)

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

  if (!showResults) {
    return (
      <NonPatentBanner jurisdiction={data.jurisdiction} onShowResults={() => {
        setShowResults(true)
        // Reset cascade so results animate in fresh
        setMounted(false)
        setBarVisible(false)
        setTimeout(() => setMounted(true), 50)
        setTimeout(() => setBarVisible(true), 300)
      }} />
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
    <div className="space-y-4">
      {filename && (
        <div className="flex items-center justify-between gap-3">
          <p className="min-w-0 text-sm text-muted-foreground">{t('analysis.label')}: {filename}</p>
          {data.jurisdiction && (
            <span
              className="whitespace-nowrap rounded-full px-3 py-1 text-xs font-semibold tracking-wide"
              style={{
                background: `linear-gradient(135deg, ${JURISDICTION_COLORS[data.jurisdiction]}, ${JURISDICTION_COLORS[data.jurisdiction]}cc)`,
                color: '#fff',
                boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.2), 0 1px 3px rgba(0,0,0,0.2)',
              }}
            >
              {t(JURISDICTION_I18N[data.jurisdiction])}
            </span>
          )}
        </div>
      )}

      {/* Summary cards with stagger cascade */}
      <div style={cascadeDelay(0)}>
        <HealthDonut data={consolidatedData} animate={mounted} />
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
        />
        <SectionPanel
          title={t(jConfig.drawingsSectionKey)}
          checks={consolidatedData.drawings_checks}
          defaultOpen
          jurisdiction={data.jurisdiction}
        />
        <SectionPanel
          title={t(jConfig.claimsSectionKey)}
          checks={consolidatedData.claims_checks}
          defaultOpen
          jurisdiction={data.jurisdiction}
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
        />
      </div>

      {/* Spacer so content isn't hidden behind sticky bar */}
      <div className="h-28" />

      {/* Single-row action bar with security status */}
      <div
        className="fixed bottom-0 left-0 right-0 z-40 border-t bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 transition-transform duration-300"
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
