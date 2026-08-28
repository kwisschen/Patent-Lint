// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025-2026 Christopher Chen
//
// Regression guard for the 2026-08-28 dropped-verdict bug.
//
// ReportModal calls onConfirm(userComment, disposition, findingDispositions)
// and refuses to submit until the reporter picks a disposition. Two of the
// four surfaces that render it declared their handler as `(userComment)` and
// silently dropped arguments 2 and 3, so the reporter was REQUIRED to choose a
// verdict that was then discarded before the request was built. 36 reports
// reached the tracker with no verdict before anyone noticed, and the only
// symptom was an odd label distribution weeks later.
//
// This is a SOURCE-level contract test on purpose. The bug is a dropped
// function parameter, which is invisible to a rendering test of any single
// component and would have to be re-written for each new surface. Checking the
// source catches it for surfaces that do not exist yet - which matters, because
// the fourth surface (AntecedentBasisCard) was one I did not know about while
// diagnosing this.
import { readFileSync, readdirSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, it, expect } from 'vitest'

// fileURLToPath, not URL.pathname: under the jsdom environment the latter
// resolves against the document base and yields an absolute-looking '/src/...'
// that does not exist on disk.
const COMPONENTS = resolve(dirname(fileURLToPath(import.meta.url)), '..', 'components')

function sourcesRenderingReportModal() {
  return readdirSync(COMPONENTS)
    .filter((f) => f.endsWith('.jsx') && f !== 'ReportModal.jsx')
    .map((f) => [f, readFileSync(join(COMPONENTS, f), 'utf8')])
    .filter(([, src]) => src.includes('<ReportModal'))
}

describe('report disposition contract', () => {
  it('finds every surface that renders ReportModal', () => {
    const names = sourcesRenderingReportModal().map(([f]) => f).sort()
    // Guards against the discovery problem that caused the original bug: a
    // surface nobody remembered. If this list changes, the new file must also
    // satisfy the handler-signature test below.
    expect(names).toEqual([
      'AntecedentBasisCard.jsx',
      'CheckItem.jsx',
      'SpecSupportCard.jsx',
      'TriagePanel.jsx',
    ])
  })

  it.each(sourcesRenderingReportModal())(
    '%s passes the disposition through to sendReport',
    (_file, src) => {
      // Every handler wired to onConfirm must accept the disposition argument.
      const handlers = [...src.matchAll(/const\s+(handle\w*Confirm)\s*=\s*\(([^)]*)\)/g)]
      expect(handlers.length).toBeGreaterThan(0)

      for (const [, name, params] of handlers) {
        const args = params.split(',').map((s) => s.trim()).filter(Boolean)
        expect(
          args.length,
          `${name} must accept the disposition argument, not just the comment`,
        ).toBeGreaterThanOrEqual(2)
        expect(args[1]).toMatch(/disposition/i)
      }

      // ...and must actually forward it, not merely accept it.
      const calls = [...src.matchAll(/sendReport\(\{([\s\S]*?)\}\)/g)]
      expect(calls.length).toBeGreaterThan(0)
      for (const [, body] of calls) {
        expect(body).toMatch(/\bdisposition\b/)
      }
    },
  )
})
