// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025-2026 Christopher Chen
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { MessageSquare } from 'lucide-react'
import { formatDetails } from "../lib/detailsFormatter"
import { Button } from "./ui/button"
import { composeFeedback, sendReport } from "../lib/feedback"
import { useFeedback } from "../hooks/useFeedback"
import FlaggedTermList from "./FlaggedTermList"
import NumeralFindingList from "./NumeralFindingList"
import ReportModal from "./ReportModal"
import InfoTooltip from "./ui/info-tooltip"
import { getCitation, getCitationTooltipKey, getExplainKey } from "../lib/citations"

export default function CheckItem({ status, message, message_key, details, details_key, details_params, reference, jurisdiction, diagnostics }) {
  const { t, i18n } = useTranslation()
  const { sendFeedback } = useFeedback()
  const [reportModalOpen, setReportModalOpen] = useState(false)
  const displayMessage = message_key && i18n.exists(message_key) ? formatDetails(message_key, details_params, t) : message
  const displayDetails = details_key && i18n.exists(details_key) ? formatDetails(details_key, details_params, t) : details
  const citation = getCitation(message_key) || reference || null
  const explainKey = getExplainKey(message_key)
  const explainText = explainKey && i18n.exists(explainKey) ? t(explainKey) : null
  const statusTipKey = `tooltip.status.${status}`
  const statusTip = i18n.exists(statusTipKey) ? t(statusTipKey) : null
  const citationTipKey = getCitationTooltipKey(citation)
  const citationTip = citationTipKey && i18n.exists(citationTipKey) ? t(citationTipKey) : null

  const handleReport = () => {
    setReportModalOpen(true)
  }

  // ReportModal calls onConfirm(comment, disposition, findingDispositions) and
  // gates its own Send button on a disposition being chosen. Dropping the 2nd
  // and 3rd arguments here made every CheckItem-routed report (D1
  // numeralConsistency, paragraphEnding, symbolTableCoverage, and every other
  // generic check) arrive with no disposition at all, so the reporter was
  // required to pick a verdict that was then discarded on the wire and the
  // issue landed with no TP/FP label - the ADR-159 label intake silently lost
  // its input. SpecSupportCard has always threaded these through.
  const handleAnonymousConfirm = (userComment, disposition, findingDispositions) =>
    sendReport({
      checkKey: message_key || 'generic',
      jurisdiction: jurisdiction || 'unknown',
      locale: i18n.language,
      diagnostics: diagnostics || {},
      userComment,
      disposition,
      findingDispositions,
    })

  const handleMailtoFallback = () => {
    sendFeedback(
      composeFeedback(
        {
          check_key: message_key || 'generic',
          message: displayMessage,
          details: displayDetails,
          status,
          jurisdiction: jurisdiction || 'unknown',
          diagnostics: diagnostics || null,
        },
        t,
        { locale: i18n.language },
      ),
      { verb: 'report' },
    )
  }

  // Layout: on mobile (<sm = 640px), stack the status pill + citation
  // ABOVE the message so the message body can use full row width
  // (otherwise the message wraps in a narrow right-side column). On
  // larger screens, keep the inline-row layout for compactness.
  // The numeral table is the PRIMARY presentation of these findings, not an
  // overflow affordance, so it renders at any count. It used to be gated above
  // 3, which meant a draft with one or two conflicts got the run-on sentence
  // and no table at all.
  const hasNumeralTable =
    Array.isArray(details_params?.findings)
    && details_params.findings.length > 0
    && (message_key?.includes('numeralConsistency')
        || message_key?.includes('symbolTableCoverage'))

  return (
    <div
      className="py-2 px-3 border-l-[3px]"
      style={{ borderLeftColor: `var(--${status}-border)` }}
    >
      <div className="group flex flex-col sm:flex-row sm:items-center gap-1.5 sm:gap-2">
        {/* Fixed-width on sm+ for the same reason as TriagePanel: a long
            citation otherwise shoves its message out of line with every other
            row in the section. See that component for the full rationale. */}
        <div className="flex items-start gap-2 shrink-0 sm:w-56">
          <InfoTooltip label={statusTip}>
            <span
              className="inline-block rounded px-1.5 py-0.5 text-[10px] font-bold uppercase leading-none"
              style={{
                backgroundColor: `var(--${status}-bg)`,
                color: `var(--${status}-tag-text)`,
              }}
            >
              {t(`status.${status}`)}
            </span>
          </InfoTooltip>
          {citation && (
            <InfoTooltip label={citationTip}>
              <span
                className={
                  "citation-badge inline-block rounded px-1.5 py-0.5 text-[11px] font-mono leading-tight break-words text-left"
                  + (citationTip ? " underline decoration-dotted underline-offset-[3px] decoration-muted-foreground/60" : "")
                }
              >
                {citation}
              </span>
            </InfoTooltip>
          )}
        </div>
        <span className="text-sm flex-1 min-w-0">{displayMessage}</span>
        <Button
          variant="ghost"
          size="xs"
          onClick={handleReport}
          title={t('feedback.reportProblem')}
          aria-label={t('feedback.reportProblem')}
          // Quiet by default on hover-capable devices so a screenful of PASS
          // rows is not a column of repeated buttons; revealed on row hover or
          // keyboard focus. Touch devices keep it visible (they have no hover),
          // and opacity leaves it in the accessibility tree either way, so a
          // screen reader still reaches it.
          className={"shrink-0 self-start sm:self-auto " + "[@media(hover:hover)]:opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 focus-visible:opacity-100 transition-opacity"}
        >
          <MessageSquare />
          <span className="hidden sm:inline">{t('feedback.report')}</span>
        </Button>
        <ReportModal
          open={reportModalOpen}
          onOpenChange={setReportModalOpen}
          checkKey={message_key || 'generic'}
          jurisdiction={jurisdiction || 'unknown'}
          locale={i18n.language}
          diagnostics={diagnostics || {}}
          onConfirm={handleAnonymousConfirm}
          onMailtoFallback={handleMailtoFallback}
        />
      </div>
      {details_params?.flagged_phrases?.items?.length > 0 && (
        <FlaggedTermList
          items={details_params.flagged_phrases.items}
          status={status}
          className="mt-1 sm:ml-[52px]"
        />
      )}
      {hasNumeralTable && (
        <NumeralFindingList
          findings={details_params.findings}
          status={status}
          className="sm:ml-[52px]"
        />
      )}
      {/* The numeral table already states every numeral, name and count, so
          the detail sentence beneath it only repeated the message. */}
      {displayDetails && !hasNumeralTable && (
        <p className="text-xs text-muted-foreground mt-1 sm:ml-[52px]">{displayDetails}</p>
      )}
      {explainText && (
        <p className="text-xs text-muted-foreground/80 mt-1 sm:ml-[52px] italic">
          {explainText}
        </p>
      )}
    </div>
  )
}
