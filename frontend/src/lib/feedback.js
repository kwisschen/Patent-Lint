// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
/* global __BUILD_HASH__ */
import { emitOutgoing } from './outgoingRequests'

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

// Outlook web compose. office.com covers Microsoft 365 / work Outlook
// (the case where Gmail sign-in breaks for corporate users). Personal
// outlook.com/Hotmail accounts may see a brief redirect but the params
// survive. Matches the UX pattern of Gmail compose: new tab, pre-filled
// compose view opens directly, user reviews and sends.
const OUTLOOK_COMPOSE_BASE = 'https://outlook.office.com/mail/deeplink/compose'

// localStorage key for the user's chosen send method. Persists across
// sessions (unlike the session-scoped update-dismissal state) so a
// user's preference sticks. Values: 'gmail' | 'outlook' | 'clipboard'.
const METHOD_KEY = 'patentlint:feedback-method'
const VALID_METHODS = ['gmail', 'outlook', 'mailto', 'clipboard']

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

// Per-script context window for per-finding diagnostic excerpts. Mirrors
// `src/patentlint/diagnostic_extractors.py::_context_window_for` so the
// per-claim React-side payload matches what the Python section-level
// extractor produces. Detection is content-driven (reads claim text), not
// UI-locale-driven: a US user analyzing a TW patent still gets the Han
// window because the claim text itself is Han-dominant.
const CONTEXT_WINDOW_LATIN = 30
const CONTEXT_WINDOW_JA = 22
const CONTEXT_WINDOW_HANGUL = 18
const CONTEXT_WINDOW_HAN = 12

export const SAMPLE_SIZE = 5

function contextWindowFor(text) {
  if (!text) return CONTEXT_WINDOW_LATIN
  let kana = 0, han = 0, hangul = 0
  for (const c of text) {
    const cp = c.codePointAt(0)
    if (cp >= 0x3040 && cp <= 0x30FF) kana++
    else if (cp >= 0x4E00 && cp <= 0x9FFF) han++
    else if (cp >= 0xAC00 && cp <= 0xD7AF) hangul++
  }
  if (kana >= 3) return CONTEXT_WINDOW_JA
  const n = text.length
  if (han / n > 0.3) return CONTEXT_WINDOW_HAN
  if (hangul / n > 0.3) return CONTEXT_WINDOW_HANGUL
  return CONTEXT_WINDOW_LATIN
}

// Locate first occurrence of `target` inside `text` and return excerpt
// data: { context_before, context_after, char_offset }. Mirrors Python's
// `_excerpt_around`. All-null if not found or empty.
export function excerptAround(text, target) {
  if (!text || !target) {
    return { context_before: null, context_after: null, char_offset: null }
  }
  const idx = text.indexOf(target)
  if (idx < 0) {
    return { context_before: null, context_after: null, char_offset: null }
  }
  const window = contextWindowFor(text)
  const context_before = text.slice(Math.max(0, idx - window), idx) || null
  const end = idx + target.length
  const context_after = text.slice(end, end + window) || null
  return { context_before, context_after, char_offset: idx }
}

