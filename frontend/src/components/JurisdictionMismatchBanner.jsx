// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
import { useTranslation } from 'react-i18next'
import { AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'

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
      <div
        className="max-w-lg w-full mx-auto rounded-xl border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/30 p-8 text-center animate-in fade-in zoom-in-95 duration-400"
      >
        <AlertTriangle className="mx-auto h-12 w-12 text-amber-500 dark:text-amber-400 mb-4" />
        <h2 className="text-xl font-bold text-amber-900 dark:text-amber-100 mb-3">
          {t('results.jurisdictionMismatchTitle', { suggested: suggestedLabel })}
        </h2>
        <p className="text-sm text-amber-800 dark:text-amber-200/80 leading-relaxed mb-6">
          {t('results.jurisdictionMismatchDetails', {
            selected: selectedLabel,
            suggested: suggestedLabel,
          })}
        </p>
        <div className="flex items-center justify-center gap-3 flex-wrap">
          <Button
            className="bg-amber-600 hover:bg-amber-700 text-white"
            onClick={onSwitch}
          >
            {t('results.jurisdictionMismatchSwitch', { suggested: suggestedLabel })}
          </Button>
          <Button
            variant="outline"
            className="border-amber-300 dark:border-amber-700 text-amber-800 dark:text-amber-200 hover:bg-amber-100 dark:hover:bg-amber-900/40"
            onClick={onDismiss}
          >
            {t('results.jurisdictionMismatchDismiss')}
          </Button>
        </div>
      </div>
    </div>
  )
}
