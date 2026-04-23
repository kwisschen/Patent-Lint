// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
import { useTranslation } from 'react-i18next'
import { AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'

// Banner copy is keyed off BOTH the selected jurisdiction and the actual
// rejection reason (ADR-150). Pre-ADR-150 the banner always said "your
// document doesn't have standard sections/claims/numbering" regardless
// of whether detection actually checked any of that — so a document
// that happened to trip the cross-script short-circuit would be told
// its sections were missing (a lie). Keying off the reason lets each
// message honestly describe what the detector saw.
//
// Reason codes mirror patentlint.parser.detection.DetectionReason.
// Fallback chain: try (jurisdiction + reason) → (jurisdiction + generic)
// → (generic + reason) → (global generic). Guarantees we always render
// something sensible even if a new reason ships without full translations.
const REASONS = {
  content_missing: 'ContentMissing',
  cross_script_japanese: 'CrossScriptJapanese',
  cross_script_korean: 'CrossScriptKorean',
  weak_signal: 'WeakSignal',
}

const JURISDICTION_SUFFIXES = {
  US: 'Us',
  CN: 'Cn',
  TW: 'Tw',
}

function buildCandidateKeys(field, jurisdiction, reason) {
  const reasonSuffix = REASONS[reason] || REASONS.content_missing
  const jurSuffix = JURISDICTION_SUFFIXES[jurisdiction] || ''
  // field examples: "nonPatentWarning" / "nonPatentWarningDetails"
  return [
    `results.${field}${jurSuffix}${reasonSuffix}`,
    `results.${field}${reasonSuffix}`,
    `results.${field}${jurSuffix}`,
    `results.${field}`,
  ]
}

export default function NonPatentBanner({ onShowResults, jurisdiction, reason = 'content_missing' }) {
  const { t, i18n } = useTranslation()

  const resolveKey = (field) => {
    const candidates = buildCandidateKeys(field, jurisdiction, reason)
    for (const key of candidates) {
      if (i18n.exists(key)) return key
    }
    return candidates[candidates.length - 1]
  }

  const warningKey = resolveKey('nonPatentWarning')
  const detailsKey = resolveKey('nonPatentWarningDetails')

  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div
        className="max-w-lg w-full mx-auto rounded-xl border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/30 p-8 text-center animate-in fade-in zoom-in-95 duration-400"
      >
        <AlertTriangle className="mx-auto h-12 w-12 text-amber-500 dark:text-amber-400 mb-4" />
        <h2 className="text-xl font-bold text-amber-900 dark:text-amber-100 mb-3">
          {t(warningKey)}
        </h2>
        <p className="text-sm text-amber-800 dark:text-amber-200/80 leading-relaxed mb-6">
          {t(detailsKey)}
        </p>
        <Button
          variant="outline"
          className="border-amber-300 dark:border-amber-700 text-amber-800 dark:text-amber-200 hover:bg-amber-100 dark:hover:bg-amber-900/40"
          onClick={onShowResults}
        >
          {t('results.showResultsAnyway')}
        </Button>
      </div>
    </div>
  )
}
