// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2025 Christopher Chen
import { useTranslation } from 'react-i18next'
import { AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'

export default function ScannedDocBanner({ onReset }) {
  const { t } = useTranslation()

  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div
        className="max-w-lg w-full mx-auto rounded-xl border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/30 p-8 text-center animate-in fade-in zoom-in-95 duration-400"
      >
        <AlertTriangle className="mx-auto h-12 w-12 text-amber-500 dark:text-amber-400 mb-4" />
        <h2 className="text-xl font-bold text-amber-900 dark:text-amber-100 mb-3">
          {t('results.scannedDocWarning')}
        </h2>
        <p className="text-sm text-amber-800 dark:text-amber-200/80 leading-relaxed mb-6">
          {t('results.scannedDocWarningDetails')}
        </p>
        <Button
          variant="outline"
          className="border-amber-300 dark:border-amber-700 text-amber-800 dark:text-amber-200 hover:bg-amber-100 dark:hover:bg-amber-900/40"
          onClick={onReset}
        >
          {t('button.newAnalysis')}
        </Button>
      </div>
    </div>
  )
}
