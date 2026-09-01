// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025-2026 Christopher Chen
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { MessageSquare } from 'lucide-react'
import { formatDetails } from "../lib/detailsFormatter"
import { Button } from "./ui/button"
import { composeFeedback, sendReport } from "../lib/feedback"
import { useFeedback } from "./FeedbackPicker"
import FlaggedTermList from "./FlaggedTermList"
import NumeralFindingList from "./NumeralFindingList"
import ReportModal from "./ReportModal"
import InfoTooltip from "./ui/info-tooltip"

const CITATION_MAP = {
  'check.spec.restrictiveWording': '§ 112(b)',
  // Re-pinned in #464 after verifying the primary source: MPEP § 608.01
  // quotes 37 CFR 1.52(b)(6) for paragraph numbering, and § 608.01(p) is a
  // different subject entirely. This badge kept showing the old citation
  // after that PR corrected models.py, the six locale files and CHECKS.md -
  // a fourth surface nobody thought to grep. Cross-check every citation
  // surface when re-pinning one.
  'check.spec.paragraphSequential': '37 CFR 1.52(b)(6)',
  // paragraphEnding carries NO citation: verified against the primary
  // source (report #600) that MPEP § 608.01 states no paragraph-punctuation
  // requirement at all. It had cited § 608.01(p), which is Completeness of
  // Specification. The reporter proposed § 608.01(m), which is Form of
  // Claims and governs claims, not specification paragraphs. Both are wrong,
  // so the badge is dropped rather than re-pinned - this is a drafting
  // convention, and the AboutPage already labels the EPC twin as hygiene.
  'check.spec.sequenceListing': '§ 2422',
  'check.spec.crossReference': '§ 608.01',
  'check.spec.priorArt': '§ 608.01(c)',
  'check.spec.drawings': '§ 608.02',
  'check.claims.restrictiveAbsolutes': '§ 2173.01',
  'check.claims.indefiniteWording': '§ 2173.05(b)',
  'check.claims.sequential': '§ 608.01(m)',
  'check.claims.multipleDependent': '§ 608.01(n)',
  'check.claims.selfDependent': '§ 112(d)',
  'check.claims.missingPeriod': '§ 608.01(m)',
  'check.claims.extraPeriod': '§ 608.01(m)',
  'check.claims.whereinComma': '§ 608.01(m)',
  'check.claims.meansFunction': '§ 112(f)',
  'check.claims.antecedentBasis': '§ 112(b)',
  'check.claims.preamble': '§ 112(d)',
  'checks.preamble_noun_mismatch': '§ 112(d)',
  'checks.preamble_cross_category_mismatch': '§ 112(d)',
  'checks.preamble_indefinite_article': '§ 608.01(m)',
  'checks.preamble_cross_category_pass': '§ 112(d)',
  'check.claims.missingTransition': '§ 112(b)',
  'check.claims.transitionsPresent': '§ 112(b)',
  'claims.missingPeriod': '§ 608.01(m)',
  'claims.extraPeriod': '§ 608.01(m)',
  'claims.whereinComma': '§ 608.01(m)',
  'claims.punctuationPass': '§ 608.01(m)',
  'claims.jepsonPriorArt': '§ 2129',
  'claims.crmNonTransitory': '§ 101',
  'claims.markushOpenTransition': '§ 2117',
  'claims.omnibusClaim': '§ 112(b)',
  'checks.spec_support_unsupported_terms': '§ 112(a)',
  'check.abstract.legalPhraseology': '§ 608.01(b)',
  'check.abstract.meritLanguage': '§ 608.01(b)',
  'check.abstract.structure': '§ 608.01(b)',
  'check.abstract.impliedPhrases': '§ 608.01(b)',
  'check.abstract.wordCount': '§ 608.01(b)',
  'check.drawings.singleFigure': '§ 608.02',
  'check.drawings.priorArt': '§ 608.02',
  'check.drawings.sequential': '§ 608.02',
  'check.drawings.count': '§ 608.02',
}

// Citation badges are bare section numbers - `§ 112(b)`, `§ 2129`, `§ 101` -
// which say nothing on their own to a reader who does not already know the
// number. This maps the badge text to a `tooltip.citation.*` key carrying the
// instrument and the section's subject.
//
// SCOPED TO THE US SHORTHAND ON PURPOSE. The CN / TW / EPC references this
// component also renders already name their instrument (`專利法施行細則 §18`,
// `Rule 43(4) EPC`, `EPO Guidelines F-II § 2.3`), so a tooltip there would
// restate what is already on screen. A citation with no entry renders exactly
// as before, with no trigger and no affordance.
//
// Every title below was verified against the USPTO primary source rather than
// recalled - this file has already shipped a wrong citation twice (#464, #600).
const CITATION_TOOLTIP_KEY = {
  '35 U.S.C. \u00a7 112(a)': '112a',
  '\u00a7 112(a)': '112a',
  '\u00a7 112(b)': '112b',
  '\u00a7 112(d)': '112d',
  '\u00a7 112(f)': '112f',
  '\u00a7 101': '101',
  '37 CFR 1.52(b)(6)': 'cfr1526',
  '\u00a7 608.01': '60801',
  '\u00a7 608.01(b)': '60801b',
  '\u00a7 608.01(c)': '60801c',
  '\u00a7 608.01(m)': '60801m',
  '\u00a7 608.01(n)': '60801n',
  '\u00a7 608.02': '60802',
  '\u00a7 2117': '2117',
  '\u00a7 2129': '2129',
  '\u00a7 2173.01': '217301',
  '\u00a7 2173.05(b)': '217305b',
  '\u00a7 2422': '2422',
}

function getCitationTooltipKey(citation) {
  const slug = citation && CITATION_TOOLTIP_KEY[citation.trim()]
  return slug ? `tooltip.citation.${slug}` : null
}

export { getCitationTooltipKey }

// Optional plain-language explainer for a check, keyed `explain.<base>` where
// <base> is the message key with its .pass/.verify/.amend suffix stripped.
// Exists because several checks are correct but opaque without domain context:
// "No special claim format issues detected" does not tell a drafter WHICH
// formats were examined. Purely additive - a check with no explain key renders
// exactly as before.
function getExplainKey(messageKey) {
  if (!messageKey) return null
  return `explain.${messageKey.replace(/\.(pass|verify|amend|missing)$/, '')}`
}

export { getExplainKey }

function getCitation(messageKey) {
  if (!messageKey) return null
  // Try exact match first, then strip .pass/.verify/.amend suffix
  if (CITATION_MAP[messageKey]) return CITATION_MAP[messageKey]
  const base = messageKey.replace(/\.(pass|verify|amend)$/, '')
  return CITATION_MAP[base] || null
}

export { getCitation }

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
  const isExpandableD1D3 =
    Array.isArray(details_params?.findings)
    && details_params.findings.length > 3
    && (message_key?.includes('numeralConsistency')
        || message_key?.includes('symbolTableCoverage'))

  return (
    <div
      className="py-2 px-3 border-l-[3px]"
      style={{ borderLeftColor: `var(--${status}-border)` }}
    >
      <div className="flex flex-col sm:flex-row sm:items-center gap-1.5 sm:gap-2">
        <div className="flex items-center gap-2 shrink-0">
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
                  "citation-badge inline-block rounded px-1.5 py-0.5 text-[11px] font-mono leading-none"
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
          className="shrink-0 self-start sm:self-auto"
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
      {isExpandableD1D3 && (
        <NumeralFindingList
          findings={details_params.findings}
          status={status}
          className="sm:ml-[52px]"
        />
      )}
      {displayDetails && (
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
