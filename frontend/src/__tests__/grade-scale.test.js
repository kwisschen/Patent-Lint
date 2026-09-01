// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025-2026 Christopher Chen
//
// The score -> letter table lived in three places (pdfExport, AnalysisReport,
// and it was about to gain a third copy in RubricHero for the animated
// letter). All three happened to agree with rubric.py, but nothing held them
// together. lib/gradeScale is now the only copy; this pins it to the Python
// source of truth band for band.
import { describe, it, expect } from 'vitest'
import { letterForScore, letterForSectionGrade, GRADE_BANDS } from '../lib/gradeScale'

describe('gradeScale', () => {
  // Mirrors rubric.py::letter_for_score exactly.
  const cases = [
    [100, 'A'], [93, 'A'], [92, 'A-'], [90, 'A-'],
    [89, 'B+'], [87, 'B+'], [86, 'B'], [83, 'B'], [82, 'B-'], [80, 'B-'],
    [79, 'C+'], [77, 'C+'], [76, 'C'], [73, 'C'], [72, 'C-'], [70, 'C-'],
    [69, 'D+'], [67, 'D+'], [66, 'D'], [63, 'D'], [62, 'D-'], [60, 'D-'],
    [59, 'F'], [0, 'F'],
  ]
  it.each(cases)('score %i is %s', (score, letter) => {
    expect(letterForScore(score)).toBe(letter)
  })

  it('every band boundary is exactly one point below the band above', () => {
    for (let i = 1; i < GRADE_BANDS.length; i++) {
      const [floor] = GRADE_BANDS[i]
      const [aboveFloor] = GRADE_BANDS[i - 1]
      expect(letterForScore(aboveFloor - 1)).toBe(GRADE_BANDS[i][1])
      expect(floor).toBeLessThan(aboveFloor)
    }
  })

  it('never throws on a missing or junk score', () => {
    expect(letterForScore(undefined)).toBe('F')
    expect(letterForScore(null)).toBe('F')
    expect(letterForScore(NaN)).toBe('F')
  })

  it('a non-applicable section has no letter', () => {
    expect(letterForSectionGrade({ score: 100, applicable: false })).toBeNull()
    expect(letterForSectionGrade(null)).toBeNull()
    expect(letterForSectionGrade({ score: null, applicable: true })).toBeNull()
    expect(letterForSectionGrade({ score: 67, applicable: true })).toBe('D+')
  })
})
