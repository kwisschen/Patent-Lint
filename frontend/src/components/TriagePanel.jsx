// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025–2026 Christopher Chen
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { AlertCircle, Search, CheckCircle, ChevronDown, Flag } from 'lucide-react'
import { getCitation } from './CheckItem'
import { getJurisdictionConfig } from '../lib/jurisdictionConfig'
import { formatDetails } from '../lib/detailsFormatter'
import { composeFeedback, sendReport } from '../lib/feedback'
import { useFeedback } from './FeedbackPicker'
import { Button } from './ui/button'
import { FrostCard } from './ui/frost-card'
import FlaggedTermList from './FlaggedTermList'
import NumeralFindingList from './NumeralFindingList'
import ReportModal from './ReportModal'

const GROUP_CONFIG = [
  { status: 'amend', titleKey: 'triage.amend', emptyKey: 'triage.amendEmpty', Icon: AlertCircle },
  { status: 'verify', titleKey: 'triage.verify', emptyKey: 'triage.verifyEmpty', Icon: Search },
  { status: 'pass', titleKey: 'triage.pass', emptyKey: null, Icon: CheckCircle },
]

function TriageItem({ check, t, i18n, compact, jurisdiction }) {
  const { sendFeedback } = useFeedback()
  const [reportModalOpen, setReportModalOpen] = useState(false)
  const msg = check.message_key && i18n.exists(check.message_key) ? formatDetails(check.message_key, check.details_params, t) : check.message
  const citation = getCitation(check.message_key) || check.reference || null
  const details = check.details_key && i18n.exists(check.details_key) ? formatDetails(check.details_key, check.details_params, t) : check.details
  // Pass findings aren't reportable — nothing to diagnose when nothing
  // went wrong.
  const showReport = check.status !== 'pass'

  // Default flow: open the anonymous-send modal. Modal previews the
  // exact wire payload, fires sendReport on confirm. Mailto remains
  // accessible as a tertiary fallback inside the modal.
  const handleReport = () => {
    setReportModalOpen(true)
  }

  const handleAnonymousConfirm = () =>
    sendReport({
      checkKey: check.message_key || 'generic',
      jurisdiction: jurisdiction || 'unknown',
      locale: i18n.language,
      diagnostics: check.diagnostics || {},
    })

  const handleMailtoFallback = () => {
    sendFeedback(
      composeFeedback(
        {
          check_key: check.message_key || 'generic',
          message: msg,
          details,
          status: check.status,
          jurisdiction: jurisdiction || 'unknown',
          diagnostics: check.diagnostics || null,
        },
        t,
        { locale: i18n.language },
      ),
      { verb: 'report' },
    )
  }

  // Layout: on mobile (sm breakpoint and below), stack section + citation
  // ABOVE the message so the message can use full row width. On larger
  // screens, keep them inline-left for compactness.
  return (
    <div className="flex flex-col sm:flex-row items-start gap-1 sm:gap-2 py-1.5 px-3 group">
      <div className="flex items-center gap-2 shrink-0">
        <span className="text-[11px] text-muted-foreground">
          {check.section}
        </span>
        {citation && (
          <span className="citation-badge rounded px-1.5 py-0.5 text-[11px] font-mono leading-none">
            {citation}
          </span>
        )}
      </div>
      <div className="min-w-0 flex-1 w-full">
        <span className="text-sm">{msg}</span>
        {!compact && check.details_params?.flagged_phrases?.items?.length > 0 && (
          <FlaggedTermList
            items={check.details_params.flagged_phrases.items}
            status={check.status}
            className="mt-0.5"
          />
        )}
        {!compact && Array.isArray(check.details_params?.findings)
            && check.details_params.findings.length > 3
            && (check.message_key?.includes("numeralConsistency")
                || check.message_key?.includes("symbolTableCoverage")) && (
          <NumeralFindingList
            findings={check.details_params.findings}
            status={check.status}
          />
        )}
        {!compact && details && (
          <p className="text-xs text-muted-foreground mt-0.5">
            {details}
          </p>
        )}
      </div>
      {showReport && (
        <>
          <Button
            variant="ghost"
            size="xs"
            onClick={handleReport}
            title={t('feedback.reportProblem')}
            aria-label={t('feedback.reportProblem')}
            className="shrink-0 opacity-0 group-hover:opacity-100 focus-visible:opacity-100 transition-opacity"
          >
            <Flag />
            <span className="hidden sm:inline">{t('feedback.report')}</span>
          </Button>
          <ReportModal
            open={reportModalOpen}
            onOpenChange={setReportModalOpen}
            checkKey={check.message_key || 'generic'}
            jurisdiction={jurisdiction || 'unknown'}
            locale={i18n.language}
            diagnostics={check.diagnostics || {}}
            onConfirm={handleAnonymousConfirm}
            onMailtoFallback={handleMailtoFallback}
          />
        </>
      )}
    </div>
  )
}

