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

// Build a feedback email and return BOTH the Gmail compose URL and the
// plain-text body. The URL opens Gmail pre-filled (works for Gmail users
// out of the box, Google Workspace users whose domain uses Gmail, and
// personal-Google-account users). The plain text gets copied to the
// clipboard at send time as a universal fallback — corporate users with
// Outlook/Microsoft 365/other provider can close the Gmail tab and paste
// into their own email. No mail provider is lucky enough to catch everyone,
// so we give the user both paths and let them pick silently.
//
// Subject line stays English so the maintainer's inbox can filter
// consistently across locales.
function buildEmail(subject, body) {
  return { url: buildGmailUrl(subject, body), text: body }
}

// Compose per-finding feedback — finding fields + environment metadata
// merged into one aligned data block around a localized greeting +
// placeholder.
export function composeFeedback(finding, t, { locale } = {}) {
  const env = {
    browser: detectBrowser(),
    locale: locale || (typeof navigator !== 'undefined' ? navigator.language : 'unknown'),
    patentlint_build: buildHash(),
  }
  const checkKey = finding.check_key || 'unknown'
  const subject = `PatentLint finding report — ${checkKey}`
  const dataSection = formatSection({ ...finding, ...env })
  const body = [
    t('feedback.emailGreeting'),
    '',
    dataSection,
    '',
    t('feedback.bodyPlaceholder'),
  ].join('\n')
  return buildEmail(subject, body)
}

// Compose footer-link free-form feedback. Localized greeting + intro +
// placeholder, no finding-specific data.
export function composeFooterFeedback(t) {
  const subject = 'PatentLint feedback'
  const body = [
    t('feedback.emailGreeting'),
    '',
    t('feedback.footerIntro'),
    '',
    t('feedback.footerPlaceholder'),
  ].join('\n')
  return buildEmail(subject, body)
}

// Compose enterprise-deployment inquiry. Localized greeting + intro +
// placeholder with requirement prompts.
export function composeEnterprise(t) {
  const subject = 'PatentLint enterprise inquiry'
  const body = [
    t('feedback.emailGreeting'),
    '',
    t('feedback.enterpriseIntro'),
    '',
    t('feedback.enterprisePlaceholder'),
  ].join('\n')
  return buildEmail(subject, body)
}

// Send a composed email: copy the plain-text body to the clipboard AND
// open the Gmail compose URL in a new tab, then show a confirmation
// toast. The dual-channel send is deliberate:
//   - Gmail tab: works instantly for Gmail / Google Workspace users
//   - Clipboard: universal fallback for corporate / Outlook / other-provider
//     users whose Gmail sign-in would be a dead end — they can close the
//     Gmail tab and paste into any email app
// Clipboard write is best-effort (silent fail on unsupported / blocked).
// Focus order matters: write clipboard BEFORE opening the new tab,
// because window.open may shift focus and some browsers require the
// original tab to be focused for clipboard writes to succeed.
export function sendFeedback(email, t) {
  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(email.text).catch(() => {})
  }
  if (typeof window !== 'undefined') {
    window.open(email.url, '_blank', 'noopener,noreferrer')
  }
  toast(t('feedback.confirmation'), {
    id: FEEDBACK_TOAST_ID,
    duration: Infinity,
    closeButton: true,
  })
}
