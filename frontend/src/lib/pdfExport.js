// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025–2026 Christopher Chen
/* global __BUILD_HASH__ */
import pdfMake from 'pdfmake/build/pdfmake'
import pdfFonts from 'pdfmake/build/vfs_fonts'
import { formatDetails } from './detailsFormatter'
import { CHECKS_RAW } from '../generated/stats'

// Register bundled Roboto fonts into pdfmake's internal VirtualFileSystem.
// In module/bundler context, vfs_fonts.js does NOT auto-register — we must
// call addVirtualFileSystem() explicitly (it calls fs.writeFileSync internally).
pdfMake.addVirtualFileSystem(pdfFonts)

/**
 * Replace Unicode glyphs that pdfmake's bundled Roboto font cannot render.
 * Applied to all dynamic/user-facing text before it enters pdfmake nodes.
 * CJK text is left intact — CJK fonts handle those glyphs.
 */
function sanitizeText(str) {
  if (!str) return str
  return String(str)
    .replace(/[←→➜➔]/g, '>')
    .replace(/[•▸▪■◆►▶]/g, '-')
    .replace(/[✓✔☑]/g, '[x]')
    .replace(/—/g, '--')
    .replace(/–/g, '-')
    .replace(/…/g, '...')
    .replace(/©/g, '(c)')
}

const STATUS_COLORS = {
  AMEND: '#dc2626',
  VERIFY: '#b45309',
  PASS: '#2563eb',
}

const STATUS_TINTS = {
  AMEND: '#fef2f2',
  VERIFY: '#fffbeb',
  PASS: '#eff6ff',
}

function statusColor(status) {
  return STATUS_COLORS[status?.toUpperCase()] || '#666666'
}

function statusTint(status) {
  return STATUS_TINTS[status?.toUpperCase()] || '#f8fafc'
}

// --- CJK font lazy-loading ---

const CJK_FONT_URLS = {
  'zh-TW': 'https://fonts.gstatic.com/s/notosanstc/v39/-nFuOG829Oofr2wohFbTp9ifNAn722rq0MXz76Cy_Co.ttf',
  'zh-CN': 'https://fonts.gstatic.com/s/notosanssc/v40/k3kCo84MPvpLmixcA63oeAL7Iqp5IZJF9bmaG9_FnYw.ttf',
  'ja': 'https://fonts.gstatic.com/s/notosansjp/v56/-F6jfjtqLzI2JPCgQBnw7HFyzSD-AsregP8VFBEj75s.ttf',
  'ko': 'https://fonts.gstatic.com/s/notosanskr/v39/PbyxFmXiEBPT4ITbgNA5Cgms3VYcOA-vvnIzzuoyeLQ.ttf',
}

// Module-level cache: { [language]: base64String }
const fontCache = {}

function arrayBufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i])
  }
  return btoa(binary)
}

async function loadCjkFont(language) {
  if (fontCache[language]) return fontCache[language]
  const url = CJK_FONT_URLS[language]
  if (!url) return null
  const response = await fetch(url)
  if (!response.ok) throw new Error(`Failed to fetch CJK font: ${response.status}`)
  const buffer = await response.arrayBuffer()
  const base64 = arrayBufferToBase64(buffer)
  fontCache[language] = base64
  return base64
}

export async function prefetchCjkFont(language) {
  try {
    await loadCjkFont(language)
  } catch {
    // Silent prefetch failure — will retry at save time
  }
}

// --- PDF content builders ---

function translateMessage(item, t) {
  if (item.message_key) {
    const translated = formatDetails(item.message_key, item.details_params, t)
    if (translated && translated !== item.message_key) return translated
  }
  return item.message
}

// message_keys for UI-internal checks — excluded from PDF entirely
const INTERNAL_CHECK_KEYS = new Set([
  'check.drawings.count',
  'check.spec.drawings',
  'check.claims.overview',
])

function filterInternalChecks(sections) {
  return sections.map((s) => ({
    ...s,
    items: s.items.filter((c) => !INTERNAL_CHECK_KEYS.has(c.message_key)),
  }))
}

// --- Shared presentation helpers ---

// Section header: title text + short colored accent line beneath. No
// frost band, no fill — relies on whitespace and the colored bar to
// read as a section break. Mirrors filing convention (paper +
// printed heading, no decorative chrome).
function accentedHeader(text, accentColor, fontName) {
  return {
    stack: [
      {
        text,
        fontSize: 14,
        bold: true,
        color: '#1e293b',
        margin: [0, 0, 0, 4],
        ...(fontName ? { font: fontName } : {}),
      },
      {
        canvas: [{ type: 'line', x1: 0, y1: 0, x2: 48, y2: 0, lineWidth: 2.5, lineColor: accentColor }],
      },
    ],
    margin: [0, 22, 0, 12],
    // Tagged so docDefinition.pageBreakBefore can detect orphan headers
    // (a header at the very bottom of a page with no body following) and
    // push them to the next page along with their content.
    headlineLevel: 1,
  }
}

