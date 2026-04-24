// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
import { useTranslation } from 'react-i18next'
import { Flag } from 'lucide-react'
import { formatDetails } from "../lib/detailsFormatter"
import { Button } from "./ui/button"
import { composeFeedback } from "../lib/feedback"
import { useFeedback } from "./FeedbackPicker"
import FlaggedTermList from "./FlaggedTermList"

const CITATION_MAP = {
  'check.spec.restrictiveWording': '§ 112(b)',
  'check.spec.paragraphSequential': '§ 608.01(p)',
  'check.spec.paragraphEnding': '§ 608.01(p)',
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
  const displayMessage = message_key && i18n.exists(message_key) ? formatDetails(message_key, details_params, t) : message
  const displayDetails = details_key && i18n.exists(details_key) ? formatDetails(details_key, details_params, t) : details
  const citation = getCitation(message_key) || reference || null

  const handleReport = () => {
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
          <span className="hidden sm:inline">{t('feedback.report')}</span>
        </Button>
      </div>
      {details_params?.flagged_phrases?.items?.length > 0 && (
        <FlaggedTermList
          items={details_params.flagged_phrases.items}
          status={status}
          className="mt-1 ml-10 sm:ml-[52px]"
        />
      )}
      {displayDetails && (
        <p className="text-xs text-muted-foreground mt-1 ml-10 sm:ml-[52px]">{displayDetails}</p>
      )}
    </div>
  )
}
