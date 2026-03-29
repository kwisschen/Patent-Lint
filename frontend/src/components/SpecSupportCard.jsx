// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025 Christopher Chen
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { FileSearch, ChevronRight } from 'lucide-react'

function ClaimRow({ claimNumber, phrases }) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState(false)

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        className="flex items-center gap-2 px-3 py-2 rounded-md hover:bg-[var(--attention-bg)]/60 transition-colors cursor-pointer"
        onClick={() => setExpanded(!expanded)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            setExpanded(!expanded)
          }
        }}
      >
        <ChevronRight
          className={`h-3.5 w-3.5 shrink-0 transition-transform duration-200 ${expanded ? 'rotate-90' : ''}`}
          style={{ color: 'var(--attention-border)' }}
        />
        <span
          className="inline-flex items-center justify-center h-6 w-6 rounded-full text-xs font-bold shrink-0"
          style={{
            backgroundColor: 'var(--attention-bg)',
            color: 'var(--attention-text)',
            border: '1.5px solid var(--attention-border)',
          }}
        >
          {claimNumber}
        </span>
        <span className="text-sm text-muted-foreground">
          {phrases.map((phrase, i) => (
            <span key={i}>
              {i > 0 && ', '}
              <span className="font-medium" style={{ color: 'var(--attention-text)' }}>
                "{phrase}"
              </span>
            </span>
          ))}
        </span>
      </div>
      {expanded && (
        <div className="mx-3 mb-2 px-3 py-2 rounded text-xs leading-relaxed border" style={{
          borderColor: 'var(--attention-border)',
          backgroundColor: 'var(--attention-bg)',
        }}>
          <p className="text-muted-foreground">
            {t('details.specSupportUnsupported', { count: phrases.length })}
          </p>
        </div>
      )}
    </div>
  )
}

export default function SpecSupportCard({ unsupportedTerms }) {
  const { t } = useTranslation()

  if (!unsupportedTerms || unsupportedTerms.length === 0) return null

  // Group by claim_number
  const grouped = {}
  unsupportedTerms.forEach(({ claim_number, phrase }) => {
    if (!grouped[claim_number]) grouped[claim_number] = new Set()
    grouped[claim_number].add(phrase)
  })

  const claimIds = Object.keys(grouped).map(Number).sort((a, b) => a - b)
  const totalItems = unsupportedTerms.length

  return (
    <div
      className="rounded-lg border-l-4 border bg-card overflow-hidden"
      style={{ borderLeftColor: 'var(--attention-border)' }}
    >
      <div className="flex items-center gap-3 px-4 py-3">
        <FileSearch className="h-5 w-5 shrink-0" style={{ color: 'var(--attention-border)' }} />
        <h3 className="text-sm font-semibold flex-1">{t('specSupport.title')}</h3>
        <span
          className="rounded-full px-2.5 py-0.5 text-xs font-bold"
          style={{
            backgroundColor: 'var(--attention-bg)',
            color: 'var(--attention-text)',
            border: '1px solid var(--attention-border)',
          }}
        >
          {totalItems} {totalItems !== 1 ? t('specSupport.items') : t('specSupport.item')}
        </span>
      </div>
      <div className="border-t px-1 py-1">
        {claimIds.map((id) => (
          <ClaimRow key={id} claimNumber={id} phrases={[...grouped[id]]} />
        ))}
      </div>
    </div>
  )
}
