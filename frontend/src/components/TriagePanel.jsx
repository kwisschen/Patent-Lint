// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025-2026 Christopher Chen
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { AlertCircle, Search, CheckCircle, ChevronDown, MessageSquare, CornerDownRight, ArrowUp, Undo2 } from 'lucide-react'
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
  { status: 'amend', titleKey: 'triage.amend', Icon: AlertCircle },
  { status: 'verify', titleKey: 'triage.verify', emptyKey: 'triage.verifyEmpty', Icon: Search },
  { status: 'pass', titleKey: 'triage.pass', emptyKey: null, Icon: CheckCircle },
]

function TriageItem({ check, t, i18n, compact, jurisdiction, canPromote, isPromoted, onPromote, onDemote }) {
  const { sendFeedback } = useFeedback()
  const [reportModalOpen, setReportModalOpen] = useState(false)
  const msg = check.message_key && i18n.exists(check.message_key) ? formatDetails(check.message_key, check.details_params, t) : check.message
  const citation = getCitation(check.message_key) || check.reference || null
  const details = check.details_key && i18n.exists(check.details_key) ? formatDetails(check.details_key, check.details_params, t) : check.details
  // Pass findings aren't reportable - nothing to diagnose when nothing
  // went wrong.
  const showReport = check.status !== 'pass'

  // §112 jump-to: the antecedent-basis and spec-support review lines are long,
  // dense sentences. Offer a polished one-click pill that jumps down to the
  // per-claim card instead of forcing the user to parse the description. Only
  // on the verify/amend rows (the card - not a pass placeholder - is the target).
  const mk = check.message_key || ''
  const isAntecedent = /antecedentBasis/.test(mk)
  const isSpecSupport = mk === 'checks.spec_support_unsupported_terms' || /specSupport/.test(mk)
  // Only offer the jump when the target section/card actually renders for this
  // jurisdiction (the §112 container is gated on showClaimTree; the spec-support
  // card additionally on supportsSpecSupport - currently true for US/EPC/TW/CN,
  // but the guard keeps the pill honest if a future jurisdiction omits it).
  // Avoids a polished button that jumps to nothing.
  const jConfig = getJurisdictionConfig(jurisdiction)
  const jumpTarget =
    check.status === 'pass' || !jConfig.showClaimTree ? null
      : isAntecedent ? 'section112-antecedent'
      : (isSpecSupport && jConfig.supportsSpecSupport) ? 'section112-specsupport'
      : null
  const jumpLabelKey = isAntecedent ? 'triage.jumpAntecedent' : 'triage.jumpSpecSupport'
  const handleJump = () => {
    document
      .getElementById(jumpTarget)
      ?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  // Default flow: open the anonymous-send modal. Modal previews the
  // exact wire payload, fires sendReport on confirm. Mailto remains
  // accessible as a tertiary fallback inside the modal.
  const handleReport = () => {
    setReportModalOpen(true)
  }

  // Same contract as CheckItem: ReportModal passes the disposition (and the
  // per-finding verdicts when a report carries >= 2 findings) as the 2nd and
  // 3rd arguments. Dropping them discarded the reporter's verdict on the wire.
  const handleAnonymousConfirm = (userComment, disposition, findingDispositions) =>
    sendReport({
      checkKey: check.message_key || 'generic',
      jurisdiction: jurisdiction || 'unknown',
      locale: i18n.language,
      diagnostics: check.diagnostics || {},
      userComment,
      disposition,
      findingDispositions,
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
        {isPromoted && (
          <span
            className="ml-2 inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-semibold align-middle"
            style={{ backgroundColor: 'var(--amend-bg)', color: 'var(--amend-text)' }}
            title={t('triage.promotedNote')}
          >
            {t('triage.promotedBadge')}
          </span>
        )}
        {jumpTarget && (
          <div className="mt-1.5">
            <button
              type="button"
              onClick={handleJump}
              title={t('triage.jumpTo', { section: t(jumpLabelKey) })}
              aria-label={t('triage.jumpTo', { section: t(jumpLabelKey) })}
              className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold transition-colors hover:bg-[var(--attention-bg)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--attention-border)]"
              style={{ color: 'var(--attention-text)', borderColor: 'var(--attention-border)' }}
            >
              <CornerDownRight className="h-3.5 w-3.5" />
              {t(jumpLabelKey)}
            </button>
          </div>
        )}
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
        {/* Render the raw `details` line ONLY when it adds information the
            user can't already see. Suppress it when:
              - the jump pill already provides the affordance, or
              - it merely echoes claim numbers already in the message (the
                "3, 8" / "7, 9" anti-pattern - many checks set
                details=", ".join(claim_ids), which duplicates "Claim(s) 3, 8…"), or
              - flagged_phrases pills already surface the offending content. */}
        {!compact && details && !jumpTarget
          && !(typeof msg === 'string' && msg.includes(String(details).trim()))
          && !(check.details_params?.flagged_phrases?.items?.length > 0) && (
          <p className="text-xs text-muted-foreground mt-0.5">
            {details}
          </p>
        )}
      </div>
      {/* Right-side action cluster - anchored to the row's right edge (and the
          bottom on mobile), so the Treat-as-fix / Move-to-review controls sit
          in a CONSISTENT position regardless of the left section/citation width
          or the message length. Promote/demote are always visible; the report
          button keeps its hover-reveal below them. */}
      {(canPromote || isPromoted || showReport) && (
        <div className="flex flex-row sm:flex-col items-start sm:items-end gap-1.5 shrink-0">
          {/* Promote a Review item up to Needs Fixing - the user's own triage
              call (a flag we surfaced for review may, on their reading, be a
              real defect). Grade-neutral: PatentLint's deterministic verdict is
              unchanged; this just reorganizes the user's worklist. */}
          {canPromote && (
            <button
              type="button"
              onClick={() => onPromote(check._id)}
              title={t('triage.promoteTitle')}
              aria-label={t('triage.promoteTitle')}
              className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold transition-colors hover:bg-[var(--amend-bg)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--amend-border)]"
              style={{ color: 'var(--amend-text)', borderColor: 'var(--amend-border)' }}
            >
              <ArrowUp className="h-3.5 w-3.5" />
              {t('triage.promote')}
            </button>
          )}
          {isPromoted && (
            <button
              type="button"
              onClick={() => onDemote(check._id)}
              title={t('triage.demoteTitle')}
              aria-label={t('triage.demoteTitle')}
              className="inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-foreground/[0.04] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Undo2 className="h-3.5 w-3.5" />
              {t('triage.demote')}
            </button>
          )}
          {showReport && (
            <>
              <Button
                variant="ghost"
                size="xs"
                onClick={handleReport}
                title={t('feedback.reportProblem')}
                aria-label={t('feedback.reportProblem')}
                className="opacity-0 group-hover:opacity-100 focus-visible:opacity-100 transition-opacity"
              >
                <MessageSquare />
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
      )}
    </div>
  )
}

function TriageGroup({
  status, title, emptyMessage, Icon, items, defaultOpen, t, i18n, jurisdiction,
  canPromote, promotedIds, onPromote, onDemote,
}) {
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
            items.map((check) => (
              <TriageItem
                key={check._id}
                check={check}
                t={t}
                i18n={i18n}
                compact={compact}
                jurisdiction={jurisdiction}
                canPromote={canPromote && check.status === 'verify'}
                isPromoted={promotedIds?.has(check._id)}
                onPromote={onPromote}
                onDemote={onDemote}
              />
            ))
          )}
        </div>
      )}
    </FrostCard>
  )
}