// Compact filled pill showing the status label (AMEND / VERIFY).
// Solid status color background, white text, no rim border. lineHeight: 1
// prevents pdfmake's default leading from creating extra space below CJK
// glyphs (which fill the full em-square — without lineHeight: 1 the cell
// gets extra height from line-height that pushes the visual character
// to the top of the rectangle).
function statusPill(status, t, fontName) {
  const label = t(`status.${status}`)
  return {
    width: 'auto',
    table: {
      widths: ['auto'],
      body: [[
        {
          text: label,
          color: 'white',
          bold: true,
          fontSize: 8,
          lineHeight: 1,
          alignment: 'center',
          noWrap: true,
          ...(fontName ? { font: fontName } : {}),
        },
      ]],
    },
    layout: {
      hLineWidth: () => 0,
      vLineWidth: () => 0,
      fillColor: () => statusColor(status),
      paddingLeft: () => 7,
      paddingRight: () => 7,
      paddingTop: () => 4,
      paddingBottom: () => 4,
    },
  }
}

// Tinted chip for flagged terms (React FlaggedTermList parity). Light
// tint background, status-colored text, no rim border. Same lineHeight:
// 1 trick as statusPill so CJK glyphs center properly in the cell.
function termChip(token, status, fontName) {
  return {
    width: 'auto',
    table: {
      widths: ['auto'],
      body: [[
        {
          text: token,
          color: statusColor(status),
          bold: true,
          fontSize: 8,
          lineHeight: 1,
          alignment: 'center',
          noWrap: true,
          ...(fontName ? { font: fontName } : {}),
        },
      ]],
    },
    layout: {
      hLineWidth: () => 0,
      vLineWidth: () => 0,
      fillColor: () => statusTint(status),
      paddingLeft: () => 6,
      paddingRight: () => 6,
      paddingTop: () => 4,
      paddingBottom: () => 4,
    },
    margin: [0, 0, 4, 2],
  }
}

// Chip-row from details_params.flagged_phrases.items. pdfmake's columns
// layout flows chips horizontally; multi-row wrap on narrow PDF widths
// works because each chip is its own auto-sized column cell followed by a
// thin spacer. Returns null when there is nothing to render so callers can
// unconditionally spread the result.
// Capped at MAX_PDF_CHIPS to avoid overflowing the page width on
// heavily-flagged documents; overflow is denoted with a "+N more" chip
// (React parity; PDF can't expand interactively).
const MAX_PDF_CHIPS = 20

function flaggedPhrasesRow(details_params, status, t, fontName) {
  const items = details_params?.flagged_phrases?.items
  if (!Array.isArray(items) || items.length === 0) return null
  const total = items.length
  const cap = Math.min(MAX_PDF_CHIPS, total)
  const visible = items.slice(0, cap)
  const overflow = total - cap
  const chips = visible.map((item) => termChip(item.token, status, fontName))
  if (overflow > 0) {
    chips.push(termChip(t('chip.more', { n: overflow, defaultValue: `+${overflow} more` }), status, fontName))
  }
  return {
    columns: [
      { width: 60, text: '' },
      {
        width: '*',
        columns: chips,
        columnGap: 0,
      },
    ],
    margin: [0, 2, 0, 2],
  }
}

// Numeral-conflict findings list for D1 / D3 — when there are more than
// 3 findings, the inline message shows only top-3 + "(+N more)" trailer.
// PDF readers can't click to expand, so we render the FULL list as
// indented rows below the message line. Each row: numeral + name(s).
const MAX_PDF_FINDINGS = 30