// Per-key locale-bundle path for each known metadata key. Keys not in
// this map fall back to a sentence-case version of the raw key so new
// fields work without code changes (and the maintainer still sees a
// readable label even if a translation hasn't been added yet).
//
// Exported for ReportModal to render localized labels in its payload
// preview — same labels users see in the modal show up in their email
// client when they choose the mailto fallback.
export const FIELD_LABEL_KEYS = {
  check_key: 'feedback.email.fieldCheck',
  message: 'feedback.email.fieldMessage',
  details: 'feedback.email.fieldDetails',
  status: 'feedback.email.fieldStatus',
  claim_id: 'feedback.email.fieldClaim',
  flagged_claim_id: 'feedback.email.fieldClaim',
  terms: 'feedback.email.fieldTerms',
  phrases: 'feedback.email.fieldPhrases',
  reference_form: 'feedback.email.fieldReferenceForm',
  jurisdiction: 'feedback.email.fieldJurisdiction',
  browser: 'feedback.email.fieldBrowser',
  locale: 'feedback.email.fieldLocale',
  patentlint_build: 'feedback.email.fieldBuild',
  flagged_count: 'feedback.email.fieldFlaggedCount',
  total_count: 'feedback.email.fieldTotalCount',
  total_kind: 'feedback.email.fieldTotalKind',
  hit_count: 'feedback.email.fieldHitCount',
  fixture_shape_hash: 'feedback.email.fieldShapeHash',
  reason_code: 'feedback.email.fieldReasonCode',
  findings_in_group: 'feedback.email.fieldFindingsInGroup',
  // Aliases for keys already used by existing _dx() emit sites (so the
  // modal preview localizes them too without renaming source-side).
  issue_count: 'feedback.email.fieldIssueCount',
  claim_count: 'feedback.email.fieldClaimCount',
  total_claims: 'feedback.email.fieldTotalClaims',
  unsupported_phrase_count: 'feedback.email.fieldFlaggedCount',
  total_findings: 'feedback.email.fieldHitCount',
  // Per-finding fields surfaced by the diagnostic_extractors module
  // (categories A through E). Each finding inside a `findings: [...]`
  // array uses these labels.
  findings: 'feedback.email.fieldFindings',
  term: 'feedback.email.fieldTerm',
  did_you_mean: 'feedback.email.fieldDidYouMean',
  did_you_mean_claim_id: 'feedback.email.fieldDidYouMeanClaimId',
  category: 'feedback.email.fieldCategory',
  char_offset: 'feedback.email.fieldCharOffset',
  context_before: 'feedback.email.fieldContextBefore',
  context_after: 'feedback.email.fieldContextAfter',
  claim_text_charlen: 'feedback.email.fieldClaimTextCharlen',
  phrase: 'feedback.email.fieldPhrase',
  tiers_checked: 'feedback.email.fieldTiersChecked',
  cross_ref: 'feedback.email.fieldCrossRef',
  spec_paragraph_count: 'feedback.email.fieldSpecParagraphCount',
  reference_form: 'feedback.email.fieldReferenceForm',
  matched_phrase: 'feedback.email.fieldMatchedPhrase',
  preamble: 'feedback.email.fieldPreamble',
  kind: 'feedback.email.fieldKind',
  first_5_numbers: 'feedback.email.fieldFirst5Numbers',
  last_5_numbers: 'feedback.email.fieldLast5Numbers',
  gap_at_index: 'feedback.email.fieldGapAtIndex',
  expected_after: 'feedback.email.fieldExpectedAfter',
  found_after: 'feedback.email.fieldFoundAfter',
  gap_size: 'feedback.email.fieldGapSize',
  missing_sections: 'feedback.email.fieldMissingSections',
  detected_count: 'feedback.email.fieldDetectedCount',
  detected_headers_sample: 'feedback.email.fieldDetectedHeadersSample',
  canonical_count: 'feedback.email.fieldCanonicalCount',
  seen_indices: 'feedback.email.fieldSeenIndices',
  is_increasing: 'feedback.email.fieldIsIncreasing',
  sample_paragraph_ids: 'feedback.email.fieldSampleParagraphIds',
  input_format: 'feedback.email.fieldInputFormat',
  total_paragraphs: 'feedback.email.fieldTotalParagraphs',
  what: 'feedback.email.fieldWhat',
  flagged_claim_id: 'feedback.email.fieldClaim',
  orphans: 'feedback.email.fieldOrphans',
  brief_figs_sample: 'feedback.email.fieldBriefFigsSample',
  detailed_figs_sample: 'feedback.email.fieldDetailedFigsSample',
}

