// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025 Christopher Chen
import pdfMake from 'pdfmake/build/pdfmake'
import pdfFonts from 'pdfmake/build/vfs_fonts'

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

function statusColor(status) {
  return STATUS_COLORS[status?.toUpperCase()] || '#666666'
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
    const translated = t(item.message_key, { ...item.details_params, defaultValue: '' })
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

function buildTriagePanel(sections, t) {
  const content = [{ text: t('pdf.triage.title'), style: 'sectionHeader' }]

  for (const severity of ['amend', 'verify']) {
    const items = []
    for (const section of sections) {
      for (const item of section.items) {
        if (item.status === severity) {
          items.push({ item, sectionName: section.name })
        }
      }
    }

    const label = severity === 'amend' ? t('pdf.amend') : t('pdf.verify')
    const color = severity === 'amend' ? STATUS_COLORS.AMEND : STATUS_COLORS.VERIFY

    content.push({
      text: `${label} (${items.length})`,
      bold: true,
      color,
      fontSize: 11,
      margin: [0, 8, 0, 4],
    })

    for (const { item, sectionName } of items) {
      const heading = sanitizeText(translateMessage(item, t))
      content.push({
        text: `${heading} (${sectionName})`,
        fontSize: 10,
        margin: [8, 2, 0, 2],
      })
    }
  }

  return content
}

function buildPassSummary(sections, t) {
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
    {
      text: `${t('pdf.passedSummary.title')} (${totalCount})`,
      style: 'sectionHeader',
    },
  ]

  for (const group of passItems) {
    const headings = group.items.map((item) => sanitizeText(translateMessage(item, t))?.replace(/\.\s*$/, ''))
    content.push({
      text: [
        { text: `${group.sectionName}: `, bold: true, fontSize: 10 },
        { text: headings.join('; '), fontSize: 10 },
      ],
      margin: [0, 2, 0, 2],
    })
  }

  return content
}

function buildSectionChecks(sections, t) {
  if (!sections || sections.length === 0) return []

  const content = []
  for (const section of sections) {
    // Only AMEND then VERIFY — no PASS items in section details
    const amendItems = section.items.filter((c) => c.status === 'amend')
    const verifyItems = section.items.filter((c) => c.status === 'verify')
    const orderedItems = [...amendItems, ...verifyItems]
    if (orderedItems.length === 0) continue

    content.push({ text: section.name, style: 'sectionHeader' })
    for (const item of orderedItems) {
      const msg = sanitizeText(translateMessage(item, t))
      content.push({
        columns: [
          {
            width: 55,
            text: ` ${t(`status.${item.status}`)} `,
            bold: true,
            color: statusColor(item.status),
            fontSize: 9,
          },
          { width: '*', text: msg, fontSize: 10 },
        ],
        margin: [0, 3, 0, 3],
      })
      const detailText = item.details_key && t(item.details_key, item.details_params || {}) !== item.details_key
        ? t(item.details_key, item.details_params || {})
        : item.details
      if (detailText) {
        content.push({
          text: sanitizeText(detailText),
          fontSize: 9,
          color: '#555555',
          margin: [55, 0, 0, 4],
        })
      }
    }
  }
  return content
}

