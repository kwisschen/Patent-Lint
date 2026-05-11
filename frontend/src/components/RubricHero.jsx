// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025–2026 Christopher Chen
import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useCountUp } from '../hooks/useCountUp'
import { FrostCard } from './ui/frost-card'

// Map a letter grade to one of the existing status CSS-variable families
// (pass / verify / amend) so the grade color reuses the same palette as
// the donut arcs. Picked by tier rather than per-letter to keep visual
// intent legible: A range = pass-blue, B/C = verify-green, D/F = amend-red.
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
    <FrostCard tier="elevated" accent="amend" className="flex flex-col items-center gap-2 px-6 py-8 text-center">
      <span className="text-2xl font-bold" style={{ color: 'var(--amend-text)' }}>
        {t('rubric.completenessGate.title')}
      </span>
      <p className="text-sm text-muted-foreground">
        {t('rubric.completenessGate.missingSections', { sections: labels.join(', ') })}
      </p>
    </FrostCard>
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

  const size = 144
  const strokeWidth = 14
  const radius = (size - strokeWidth) / 2
  const cx = size / 2
  const cy = size / 2

  const segments = [
    { key: 'pass', count: counts.pass, color: 'var(--pass-border)', label: t('status.pass') },
    { key: 'verify', count: counts.verify, color: 'var(--verify-border)', label: t('status.verify') },
    { key: 'amend', count: counts.amend, color: 'var(--amend-border)', label: t('status.amend') },
  ].filter((s) => s.count > 0)

  // Render each segment as a discrete SVG <path> arc rather than a full
  // <circle> with strokeDasharray. The dasharray approach left adjacent
  // segments meeting at sub-pixel boundaries that anti-aliased
  // inconsistently — most visible as a jagged seam at the 12 o'clock
  // wrap-around where AMEND ends and PASS begins. Explicit paths with
  // shared endpoint coordinates eliminate the alignment ambiguity.
  //
  // Single-segment edge case: a path A-command from a point to itself is
  // a no-op (zero-length arc). When only one status type has findings we
  // emit a full circle by drawing two half-arcs back-to-back.
  let cumAngle = -Math.PI / 2 // start at 12 o'clock
  const arcs = segments.map((seg) => {
    const fraction = total > 0 ? seg.count / total : 0
    const sweep = fraction * 2 * Math.PI
    const startAngle = cumAngle
    const endAngle = startAngle + sweep
    cumAngle = endAngle

    const startX = cx + radius * Math.cos(startAngle)
    const startY = cy + radius * Math.sin(startAngle)
    const endX = cx + radius * Math.cos(endAngle)
    const endY = cy + radius * Math.sin(endAngle)
    const largeArc = sweep > Math.PI ? 1 : 0

    let d
    if (segments.length === 1) {
      // Full circle as two half-arcs through the antipode.
      const midX = cx + radius * Math.cos(startAngle + Math.PI)
      const midY = cy + radius * Math.sin(startAngle + Math.PI)
      d = `M ${startX} ${startY} A ${radius} ${radius} 0 0 1 ${midX} ${midY} A ${radius} ${radius} 0 0 1 ${startX} ${startY}`
    } else {
      d = `M ${startX} ${startY} A ${radius} ${radius} 0 ${largeArc} 1 ${endX} ${endY}`
    }
    return { ...seg, d }
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
    <div className="flex flex-col items-center gap-3 px-4 py-5 sm:px-6 sm:py-6">
      <div className="relative" style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          shapeRendering="geometricPrecision"
        >
          {arcs.map((arc) => (
            <path
              key={arc.key}
              d={arc.d}
              fill="none"
              stroke={arc.color}
              strokeWidth={strokeWidth}
              strokeLinecap="butt"
              pathLength={100}
              strokeDasharray={drawn ? '100 0' : '0 100'}
              style={{ transition: 'stroke-dasharray 800ms ease-out' }}
            />
          ))}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center leading-none">
          <span
            className="text-5xl font-bold tracking-tight"
            style={{ color: letterColor, textShadow: '0 1px 2px rgba(15,23,42,0.06)' }}
          >
            {letter}
          </span>
          {grade && (
            <span className="mt-1.5 text-xs font-medium text-muted-foreground">
              {animatedScore} / 100
            </span>
          )}
        </div>
      </div>

      {/* Status legend — preserves visibility of pass/review/fix counts. */}
      {segments.length > 0 && (
        <div className="flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-xs">
          {segments.map((seg) => (
            <div key={seg.key} className="flex items-center gap-1.5">
              <span
                className="inline-block h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: seg.color, boxShadow: '0 0 0 2px var(--background)' }}
              />
              <span className="text-muted-foreground">{seg.label}</span>
              <span className="font-semibold tabular-nums">{countMap[seg.key]}</span>
            </div>
          ))}
        </div>
      )}

      <div className="w-full border-t border-border/40" aria-hidden="true" />

      <p className="max-w-md text-center text-sm leading-relaxed text-foreground">
        {t('rubric.trust.line')}
      </p>

      {/* Discoverable link to the rubric exposition page. The explanation
          lives at /rubric where the gate rules are documented in full,
          instead of crowding the hero with internal mechanics. */}
      <Link
        to="/rubric"
        className="text-xs text-muted-foreground hover:text-foreground transition-colors underline-offset-2 hover:underline"
      >
        {t('rubric.howWeScore')}
      </Link>
    </div>
  )
}
