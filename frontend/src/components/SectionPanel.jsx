// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ChevronDown } from 'lucide-react'
import CheckItemComponent from './CheckItem'

export default function SectionPanel({ title, checks = [], defaultOpen = false, children, jurisdiction }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(defaultOpen)

  const counts = { pass: 0, verify: 0, amend: 0 }
  checks.forEach((c) => {
    if (counts[c.status] !== undefined) counts[c.status]++
  })

  return (
    <div>
      <button
        className="flex w-full items-center justify-between rounded-lg border bg-card px-4 py-3 text-left hover:bg-accent/50 transition-colors"
        onClick={() => setOpen(!open)}
      >
        <span className="font-semibold">{title}</span>
        <div className="flex items-center gap-2">
          {counts.amend > 0 && (
            <span
              className="rounded px-1.5 py-0.5 text-[10px] font-bold leading-none"
              style={{ backgroundColor: 'var(--amend-bg)', color: 'var(--amend-tag-text)' }}
            >
              {counts.amend} {t('status.amend').toLowerCase()}
            </span>
          )}
          {counts.verify > 0 && (
            <span
              className="rounded px-1.5 py-0.5 text-[10px] font-bold leading-none"
              style={{ backgroundColor: 'var(--verify-bg)', color: 'var(--verify-tag-text)' }}
            >
              {counts.verify} {t('status.verify').toLowerCase()}
            </span>
          )}
          {counts.pass > 0 && (
            <span
              className="rounded px-1.5 py-0.5 text-[10px] font-bold leading-none"
              style={{ backgroundColor: 'var(--pass-bg)', color: 'var(--pass-tag-text)' }}
            >
              {counts.pass} {t('status.pass').toLowerCase()}
            </span>
          )}
          <ChevronDown
            className={`h-4 w-4 text-muted-foreground transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
          />
        </div>
      </button>
      {open && (
        <div className="mt-1 space-y-1 rounded-lg border bg-card p-2 animate-in fade-in-0 slide-in-from-top-1 duration-200">
          {checks.map((check, i) => (
            <CheckItemComponent key={i} {...check} jurisdiction={jurisdiction} />
          ))}
          {children}
        </div>
      )}
    </div>
  )
}
