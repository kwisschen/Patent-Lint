// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025–2026 Christopher Chen
import { useTranslation } from 'react-i18next'
import { AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { FrostCard } from '@/components/ui/frost-card'

export default function TrackedChangesBanner({ onAnalyzeAgain, onShowResults }) {
  const { t } = useTranslation()

  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <FrostCard
        tier="elevated"
        accent="attention"
        className="max-w-lg w-full mx-auto p-8 pl-9 text-center animate-in fade-in zoom-in-95 duration-[var(--motion-duration-slow)]"
      >
        <AlertTriangle className="mx-auto h-12 w-12 mb-4" style={{ color: 'var(--attention-border)' }} />
        <p className="text-sm leading-relaxed mb-6 text-foreground">
          {t('results.trackedChangesWarning')}
        </p>
        <div className="flex items-center justify-center gap-3">
          <Button onClick={onAnalyzeAgain}>
            {t('results.analyzeAgain')}
          </Button>
          <Button variant="outline" onClick={onShowResults}>
            {t('results.showResultsAnyway')}
          </Button>
        </div>
      </FrostCard>
    </div>
  )
}
