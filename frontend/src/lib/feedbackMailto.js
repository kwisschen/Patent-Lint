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
//
// iOS variants come first because Apple requires all iOS browsers to use
// WebKit — the UA reports CriOS / FxiOS / EdgiOS instead of Chrome /
// Firefox / Edg, and they all end with "Safari/". Without iOS-specific
// patterns, iPhone Chrome would fall through to "unknown" (no Chrome
// token, no Version/Safari token).
function detectBrowser() {
  if (typeof navigator === 'undefined') return 'unknown'
  const ua = navigator.userAgent
  const families = [
    [/CriOS\/(\d+)/, 'Chrome iOS'],
    [/FxiOS\/(\d+)/, 'Firefox iOS'],
    [/EdgiOS\/(\d+)/, 'Edge iOS'],
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

// Human-readable label for each known metadata key. Keys not in this
// map pass through as-is (so callers can add new fields without this
// util needing updates — they just get the raw key as the label).
const FIELD_LABELS = {
  check_key: 'Check',
  message: 'Message',
  details: 'Details',
  status: 'Status',
  claim_id: 'Claim',
  terms: 'Terms',
  phrases: 'Phrases',
  reference_form: 'Reference form',
  jurisdiction: 'Jurisdiction',
  browser: 'Browser',
  locale: 'Locale',
  patentlint_build: 'Build',
}

// Pad labels in a section so values align in a monospace mail client.
// Aligns to the longest label + 2 spaces.
function formatSection(entries) {
  const rows = Object.entries(entries).filter(
    ([, value]) => value !== undefined && value !== null && value !== '',
  )
  if (rows.length === 0) return ''
  const maxLabel = Math.max(
    ...rows.map(([key]) => (FIELD_LABELS[key] || key).length),
  )
  return rows
    .map(([key, value]) => {
      const label = FIELD_LABELS[key] || key
      const padded = label.padEnd(maxLabel + 2, ' ')
      return `${padded}${value}`
    })
    .join('\n')
}

// Compose a mailto: URL pre-filled with a per-finding feedback email.
// Finding fields + environment metadata are merged into one aligned
// data block — field labels make the structure obvious without needing
// section-header decoration, and merging the blocks keeps the URL short
// enough to survive Gmail web-handler compose-URL length limits and
// other protocol-handler quirks. Professional framing comes from a
// localized greeting + closing around the data.
//
// finding: an object whose enumerable keys become "Label: value" lines.
// Pass only what's relevant to the surface.
//
// Subject line stays English so the maintainer's inbox can filter
// consistently across locales: "PatentLint finding report — {check_key}".
//
// Returns a fully URL-encoded mailto: string.
export function composeFeedbackMailto(finding, t, { locale } = {}) {
  const env = {
    browser: detectBrowser(),
    locale: locale || (typeof navigator !== 'undefined' ? navigator.language : 'unknown'),
    patentlint_build: buildHash(),
  }

  const checkKey = finding.check_key || 'unknown'
  const subject = `PatentLint finding report — ${checkKey}`

  // Merge finding + env into a single aligned block. The FIELD_LABELS
  // map above turns raw keys into human-readable column 1; formatSection
  // pads to the longest label so everything aligns in monospace mail.
  const dataSection = formatSection({ ...finding, ...env })

  const body = [
    t('feedback.emailGreeting'),
    '',
    dataSection,
    '',
    t('feedback.bodyPlaceholder'),
    '',
    t('feedback.emailClosing'),
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

// Open a mailto: URL by simulating a user-gestured click on a dynamic
// anchor element. More reliable than `window.location.href = href` for
// protocol handlers — some browsers (notably Chrome on Windows with
// Gmail web-handler registered for mailto:) treat programmatic
// `location.href` assignments as non-user-initiated and can fail to
// dispatch to the external handler, especially on repeat attempts. An
// anchor click within an onClick handler carries user-activation
// context that protocol handlers trust.
export function openMailto(href) {
  const a = document.createElement('a')
  a.href = href
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

// Compose a mailto: URL for the footer "Feedback" link. General-purpose
// feedback (bug reports, feature requests, questions, comments) — not
// per-finding. Reuses the localized greeting + closing pattern.
export function composeFooterFeedbackMailto(t) {
  const subject = 'PatentLint feedback'
  const body = [
    t('feedback.emailGreeting'),
    '',
    t('feedback.footerIntro'),
    '',
    t('feedback.footerPlaceholder'),
    '',
    t('feedback.emailClosing'),
  ].join('\n')
  return `mailto:${MAINTAINER_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`
}

// Compose a mailto: URL for the Security page's enterprise-deployment
// link. Prospective self-hosted / air-gapped inquiries. Reuses the
// localized greeting + closing pattern; own subject line and intro.
export function composeEnterpriseMailto(t) {
  const subject = 'PatentLint enterprise inquiry'
  const body = [
    t('feedback.emailGreeting'),
    '',
    t('feedback.enterpriseIntro'),
    '',
    t('feedback.enterprisePlaceholder'),
    '',
    t('feedback.emailClosing'),
  ].join('\n')
  return `mailto:${MAINTAINER_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`
}
