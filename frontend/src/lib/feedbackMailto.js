// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2025 Christopher Chen
/* global __BUILD_HASH__ */
import { toast } from 'sonner'

// Source of truth for the maintainer email; mirrors Footer.jsx:12.
const MAINTAINER_EMAIL = 'kwisschen@gmail.com'

// Shared toast id so rapid-fire reports don't stack — subsequent calls
// replace the existing confirmation instead of piling up.
const FEEDBACK_TOAST_ID = 'patentlint-feedback-confirmation'

// Coarse browser detection — major-family + version-family only. We don't
// fingerprint precisely; the goal is "Safari 18 / Chrome 13x / Firefox 14x"
// so a maintainer reading a stack of reports can spot browser-specific bugs.
function detectBrowser() {
  if (typeof navigator === 'undefined') return 'unknown'
  const ua = navigator.userAgent
  // Order matters: Edge UA contains Chrome; Chrome UA contains Safari.
  const families = [
    [/Edg\/(\d+)/, 'Edge'],
    [/Chrome\/(\d+)/, 'Chrome'],
    [/Firefox\/(\d+)/, 'Firefox'],
    [/Version\/(\d+).*Safari/, 'Safari'],
  ]
  for (const [pattern, name] of families) {
    const match = ua.match(pattern)
    if (match) return `${name} ${match[1]}`
  }
  return 'unknown'
}

function buildHash() {
  try {
    return __BUILD_HASH__
  } catch {
    return 'dev'
  }
}

// Compose a mailto: URL pre-filled with structured per-finding feedback.
// Caller passes the finding-specific fields; the util adds environment
// metadata + a localized plain-text scaffold encouraging the user to
// describe the issue without pasting draft text.
//
// finding: an object whose enumerable keys become "key: value" lines in
// the body. Pass only what's relevant to the surface — the util doesn't
// validate the shape.
//
// options.locale: IETF tag, used in the structured metadata only.
// options.bodyPlaceholder: localized instruction text shown to the user
//   in their email client after a separator. Always pass this from the
//   caller's `t('feedback.bodyPlaceholder')` — the util keeps the subject
//   line and metadata keys in English (for maintainer filtering) but the
//   part the user reads and replies to localizes to their UI language.
//
// Returns a fully URL-encoded mailto: string ready for window.location.href.
export function composeFeedbackMailto(finding, { locale, bodyPlaceholder } = {}) {
  const env = {
    browser: detectBrowser(),
    locale: locale || (typeof navigator !== 'undefined' ? navigator.language : 'unknown'),
    patentlint_build: buildHash(),
  }

  const checkKey = finding.check_key || 'unknown'
  const subject = `PatentLint finding report — ${checkKey}`

  const lines = []
  for (const [key, value] of Object.entries(finding)) {
    if (value === undefined || value === null || value === '') continue
    lines.push(`${key}: ${value}`)
  }
  for (const [key, value] of Object.entries(env)) {
    lines.push(`${key}: ${value}`)
  }

  const body = [
    lines.join('\n'),
    '',
    '---',
    '',
    bodyPlaceholder || '',
  ].join('\n')

  return `mailto:${MAINTAINER_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`
}

// Show the "Auto-filled in your email client for review. Your draft
// stayed put." confirmation toast. Persistent (duration: Infinity) with
// an X close button so users who tab-switch to their email client and
// come back still see the acknowledgment. Fixed id so rapid-fire reports
// replace the existing toast rather than stack.
export function showFeedbackToast(t) {
  toast(t('feedback.confirmation'), {
    id: FEEDBACK_TOAST_ID,
    duration: Infinity,
    closeButton: true,
  })
}
