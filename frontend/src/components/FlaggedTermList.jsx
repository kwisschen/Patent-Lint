// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
//
// Inline chip list for flagged tokens detected by walkers — restrictive
// wording, implied phrases, terminology leaks, commercial language, etc.
// Consumes a structured items payload (details_params.flagged_phrases) and
// renders each token as a small color-coded chip so the user sees WHICH
// specific token triggered the finding, rather than an opaque comma-joined
// string or placeholder example.
//
// Design: block-above-text. The chip row sits above the explanation
// paragraph so narrow viewports (mobile 375px) can wrap chips cleanly
// without splitting CJK characters mid-word. Each chip is a single token.
//
// Features:
// - Hover tooltip surfaces location when item.location is set
//   ("from paragraph 4", "from claim 8") — gives context without
//   cluttering the chip text.
// - Overflow truncation: cap at DEFAULT_MAX visible chips; render a
//   "+N more" badge when more exist. Prevents UI explosion on
//   heavily-flagged docs.
import { useTranslation } from 'react-i18next'
import { useState } from 'react'

const DEFAULT_MAX = 20

function chipTitle(item, t) {
  if (item?.location == null) return undefined
  const kind = item.kind || "phrase"
  // reference / header items come from structural checks where the location
  // is usually a claim id; phrase / term items come from paragraph-scoped
  // checks where the location is usually a paragraph id. Fall back to
  // "from claim N" when we can't tell.
  if (kind === "reference" || kind === "term" || kind === "header") {
    return t("chip.fromClaim", { n: item.location, defaultValue: `from claim ${item.location}` })
  }
  return t("chip.fromParagraph", { n: item.location, defaultValue: `from paragraph ${item.location}` })
}

export default function FlaggedTermList({ items, status = "verify", className = "", max = DEFAULT_MAX }) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState(false)
  if (!Array.isArray(items) || items.length === 0) return null

  const total = items.length
  const cap = expanded ? total : Math.min(max, total)
  const visible = items.slice(0, cap)
  const overflow = total - cap

  return (
    <div className={`flex flex-wrap gap-1 ${className}`.trim()}>
      {visible.map((item, idx) => {
        const title = chipTitle(item, t)
        return (
          <span
            key={`${item.token}-${idx}`}
            title={title}
            className="inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-medium leading-none border"
            style={{
              backgroundColor: `var(--${status}-bg)`,
              color: `var(--${status}-tag-text)`,
              borderColor: `var(--${status}-border)`,
            }}
          >
            {item.token}
          </span>
        )
      })}
      {overflow > 0 && (
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-medium leading-none border border-dashed hover:opacity-80 transition-opacity"
          style={{
            backgroundColor: "transparent",
            color: `var(--${status}-tag-text)`,
            borderColor: `var(--${status}-border)`,
          }}
        >
          {t("chip.more", { n: overflow, defaultValue: `+${overflow} more` })}
        </button>
      )}
    </div>
  )
}
