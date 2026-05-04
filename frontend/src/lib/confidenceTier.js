// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
//
// Confidence-tier helpers for the antecedent-basis findings UI.
//
// The walker emits a 0-100 `confidence_score` per finding (see
// patentlint/analysis/utils.py::compute_confidence_score). The frontend
// uses these scores to bucket findings into three tiers for the
// "Less certain" disclosure UX:
//
//   high   (score >= T_HIGH, default 75): shown by default. Target 70%+
//          precision per the precision-push plan §Phase 5.
//   medium (T_LOW <= score < T_HIGH, default 40-74): collapsed under
//          "Less certain" expandable.
//   low    (score < T_LOW, default <40): hidden by default; visible
//          only in "show all" mode.
//
// THRESHOLD CALIBRATION: the T_HIGH / T_LOW defaults below are
// PLACEHOLDERS pending Phase 1 verdict calibration via
// tests/eval/calibrate_confidence_threshold.py. Per-jurisdiction
// differential thresholds are supported via the `jurisdiction` arg of
// `tierForScore`. Until calibration commits land, all jurisdictions
// share the same defaults.

// Per-jurisdiction calibrated thresholds — POST-Phase-1 calibration
// against the supplement_v2 verdicts (605 weighted-sampled drafts on
// post-R48 walker, 2026-05-05). Each T_HIGH is the threshold where
// bucket precision peaks above the absolute baseline by the largest
// yield × precision tradeoff with bucket_size ≥ 10.
// Format: { US: { high: N, low: N }, CN: ..., TW: ... }
//
// Refresh by re-running:
//   python -m tests.eval.calibrate_confidence_threshold \
//     tests/eval/phase2b_results_supplement_v2.json
export const TIER_THRESHOLDS = {
  // Post-Phase-1 sweet spots from
  // tests/eval/phase2b_results_supplement_v2_calibration.json:
  US: { high: 50, low: 30 }, // 40.4% bucket precision (+4.9pp vs absolute 35.5%, 803 findings)
  CN: { high: 65, low: 30 }, // 20.8% bucket precision (+6.4pp vs absolute 14.4%, 606 findings)
  TW: { high: 65, low: 30 }, // 17.5% bucket precision (+4.9pp vs absolute 12.6%, 702 findings)
  // Default-fallback for any jurisdiction not explicitly listed.
  DEFAULT: { high: 60, low: 30 },
}

export const TIER_HIGH = 'high'
export const TIER_MEDIUM = 'medium'
export const TIER_LOW = 'low'

/**
 * Map a confidence score to a tier label.
 * @param {number|null|undefined} score 0..100 confidence score
 * @param {string} jurisdiction One of "US", "CN", "TW" (case-insensitive)
 * @returns {string} TIER_HIGH | TIER_MEDIUM | TIER_LOW
 */
export function tierForScore(score, jurisdiction = 'DEFAULT') {
  // Defensive: if score is missing (legacy finding shape), default to
  // medium so the UX doesn't spuriously hide unscored findings.
  if (typeof score !== 'number' || Number.isNaN(score)) return TIER_MEDIUM
  const j = (jurisdiction || 'DEFAULT').toUpperCase()
  const thresholds = TIER_THRESHOLDS[j] ?? TIER_THRESHOLDS.DEFAULT
  if (score >= thresholds.high) return TIER_HIGH
  if (score >= thresholds.low) return TIER_MEDIUM
  return TIER_LOW
}

/**
 * Convenience predicate: is this finding in the high-confidence tier?
 */
export function isHighConfidence(score, jurisdiction = 'DEFAULT') {
  return tierForScore(score, jurisdiction) === TIER_HIGH
}

/**
 * Aggregate a group of findings (with `confidence_score` per finding)
 * to its representative tier. A group is considered "high" if ANY of
 * its findings is high-conf — the methodology assumes high-conf
 * findings dominate user attention, and a group with one strong signal
 * + several weaker ones should surface in the high tier.
 */
export function groupTier(findings, jurisdiction = 'DEFAULT') {
  if (!Array.isArray(findings) || findings.length === 0) return TIER_MEDIUM
  let bestTier = TIER_LOW
  for (const f of findings) {
    const t = tierForScore(f?.confidence_score, jurisdiction)
    if (t === TIER_HIGH) return TIER_HIGH
    if (t === TIER_MEDIUM && bestTier === TIER_LOW) bestTier = TIER_MEDIUM
  }
  return bestTier
}
