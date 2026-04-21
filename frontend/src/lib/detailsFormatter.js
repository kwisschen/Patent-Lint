// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
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
 * Render a list of {figure, paragraphs: number[]} objects.
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
 * Render a list of paragraph numbers.
 */
function formatParagraphList(arr, t) {
  if (!Array.isArray(arr) || arr.length === 0) return ""
  return arr.map(n => t("term.paragraph.numbered", { n })).join(", ")
}

// Primitive list formatters (truncate at 10 + localized ellipsis)
function formatFigureList(figs, t) {
  if (!Array.isArray(figs) || figs.length === 0) return ""
  const truncated = figs.length > 10
  const shown = figs.slice(0, 10)
  const rendered = shown.map(n => t("term.figure.numbered", { n })).join(t("punct.listSeparator"))
  return truncated ? rendered + t("punct.ellipsis") : rendered
}

function formatClaimList(claims, t) {
  if (!Array.isArray(claims) || claims.length === 0) return ""
  const truncated = claims.length > 10
  const shown = claims.slice(0, 10)
  const rendered = shown.map(n => t("term.claim.numbered", { n })).join(t("punct.listSeparator"))
  return truncated ? rendered + t("punct.ellipsis") : rendered
}

function formatParagraphListSimple(paras, t) {
  if (!Array.isArray(paras) || paras.length === 0) return ""
  const truncated = paras.length > 10
  const shown = paras.slice(0, 10)
  const rendered = shown.map(n => t("term.paragraph.numbered", { n })).join(t("punct.listSeparator"))
  return truncated ? rendered + t("punct.ellipsis") : rendered
}

function formatNumeralList(nums, t) {
  if (!Array.isArray(nums) || nums.length === 0) return ""
  const truncated = nums.length > 10
  const shown = nums.slice(0, 10)
  const rendered = shown.join(t("punct.listSeparator"))
  return truncated ? rendered + t("punct.ellipsis") : rendered
}

// Component-name list for the connection-relationships check. Joins
// noun-phrase heads with the locale's list separator and appends an
// ellipsis when the underlying claim has more components than the
// 3-name sample. The total count comes from the sibling
// `component_count` param so the formatter knows when to truncate.
function formatSampleNames(names, t, params) {
  if (!Array.isArray(names) || names.length === 0) return ""
  const joined = names.join(t("punct.listSeparator"))
  const total = params?.component_count
  if (typeof total === "number" && total > names.length) {
    return joined + t("punct.ellipsis")
  }
  return joined
}

// Figure reference inconsistency — two-direction mismatch
function formatFigureRefInconsistency(data, t) {
  if (!data || typeof data !== "object") return ""
  const { only_drawings = [], only_embodiment = [], jurisdiction = "cn" } = data
  const parts = []
  if (only_drawings.length) {
    parts.push(t(`details.${jurisdiction}.figureRefInconsistency.onlyDrawings`, {
      figs: formatFigureList(only_drawings, t),
    }))
  }
  if (only_embodiment.length) {
    parts.push(t(`details.${jurisdiction}.figureRefInconsistency.onlyEmbodiment`, {
      figs: formatFigureList(only_embodiment, t),
    }))
  }
  return parts.join(t("punct.sentenceSeparator"))
}

// Symbol table inconsistency (TW-specific)
function formatSymbolTableInconsistency(data, t) {
  if (!data || typeof data !== "object") return ""
  const { unreferenced = [], undefined: undef = [] } = data
  const parts = []
  if (unreferenced.length) {
    parts.push(t("details.tw.symbolTableInconsistency.unreferenced", {
      symbols: formatNumeralList(unreferenced, t),
    }))
  }
  if (undef.length) {
    parts.push(t("details.tw.symbolTableInconsistency.undefined", {
      symbols: formatNumeralList(undef, t),
    }))
  }
  return parts.join(t("punct.sentenceSeparator"))
}

// Representative drawing vs symbol table mismatches (TW-specific)
function formatSymbolMismatchTriples(data, t) {
  if (!data || typeof data !== "object") return ""
  const { mismatches = [] } = data
  return mismatches.slice(0, 10).map(m => {
    if (m.kind === "not_in_table") {
      return t("details.tw.symbolVsRepDrawing.notInTable", {
        numeral: m.numeral,
        name: m.rep_name,
      })
    } else if (m.kind === "name_mismatch") {
      return t("details.tw.symbolVsRepDrawing.nameMismatch", {
        numeral: m.numeral,
        rep_name: m.rep_name,
        table_name: m.table_name,
      })
    }
    return ""
  }).filter(Boolean).join(t("punct.sentenceSeparator"))
}

// Title prohibited items (trademark, commercial language, model numbers)
function formatTitleProhibitedItems(data, t) {
  if (!data || typeof data !== "object") return ""
  const { items = [] } = data
  return items.map(item => t(`details.titleProhibited.${item.kind}`, {
    token: item.token,
  })).join(t("punct.sentenceSeparator"))
}

// Paragraph format violations (examples + count)
function formatParagraphFormatViolations(data, t) {
  if (!data || typeof data !== "object") return ""
  const { examples = [], count = 0 } = data
  return t("details.paragraphFormat.examples", {
    examples: examples.slice(0, 5).join(t("punct.listSeparator")),
    count,
  })
}

// Registry of structured field names to their formatters.
const STRUCTURED_FORMATTERS = {
  numerals_with_locations: formatNumeralsWithLocations,
  figures_with_locations: formatFiguresWithLocations,
  paragraph_list: formatParagraphList,
  figure_list: formatFigureList,
  claim_list: formatClaimList,
  paragraph_list_simple: formatParagraphListSimple,
  numeral_list: formatNumeralList,
  // Semantic aliases: allow Python emit sites to name fields by what they
  // contain ("claims", "paragraphs", "duplicates") while reusing the same
  // formatter functions.
  claims: formatClaimList,
  paragraphs: formatParagraphListSimple,
  sample_names: formatSampleNames,
  figure_ref_inconsistency: formatFigureRefInconsistency,
  symbol_table_inconsistency: formatSymbolTableInconsistency,
  symbol_mismatch_triples: formatSymbolMismatchTriples,
  title_prohibited_items: formatTitleProhibitedItems,
  paragraph_format_violations: formatParagraphFormatViolations,
}

// Fields whose formatter accepts a plain array (legacy shape).
const ARRAY_FORMATTER_FIELDS = new Set([
  "numerals_with_locations",
  "figures_with_locations",
  "paragraph_list",
  "figure_list",
  "claim_list",
  "paragraph_list_simple",
  "numeral_list",
  "claims",
  "paragraphs",
  "sample_names",
])

/**
 * Pre-render any structured fields in details_params, then call t().
 */
export function formatDetails(key, details_params, t) {
  if (!key) return ""
  if (!details_params) return t(key)

  const rendered = { ...details_params }
  for (const [field, formatter] of Object.entries(STRUCTURED_FORMATTERS)) {
    const value = details_params[field]
    if (value === undefined || value === null) continue
    if (ARRAY_FORMATTER_FIELDS.has(field)) {
      if (Array.isArray(value)) rendered[field] = formatter(value, t, details_params)
    } else {
      // Object-shaped payload
      if (typeof value === "object") rendered[field] = formatter(value, t, details_params)
    }
  }
  return t(key, rendered)
}
