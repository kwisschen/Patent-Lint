// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
import { useTranslation } from 'react-i18next'
import { AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { FrostCard } from '@/components/ui/frost-card'

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
      <FrostCard
        tier="elevated"
        accent="attention"
        className="max-w-lg w-full mx-auto p-8 pl-9 text-center animate-in fade-in zoom-in-95 duration-[var(--motion-duration-slow)]"
      >
        <AlertTriangle className="mx-auto h-12 w-12 mb-4" style={{ color: 'var(--attention-border)' }} />
        <h2 className="text-xl font-bold mb-3" style={{ color: 'var(--attention-text)' }}>
          {t(warningKey)}
        </h2>
        <p className="text-sm leading-relaxed mb-6 text-foreground">
          {t(detailsKey)}
        </p>
        <Button variant="outline" onClick={onShowResults}>
          {t('results.showResultsAnyway')}
        </Button>
      </FrostCard>
    </div>
  )
}
