// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025-2026 Christopher Chen
//
// Reference-numeral conflicts, rendered as the table they always were.
//
// WHAT THIS REPLACED. The check flattened inherently tabular data into one
// run-on sentence and then printed nearly the same sentence again underneath:
//
//   5 reference numeral(s) with possibly inconsistent naming - please review.
//   Examples: #123: "auxiliary elastic structures" (5×), "auxiliary engaging
//   structures" (1×), "auxiliary engaging structure" (1×); #13: "two conductive
//   components" (34×), "two elastic clamping structures" (1×); #14: ... (+2 more)
//
// Nothing about that is scannable: the reader has to parse semicolons to find
// where one numeral ends and the next begins, and the counts - the single most
// useful signal, because a name used 34× against one used 1× tells you
// instantly which is the typo - are buried mid-sentence.
//
// The payload was already structured (`canonical` + `canonical_count` +
// `outliers[]`); only the presentation was prose. This renders it as a numeral
// column, its names ordered most-used first, and right-aligned tabular counts,
// so the 34-versus-1 contrast is visible without reading a word.
//
// It deliberately does NOT assert which name is correct. The dominant name is
// given normal weight and the rest are muted, which conveys the likelihood
// through ordering and count rather than through a verdict the checker is not
// entitled to make.
//
// Shapes supported (unchanged):
//   D1: { numeral, canonical, canonical_count, outliers: [{name, count}] }
//   D3 grouped: { name, numerals: [], refnum_count }
//   D3 legacy:  { numeral, name, occurrences }
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ChevronDown } from 'lucide-react'

const PREVIEW = 3

function Count({ n }) {
  if (n == null || n <= 0) return null
  return (
    <span className="shrink-0 tabular-nums text-[11px] text-muted-foreground/80">
      {n}&times;
    </span>
  )
}

/** One name + its count, as a row inside a numeral's group. */
function NameRow({ name, count, dominant }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className={dominant ? 'min-w-0 break-words' : 'min-w-0 break-words text-muted-foreground'}>
        {name}
      </span>
      <Count n={count} />
    </div>
  )
}

/** A numeral and every name used for it, most-used first. */
function NumeralGroup({ finding, status }) {
  // D1: canonical + outliers.
  if (finding.canonical !== undefined && Array.isArray(finding.outliers)) {
    const rows = [
      { name: finding.canonical, count: finding.canonical_count, dominant: true },
      ...finding.outliers.map((o) => ({ name: o.name, count: o.count, dominant: false })),
    ]
    return (
      <div className="flex gap-3 py-1.5">
        <span
          className="w-14 shrink-0 font-mono text-[11px] font-semibold"
          style={{ color: `var(--${status}-text)` }}
        >
          #{finding.numeral}
        </span>
        <div className="min-w-0 flex-1 space-y-0.5">
          {rows.map((r, i) => (
            <NameRow key={i} name={r.name} count={r.count} dominant={r.dominant} />
          ))}
        </div>
      </div>
    )
  }

  // D3 grouped: one name carrying several numerals.
  if (Array.isArray(finding.numerals)) {
    return (
      <div className="flex gap-3 py-1.5">
        <span
          className="w-14 shrink-0 font-mono text-[11px] font-semibold"
          style={{ color: `var(--${status}-text)` }}
        >
          {finding.numerals.join(', ')}
        </span>
        <div className="min-w-0 flex-1">
          <NameRow name={finding.name} count={finding.refnum_count > 1 ? finding.refnum_count : null} dominant />
        </div>
      </div>
    )
  }

  // D3 legacy: one numeral, one name.
  return (
    <div className="flex gap-3 py-1.5">
      <span
        className="w-14 shrink-0 font-mono text-[11px] font-semibold"
        style={{ color: `var(--${status}-text)` }}
      >
        #{finding.numeral}
      </span>
      <div className="min-w-0 flex-1">
        <NameRow name={finding.name} count={finding.occurrences} dominant />
      </div>
    </div>
  )
}

export default function NumeralFindingList({ findings, status = 'amend', className = '' }) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState(false)
  if (!Array.isArray(findings) || findings.length === 0) return null

  const total = findings.length
  // Previously this whole component only rendered above 3 findings, so a draft
  // with one or two conflicts got the run-on sentence and nothing else. The
  // table is the primary presentation now, so it always renders; only the
  // OVERFLOW is gated.
  const visible = expanded ? findings : findings.slice(0, PREVIEW)
  const hidden = total - visible.length

  return (
    <div className={`mt-1.5 text-xs ${className}`.trim()}>
      <div className="divide-y divide-border/40 rounded-md border border-border/40 px-2.5 py-0.5">
        {visible.map((f, i) => (
          <NumeralGroup key={i} finding={f} status={status} />
        ))}
      </div>
      {hidden > 0 && (
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="mt-1 inline-flex items-center gap-1 text-xs font-medium transition-opacity hover:opacity-80
                     focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 rounded"
          style={{ color: `var(--${status}-text)` }}
        >
          <ChevronDown className="h-3 w-3" />
          {t('numeralFindings.expand', { count: total })}
        </button>
      )}
      {expanded && total > PREVIEW && (
        <button
          type="button"
          onClick={() => setExpanded(false)}
          className="mt-1 inline-flex items-center gap-1 text-xs font-medium transition-opacity hover:opacity-80
                     focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 rounded"
          style={{ color: `var(--${status}-text)` }}
        >
          <ChevronDown className="h-3 w-3 rotate-180" />
          {t('numeralFindings.collapse')}
        </button>
      )}
    </div>
  )
}
