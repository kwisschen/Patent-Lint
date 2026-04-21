// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useCountUp } from '../hooks/useCountUp'

export default function HealthDonut({ data, animate = false }) {
  const { t } = useTranslation()
  const [drawn, setDrawn] = useState(false)

  useEffect(() => {
    if (animate) {
      const timer = setTimeout(() => setDrawn(true), 100)
      return () => clearTimeout(timer)
    }
  }, [animate])

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
  if (total === 0) return null

  const size = 120
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
    const fraction = seg.count / total
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
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-2xl font-bold">{total}</span>
        </div>
      </div>
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
    </div>
  )
}