function numeralFindingsRow(details_params, status, fontName) {
  const findings = details_params?.findings
  if (!Array.isArray(findings) || findings.length <= 3) return null
  const total = findings.length
  const cap = Math.min(MAX_PDF_FINDINGS, total)
  const visible = findings.slice(0, cap)
  const accent = statusColor(status)
  const lines = visible.map((f) => {
    // D1 shape: { numeral, canonical, canonical_count, outliers }
    if (f.canonical !== undefined && Array.isArray(f.outliers)) {
      const canonCount = (f.canonical_count != null && f.canonical_count > 0)
        ? ` (${f.canonical_count}×)` : ""
      let body = ` "${f.canonical}"${canonCount}`
      for (const o of f.outliers) {
        const oCount = (o.count != null && o.count > 0) ? ` (${o.count}×)` : ""
        body += `, "${o.name}"${oCount}`
      }
      return {
        text: [
          { text: `#${f.numeral}`, color: accent, bold: true, fontSize: 9 },
          { text: body, color: "#475569", fontSize: 9 },
        ],
        ...(fontName ? { font: fontName } : {}),
      }
    }
    // D3 grouped shape: { name, numerals: [], refnum_count }
    if (Array.isArray(f.numerals)) {
      const nums = f.numerals.join(", ")
      const tail = f.refnum_count > 1 ? `, ${f.refnum_count} refnums` : ""
      return {
        text: [
          { text: f.name ? `"${f.name}"` : "", color: accent, bold: true, fontSize: 9 },
          { text: ` (${nums}${tail})`, color: "#475569", fontSize: 9 },
        ],
        ...(fontName ? { font: fontName } : {}),
      }
    }
    // D3 legacy shape: { numeral, name, occurrences }
    let body = ""
    if (f.name) {
      body = ` "${f.name}"`
      if (f.occurrences != null) body += ` (${f.occurrences}×)`
    }
    return {
      text: [
        { text: `#${f.numeral}`, color: accent, bold: true, fontSize: 9 },
        { text: body, color: "#475569", fontSize: 9 },
      ],
      ...(fontName ? { font: fontName } : {}),
    }
  })
  if (total > cap) {
    lines.push({
      text: `… +${total - cap} more`,
      color: "#94a3b8",
      fontSize: 9,
      italics: true,
      ...(fontName ? { font: fontName } : {}),
    })
  }
  return {
    columns: [
      { width: 60, text: "" },
      { width: "*", stack: lines, margin: [0, 2, 0, 2] },
    ],
    margin: [0, 2, 0, 2],
  }
}

// Two-cell callout card: 3pt colored strip + tinted content. Used for the
// AMEND / VERIFY triage groups. Renders "— None" for an empty group.
function triageCard(severity, items, t, fontName) {
  const label = severity === 'amend' ? t('pdf.amend') : t('pdf.verify')
  const accent = statusColor(severity)
  const bg = statusTint(severity)

  const header = {
    text: [
      { text: label, color: accent, bold: true, fontSize: 11 },
      { text: `  (${items.length})`, color: '#64748b', fontSize: 10 },
    ],
    margin: [0, 0, 0, items.length === 0 ? 0 : 6],
    ...(fontName ? { font: fontName } : {}),
  }

  let bodyContent
  if (items.length === 0) {
    bodyContent = [{
      text: '—',
      italics: true,
      color: '#94a3b8',
      fontSize: 10,
      margin: [0, 4, 0, 0],
      ...(fontName ? { font: fontName } : {}),
    }]
  } else {
    // Aggregate consecutive same-message_key items so the PDF doesn't
    // render N near-identical rows for one check that fired N times.
    // First occurrence renders the full message + section; subsequent
    // matches collapse into a "+N similar findings" tail. Web keeps
    // per-finding rows (chips give per-finding context); PDF favors
    // compactness because a static doc can't be expanded.
    const groups = []
    let lastKey = null
    let lastGroup = null
    items.forEach(({ item, sectionName }) => {
      const key = item.message_key || `__nokey__${groups.length}`
      if (key === lastKey && lastGroup) {
        lastGroup.duplicates.push({ item, sectionName })
      } else {
        lastGroup = { item, sectionName, duplicates: [] }
        groups.push(lastGroup)
        lastKey = key
      }
    })

    bodyContent = groups.flatMap(({ item, sectionName, duplicates }) => {
      const heading = sanitizeText(translateMessage(item, t))
      const result = [{
        text: [
          { text: '\u2022  ', color: accent, bold: true },
          { text: heading, color: '#1e293b' },
          { text: `   \u2014 ${sectionName}`, color: '#64748b', italics: true, fontSize: 9 },
        ],
        fontSize: 10,
        margin: [0, 2, 0, 2],
        ...(fontName ? { font: fontName } : {}),
      }]
      if (duplicates.length > 0) {
        result.push({
          text: t('pdf.similarFindings', {
            count: duplicates.length,
            defaultValue: `   + ${duplicates.length} similar finding${duplicates.length === 1 ? '' : 's'} on the same check`,
          }),
          color: '#94a3b8',
          italics: true,
          fontSize: 9,
          margin: [12, 0, 0, 4],
          ...(fontName ? { font: fontName } : {}),
        })
      }
      return result
    })
  }

  return {
    table: {
      widths: [3, '*'],
      body: [[
        { text: '', fillColor: accent },
        { stack: [header, ...bodyContent], fillColor: bg, margin: [12, 10, 12, 10] },
      ]],
    },
    layout: {
      hLineWidth: () => 0,
      vLineWidth: () => 0,
      paddingLeft: () => 0,
      paddingRight: () => 0,
      paddingTop: () => 0,
      paddingBottom: () => 0,
    },
    margin: [0, 0, 0, 10],
  }
}

