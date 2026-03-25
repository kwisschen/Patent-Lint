// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025 Christopher Chen
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { AlertCircle, Search, CheckCircle, ChevronDown } from 'lucide-react'
import { getCitation } from './CheckItem'

const GROUP_CONFIG = [
  { status: 'amend', titleKey: 'triage.amend', emptyKey: 'triage.amendEmpty', Icon: AlertCircle },
  { status: 'verify', titleKey: 'triage.verify', emptyKey: 'triage.verifyEmpty', Icon: Search },
  { status: 'pass', titleKey: 'triage.pass', emptyKey: null, Icon: CheckCircle },
]

function TriageItem({ check, t, i18n, compact }) {
  const msg = check.message_key && i18n.exists(check.message_key) ? t(check.message_key) : check.message
  const citation = getCitation(check.message_key)

  return (
    <div className="flex items-start gap-2 py-1.5 px-3">
      <span className="shrink-0 text-[11px] text-muted-foreground mt-0.5">
        {check.section}
      </span>
      {citation && (
        <span className="citation-badge shrink-0 rounded px-1.5 py-0.5 text-[11px] font-mono leading-none mt-0.5">
          {citation}
        </span>
      )}
      <div className="min-w-0">
        <span className="text-sm">{msg}</span>
        {!compact && check.details && (
          <p className="text-xs text-muted-foreground mt-0.5">{check.details}</p>
        )}
      </div>
    </div>
  )
}

function TriageGroup({ status, title, emptyMessage, Icon, items, defaultOpen, t, i18n }) {
  const [open, setOpen] = useState(defaultOpen)
  const count = items.length
  const compact = status === 'pass'

  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-3 rounded-lg px-4 py-3 text-left transition-colors hover:opacity-90"
        style={{
          borderLeft: `4px solid var(--${status}-border)`,
          backgroundColor: `var(--${status}-bg)`,
        }}
      >
        <Icon className="h-5 w-5 shrink-0" style={{ color: `var(--${status}-text)` }} />
        <span className="font-semibold flex-1">{title}</span>
        <span className="text-xs font-medium" style={{ color: `var(--${status}-tag-text)` }}>
          {count} {count === 1 ? t('triage.item') : t('triage.items')}
        </span>
        <ChevronDown
          className={`h-4 w-4 text-muted-foreground transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
        />
      </button>
      {open && (
        <div className="mt-1 rounded-lg border bg-card p-1 animate-in fade-in-0 slide-in-from-top-1 duration-200">
          {count === 0 && emptyMessage ? (
            <p className="px-3 py-2 text-sm text-muted-foreground">{emptyMessage}</p>
          ) : (
            items.map((check, i) => (
              <TriageItem key={i} check={check} t={t} i18n={i18n} compact={compact} />
            ))
          )}
        </div>
      )}
    </div>
  )
}

export default function TriagePanel({ data }) {
  const { t, i18n } = useTranslation()

  const allChecks = [
    ...(data.specification_checks || []).map((c) => ({ ...c, section: t('section.specification') })),
    ...(data.drawings_checks || []).map((c) => ({ ...c, section: t('section.drawingsShort') })),
    ...(data.claims_checks || []).map((c) => ({ ...c, section: t('section.claims') })),
    ...(data.abstract_checks || []).map((c) => ({ ...c, section: t('section.abstract') })),
  ]

  const byStatus = {
    amend: allChecks.filter((c) => c.status === 'amend'),
    verify: allChecks.filter((c) => c.status === 'verify'),
    pass: allChecks.filter((c) => c.status === 'pass'),
  }

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
        {t('triage.title')}
      </h3>
      {GROUP_CONFIG.map(({ status, titleKey, emptyKey, Icon }) => (
        <TriageGroup
          key={status}
          status={status}
          title={t(titleKey)}
          emptyMessage={emptyKey ? t(emptyKey) : null}
          Icon={Icon}
          items={byStatus[status]}
          defaultOpen={
            status === 'amend' ||
            (status === 'verify' && byStatus.amend.length === 0)
          }
          t={t}
          i18n={i18n}
        />
      ))}
    </div>
  )
}