export default function TriagePanel({ data }) {
  const { t, i18n } = useTranslation()
  // User-promoted Review items (by stable _id). Session-scoped: a re-analysis
  // remounts the panel and clears these. Grade-neutral - promotion reorganizes
  // the user's worklist; it does NOT alter PatentLint's deterministic verdict.
  const [promoted, setPromoted] = useState(() => new Set())

  const promote = (id) =>
    setPromoted((prev) => new Set(prev).add(id))
  const demote = (id) =>
    setPromoted((prev) => {
      const next = new Set(prev)
      next.delete(id)
      return next
    })

  const jConfig = getJurisdictionConfig(data.jurisdiction)
  // Assign a stable id to every check so promotion survives re-renders and the
  // promoted Set has a reliable key (index into the flattened, ordered list).
  const allChecks = [
    ...(data.specification_checks || []).map((c) => ({ ...c, section: t(jConfig.specSectionKey) })),
    ...(data.drawings_checks || []).map((c) => ({ ...c, section: t(jConfig.drawingsShortKey) })),
    ...(data.claims_checks || []).map((c) => ({ ...c, section: t(jConfig.claimsSectionKey) })),
    ...(data.abstract_checks || []).map((c) => ({ ...c, section: t(jConfig.abstractSectionKey) })),
  ].map((c, i) => ({ ...c, _id: i }))

  // Effective grouping: a promoted Review item moves into Needs Fixing; a
  // genuine 'amend' check is always there. Order: system fixes first, then
  // the user's promoted items.
  const systemAmend = allChecks.filter((c) => c.status === 'amend')
  const promotedAmend = allChecks.filter((c) => c.status === 'verify' && promoted.has(c._id))
  const byStatus = {
    amend: [...systemAmend, ...promotedAmend],
    verify: allChecks.filter((c) => c.status === 'verify' && !promoted.has(c._id)),
    pass: allChecks.filter((c) => c.status === 'pass'),
  }

  const hasReview = byStatus.verify.length > 0
  // Context-aware empty copy for Needs Fixing: never imply the draft is clean
  // when Review items still exist (the old "No fixes needed." over-claimed).
  const amendEmpty = hasReview ? t('triage.amendEmptyReview') : t('triage.amendEmptyClean')

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
          emptyMessage={status === 'amend' ? amendEmpty : (emptyKey ? t(emptyKey) : null)}
          Icon={Icon}
          items={byStatus[status]}
          defaultOpen={
            // FIX + REVIEW open by default - both feed the rubric grade,
            // so they're load-bearing for the user's decision-making.
            // PASS stays collapsed (informational only).
            status === 'amend' || status === 'verify'
          }
          t={t}
          i18n={i18n}
          jurisdiction={data.jurisdiction}
          canPromote={status === 'verify'}
          promotedIds={promoted}
          onPromote={promote}
          onDemote={demote}
        />
      ))}
      {(hasReview || promoted.size > 0) && (
        <p className="px-1 pt-1 text-xs text-muted-foreground">
          {t('triage.promoteHint')}
        </p>
      )}
    </div>
  )
}