// --- Main section builders ---

function buildTriagePanel(sections, t, fontName) {
  const groups = { amend: [], verify: [] }
  for (const section of sections) {
    for (const item of section.items) {
      if (groups[item.status]) {
        groups[item.status].push({ item, sectionName: section.name })
      }
    }
  }

  const content = [accentedHeader(t('pdf.triage.title'), STATUS_COLORS.AMEND, fontName)]
  content.push(triageCard('amend', groups.amend, t, fontName))
  content.push(triageCard('verify', groups.verify, t, fontName))
  return content
}

function buildPassSummary(sections, t, fontName) {
  const passItems = []
  for (const section of sections) {
    const passed = section.items.filter((c) => c.status === 'pass')
    if (passed.length > 0) {
      passItems.push({ sectionName: section.name, items: passed })
    }
  }

  const totalCount = passItems.reduce((sum, g) => sum + g.items.length, 0)
  if (totalCount === 0) return []

  const content = [
    accentedHeader(`${t('pdf.passedSummary.title')} (${totalCount})`, '#16a34a', fontName),
  ]

  for (const group of passItems) {
    const headings = group.items.map((item) => sanitizeText(translateMessage(item, t)))
    content.push({
      stack: [
        {
          text: group.sectionName,
          bold: true,
          fontSize: 10,
          color: '#334155',
          margin: [0, 6, 0, 2],
          ...(fontName ? { font: fontName } : {}),
        },
        {
          ul: headings.map((h) => ({
            text: h,
            fontSize: 9,
            color: '#475569',
            ...(fontName ? { font: fontName } : {}),
          })),
          color: '#94a3b8',
          margin: [6, 0, 0, 0],
        },
      ],
    })
  }

  return content
}

function buildSectionChecks(sections, t, fontName) {
  if (!sections || sections.length === 0) return []

  const content = []
  for (const section of sections) {
    // Only AMEND then VERIFY — no PASS items in section details
    const amendItems = section.items.filter((c) => c.status === 'amend')
    const verifyItems = section.items.filter((c) => c.status === 'verify')
    const orderedItems = [...amendItems, ...verifyItems]
    if (orderedItems.length === 0) continue

    content.push(accentedHeader(section.name, '#3b82f6', fontName))

    orderedItems.forEach((item, idx) => {
      const msg = sanitizeText(translateMessage(item, t))
      content.push({
        columns: [
          statusPill(item.status, t, fontName),
          {
            width: '*',
            text: msg,
            fontSize: 10,
            color: '#1e293b',
            margin: [8, 2, 0, 0],
            ...(fontName ? { font: fontName } : {}),
          },
        ],
        columnGap: 0,
        margin: [0, 4, 0, 2],
      })
      const chipRow = flaggedPhrasesRow(item.details_params, item.status, t, fontName)
      if (chipRow) {
        content.push(chipRow)
      }
      if (item.message_key && (item.message_key.includes("numeralConsistency")
          || item.message_key.includes("symbolTableCoverage"))) {
        const findingsRow = numeralFindingsRow(item.details_params, item.status, fontName)
        if (findingsRow) content.push(findingsRow)
      }
      const detailText = item.details_key && formatDetails(item.details_key, item.details_params, t) !== item.details_key
        ? formatDetails(item.details_key, item.details_params, t)
        : item.details
      if (detailText) {
        content.push({
          text: sanitizeText(detailText),
          fontSize: 9,
          color: '#64748b',
          margin: [60, 2, 0, 4],
          ...(fontName ? { font: fontName } : {}),
        })
      }
      if (idx < orderedItems.length - 1) {
        content.push({
          canvas: [{ type: 'line', x1: 0, y1: 0, x2: 515, y2: 0, lineWidth: 0.5, lineColor: '#f1f5f9' }],
          margin: [0, 4, 0, 0],
        })
      }
    })
  }
  return content
}

// Map a letter grade to a color. Matches the web hero (--pass-border /
// --verify-border / --amend-border on light mode); PDFs don't have a
// dark mode, so light-mode hex values are canonical.
function gradeColor(letter) {
  if (!letter || letter === '—') return '#6b7280'
  if (letter.startsWith('A')) return '#2563eb'  // blue, web pass-border
  if (letter.startsWith('B') || letter.startsWith('C')) return '#16a34a'  // green, verify-border
  return '#dc2626'  // D / F red, amend-border
}

