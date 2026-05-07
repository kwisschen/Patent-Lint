// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
//
// Shared filter for trust-relevant PerformanceObserver entries.
//
// INVARIANT: every trust-surfacing PerformanceObserver in this app
// (the AnalysisReport network dot via useNetworkMonitor, the ProveIt
// modal's live activity log, and any future trust surface) MUST pass
// observer entries through `isTrustRelevantResource` before counting
// or displaying them. Raw `PerformanceResourceTiming` includes events
// that are NOT network egress — local file reads, blob URLs, data
// URIs, browser-attempted-but-failed fetches — and surfacing those as
// "network active" directly contradicts the no-upload trust copy.
//
// Background — the bug this prevents (fix shipped 2026-05-07, f3f6575):
// dragging a .docx into the dropzone caused macOS / the browser to load
// a drag-preview thumbnail off disk via file:// (often a recent
// screencaptureui screenshot in /var/folders/.../TemporaryItems/).
// PerformanceObserver surfaced it as a resource entry, useNetworkMonitor
// forwarded it unfiltered, and the trust dot flashed red on the very
// first analysis after page load — the worst possible moment for a
// trust violation. Centralizing the filter here means a future third
// observer can't accidentally bypass the rule.
//
// What gets filtered:
//   - non-HTTP(S) URLs (file://, blob:, data:, chrome-extension://, etc.):
//     local disk / in-memory reads, never network egress
//   - failed fetches (responseStart === 0): browser ATTEMPTED the request
//     but no response arrived (offline, blocked, CORS rejection)
//
// What stays:
//   - successful HTTP(S) fetches — the only thing that should ever be
//     called "network activity" in the trust panel
//
// If you add a new trust observer, import this helper. Do not write
// your own filter inline — that's how this bug shipped in March and
// went latent for 6 weeks.
export function isTrustRelevantResource(entry) {
  if (!entry || typeof entry.name !== 'string') return false
  if (!/^https?:/i.test(entry.name)) return false
  if (entry.responseStart === undefined || entry.responseStart <= 0) return false
  return true
}
