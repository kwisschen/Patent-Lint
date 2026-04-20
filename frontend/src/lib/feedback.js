// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2025 Christopher Chen
/* global __BUILD_HASH__ */
import { toast } from 'sonner'

// Source of truth for the maintainer email; mirrors Footer.jsx usage.
const MAINTAINER_EMAIL = 'kwisschen@gmail.com'

// Gmail web compose URL. Supports ?to=, ?su=, ?body= query params, and
// ?view=cm&fs=1 to open directly in the full-screen compose modal.
//
// Chosen over mailto: because mailto: requires an OS-level handler to
// be registered + functional, which a meaningful fraction of users
// (including the maintainer's own Windows setup) do not have — the
// dispatch chain silently fails with no user-visible error. An https://
// URL bypasses the OS handler layer entirely; every browser opens it
// as a regular webpage regardless of configuration.
//
// Preserves the PatentLint trust property ("indicator stays green"):
// opening a new tab via window.open('https://...') causes the NEW tab
// to fetch Gmail — PatentLint's tab makes zero network calls.
// `useNetworkMonitor`'s PerformanceObserver is scoped to PatentLint's
// tab and doesn't see the new tab's resources. Same handoff pattern as
// mailto:, just to a URL instead of a protocol.
const GMAIL_COMPOSE_BASE = 'https://mail.google.com/mail/?view=cm&fs=1'

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

// Build a Gmail compose URL with the given subject + body. Uses
// URLSearchParams so encoding is handled consistently (spaces as +,
// CJK characters as %XX, etc.).
function buildGmailUrl(subject, body) {
  const params = new URLSearchParams({
    to: MAINTAINER_EMAIL,
    su: subject,
    body: body,
  })
  return `${GMAIL_COMPOSE_BASE}&${params.toString()}`
}

// Compose a Gmail-compose URL pre-filled with per-finding feedback.
// Finding fields + environment metadata are merged into one aligned
// data block — field labels make the structure obvious without needing
// section-header decoration. Professional framing comes from a localized
// greeting + closing around the data.
//
// finding: an object whose enumerable keys become "Label: value" lines.
// Pass only what's relevant to the surface.
//
// Subject line stays English so the maintainer's inbox can filter
// consistently across locales: "PatentLint finding report — {check_key}".
//
// Returns a fully-encoded https:// URL ready for openFeedbackTab.
export function composeFeedbackUrl(finding, t, { locale } = {}) {
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

  return buildGmailUrl(subject, body)
}

// Compose a Gmail-compose URL for the footer "Feedback" link.
// General-purpose feedback (bug reports, feature requests, questions,
// comments) — not per-finding. Reuses the localized greeting + closing
// pattern.
export function composeFooterFeedbackUrl(t) {
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
  return buildGmailUrl(subject, body)
}

// Compose a Gmail-compose URL for the enterprise-deployment inquiry
// links. Prospective self-hosted / air-gapped inquiries. Reuses the
// localized greeting + closing pattern; own subject line and intro.
export function composeEnterpriseUrl(t) {
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
  return buildGmailUrl(subject, body)
}

// Open a Gmail compose URL in a new tab. Called from onClick handlers
// so the user-activation context carries through (no popup blocking).
// noopener+noreferrer so the new tab can't reach back into PatentLint's
// window — pure handoff.
export function openFeedbackTab(url) {
  window.open(url, '_blank', 'noopener,noreferrer')
}

// Show the "Auto-filled an error report for your review. Your draft
// stayed put." confirmation toast. Persistent (duration: Infinity) with
// an X close button so users who tab-away to the new Gmail tab and come
// back still see the acknowledgment. Fixed id so rapid-fire reports
// replace the existing toast rather than stack.
export function showFeedbackToast(t) {
  toast(t('feedback.confirmation'), {
    id: FEEDBACK_TOAST_ID,
    duration: Infinity,
    closeButton: true,
  })
}