// Standard US 12-tier letter map (no A+, matches rubric.py letter_for_score).
function letterFromScore(score, applicable) {
  if (!applicable) return null
  if (score >= 93) return 'A'
  if (score >= 90) return 'A-'
  if (score >= 87) return 'B+'
  if (score >= 83) return 'B'
  if (score >= 80) return 'B-'
  if (score >= 77) return 'C+'
  if (score >= 73) return 'C'
  if (score >= 70) return 'C-'
  if (score >= 67) return 'D+'
  if (score >= 63) return 'D'
  if (score >= 60) return 'D-'
  return 'F'
}

// Cover treatment: NO container/wrapper around the rubric. Letter grade
// sits cleanly on the page (filing-cover-sheet convention — paper +
// printed letter, nothing else). Section grades render as an inline
// "label letter" row separated by mid-dots; the letter itself carries
// the tier color, no boxes around individual pills. Cleaner than the
// previous bordered-chip-row treatment, prints sharp.
function buildRubricCover(rubricGrade, t, fontName) {
  if (!rubricGrade) return []
  const fontProp = fontName ? { font: fontName } : {}

  // Completeness gate: no grade emitted, surface the gap.
  if (rubricGrade.completeness_gap?.missing_sections?.length) {
    const labels = rubricGrade.completeness_gap.missing_sections.map((s) =>
      t(`rubric.section.${s}`, { defaultValue: s })
    )
    return [
      {
        text: t('rubric.completenessGate.title'),
        fontSize: 18,
        bold: true,
        color: '#b91c1c',
        alignment: 'center',
        margin: [0, 16, 0, 6],
        ...fontProp,
      },
      {
        text: t('rubric.completenessGate.missingSections', { sections: labels.join(', ') }),
        fontSize: 11,
        color: '#4b5563',
        alignment: 'center',
        margin: [0, 0, 0, 18],
        ...fontProp,
      },
    ]
  }

  const letter = rubricGrade.letter || '—'
  const score = rubricGrade.score ?? 0
  const cover = [
    {
      text: letter,
      fontSize: 64,
      bold: true,
      lineHeight: 1,
      color: gradeColor(letter),
      alignment: 'center',
      margin: [0, 4, 0, 0],
      ...fontProp,
    },
    {
      text: `${score} / 100`,
      fontSize: 12,
      color: '#4b5563',
      alignment: 'center',
      margin: [0, 2, 0, 0],
      ...fontProp,
    },
    {
      text: t('rubric.trust.line'),
      fontSize: 9,
      italics: true,
      color: '#64748b',
      alignment: 'center',
      margin: [0, 8, 0, 0],
      ...fontProp,
    },
  ]

  // Section grades: inline `label letter` pairs separated by mid-dots.
  // Renders as one centered text line; each letter colored by tier.
  if (rubricGrade.section_grades?.length) {
    const inlineParts = []
    rubricGrade.section_grades.forEach((sg, idx) => {
      const sLetter = letterFromScore(sg.score, sg.applicable)
      const sectionLabel = t(`rubric.section.${sg.section}`, { defaultValue: sg.section })
      const isNa = !sg.applicable
      const letterText = isNa ? t('rubric.section.notApplicable') : sLetter
      const letterColor = isNa ? '#9ca3af' : gradeColor(sLetter)
      if (idx > 0) {
        inlineParts.push({ text: '  ·  ', color: '#cbd5e1', ...fontProp })
      }
      inlineParts.push({ text: `${sectionLabel} `, color: '#64748b', ...fontProp })
      inlineParts.push({ text: letterText, bold: true, color: letterColor, ...fontProp })
    })
    cover.push({
      text: inlineParts,
      fontSize: 9.5,
      alignment: 'center',
      margin: [0, 10, 0, 0],
    })
  }

  cover.push({
    text: t('rubric.version', { version: rubricGrade.rubric_version || '1.0', count: CHECKS_RAW }),
    fontSize: 7,
    color: '#9ca3af',
    alignment: 'center',
    margin: [0, 8, 0, 12],
    ...fontProp,
  })

  return cover
}