function buildClaimTable(claimTrees, t) {
  if (!claimTrees || claimTrees.length === 0) return []

  const content = [{ text: t('pdf.claimDependency'), style: 'sectionHeader' }]

  for (const group of claimTrees) {
    content.push({
      text: group.label,
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

  // Group by claim_id
  const grouped = {}
  for (const issue of issues) {
    const cid = String(issue.claim_id)
    if (!grouped[cid]) grouped[cid] = []
    grouped[cid].push(sanitizeText(issue.term))
  }

  const body = [
    [
      { text: t('pdf.claimNumber'), bold: true, fillColor: '#fef3c7', color: '#92400e' },
      { text: t('pdf.antecedentTerms'), bold: true, fillColor: '#fef3c7', color: '#92400e' },
    ],
  ]

  for (const cid of Object.keys(grouped).sort((a, b) => Number(a) - Number(b))) {
    body.push([
      { text: cid, fontSize: 9 },
      { text: sanitizeText(grouped[cid].join(', ')), fontSize: 9 },
    ])
  }

  return [
    { text: t('pdf.antecedentBasis'), style: 'sectionHeader' },
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

  // Group by claim_number
  const grouped = {}
  for (const ut of unsupportedTerms) {
    const cid = String(ut.claim_number)
    if (!grouped[cid]) grouped[cid] = []
    grouped[cid].push(sanitizeText(ut.phrase))
  }

  const body = [
    [
      { text: t('pdf.claimNumber'), bold: true, fillColor: '#fef3c7', color: '#92400e' },
      { text: t('pdf.specTerms'), bold: true, fillColor: '#fef3c7', color: '#92400e' },
    ],
  ]

  for (const cid of Object.keys(grouped).sort((a, b) => Number(a) - Number(b))) {
    body.push([
      { text: cid, fontSize: 9 },
      { text: sanitizeText(grouped[cid].join(', ')), fontSize: 9 },
    ])
  }

  return [
    { text: t('pdf.specSupport'), style: 'sectionHeader' },
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
  const filename = originalFilename || reportData.filename || 'report'
  const isCN = reportData.jurisdiction === 'CN'

  const sections = filterInternalChecks([
    { name: t('section.specification'), items: reportData.specification_checks || [] },
    { name: t('section.drawings'), items: reportData.drawings_checks || [] },
    { name: t('section.claims'), items: reportData.claims_checks || [] },
    { name: t('section.abstract'), items: reportData.abstract_checks || [] },
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
  // CN jurisdiction content contains simplified Chinese (section names, CNIPA refs)
  // regardless of UI language, so always load Noto Sans SC for CN reports.
  const isCjkLocale = !!CJK_FONT_URLS[language]
  const needsCjk = isCjkLocale || isCN
  const cjkLanguage = isCjkLocale ? language : (isCN ? 'zh-CN' : null)
  let cjkBase64 = null
  if (needsCjk && cjkLanguage) {
    try {
      cjkBase64 = await loadCjkFont(cjkLanguage)
    } catch {
      console.warn('CJK font unavailable (offline?) — falling back to default font')
    }
  }

  const docDefinition = {
    pageSize: 'LETTER',
    pageMargins: [40, 60, 40, 60],

    header: {
      text: t('pdf.header'),
      alignment: 'right',
      fontSize: 8,
      color: '#999999',
      margin: [0, 20, 40, 0],
    },

    footer: (currentPage, pageCount) => ({
      text: `Page ${currentPage} of ${pageCount}  ·  © 2025 Christopher Chen  ·  patentlint.com`,
      alignment: 'center',
      fontSize: 8,
      color: '#999999',
      margin: [0, 20, 0, 0],
    }),

    content: [
      { text: `${t('analysis.label')}: ${sanitizeText(filename)}`, style: 'title' },
      { text: `${dateStr}`, style: 'subtitle' },
      {
        text: t('pdf.securityNote'),
        style: 'securityNote',
      },

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
      {
        text: t('pdf.summaryStats'),
        style: 'sectionHeader',
      },
      {
        layout: 'lightHorizontalLines',
        margin: [0, 0, 0, 16],
        table: {
          widths: ['50%', '*'],
          body: [
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
              { text: t(isCN ? 'pdf.abstractCharCount' : 'pdf.abstractWordCount'), bold: true, color: '#555555', fontSize: 10 },
              { text: String(reportData.abstract_word_count ?? 0), fontSize: 10 },
            ],
          ],
        },
      },

      // Actionable triage panel
      ...buildTriagePanel(sections, t),

      // Per-section checks (AMEND then VERIFY, no PASS)
      ...buildSectionChecks(sections, t),

      // PASS summary
      ...buildPassSummary(sections, t),

      // Claim trees
      ...buildClaimTable(reportData.claim_trees, t),

      // Antecedent basis
      ...buildAntecedentBasis(reportData.antecedent_basis_issues, t),

      // Spec support
      ...buildSpecSupport(reportData.unsupported_terms, t),

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
      title: { fontSize: 18, bold: true, margin: [0, 0, 0, 8] },
      subtitle: { fontSize: 10, color: '#666666', margin: [0, 0, 0, 4] },
      securityNote: {
        fontSize: 8,
        color: '#16a34a',
        italics: true,
        margin: [0, 0, 0, 20],
      },
      sectionHeader: {
        fontSize: 14,
        bold: true,
        margin: [0, 20, 0, 8],
        color: '#1e293b',
      },
    },
    defaultStyle: {
      fontSize: 10,
      ...(needsCjk && cjkBase64 ? { font: 'CJK' } : {}),
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