function TriageGroup({ status, title, emptyMessage, Icon, items, defaultOpen, t, i18n, jurisdiction }) {
  const [open, setOpen] = useState(defaultOpen)
  const count = items.length
  const compact = status === 'pass'

  return (
    <FrostCard tier="resting" accent={status} className="overflow-visible">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-3 px-4 py-3 pl-5 text-left transition-colors duration-[var(--motion-duration-fast)] hover:bg-foreground/[0.02]"
        style={{ backgroundColor: `var(--${status}-bg)`, color: `var(--${status}-tag-text)` }}
        aria-expanded={open}
      >
        <Icon className="h-5 w-5 shrink-0" style={{ color: `var(--${status}-text)` }} />
        <span className="font-semibold flex-1">{title}</span>
        <span className="text-xs font-medium tabular-nums">
          {count} {count === 1 ? t('triage.item') : t('triage.items')}
        </span>
        <ChevronDown
          className={`h-4 w-4 transition-transform duration-[var(--motion-duration-base)] ${open ? 'rotate-180' : ''}`}
          style={{ color: `var(--${status}-text)` }}
        />
      </button>
      {open && (
        <div className="border-t border-border/40 p-1 animate-in fade-in-0 slide-in-from-top-1 duration-[var(--motion-duration-base)]">
          {count === 0 && emptyMessage ? (
            <p className="px-3 py-2 text-sm text-muted-foreground">{emptyMessage}</p>
          ) : (
            items.map((check, i) => (
              <TriageItem key={i} check={check} t={t} i18n={i18n} compact={compact} jurisdiction={jurisdiction} />
            ))
          )}
        </div>
      )}
    </FrostCard>
  )
}

export default function TriagePanel({ data }) {
  const { t, i18n } = useTranslation()

  const jConfig = getJurisdictionConfig(data.jurisdiction)
  const allChecks = [
    ...(data.specification_checks || []).map((c) => ({ ...c, section: t(jConfig.specSectionKey) })),
    ...(data.drawings_checks || []).map((c) => ({ ...c, section: t(jConfig.drawingsShortKey) })),
    ...(data.claims_checks || []).map((c) => ({ ...c, section: t(jConfig.claimsSectionKey) })),
    ...(data.abstract_checks || []).map((c) => ({ ...c, section: t(jConfig.abstractSectionKey) })),
  ]

  const byStatus = {
    amend: allChecks.filter((c) => c.status === 'amend'),
    verify: allChecks.filter((c) => c.status === 'verify'),
    pass: allChecks.filter((c) => c.status === 'pass'),
  }

  return (
    <div className="space-y-2">
      <h3 className="text-base font-bold text-foreground uppercase tracking-wide mb-3">
        {t('triage.title')}
      </h3>
      {GROUP_CONFIG.map(({ status, titleKey, emptyKey, Icon }) => (
        <TriageGroup
          key={status}
          status={status}
          title={t(titleKey)}
          emptyMessage={emptyKey ? t(emptyKey) : null}
          Icon={Icon}
          items={byStatus[status]}
          defaultOpen={
            // FIX + REVIEW open by default — both feed the rubric grade,
            // so they're load-bearing for the user's decision-making.
            // PASS stays collapsed (informational only).
            status === 'amend' || status === 'verify'
          }
          t={t}
          i18n={i18n}
          jurisdiction={data.jurisdiction}
        />
      ))}
    </div>
  )
}