function buildClaimTable(claimTrees, t) {
  if (!claimTrees || claimTrees.length === 0) return []

  const content = [accentedHeader(t('pdf.claimDependency'), '#64748b', undefined)]

  const labelKey = (label) => label === 'Method Claims'
    ? 'tree.methodClaims'
    : label === 'Claims'
      ? 'tree.claims'
      : 'tree.apparatusClaims'

  for (const group of claimTrees) {
    content.push({
      text: t(labelKey(group.label)),
      bold: true,
      fontSize: 12,
      margin: [0, 10, 0, 6],
      color: '#1e293b',
    })

    const body = [
      [
        { text: t('pdf.claimNumber'), bold: true, fillColor: '#f3f4f6' },
        { text: t('pdf.claimType'), bold: true, fillColor: '#f3f4f6' },
        { text: t('pdf.dependencyChain'), bold: true, fillColor: '#f3f4f6' },
        { text: t('pdf.claimText'), bold: true, fillColor: '#f3f4f6' },
      ],
    ]

    for (const row of group.rows) {
      const text = sanitizeText(row.claim_text || '')
      const truncated = text.length > 100 ? text.slice(0, 100) + '...' : text
      body.push([
        { text: String(row.claim_id), fontSize: 9 },
        { text: row.claim_type, fontSize: 9 },
        { text: sanitizeText(row.chain), fontSize: 9 },
        { text: truncated, fontSize: 8, color: '#555555' },
      ])
    }

    content.push({
      table: {
        headerRows: 1,
        widths: [35, 65, 'auto', '*'],
        body,
      },
      layout: {
        hLineWidth: () => 0.5,
        vLineWidth: () => 0.5,
        hLineColor: () => '#d1d5db',
        vLineColor: () => '#d1d5db',
      },
    })
  }
  return content
}

function buildAntecedentBasis(issues, t) {
  if (!issues || issues.length === 0) return []

  // Group by claim_id; preserve per-finding hints (suggested_match, cross_ref)
  // for an inline hint cell rendered below the term cell.
  const grouped = {}
  for (const issue of issues) {
    const cid = String(issue.claim_id)
    if (!grouped[cid]) grouped[cid] = []
    grouped[cid].push(issue)
  }

  const body = [
    [
      { text: t('pdf.claimNumber'), bold: true, fillColor: '#fef3c7', color: '#92400e' },
      { text: t('pdf.antecedentTerms'), bold: true, fillColor: '#fef3c7', color: '#92400e' },
    ],
  ]

  for (const cid of Object.keys(grouped).sort((a, b) => Number(a) - Number(b))) {
    const findings = grouped[cid]
    const termsText = sanitizeText(
      findings.map((f) => f.reference_form || f.term).join(', ')
    )
    const hintLines = []
    for (const f of findings) {
      if (f.suggested_match) {
        hintLines.push(
          sanitizeText(
            t('antecedent.didYouMean', {
              term: f.suggested_match.term,
              claim_id: f.suggested_match.claim_id,
            })
          )
        )
      }
      if (f.cross_ref === 'spec_support') {
        hintLines.push(sanitizeText(t('antecedent.crossRefSpecSupport')))
      }
    }

    const cellStack = [{ text: termsText, fontSize: 9 }]
    if (hintLines.length > 0) {
      cellStack.push({
        text: hintLines.join('\n'),
        fontSize: 8,
        italics: true,
        color: '#92400e',
        margin: [0, 2, 0, 0],
      })
    }
    body.push([
      { text: cid, fontSize: 9 },
      { stack: cellStack },
    ])
  }

  return [
    accentedHeader(t('pdf.antecedentBasis'), '#f59e0b', undefined),
    {
      text: t('antecedentBasis.disclaimer'),
      fontSize: 8,
      italics: true,
      color: '#6b7280',
      margin: [0, 0, 0, 6],
    },
    {
      table: {
        headerRows: 1,
        widths: [50, '*'],
        body,
      },
      layout: {
        hLineWidth: () => 0.5,
        vLineWidth: () => 0.5,
        hLineColor: () => '#fcd34d',
        vLineColor: () => '#fcd34d',
      },
    },
  ]
}

