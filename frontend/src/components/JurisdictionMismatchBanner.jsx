// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
import { useTranslation } from 'react-i18next'
import { AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { FrostCard } from '@/components/ui/frost-card'

// Issue #9 / ADR-082 revisited (2026-04-27). Renders when the Python
// detector at parser/jurisdiction_mismatch.py concludes the document
// looks like a different supported jurisdiction than the one the user
// selected. The user can re-run analysis against the suggested
// jurisdiction with a single click (no re-upload), or dismiss and view
// the (likely-degraded) results from the originally-selected pipeline.
export default function JurisdictionMismatchBanner({
  selectedJurisdiction,
  suggestedJurisdiction,
  onSwitch,
  onDismiss,
}) {
  const { t } = useTranslation()

  const selectedLabel = t(`jurisdiction.${selectedJurisdiction.toLowerCase()}`)
  const suggestedLabel = t(`jurisdiction.${suggestedJurisdiction.toLowerCase()}`)

  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <FrostCard
        tier="elevated"
        accent="attention"
        className="max-w-lg w-full mx-auto p-8 pl-9 text-center animate-in fade-in zoom-in-95 duration-[var(--motion-duration-slow)]"
      >
        <AlertTriangle className="mx-auto h-12 w-12 mb-4" style={{ color: 'var(--attention-border)' }} />
        <h2 className="text-xl font-bold mb-3" style={{ color: 'var(--attention-text)' }}>
          {t('results.jurisdictionMismatchTitle', { suggested: suggestedLabel })}
        </h2>
        <p className="text-sm leading-relaxed mb-6 text-foreground">
          {t('results.jurisdictionMismatchDetails', {
            selected: selectedLabel,
            suggested: suggestedLabel,
          })}
        </p>
        <div className="flex items-center justify-center gap-3 flex-wrap">
          <Button onClick={onSwitch}>
            {t('results.jurisdictionMismatchSwitch', { suggested: suggestedLabel })}
          </Button>
          <Button variant="outline" onClick={onDismiss}>
            {t('results.jurisdictionMismatchDismiss')}
          </Button>
        </div>
      </FrostCard>
    </div>
  )
}
