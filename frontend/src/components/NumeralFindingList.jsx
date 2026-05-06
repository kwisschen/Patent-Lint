// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
//
// Expandable list of numeral-conflict findings — used by D1
// (numeralConsistency) and D3 (symbolTableCoverage). The check message
// caps inline preview at 3 entries with a "+N more" trailer; this
// component lets users expand and see ALL findings in a structured
// row layout so they can navigate every conflict, not just the
// top-3 sample.
//
// Two finding shapes are supported:
//   D1: { numeral, canonical, canonical_count, outliers: [{name, count}] }
//   D3: { numeral, name, occurrences }
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ChevronDown } from 'lucide-react'

const PREVIEW = 3

export default function NumeralFindingList({ findings, status = "amend", className = "" }) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState(false)
  if (!Array.isArray(findings) || findings.length === 0) return null
  const total = findings.length
  if (total <= PREVIEW) return null
  const remaining = total - PREVIEW

  return (
    <div className={`mt-1 ${className}`.trim()}>
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="inline-flex items-center gap-1 text-xs font-medium hover:opacity-80 transition-opacity"
        style={{ color: `var(--${status}-text)` }}
        aria-expanded={expanded}
      >
        <ChevronDown
          className={`h-3 w-3 transition-transform duration-150 ${expanded ? "rotate-180" : ""}`}
        />
        {expanded
          ? t("numeralFindings.collapse", { defaultValue: "Show fewer" })
          : t("numeralFindings.expand", {
              count: total,
              defaultValue: `Show all ${total} (+${remaining} more)`,
            })}
      </button>
      {expanded && (
        <ul className="mt-1.5 space-y-1 pl-4 text-xs text-muted-foreground">
          {findings.map((f, i) => {
            // D1 shape: { numeral, canonical, canonical_count, outliers }
            if (f.canonical !== undefined && Array.isArray(f.outliers)) {
              return (
                <li key={i}>
                  <span className="font-mono font-semibold">#{f.numeral}</span>
                  <span className="ml-2">
                    “{f.canonical}” ({f.canonical_count}×)
                  </span>
                  {f.outliers.map((o, j) => (
                    <span key={j} className="ml-1.5">
                      , “{o.name}” ({o.count}×)
                    </span>
                  ))}
                </li>
              )
            }
            // D3 grouped shape: { name, numerals: [], refnum_count, occurrences }
            if (Array.isArray(f.numerals)) {
              const nums = f.numerals.join(", ")
              return (
                <li key={i}>
                  {f.name && <span>“{f.name}”</span>}
                  <span className="ml-1 font-mono">({nums})</span>
                  {f.refnum_count > 1 && (
                    <span className="ml-1 opacity-70">
                      , {f.refnum_count} refnums
                    </span>
                  )}
                </li>
              )
            }
            // D3 legacy shape: { numeral, name, occurrences }
            return (
              <li key={i}>
                <span className="font-mono font-semibold">#{f.numeral}</span>
                {f.name && (
                  <span className="ml-2">“{f.name}”</span>
                )}
                {f.occurrences != null && (
                  <span className="ml-1 opacity-70">
                    ({f.occurrences}×)
                  </span>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
