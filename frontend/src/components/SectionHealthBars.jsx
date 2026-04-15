// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2025 Christopher Chen
import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { getJurisdictionConfig } from '../lib/jurisdictionConfig'

function HealthBar({ label, checks = [], animate, delay = 0 }) {
  const [grown, setGrown] = useState(false)

  useEffect(() => {
    if (animate) {
      const timer = setTimeout(() => setGrown(true), delay)
      return () => clearTimeout(timer)
    }
  }, [animate, delay])

  const counts = { pass: 0, verify: 0, amend: 0 }
  checks.forEach((c) => {
    if (counts[c.status] !== undefined) counts[c.status]++
  })
  const total = counts.pass + counts.verify + counts.amend
  if (total === 0) return null

  const segments = [
    { key: 'pass', count: counts.pass, color: 'var(--pass-border)' },
    { key: 'verify', count: counts.verify, color: 'var(--verify-border)' },
    { key: 'amend', count: counts.amend, color: 'var(--amend-border)' },
  ].filter((s) => s.count > 0)

  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-muted-foreground w-24 text-right shrink-0">{label}</span>
      <div className="flex-1 flex h-3 rounded-full overflow-hidden bg-secondary">
        {segments.map((seg) => (
          <div
            key={seg.key}
            className="h-full"
            style={{
              width: grown ? `${(seg.count / total) * 100}%` : '0%',
              backgroundColor: seg.color,
              transition: `width 500ms var(--ease-bounce)`,
            }}
          />
        ))}
      </div>
    </div>
  )
}

export default function SectionHealthBars({ data, animate = false }) {
  const { t } = useTranslation()
  const jConfig = getJurisdictionConfig(data.jurisdiction)
  const sections = [
    { label: t(jConfig.specSectionKey), checks: data.specification_checks },
    { label: t(jConfig.drawingsShortKey), checks: data.drawings_checks },
    { label: t(jConfig.claimsSectionKey), checks: data.claims_checks },
    { label: t(jConfig.abstractSectionKey), checks: data.abstract_checks },
  ]

  return (
    <div className="space-y-2">
      {sections.map((s, i) => (
        <HealthBar key={s.label} label={s.label} checks={s.checks} animate={animate} delay={i * 100} />
      ))}
    </div>
  )
}
