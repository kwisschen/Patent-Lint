// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025-2026 Christopher Chen
//
// "Why this grade" - the arithmetic behind the hero letter, inline.
//
// The rubric page explains the SYSTEM (weights, the FIX gate) but says nothing
// about THIS draft, and reaching it means leaving the report mid-review. Two
// facts were computed and then never shown:
//
//   1. Each section's weight and its own score. The hero letter is a weighted
//      average of five numbers the reader could not see.
//   2. `cap_reason`. On the fixture used to build this, the weighted sections
//      average ~72 (C-) and the displayed grade is 67 (D+), because six FIX
//      findings cap it. That is a two-band drop with no explanation anywhere
//      in the UI - the single most confusing thing about the grade.
//
// Collapsed by default: the grade is the headline, this is the follow-up
// question. Native <details>/<summary> so it is keyboard- and
// screen-reader-operable without any JS state.
import { useTranslation } from 'react-i18next'
import { letterForScore } from '../lib/gradeScale'

// Same tiering the hero uses for the letter, so a section bar and the headline
// letter never disagree about what "good" looks like. A single flat colour
// made a 49 and a 100 read identically at a glance, which defeats the point of
// a breakdown you are meant to SCAN.
function bandColor(score) {
  if (score >= 80) return 'var(--pass-border)'
  if (score >= 60) return 'var(--verify-border)'
  return 'var(--amend-border)'
}

export default function GradeBreakdown({ grade }) {
  const { t } = useTranslation()
  const sections = (grade?.section_grades || []).filter((s) => s.applicable !== false)
  const totalFix = sections.reduce((n, s) => n + (s.fix_count || 0), 0)
  if (!grade || sections.length === 0) return null

  return (
    <details className="group/bd w-full max-w-lg text-xs">
      <summary
        className="mx-auto flex w-fit cursor-pointer list-none items-center gap-1 rounded px-2 py-1
                   text-muted-foreground transition-colors hover:text-foreground
                   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
      >
        <span>{t('rubric.breakdown.title')}</span>
        <span aria-hidden className="transition-transform group-open/bd:rotate-180">
          {'⌄'}
        </span>
      </summary>

      <div className="mt-3 space-y-1.5">
        {sections.map((s) => {
          const letter = letterForScore(s.score)
          return (
            <div key={s.section} className="flex items-center gap-2">
              <span className="w-36 shrink-0 truncate text-muted-foreground">
                {t(`rubric.section.${s.section}`, s.section)}
              </span>
              <span className="w-10 shrink-0 text-right tabular-nums text-muted-foreground/70">
                {t('rubric.breakdown.weight', { weight: s.weight })}
              </span>
              <div
                className="h-1.5 flex-1 overflow-hidden rounded-full bg-secondary/60"
                role="img"
                aria-label={`${s.score} / 100`}
              >
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${Math.max(0, Math.min(100, s.score))}%`,
                    backgroundColor: bandColor(s.score),
                  }}
                />
              </div>
              <span className="w-14 shrink-0 text-right tabular-nums">
                {s.score}
                <span className="ml-1 text-muted-foreground/70">{letter}</span>
              </span>
            </div>
          )
        })}

        {/* `cap_reason` is a HARDCODED ENGLISH string from rubric.py
            ("6 FIX cap grade at D+"). Rendering it would put English in front
            of every non-English reader, so it is used only as the BOOLEAN
            signal that a cap applied - the sentence itself is rebuilt here
            from the structured fix count and the letter actually displayed. */}
        {grade.cap_reason && (
          <p className="pt-2 text-[11px] leading-snug" style={{ color: 'var(--amend-text)' }}>
            {t('rubric.breakdown.capped', {
              count: totalFix,
              letter: grade.letter,
            })}
          </p>
        )}
        <p className="pt-1 text-[11px] leading-snug text-muted-foreground/80">
          {t('rubric.breakdown.note')}
        </p>
      </div>
    </details>
  )
}