function buildSpecSupport(unsupportedTerms, t) {
  if (!unsupportedTerms || unsupportedTerms.length === 0) return []

  // Group by claim_number; track whether any finding in the group carries
  // a cross-reference hint to the antecedent-basis card.
  const grouped = {}
  const hasCrossRef = {}
  for (const ut of unsupportedTerms) {
    const cid = String(ut.claim_number)
    if (!grouped[cid]) grouped[cid] = []
    grouped[cid].push(sanitizeText(ut.phrase))
    if (ut.cross_ref === 'antecedent') {
      hasCrossRef[cid] = true
    }
  }

  const body = [
    [
      { text: t('pdf.claimNumber'), bold: true, fillColor: '#fef3c7', color: '#92400e' },
      { text: t('pdf.specTerms'), bold: true, fillColor: '#fef3c7', color: '#92400e' },
    ],
  ]

  for (const cid of Object.keys(grouped).sort((a, b) => Number(a) - Number(b))) {
    const cellStack = [{ text: grouped[cid].join(', '), fontSize: 9 }]
    if (hasCrossRef[cid]) {
      cellStack.push({
        text: sanitizeText(t('specSupport.crossRefAntecedent')),
        fontSize: 8,
        italics: true,
        color: '#92400e',
        margin: [0, 2, 0, 0],
      })
    }
    body.push([
      { text: cid, fontSize: 9 },
      { stack: cellStack },
    ])
  }

  return [
    accentedHeader(t('pdf.specSupport'), '#f59e0b', undefined),
    {
      text: t('antecedentBasis.disclaimer'),
      fontSize: 8,
      italics: true,
      color: '#6b7280',
      margin: [0, 0, 0, 6],
    },
    {
      table: {
        headerRows: 1,
        widths: [50, '*'],
        body,
      },
      layout: {
        hLineWidth: () => 0.5,
        vLineWidth: () => 0.5,
        hLineColor: () => '#fcd34d',
        vLineColor: () => '#fcd34d',
      },
    },
  ]
}

// --- Main export ---

