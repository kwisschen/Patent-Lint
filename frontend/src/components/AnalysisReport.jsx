// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025 Christopher Chen
import { useState, useMemo } from 'react'
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
import { Download, RotateCcw, Copy, Check } from 'lucide-react'

/**
 * Consolidate claims_checks to reduce visual noise:
 * 1. Remove redundant "Claims overview" CheckItem
 * 2. Group preamble noun-mismatch VERIFYs by root independent claim
 * 3. Replace individual antecedent basis CheckItems with one summary
 */
function consolidateClaimsChecks(checks) {
  if (!checks) return []

  const consolidated = []
  const nounMismatches = []  // message_key === 'checks.preamble_noun_mismatch'
  const antecedentItems = [] // message_key starts with 'check.claims.antecedentBasis'
  let hasAntecedentPass = false

  for (const check of checks) {
    // Filter out redundant claims overview (stat cards show this info)
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

  // Group noun mismatches by root independent claim
  if (nounMismatches.length > 0) {
    const byRoot = {}
    for (const nm of nounMismatches) {
      // details format: "Claim {dep} depends on claim {root}"
      const rootMatch = nm.details?.match(/depends on claim (\d+)/)
      const rootId = rootMatch ? rootMatch[1] : 'unknown'
      if (!byRoot[rootId]) byRoot[rootId] = { items: [], message: nm.message }
      byRoot[rootId].items.push(nm)
    }

    for (const [rootId, group] of Object.entries(byRoot)) {
      // Extract nouns from first item's message
      // message format: "Claim N: preamble noun 'X' differs from independent claim 'Y'."
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
      })
    }
  }

  // Keep antecedent basis as a single summary item pointing to the card below
  if (antecedentItems.length > 0) {
    const worst = antecedentItems.some(c => c.status === 'amend') ? 'amend' : 'verify'
    consolidated.push({
      status: worst,
      message: 'Missing antecedent basis detected.',
      message_key: 'check.claims.antecedentBasis.verify',
      details: 'See § 112 Analysis below for per-claim detail.',
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

function buildSummaryText(data, t, i18n) {
  const sections = [
    { key: 'section.specification', checks: data.specification_checks || [] },
    { key: 'section.drawings', checks: data.drawings_checks || [] },
    { key: 'section.claims', checks: data.claims_checks || [] },
    { key: 'section.abstract', checks: data.abstract_checks || [] },
  ]
  const allChecks = sections.flatMap((s) => s.checks)
  const amendCount = allChecks.filter((c) => c.status === 'amend').length
  const verifyCount = allChecks.filter((c) => c.status === 'verify').length
  const passCount = allChecks.filter((c) => c.status === 'pass').length

  const triage = [
    `--- ${t('triage.title')} ---`,
    `${t('triage.amend')}: ${amendCount} ${amendCount === 1 ? t('triage.item') : t('triage.items')}`,
    `${t('triage.verify')}: ${verifyCount} ${verifyCount === 1 ? t('triage.item') : t('triage.items')}`,
    `${t('triage.pass')}: ${passCount} ${passCount === 1 ? t('triage.item') : t('triage.items')}`,
  ].join('\n')

  const detail = sections
    .map(({ key, checks }) => {
      const header = `=== ${t(key)} ===`
      const lines = checks.map((c) => {
        const statusLabel = t(`status.${c.status}`)
        const msg = c.message_key && i18n.exists(c.message_key) ? t(c.message_key) : c.message
        return `[${statusLabel}] ${msg}${c.details ? ` — ${c.details}` : ''}`
      })
      return `${header}\n${lines.join('\n')}`
    })
    .join('\n\n')

  return `${triage}\n\n${detail}`
}

export default function AnalysisReport({ data, filename, onDownloadPdf, onReset, downloading }) {
  const { t, i18n } = useTranslation()
  const [copied, setCopied] = useState(false)

  // Consolidate checks once, use everywhere
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

  const handleCopy = async () => {
    const text = buildSummaryText(consolidatedData, t, i18n)
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const hasAntecedentIssues = data.antecedent_basis_issues?.length > 0
  const hasUnsupportedTerms = data.unsupported_terms?.length > 0

  return (
    <div className="space-y-4">
      {filename && (
        <p className="text-sm text-muted-foreground">{t('analysis.label')}: {filename}</p>
      )}

      <HealthDonut data={consolidatedData} />
      <SectionHealthBars data={consolidatedData} />
      <SummaryBar data={consolidatedData} />
      <TriagePanel data={consolidatedData} />

      <div className="space-y-3">
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

      <div className="fixed bottom-0 left-0 right-0 z-40 border-t bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-center gap-3 px-4 py-3">
          <Button className="no-print" onClick={onDownloadPdf} disabled={downloading}>
            <Download className="h-4 w-4" />
            {downloading ? t('button.generating') : t('button.downloadPdf')}
          </Button>
          <Button variant="outline" onClick={handleCopy}>
            {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
            {copied ? t('button.copied') : t('button.copySummary')}
          </Button>
          <Button variant="outline" onClick={onReset}>
            <RotateCcw className="h-4 w-4" />
            {t('button.newAnalysis')}
          </Button>
        </div>
      </div>
    </div>
  )
}
