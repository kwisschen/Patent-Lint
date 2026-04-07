// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025 Christopher Chen
//
// Shared formatter for check item details with structured payloads.
//
// Most check items emit flat string details_params and translate via
// plain t(key, params). Some checks (e.g., symbolTableConsistency)
// emit structured payloads (arrays of objects) that need pre-rendering
// before t() is called, because i18next interpolation only handles
// flat string values.
//
// The formatter detects structured fields by name and pre-renders
// them into flat strings. The locale string then references the
// pre-rendered string via the same interpolation key.
//
// Both React (CheckItem, TriagePanel) and PDF (pdfExport) consumers
// call this helper. Output is always a plain string.

/**
 * Render a list of {numeral, claims: number[]} objects as a localized
 * string like "99 (claim 1, claim 3), 100 (claim 5)".
 *
 * Uses term.claim.numbered for the per-claim format string.
 *
 * @param {Array<{numeral: string, claims: number[]}>} arr
 * @param {Function} t - i18next translate function
 * @returns {string}
 */
function formatNumeralsWithLocations(arr, t) {
  if (!Array.isArray(arr) || arr.length === 0) return ""
  return arr.map(({ numeral, claims }) => {
    const claimStrs = claims.map(n => t("term.claim.numbered", { n }))
    const claimList = claimStrs.join(", ")
    return `${numeral} (${claimList})`
  }).join(", ")
}

/**
 * Render a list of {figure, paragraphs: number[]} objects as a localized
 * string like "figure 1 (paragraph 12, paragraph 15), figure 3 (paragraph 22)".
 *
 * Stub for future check refactors that emit figure-paragraph location
 * payloads. Not currently called by any check.
 */
function formatFiguresWithLocations(arr, t) {
  if (!Array.isArray(arr) || arr.length === 0) return ""
  return arr.map(({ figure, paragraphs }) => {
    const figureStr = t("term.figure.numbered", { n: figure })
    const paraStrs = paragraphs.map(n => t("term.paragraph.numbered", { n }))
    const paraList = paraStrs.join(", ")
    return `${figureStr} (${paraList})`
  }).join(", ")
}

/**
 * Render a list of paragraph numbers as a localized string like
 * "paragraph 1, paragraph 5, paragraph 12".
 *
 * Stub for future check refactors. Not currently called by any check.
 */
function formatParagraphList(arr, t) {
  if (!Array.isArray(arr) || arr.length === 0) return ""
  return arr.map(n => t("term.paragraph.numbered", { n })).join(", ")
}

// Registry of structured field names to their formatters.
// When details_params contains a key in this registry, the formatter
// is called and the result replaces the original value before t() runs.
const STRUCTURED_FORMATTERS = {
  numerals_with_locations: formatNumeralsWithLocations,
  figures_with_locations: formatFiguresWithLocations,
  paragraph_list: formatParagraphList,
}

/**
 * Pre-render any structured fields in details_params, then call t().
 *
 * If details_params contains no structured fields, this is equivalent
 * to t(key, details_params). If it contains one or more structured
 * fields, those fields are replaced with their rendered string forms
 * before being passed to t() for interpolation.
 *
 * @param {string} key - i18next translation key
 * @param {object} details_params - flat object, may contain structured arrays
 * @param {Function} t - i18next translate function
 * @returns {string}
 */
export function formatDetails(key, details_params, t) {
  if (!key) return ""
  if (!details_params) return t(key)

  const rendered = { ...details_params }
  for (const [field, formatter] of Object.entries(STRUCTURED_FORMATTERS)) {
    if (Array.isArray(details_params[field])) {
      rendered[field] = formatter(details_params[field], t)
    }
  }
  return t(key, rendered)
}
