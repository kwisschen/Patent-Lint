// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2025 Christopher Chen
import { useTranslation } from 'react-i18next'
import { Flag } from 'lucide-react'
import { formatDetails } from "../lib/detailsFormatter"
import { Button } from "./ui/button"
import { composeFeedbackMailto, showFeedbackToast } from "../lib/feedbackMailto"

const CITATION_MAP = {
  'check.spec.restrictiveWording': '§ 112(b)',
  'check.spec.paragraphSequential': '§ 608.01(p)',
  'check.spec.paragraphEnding': '§ 608.01(p)',
  'check.spec.sequenceListing': '§ 2422',
  'check.spec.crossReference': '§ 608.01',
  'check.spec.priorArt': '§ 608.01(c)',
  'check.spec.drawings': '§ 608.02',
  'check.claims.restrictiveWording': '§ 112(b)',
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
  'check.abstract.restrictiveWording': '§ 608.01(b)',
  'check.abstract.structure': '§ 608.01(b)',
  'check.abstract.impliedPhrases': '§ 608.01(b)',
  'check.abstract.wordCount': '§ 608.01(b)',
  'check.drawings.singleFigure': '§ 608.02',
  'check.drawings.priorArt': '§ 608.02',
  'check.drawings.sequential': '§ 608.02',
  'check.drawings.count': '§ 608.02',
}

function getCitation(messageKey) {
  if (!messageKey) return null
  // Try exact match first, then strip .pass/.verify/.amend suffix
  if (CITATION_MAP[messageKey]) return CITATION_MAP[messageKey]
  const base = messageKey.replace(/\.(pass|verify|amend)$/, '')
  return CITATION_MAP[base] || null
}

export { getCitation }

export default function CheckItem({ status, message, message_key, details, details_key, details_params, reference, jurisdiction }) {
  const { t, i18n } = useTranslation()
  const displayMessage = message_key && i18n.exists(message_key) ? formatDetails(message_key, details_params, t) : message
  const displayDetails = details_key && i18n.exists(details_key) ? formatDetails(details_key, details_params, t) : details
  const citation = getCitation(message_key) || reference || null

  const handleReport = () => {
    const href = composeFeedbackMailto(
      {
        check_key: message_key || 'generic',
        message: displayMessage,
        details: displayDetails,
        status,
        jurisdiction: jurisdiction || 'unknown',
      },
      t,
      { locale: i18n.language },
    )
    window.location.href = href
    showFeedbackToast(t)
  }

  return (
    <div
      className="py-2 px-3 border-l-[3px]"
      style={{ borderLeftColor: `var(--${status}-border)` }}
    >
      <div className="flex items-center gap-2">
        <span
          className="inline-block rounded px-1.5 py-0.5 text-[10px] font-bold uppercase leading-none"
          style={{
            backgroundColor: `var(--${status}-bg)`,
            color: `var(--${status}-tag-text)`,
          }}
        >
          {t(`status.${status}`)}
        </span>
        {citation && (
          <span className="citation-badge inline-block rounded px-1.5 py-0.5 text-[11px] font-mono leading-none">
            {citation}
          </span>
        )}
        <span className="text-sm flex-1">{displayMessage}</span>
        <Button
          variant="ghost"
          size="xs"
          onClick={handleReport}
          title={t('feedback.reportProblem')}
          aria-label={t('feedback.reportProblem')}
          className="shrink-0"
        >
          <Flag />
          {t('feedback.report')}
        </Button>
      </div>
      {displayDetails && (
        <p className="text-xs text-muted-foreground mt-1 ml-[52px]">{displayDetails}</p>
      )}
    </div>
  )
}