// Format a key→value section as a localized "Label: value" stack. Drops
// the previous space-padding hack — CJK glyphs render at ~2 monospace
// widths so character-count padding skewed visibly, and the colon line
// is more scan-friendly than aligned columns anyway. Locale colon comes
// from `feedback.email.fieldColon` (":" / "：" per script convention).
function formatSection(entries, t) {
  const rows = Object.entries(entries).filter(
    ([, value]) => value !== undefined && value !== null && value !== '',
  )
  if (rows.length === 0) return ''
  const colon = t('feedback.email.fieldColon')
  return rows
    .map(([key, value]) => {
      const labelKey = FIELD_LABEL_KEYS[key]
      const label = labelKey ? t(labelKey) : key
      return `${label}${colon}${value}`
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

// Build an Outlook web compose URL. Uses `subject` (not `su`) per the
// Outlook deeplink spec.
function buildOutlookUrl(subject, body) {
  const params = new URLSearchParams({
    to: MAINTAINER_EMAIL,
    subject: subject,
    body: body,
  })
  return `${OUTLOOK_COMPOSE_BASE}?${params.toString()}`
}

// Build a mailto: URL. Used for the "Email app" picker option — on
// mobile (iOS / Android) this opens the user's default mail app with
// pre-fill working correctly (unlike iOS Gmail-app handling of https
// compose URLs, which ignores the `?view=cm&body=...` params). On
// desktop, opens whatever mail client is configured as the default
// handler (Outlook, Mail.app, Thunderbird, etc.).
function buildMailtoUrl(subject, body) {
  return `mailto:${MAINTAINER_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`
}

// Dispatch a mailto: URL via a dynamically-created anchor click.
// More reliable than window.location.href = 'mailto:...' for protocol
// handlers — browsers treat anchor clicks within an onClick handler as
// user-initiated, which protocol dispatch requires.
function openMailto(url) {
  const a = document.createElement('a')
  a.href = url
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
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
// Subject lines are localized (greeting + body label + check identifier)
// so non-English users don't see a wall of English at the moment of
// send. The "PatentLint" prefix is preserved across locales so the
// maintainer's inbox filter still catches every report regardless of
// the user's UI language.
// An email's structured data. Not tied to any specific provider — the
// send method decides at dispatch time which URL to open (or just copy
// to clipboard). `subject` and `text` are used to build provider-
// specific URLs on demand in dispatchFeedback().
function buildEmail(subject, body) {
  return { subject, text: body }
}

// Preference helpers. localStorage persists across tab sessions; user's
// "remember this choice" tick gets honored on later visits too.
export function getFeedbackMethod() {
  try {
    const method = localStorage.getItem(METHOD_KEY)
    return VALID_METHODS.includes(method) ? method : null
  } catch {
    return null
  }
}

export function setFeedbackMethod(method) {
  if (!VALID_METHODS.includes(method)) return
  try {
    localStorage.setItem(METHOD_KEY, method)
  } catch {
    // Private-mode / quota exceeded — silent fail; user just won't get
    // persistence, which is acceptable degradation.
  }
}

export function clearFeedbackMethod() {
  try {
    localStorage.removeItem(METHOD_KEY)
  } catch {
    // Silent fail.
  }
}

// Format the walker-diagnostic fingerprint as an indented block. Values
// are coerced to compact strings (true/false for booleans, str for ints)
// so the email body reads like a key/value ledger. Pure metadata by
// design — no claim text, no nouns; disclosed in Privacy §7.
function formatDiagnostics(diagnostics, t) {
  if (!diagnostics || typeof diagnostics !== 'object') return ''
  const entries = Object.entries(diagnostics).filter(
    ([, value]) => value !== undefined && value !== null && value !== '',
  )
  if (entries.length === 0) return ''
  const header = t('feedback.email.diagnosticHeader')
  const colon = t('feedback.email.fieldColon')
  const lines = entries.map(([key, value]) => {
    const displayValue = typeof value === 'boolean' ? String(value) : value
    return `  ${key}${colon}${displayValue}`
  })
  return [header, ...lines].join('\n')
}

// Compose per-finding feedback — finding fields + environment metadata
// merged into one localized data block around a localized greeting +
// placeholder. Walker diagnostics (optional) render as a separate
// fingerprint block so the maintainer can identify the exact code path
// a report came from without any claim content leaving the device.
export function composeFeedback(finding, t, { locale } = {}) {
  const env = {
    browser: detectBrowser(),
    locale: locale || (typeof navigator !== 'undefined' ? navigator.language : 'unknown'),
    patentlint_build: buildHash(),
  }
  const checkKey = finding.check_key || 'unknown'
  const subject = t('feedback.email.subjectFinding', { checkKey })
  // Strip diagnostics from the main section — they render as their own
  // block below, not as an inline "diagnostics: [object]" row.
  const { diagnostics, ...findingCore } = finding
  const dataSection = formatSection({ ...findingCore, ...env }, t)
  const diagnosticSection = formatDiagnostics(diagnostics, t)
  const sections = [
    t('feedback.emailGreeting'),
    '',
    dataSection,
  ]
  if (diagnosticSection) {
    sections.push('', diagnosticSection)
  }
  sections.push('', t('feedback.bodyPlaceholder'))
  const body = sections.join('\n')
  return buildEmail(subject, body)
}

// Compose footer-link free-form feedback. Localized greeting + intro +
// placeholder, no finding-specific data.
export function composeFooterFeedback(t) {
  const subject = t('feedback.email.subjectFooter')
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
  const subject = t('feedback.email.subjectEnterprise')
  const body = [
    t('feedback.emailGreeting'),
    '',
    t('feedback.enterpriseIntro'),
    '',
    t('feedback.enterprisePlaceholder'),
  ].join('\n')
  return buildEmail(subject, body)
}

// Dispatch a composed email via the given method. Clipboard write is
// always performed (silent fail) as a safety-net fallback regardless
// of method — even a Gmail user can tab away and paste elsewhere if
// the compose tab fails. Order matters: write clipboard BEFORE opening
// the new tab, because window.open may steal focus and some browsers
// require the original tab to be focused for clipboard writes.
//
// No confirmation toast: the picker modal already tells the user what
// will happen (pre-fill + clipboard copy), and for Gmail/Outlook/mailto
// methods the newly-opened tab or mail app is its own visible
// confirmation. For the clipboard-only path, the modal closing is the
// confirmation signal.
export function dispatchFeedback(method, email) {
  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(email.text).catch(() => {})
  }

  if (method === 'gmail') {
    if (typeof window !== 'undefined') {
      window.open(buildGmailUrl(email.subject, email.text), '_blank', 'noopener,noreferrer')
    }
  } else if (method === 'outlook') {
    if (typeof window !== 'undefined') {
      window.open(buildOutlookUrl(email.subject, email.text), '_blank', 'noopener,noreferrer')
    }
  } else if (method === 'mailto') {
    openMailto(buildMailtoUrl(email.subject, email.text))
  }
  // method === 'clipboard' → clipboard already written above, nothing to open.
}


// ---------------------------------------------------------------------------
// Anonymous error-report endpoint (POST /api/report).
//
// Same-origin Pages Function — no CORS, no env-var URL, no token in
// the bundle. The Function forwards to GitHub Issues on the
// Patent-Lint repo, where the maintainer (and Claude Code via
// `gh issue list --label report`) reads them.
//
// Trade-off vs. the mailto-based flow above:
//   mailto: zero network calls from PatentLint's tab; user reviews
//           in their email client; user's email address ends up on
//           the From header.
//   anonymous endpoint: one same-origin POST; user reviews the
//           exact payload in the modal preview before sending; no
//           account, no email address required.
// Both flows ship — modal defaults to anonymous, mailto is the
// in-modal tertiary fallback.
// ---------------------------------------------------------------------------

export function buildReportPayload({
  checkKey,
  jurisdiction,
  locale,
  diagnostics,
}) {
  const payload = {
    check_key: checkKey || 'unknown',
    patentlint_build: buildHash(),
  }
  if (jurisdiction) payload.jurisdiction = jurisdiction
  if (locale) payload.locale = locale
  if (diagnostics && typeof diagnostics === 'object') {
    for (const [k, v] of Object.entries(diagnostics)) {
      if (v === null || v === undefined || v === '') continue
      payload[k] = v
    }
  }
  return payload
}

// Send the structural payload to /api/report. Returns
// { ok: true, payload } on 2xx, { ok: false, reason } on any
// failure. The modal maps reason → localized toast string; raw HTTP
// detail never reaches the user.
export async function sendReport({ checkKey, jurisdiction, locale, diagnostics }) {
  const payload = buildReportPayload({ checkKey, jurisdiction, locale, diagnostics })

  emitOutgoing('/api/report')
  let response
  try {
    response = await fetch('/api/report', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload),
      credentials: 'omit',
      referrerPolicy: 'no-referrer',
    })
  } catch {
    return { ok: false, reason: 'network_error' }
  }

  if (response.status >= 500) {
    return { ok: false, reason: 'server_error' }
  }
  if (!response.ok) {
    return { ok: false, reason: 'request_failed' }
  }
  return { ok: true, payload }
}