export async function downloadReport(reportData, t, language, originalFilename) {
  const { getJurisdictionConfig } = await import('./jurisdictionConfig.js')
  const jConfig = getJurisdictionConfig(reportData.jurisdiction)
  const filename = originalFilename || reportData.filename || 'report'

  const sections = filterInternalChecks([
    { name: t(jConfig.specSectionKey), items: reportData.specification_checks || [] },
    { name: t(jConfig.drawingsSectionKey), items: reportData.drawings_checks || [] },
    { name: t(jConfig.claimsSectionKey), items: reportData.claims_checks || [] },
    { name: t(jConfig.abstractSectionKey), items: reportData.abstract_checks || [] },
  ])

  const now = new Date()
  const dateStr = now.toLocaleDateString(language === 'en' ? 'en-US' : language, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })

  const pdfFilename = `patentlint-${filename}.pdf`

  // Load CJK font if needed (font fetch happens before docDefinition is built).
  // CN → always SC (superset covering simplified+traditional).
  // TW → locale-aware: zh-TW→TC, zh-CN→SC, ja→JP, ko→KR, en→TC (for TIPO terms).
  // US → locale-based selection for CJK UI languages.
  const isCjkLocale = !!CJK_FONT_URLS[language]
  const needsCjk = isCjkLocale || !!jConfig.cjkFont
  const cjkLanguage = (jConfig.cjkFont && !jConfig.cjkFontLocaleAware)
    ? jConfig.cjkFont
    : (isCjkLocale ? language : jConfig.cjkFont)
  let cjkBase64 = null
  if (needsCjk && cjkLanguage) {
    try {
      cjkBase64 = await loadCjkFont(cjkLanguage)
    } catch {
      console.warn('CJK font unavailable (offline?) — falling back to default font')
    }
  }

  const fontName = needsCjk && cjkBase64 ? 'CJK' : undefined

  const docDefinition = {
    pageSize: 'LETTER',
    pageMargins: [40, 60, 40, 60],

    header: {
      text: t(jConfig.pdfHeaderKey),
      alignment: 'right',
      fontSize: 8,
      color: '#999999',
      margin: [0, 20, 40, 0],
      ...(fontName ? { font: fontName } : {}),
    },

    footer: (currentPage, pageCount) => {
      const year = new Date().getFullYear()
      const copyrightRange = year > 2025 ? `2025–${year}` : '2025'
      return {
        stack: [
          { text: 'Generated by PatentLint  ·  patentlint.com', alignment: 'center', fontSize: 8, color: '#999999' },
          { text: `© ${copyrightRange} Christopher Chen  ·  Page ${currentPage} of ${pageCount}  ·  Build ${__BUILD_HASH__.slice(0, 8)}`, alignment: 'center', fontSize: 8, color: '#999999', margin: [0, 2, 0, 0] },
        ],
        margin: [0, 16, 0, 0],
        ...(fontName ? { font: fontName } : {}),
      }
    },

    content: [
      { text: `${t('analysis.label')}: ${sanitizeText(filename)}`, style: 'title' },
      { text: `${dateStr}`, style: 'subtitle' },
      {
        text: t('pdf.securityNote'),
        style: 'securityNote',
      },

      // Rubric cover (grade letter + section-grade table) — appears
      // before the rest of the report so the grade is the headline.
      ...buildRubricCover(reportData.rubric_grade, t, fontName),

      // Non-patent warning (if applicable)
      ...(reportData.likely_patent === false ? [
        {
          text: `${sanitizeText(t('results.nonPatentWarning'))}`,
          bold: true,
          fontSize: 12,
          color: '#b45309',
          margin: [0, 0, 0, 4],
        },
        {
          text: sanitizeText(t('results.nonPatentWarningDetails')),
          fontSize: 9,
          color: '#92400e',
          margin: [0, 0, 0, 16],
          italics: true,
        },
      ] : []),

      // Summary stats
      accentedHeader(t('pdf.summaryStats'), '#64748b', fontName),
      {
        layout: 'lightHorizontalLines',
        margin: [0, 0, 0, 16],
        table: {
          widths: ['50%', '*'],
          body: [
            ...(jConfig.showPatentType ? [[
              { text: t('pdf.patentType'), bold: true, color: '#555555', fontSize: 10 },
              { text: reportData.patent_type === 'UTILITY_MODEL' ? t('summary.patentTypeUtilityModel') : t('summary.patentTypeInvention'), fontSize: 10 },
            ]] : []),
            [
              { text: t('pdf.specParagraphs'), bold: true, color: '#555555', fontSize: 10 },
              { text: String(reportData.paragraph_count ?? 0), fontSize: 10 },
            ],
            [
              { text: t('pdf.totalClaims'), bold: true, color: '#555555', fontSize: 10 },
              {
                text: `${reportData.total_claims ?? 0} (${reportData.independent_count ?? 0} ${t('pdf.independent')}, ${reportData.dependent_count ?? 0} ${t('pdf.dependent')})`,
                fontSize: 10,
              },
            ],
            [
              { text: t('pdf.figures'), bold: true, color: '#555555', fontSize: 10 },
              { text: String(reportData.figure_count ?? 0), fontSize: 10 },
            ],
            [
              { text: t(jConfig.pdfAbstractKey), bold: true, color: '#555555', fontSize: 10 },
              { text: String(reportData.abstract_word_count ?? 0), fontSize: 10 },
            ],
          ],
        },
      },

      // Actionable triage panel
      ...buildTriagePanel(sections, t, fontName),

      // Per-section checks (AMEND then VERIFY, no PASS)
      ...buildSectionChecks(sections, t, fontName),

      // PASS summary
      ...buildPassSummary(sections, t, fontName),

      // Antecedent basis
      ...buildAntecedentBasis(reportData.antecedent_basis_issues, t),

      // Spec support
      ...buildSpecSupport(reportData.unsupported_terms, t),

      // Claim-dependency table intentionally omitted from PDF — the
      // dependency structure is already conveyed by claim text itself
      // ("如請求項N所述" prefixes), and a static table can't be expanded
      // like the web ClaimTree. The web version stays interactive; the
      // PDF stays focused on findings, not duplicated reference data.

      // Disclaimer
      {
        text: t('pdf.disclaimer'),
        fontSize: 8,
        color: '#999999',
        alignment: 'center',
        margin: [0, 30, 0, 0],
      },
    ],

    styles: {
      title: { fontSize: 18, bold: true, margin: [0, 0, 0, 8], ...(fontName ? { font: fontName } : {}) },
      subtitle: { fontSize: 10, color: '#666666', margin: [0, 0, 0, 4], ...(fontName ? { font: fontName } : {}) },
      securityNote: {
        fontSize: 8,
        color: '#16a34a',
        italics: true,
        margin: [0, 0, 0, 20],
        ...(fontName ? { font: fontName } : {}),
      },
      sectionHeader: {
        fontSize: 14,
        bold: true,
        margin: [0, 20, 0, 8],
        color: '#1e293b',
        ...(fontName ? { font: fontName } : {}),
      },
    },
    defaultStyle: {
      fontSize: 10,
      lineHeight: 1.4,
      ...(fontName ? { font: fontName } : {}),
    },
    // Push orphan section headers to the next page. accentedHeader
    // tags itself with headlineLevel: 1 — when such a node has no
    // following nodes on the same page, force a break before it so
    // the header travels with its body content rather than sitting
    // alone at the bottom of a page.
    pageBreakBefore: function(currentNode, followingNodesOnPage) {
      if (currentNode.headlineLevel === 1 && followingNodesOnPage.length === 0) {
        return true
      }
      return false
    },
  }

  if (needsCjk && cjkBase64) {
    const vfsName = 'NotoSansCJK.ttf'

    // Write CJK font data into pdfmake's internal VirtualFileSystem
    pdfMake.addVirtualFileSystem({ [vfsName]: cjkBase64 })

    // Register CJK font family alongside Roboto
    pdfMake.addFonts({
      CJK: {
        normal: vfsName,
        bold: vfsName,
        italics: vfsName,
        bolditalics: vfsName,
      },
    })
  }

  pdfMake.createPdf(docDefinition).download(pdfFilename)
}
