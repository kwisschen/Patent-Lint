// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025–2026 Christopher Chen
//
// Minimal pub-sub for tracking outgoing-data network calls.
// Fired EXPLICITLY by code that POSTs/PUTs/etc. to a remote endpoint;
// NOT a passive network observer. The deliberate "explicit emit"
// design means we know exactly which calls qualify as outgoing data
// and which are routine asset loads — no false positives from font
// fetches, version checks, or internal navigation.
//
// Convention: every fetch() with method !== 'GET' must be paired
// with emitOutgoing() on the same line as the fetch call. New
// outgoing endpoints add one emit line; nothing else changes.
// XMLHttpRequest and navigator.sendBeacon would need parallel
// instrumentation if introduced (currently neither is used).
//
// Different scope from the PerformanceObserver in ProveItModal:
// that observer is a comprehensive demonstration tool that surfaces
// every request including GETs (so the test button proves "yes the
// observer catches things, now drop a file and see how nothing
// fires"). The widget powered by this module shows only outgoing
// data — the metric that actually matters for the trust claim.

const listeners = new Set()
const history = []

export function emitOutgoing(endpoint, timestamp = Date.now()) {
  const event = { endpoint, timestamp }
  history.push(event)
  listeners.forEach((cb) => cb(event))
}

export function subscribeOutgoing(callback) {
  listeners.add(callback)
  return () => listeners.delete(callback)
}

export function getOutgoingHistory() {
  return history.slice()
}
