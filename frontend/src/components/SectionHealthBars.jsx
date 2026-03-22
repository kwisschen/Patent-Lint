function HealthBar({ label, checks = [] }) {
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
            className="h-full transition-all duration-500"
            style={{
              width: `${(seg.count / total) * 100}%`,
              backgroundColor: seg.color,
            }}
          />
        ))}
      </div>
    </div>
  )
}

import { useTranslation } from 'react-i18next'

export default function SectionHealthBars({ data }) {
  const { t } = useTranslation()
  const sections = [
    { label: t('section.specification'), checks: data.specification_checks },
    { label: t('section.claims'), checks: data.claims_checks },
    { label: t('section.abstract'), checks: data.abstract_checks },
    { label: t('section.drawings'), checks: data.drawings_checks },
  ]

  return (
    <div className="space-y-2">
      {sections.map((s) => (
        <HealthBar key={s.label} label={s.label} checks={s.checks} />
      ))}
    </div>
  )
}
