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

export default function FlaggedTermList({ items, status = "verify" }) {
  if (!Array.isArray(items) || items.length === 0) return null
  return (
    <div className="mt-1 ml-10 sm:ml-[52px] flex flex-wrap gap-1">
      {items.map((item, idx) => (
        <span
          key={`${item.token}-${idx}`}
          className="inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-medium leading-none border"
          style={{
            backgroundColor: `var(--${status}-bg)`,
            color: `var(--${status}-tag-text)`,
            borderColor: `var(--${status}-border)`,
          }}
        >
          {item.token}
        </span>
      ))}
    </div>
  )
}
