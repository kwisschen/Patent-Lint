// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
import { useTranslation } from 'react-i18next'
import { AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { FrostCard } from '@/components/ui/frost-card'

export default function ScannedDocBanner({ onReset }) {
  const { t } = useTranslation()

  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <FrostCard
        tier="elevated"
        accent="attention"
        className="max-w-lg w-full mx-auto p-8 pl-9 text-center animate-in fade-in zoom-in-95 duration-[var(--motion-duration-slow)]"
      >
        <AlertTriangle className="mx-auto h-12 w-12 mb-4" style={{ color: 'var(--attention-border)' }} />
        <h2 className="text-xl font-bold mb-3" style={{ color: 'var(--attention-text)' }}>
          {t('results.scannedDocWarning')}
        </h2>
        <p className="text-sm leading-relaxed mb-6 text-foreground">
          {t('results.scannedDocWarningDetails')}
        </p>
        <Button variant="outline" onClick={onReset}>
          {t('button.newAnalysis')}
        </Button>
      </FrostCard>
    </div>
  )
}
