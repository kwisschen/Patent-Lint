// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025-2026 Christopher Chen
//
// Single source for the score -> letter mapping on the JS side.
//
// This band table existed in THREE places before this file: `pdfExport.js`,
// a local arrow function inside `AnalysisReport.jsx`, and it was about to gain
// a third copy in `RubricHero` for the animated letter. All three agreed with
// `rubric.py::letter_for_score`, which is luck rather than design - nothing
// held them together, and a rubric change would have had to find all of them.
//
// Standard US 12-tier scale, no A+ (matches rubric.py exactly):
//   A  93-100   A- 90-92
//   B+ 87-89    B  83-86   B- 80-82
//   C+ 77-79    C  73-76   C- 70-72
//   D+ 67-69    D  63-66   D- 60-62
//   F  < 60
const BANDS = [
  [93, 'A'],
  [90, 'A-'],
  [87, 'B+'],
  [83, 'B'],
  [80, 'B-'],
  [77, 'C+'],
  [73, 'C'],
  [70, 'C-'],
  [67, 'D+'],
  [63, 'D'],
  [60, 'D-'],
]

/** Letter for a 0-100 score. Returns 'F' below 60. */
export function letterForScore(score) {
  const n = Number(score)
  if (!Number.isFinite(n)) return 'F'
  for (const [floor, letter] of BANDS) {
    if (n >= floor) return letter
  }
  return 'F'
}

/** Letter for a section-grade object, or null when the section is not graded. */
export function letterForSectionGrade(sectionGrade) {
  if (!sectionGrade || !sectionGrade.applicable) return null
  if (sectionGrade.score == null) return null
  return letterForScore(sectionGrade.score)
}

export { BANDS as GRADE_BANDS }
