import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import HealthDonut from './HealthDonut'
import SectionHealthBars from './SectionHealthBars'
import SummaryBar from './SummaryBar'
import TriagePanel from './TriagePanel'
import SectionPanel from './SectionPanel'
import ClaimTree from './ClaimTree'
import ClaimDiagram from './ClaimDiagram'
import AntecedentBasisCard from './AntecedentBasisCard'
import { Button } from '@/components/ui/button'
import { Download, RotateCcw, Copy, Check } from 'lucide-react'

function buildSummaryText(data, t, i18n) {
  const sections = [
    { key: 'section.specification', checks: data.specification_checks || [] },
    { key: 'section.claims', checks: data.claims_checks || [] },
    { key: 'section.drawings', checks: data.drawings_checks || [] },
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

  const handleCopy = async () => {
    const text = buildSummaryText(data, t, i18n)
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="space-y-4">
      {filename && (
        <p className="text-sm text-muted-foreground">{t('analysis.label')}: {filename}</p>
      )}

      <HealthDonut data={data} />
      <SectionHealthBars data={data} />
      <SummaryBar data={data} />
      <TriagePanel data={data} />

      <div className="space-y-3">
        <SectionPanel
          title={t('section.specification')}
          checks={data.specification_checks}
          defaultOpen
        />
        <SectionPanel
          title={t('section.claims')}
          checks={data.claims_checks}
          defaultOpen
        >
          {data.antecedent_basis_issues?.length > 0 && (
            <AntecedentBasisCard issues={data.antecedent_basis_issues} claimTrees={data.claim_trees} />
          )}
          <ClaimTree claimTrees={data.claim_trees} />
          <ClaimDiagram claimTrees={data.claim_trees} />
        </SectionPanel>
        <SectionPanel
          title={t('section.drawings')}
          checks={data.drawings_checks}
          defaultOpen
        />
        <SectionPanel
          title={t('section.abstract')}
          checks={data.abstract_checks}
          defaultOpen
        />
      </div>

      {/* Spacer so content isn't hidden behind sticky bar */}
      <div className="h-16" />

      <div className="fixed bottom-0 left-0 right-0 z-40 border-t bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-center gap-3 px-4 py-3">
          <Button onClick={onDownloadPdf} disabled={downloading}>
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
