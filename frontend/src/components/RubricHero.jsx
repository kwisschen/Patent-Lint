// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useCountUp } from '../hooks/useCountUp'

// Map a letter grade to one of the existing status CSS-variable families
// (pass / verify / amend) so the grade color reuses the same palette as
// the donut arcs. Picked by tier rather than per-letter to keep visual
// intent legible: A range = pass-green, B/C = verify-amber, D/F = amend-red.
function letterColorVar(letter) {
  if (!letter || letter === '—') return 'var(--muted-foreground)'
  if (letter.startsWith('A')) return 'var(--pass-border)'
  if (letter.startsWith('B')) return 'var(--verify-border)'
  if (letter.startsWith('C')) return 'var(--verify-border)'
  return 'var(--amend-border)' // D / F
}

function CompletenessGate({ missingSections, t }) {
  const labels = (missingSections || []).map((s) => t(`rubric.section.${s}`, s))
  return (
    <div className="flex flex-col items-center gap-2 rounded-lg border bg-card p-6 text-center">
      <span className="text-2xl font-bold" style={{ color: 'var(--amend-text)' }}>
        {t('rubric.completenessGate.title')}
      </span>
      <p className="text-sm text-muted-foreground">
        {t('rubric.completenessGate.missingSections', { sections: labels.join(', ') })}
      </p>
    </div>
  )
}

export default function RubricHero({ data, animate = false }) {
  const { t } = useTranslation()
  const [drawn, setDrawn] = useState(false)

  useEffect(() => {
    if (animate) {
      const timer = setTimeout(() => setDrawn(true), 100)
      return () => clearTimeout(timer)
    }
  }, [animate])

  const grade = data?.rubric_grade

  // Completeness gate — no grade emitted, surface the gap.
  if (grade?.completeness_gap?.missing_sections?.length) {
    return <CompletenessGate missingSections={grade.completeness_gap.missing_sections} t={t} />
  }

  // Donut arc breakdown (same math as the legacy HealthDonut).
  const allChecks = [
    ...(data.specification_checks || []),
    ...(data.claims_checks || []),
    ...(data.abstract_checks || []),
    ...(data.drawings_checks || []),
  ]
  const counts = { pass: 0, verify: 0, amend: 0 }
  allChecks.forEach((c) => {
    if (counts[c.status] !== undefined) counts[c.status]++
  })
  const total = counts.pass + counts.verify + counts.amend

  // Defensive: if no grade *and* no findings, render nothing (caller handles).
  if (!grade && total === 0) return null

  const size = 140
  const strokeWidth = 14
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius

  const segments = [
    { key: 'pass', count: counts.pass, color: 'var(--pass-border)', label: t('status.pass') },
    { key: 'verify', count: counts.verify, color: 'var(--verify-border)', label: t('status.verify') },
    { key: 'amend', count: counts.amend, color: 'var(--amend-border)', label: t('status.amend') },
  ].filter((s) => s.count > 0)

  let offset = 0
  const arcs = segments.map((seg) => {
    const fraction = total > 0 ? seg.count / total : 0
    const dash = fraction * circumference
    const gap = circumference - dash
    const arc = { ...seg, dashArray: `${dash} ${gap}`, dashOffset: -offset, targetDash: dash }
    offset += dash
    return arc
  })

  const amendCount = useCountUp(counts.amend, 600, animate)
  const verifyCount = useCountUp(counts.verify, 600, animate)
  const passCount = useCountUp(counts.pass, 600, animate)
  const countMap = { amend: amendCount, verify: verifyCount, pass: passCount }

  const letter = grade?.letter || '—'
  const score = grade?.score ?? 0
  const animatedScore = useCountUp(score, 600, animate)
  const letterColor = letterColorVar(letter)

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          {arcs.map((arc) => (
            <circle
              key={arc.key}
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke={arc.color}
              strokeWidth={strokeWidth}
              strokeDasharray={drawn ? arc.dashArray : `0 ${circumference}`}
              strokeDashoffset={arc.dashOffset}
              strokeLinecap="butt"
              transform={`rotate(-90 ${size / 2} ${size / 2})`}
              style={{ transition: 'stroke-dasharray 800ms ease-out' }}
            />
          ))}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center leading-none">
          <span
            className="text-5xl font-bold tracking-tight"
            style={{ color: letterColor }}
          >
            {letter}
          </span>
          {grade && (
            <span className="mt-1 text-xs font-medium text-muted-foreground">
              {animatedScore} / 100
            </span>
          )}
        </div>
      </div>

      {/* Trust line — preserves the No-AI badge invariant. */}
      <p className="text-xs text-muted-foreground">{t('rubric.trust.line')}</p>

      {/* Discoverable link to the rubric exposition page. Replaces the
          raw cap-reason text — the explanation lives at /rubric where
          the gate rules are documented in full, instead of crowding
          the hero with internal mechanics. */}
      <Link
        to="/rubric"
        className="text-xs text-muted-foreground hover:text-foreground transition-colors underline-offset-2 hover:underline"
      >
        {t('rubric.howWeScore')}
      </Link>

      {/* Status legend — preserves visibility of pass/review/fix counts. */}
      {segments.length > 0 && (
        <div className="flex items-center gap-4 text-xs">
          {segments.map((seg) => (
            <div key={seg.key} className="flex items-center gap-1.5">
              <span
                className="inline-block h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: seg.color }}
              />
              <span className="text-muted-foreground">{seg.label}</span>
              <span className="font-semibold">{countMap[seg.key]}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
