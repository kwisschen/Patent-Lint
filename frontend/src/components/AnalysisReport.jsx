// SPDX-License-Identifier: AGPL-3.0-only
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
import { Button } from '@/components/ui/button'
import { Download, RotateCcw, ShieldCheck } from 'lucide-react'
import { useNetworkMonitor } from '../hooks/useNetworkMonitor'

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
      const nounMatch = first.message.match(/preamble noun '([^']+)' differs from independent claim '([^']+)'/)
      const depNoun = nounMatch ? nounMatch[1] : '?'
      const indepNoun = nounMatch ? nounMatch[2] : '?'
      const count = group.items.length

      consolidated.push({
        status: 'verify',
        message: `Preamble noun mismatch: ${count} dependent claim${count !== 1 ? 's' : ''} differ from Claim ${rootId}`,
        message_key: 'checks.preamble_noun_mismatch',
        details: `Independent: '${indepNoun}' — Dependents: '${depNoun}'`,
        details_key: 'details.nounMismatch',
        details_params: { dependent: depNoun, independent: indepNoun },
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

  const consolidatedData = useMemo(() => ({
    ...data,
    specification_checks: (data.specification_checks || []).filter(
      (c) => c.message_key !== 'check.spec.drawings'
    ),
    claims_checks: consolidateClaimsChecks(data.claims_checks),
    drawings_checks: (data.drawings_checks || []).filter(
      (c) => c.message_key !== 'check.drawings.count'
    ),
  }), [data])

  const hasAntecedentIssues = data.antecedent_basis_issues?.length > 0
  const hasUnsupportedTerms = data.unsupported_terms?.length > 0

  const cascadeDelay = (i) => ({
    opacity: mounted ? 1 : 0,
    transform: mounted ? 'translateY(0) scale(1)' : 'translateY(20px) scale(0.95)',
    transition: `opacity 400ms var(--ease-bounce) ${i * 100}ms, transform 400ms var(--ease-bounce) ${i * 100}ms`,
  })

  return (
    <div className="space-y-4">
      {filename && (
        <p className="text-sm text-muted-foreground">{t('analysis.label')}: {filename}</p>
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
      <div style={cascadeDelay(3)}>
        <TriagePanel data={consolidatedData} />
      </div>

      <div className="space-y-3" style={cascadeDelay(4)}>
        <SectionPanel
          title={t('section.specification')}
          checks={consolidatedData.specification_checks}
          defaultOpen
        />
        <SectionPanel
          title={t('section.drawings')}
          checks={consolidatedData.drawings_checks}
          defaultOpen
        />
        <SectionPanel
          title={t('section.claims')}
          checks={consolidatedData.claims_checks}
          defaultOpen
        >
          <ClaimTree claimTrees={data.claim_trees} />
          <ClaimDiagram claimTrees={data.claim_trees} />

          <Section112Container
            hasAntecedentIssues={hasAntecedentIssues}
            hasUnsupportedTerms={hasUnsupportedTerms}
            antecedentBasisIssues={data.antecedent_basis_issues}
            unsupportedTerms={data.unsupported_terms}
            claimTrees={data.claim_trees}
          />
        </SectionPanel>
        <SectionPanel
          title={t('section.abstract')}
          checks={consolidatedData.abstract_checks}
          defaultOpen
        />
      </div>

      {/* Spacer so content isn't hidden behind sticky bar */}
      <div className="h-16" />

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
