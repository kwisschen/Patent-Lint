// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025–2026 Christopher Chen
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ChevronDown } from 'lucide-react'
import CheckItemComponent from './CheckItem'
import { StatusPill } from './ui/status-pill'
import { FrostCard } from './ui/frost-card'

// Map a letter grade to one of the existing status CSS-variable families
// for the section pill — matches the RubricHero color logic.
function letterColorVar(letter) {
  if (!letter || letter === '—') return 'var(--muted-foreground)'
  if (letter.startsWith('A')) return 'var(--pass-border)'
  if (letter.startsWith('B') || letter.startsWith('C')) return 'var(--verify-border)'
  return 'var(--amend-border)' // D / F
}

export default function SectionPanel({
  title,
  checks = [],
  defaultOpen = false,
  children,
  jurisdiction,
  // Optional per-section rubric grade — when supplied, renders a pill
  // showing the section's grade letter to the left of the count badges.
  // When `applicable === false`, renders an "N/A" pill instead with a
  // tooltip explaining why (no drawings detected, etc.).
  grade = null,
  applicable = true,
}) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(defaultOpen)

  const counts = { pass: 0, verify: 0, amend: 0 }
  checks.forEach((c) => {
    if (counts[c.status] !== undefined) counts[c.status]++
  })

  // Single FrostCard wraps both header and body so they read as one
  // connected unit (rather than two floating cards with a gap). When
  // open, a hairline border separates the header button from the body
  // checks. Hover feedback is on the button itself, not the whole card,
  // so the body content doesn't lift unnecessarily when the user
  // approaches the toggle.
  return (
    <FrostCard tier="resting" className="overflow-hidden">
      <button
        className="flex w-full items-center justify-between px-4 py-3 text-left transition-colors duration-[var(--motion-duration-fast)] hover:bg-foreground/[0.03]"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
      >
        <span className="font-semibold">{title}</span>
        <div className="flex items-center gap-2">
          {applicable && grade !== null && (
            <span
              className="rounded-md px-2 py-0.5 text-xs font-bold leading-none bg-card/80"
              style={{
                border: `1px solid ${letterColorVar(grade)}`,
                color: letterColorVar(grade),
              }}
              title={t('rubric.gradePill', { letter: grade })}
            >
              {grade}
            </span>
          )}
          {!applicable && (
            <StatusPill status="muted" size="xs" title={t('rubric.section.notApplicableTooltip')}>
              {t('rubric.section.notApplicable')}
            </StatusPill>
          )}
          {counts.amend > 0 && (
            <StatusPill status="amend" size="xs">{counts.amend} {t('status.amend').toLowerCase()}</StatusPill>
          )}
          {counts.verify > 0 && (
            <StatusPill status="verify" size="xs">{counts.verify} {t('status.verify').toLowerCase()}</StatusPill>
          )}
          {counts.pass > 0 && (
            <StatusPill status="pass" size="xs">{counts.pass} {t('status.pass').toLowerCase()}</StatusPill>
          )}
          <ChevronDown
            className={`h-4 w-4 text-muted-foreground transition-transform duration-[var(--motion-duration-base)] ${open ? 'rotate-180' : ''}`}
          />
        </div>
      </button>
      {open && (
        <div className="border-t border-border/40 px-2 py-2 space-y-1 animate-in fade-in-0 slide-in-from-top-1 duration-[var(--motion-duration-base)]">
          {checks.map((check, i) => (
            <CheckItemComponent key={i} {...check} jurisdiction={jurisdiction} />
          ))}
          {children}
        </div>
      )}
    </FrostCard>
  )
}
