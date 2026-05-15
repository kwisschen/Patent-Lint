// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025–2026 Christopher Chen
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { FileSearch, ChevronRight, Flag } from 'lucide-react'
import { Button } from './ui/button'
import { FrostCard } from './ui/frost-card'
import { StatusPill } from './ui/status-pill'
import { composeFeedback, sendReport, excerptAround, SAMPLE_SIZE } from '../lib/feedback'
import { useFeedback } from './FeedbackPicker'
import ReportModal from './ReportModal'

function ClaimRow({ claimNumber, phrases, crossRefPhrases, claimText, jurisdiction }) {
  const { t, i18n } = useTranslation()
  const { sendFeedback } = useFeedback()
  // Default-expanded so per-finding Report buttons surface without an
  // extra click — matches AntecedentBasisCard sibling behavior.
  const [expanded, setExpanded] = useState(true)
  const [reportModalOpen, setReportModalOpen] = useState(false)
  const hasCrossRef = crossRefPhrases.length > 0

  const handleReport = () => {
    setReportModalOpen(true)
  }

  // Mirror the antecedent-basis pattern: build a `findings: [...]` list of
  // per-phrase pinpoint data (phrase, cross_ref, char_offset, context excerpt)
  // scoped to this claim. Same shape as the Python section-level extractor
  // so triage tooling handles per-claim and section-level reports identically.
  const buildDiagnostics = () => {
    const text = claimText || ''
    const findingsList = phrases.slice(0, SAMPLE_SIZE).map((p) => {
      const { context_before, context_after, char_offset } = excerptAround(text, p)
      return {
        claim_id: claimNumber,
        phrase: p,
        cross_ref: crossRefPhrases.includes(p) ? 'spec_support' : null,
        char_offset,
        context_before,
        context_after,
        claim_text_charlen: text.length,
      }
    })
    return {
      flagged_claim_id: claimNumber,
      findings_in_group: phrases.length,
      findings: findingsList,
      hit_count: phrases.length,
    }
  }

  const handleAnonymousConfirm = () =>
    sendReport({
      checkKey: 'specSupport',
      jurisdiction: jurisdiction || 'unknown',
      locale: i18n.language,
      diagnostics: buildDiagnostics(),
    })

  const handleMailtoFallback = () => {
    sendFeedback(
      composeFeedback(
        {
          check_key: 'specSupport',
          claim_id: claimNumber,
          phrases: phrases.join(', '),
          jurisdiction: jurisdiction || 'unknown',
        },
        t,
        { locale: i18n.language },
      ),
      { verb: 'report' },
    )
  }

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        className="flex items-center gap-2 px-3 py-2 rounded-md hover:bg-[var(--attention-bg)]/60 transition-colors cursor-pointer"
        onClick={() => setExpanded(!expanded)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            setExpanded(!expanded)
          }
        }}
      >
        <ChevronRight
          className={`h-3.5 w-3.5 shrink-0 transition-transform duration-200 ${expanded ? 'rotate-90' : ''}`}
          style={{ color: 'var(--attention-border)' }}
        />
        <span
          className="inline-flex items-center justify-center h-6 w-6 rounded-full text-xs font-bold shrink-0"
          style={{
            backgroundColor: 'var(--attention-bg)',
            color: 'var(--attention-text)',
            border: '1.5px solid var(--attention-border)',
          }}
        >
          {claimNumber}
        </span>
        <span className="text-sm text-muted-foreground">
          {phrases.map((phrase, i) => (
            <span key={i}>
              {i > 0 && ', '}
              <span className="font-medium" style={{ color: 'var(--attention-text)' }}>
                "{phrase}"
              </span>
            </span>
          ))}
        </span>
      </div>
      {expanded && (
        <div className="mx-3 mb-2 px-3 py-2 rounded text-xs leading-relaxed border flex items-start gap-2" style={{
          borderColor: 'var(--attention-border)',
          backgroundColor: 'var(--attention-bg)',
        }}>
          <div className="flex-1 min-w-0">
            <p className="text-muted-foreground">
              {t('details.specSupportUnsupported', { count: phrases.length })}
            </p>
            {hasCrossRef && (
              <p className="mt-1.5 italic" style={{ color: 'var(--attention-text)' }}>
                {t('specSupport.crossRefAntecedent')}
              </p>
            )}
          </div>
          <Button
            variant="ghost"
            size="xs"
            onClick={handleReport}
            title={t('feedback.reportProblem')}
            aria-label={t('feedback.reportProblem')}
            className="shrink-0"
          >
            <Flag />
            <span className="hidden sm:inline">{t('feedback.report')}</span>
          </Button>
        </div>
      )}
      <ReportModal
        open={reportModalOpen}
        onOpenChange={setReportModalOpen}
        checkKey="specSupport"
        jurisdiction={jurisdiction || 'unknown'}
        locale={i18n.language}
        diagnostics={buildDiagnostics()}
        onConfirm={handleAnonymousConfirm}
        onMailtoFallback={handleMailtoFallback}
      />
    </div>
  )
}

export default function SpecSupportCard({ unsupportedTerms, claimTrees, jurisdiction }) {
  const { t } = useTranslation()

  if (!unsupportedTerms || unsupportedTerms.length === 0) return null

  // Build claim text lookup from claimTrees so per-claim Report payloads
  // can include char_offset + context excerpt around each flagged phrase.
  const claimTextMap = {}
  if (claimTrees) {
    claimTrees.forEach((group) => {
      group.rows.forEach((row) => {
        claimTextMap[row.claim_id] = row.claim_text
      })
    })
  }

  // Group by claim_number, also tracking which phrases carry a cross-reference
  // hint to the antecedent-basis card.
  const grouped = {}
  const crossRefByClaim = {}
  unsupportedTerms.forEach(({ claim_number, phrase, cross_ref }) => {
    if (!grouped[claim_number]) grouped[claim_number] = new Set()
    grouped[claim_number].add(phrase)
    if (cross_ref === 'antecedent') {
      if (!crossRefByClaim[claim_number]) crossRefByClaim[claim_number] = []
      crossRefByClaim[claim_number].push(phrase)
    }
  })

  const claimIds = Object.keys(grouped).map(Number).sort((a, b) => a - b)
  const totalItems = unsupportedTerms.length

  return (
    <FrostCard tier="resting" accent="attention">
      <div className="flex items-center gap-3 px-4 py-3 pl-5">
        <FileSearch className="h-5 w-5 shrink-0" style={{ color: 'var(--attention-border)' }} />
        <h3 className="text-sm font-semibold flex-1">{t('specSupport.title')}</h3>
        <StatusPill status="attention" shape="pill">
          {totalItems} {totalItems !== 1 ? t('specSupport.items') : t('specSupport.item')}
        </StatusPill>
      </div>
      <div className="border-t border-border/40 px-1 py-1">
        {claimIds.map((id) => (
          <ClaimRow
            key={id}
            claimNumber={id}
            phrases={[...grouped[id]]}
            crossRefPhrases={crossRefByClaim[id] || []}
            claimText={claimTextMap[id]}
            jurisdiction={jurisdiction}
          />
        ))}
      </div>
    </FrostCard>
  )
}
