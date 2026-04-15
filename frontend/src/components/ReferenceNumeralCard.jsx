// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2025 Christopher Chen
import { useTranslation } from 'react-i18next'
import { Hash } from 'lucide-react'

export default function ReferenceNumeralCard({ referenceNumerals }) {
  const { t } = useTranslation()

  if (!referenceNumerals || referenceNumerals.length === 0) return null

  return (
    <div
      className="mt-3 rounded-lg border-l-4 border bg-card overflow-hidden"
      style={{ borderLeftColor: 'var(--pass-border)' }}
    >
      <div className="flex items-center gap-3 px-4 py-3">
        <Hash className="h-5 w-5 shrink-0" style={{ color: 'var(--pass-border)' }} />
        <h3 className="text-sm font-semibold flex-1">{t('referenceNumerals.title')}</h3>
        <span
          className="rounded-full px-2.5 py-0.5 text-xs font-bold"
          style={{
            backgroundColor: 'var(--pass-bg)',
            color: 'var(--pass-text)',
            border: '1px solid var(--pass-border)',
          }}
        >
          {referenceNumerals.length} {referenceNumerals.length !== 1 ? t('referenceNumerals.items') : t('referenceNumerals.item')}
        </span>
      </div>
      <div className="border-t">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/30">
              <th className="px-4 py-2 text-left font-medium">{t('referenceNumerals.numeral')}</th>
              <th className="px-4 py-2 text-left font-medium">{t('referenceNumerals.element')}</th>
              <th className="px-4 py-2 text-center font-medium">{t('referenceNumerals.occurrences')}</th>
            </tr>
          </thead>
          <tbody>
            {referenceNumerals.map((rn) => (
              <tr key={rn.number} className="border-b last:border-b-0">
                <td className="px-4 py-1.5 font-mono text-xs">{rn.number}</td>
                <td className="px-4 py-1.5">{rn.element_name}</td>
                <td className="px-4 py-1.5 text-center font-mono text-xs">{rn.occurrences}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
