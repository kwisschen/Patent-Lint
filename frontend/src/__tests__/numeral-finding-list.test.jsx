// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025-2026 Christopher Chen
//
// The reference-numeral check used to flatten tabular data into a run-on
// sentence and then repeat it underneath:
//
//   5 reference numeral(s) with possibly inconsistent naming - please review.
//   Examples: #123: "auxiliary elastic structures" (5×), "auxiliary engaging
//   structures" (1×), ...; #13: "two conductive components" (34×), ... (+2 more)
//
// It now renders as a table. These pin the three ways that could silently
// regress: the dump coming back into the copy, the table being gated on a
// count again, and the counts being dropped.
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import en from '../i18n/locales/en.json'
import de from '../i18n/locales/de.json'
import ja from '../i18n/locales/ja.json'
import ko from '../i18n/locales/ko.json'
import zhCN from '../i18n/locales/zh-CN.json'
import zhTW from '../i18n/locales/zh-TW.json'
import NumeralFindingList from '../components/NumeralFindingList'

const LOCALES = { en, de, ja, ko, 'zh-CN': zhCN, 'zh-TW': zhTW }

const D1 = [
  {
    numeral: '123',
    canonical: 'auxiliary elastic structures',
    canonical_count: 5,
    outliers: [
      { name: 'auxiliary engaging structures', count: 1 },
      { name: 'auxiliary engaging structure', count: 1 },
    ],
  },
  { numeral: '13', canonical: 'two conductive components', canonical_count: 34,
    outliers: [{ name: 'two elastic clamping structures', count: 1 }] },
]

describe('numeral check copy', () => {
  function flatten(obj, prefix = '') {
    return Object.entries(obj).reduce((acc, [k, v]) => {
      const key = prefix ? `${prefix}.${k}` : k
      if (v && typeof v === 'object') Object.assign(acc, flatten(v, key))
      else acc[key] = v
      return acc
    }, {})
  }

  it.each(Object.keys(LOCALES))(
    '%s numeral templates no longer dump the examples inline',
    (loc) => {
      const flat = flatten(LOCALES[loc])
      const offenders = Object.entries(flat)
        .filter(([k, v]) =>
          (k.includes('numeralConsistency') || k.includes('symbolTableCoverage'))
          && typeof v === 'string'
          && v.includes('{{inline_summary}}'))
        .map(([k]) => k)
      expect(offenders).toEqual([])
    },
  )

  it.each(Object.keys(LOCALES))('%s has no stray period before a citation', (loc) => {
    const flat = flatten(LOCALES[loc])
    const bad = Object.entries(flat)
      .filter(([k, v]) =>
        k.includes('numeralConsistency')
        && typeof v === 'string'
        && /[.。]\s*[(（]/.test(v))
      .map(([k]) => k)
    expect(bad).toEqual([])
  })
})

describe('NumeralFindingList', () => {
  it('renders a SINGLE finding - it is the primary view, not an overflow', () => {
    // Previously gated at `> 3`, so a draft with one or two conflicts showed
    // the run-on sentence and no table at all.
    render(<NumeralFindingList findings={[D1[0]]} status="verify" />)
    expect(screen.getByText('#123')).toBeTruthy()
    expect(screen.getByText('auxiliary elastic structures')).toBeTruthy()
  })

  it('shows every name for a numeral, with its count', () => {
    render(<NumeralFindingList findings={D1} status="verify" />)
    expect(screen.getByText('auxiliary engaging structures')).toBeTruthy()
    expect(screen.getByText('auxiliary engaging structure')).toBeTruthy()
    // The counts are the signal that tells a drafter which name is the typo.
    expect(screen.getByText(/^5×$/)).toBeTruthy()
    expect(screen.getByText(/^34×$/)).toBeTruthy()
  })

  it('previews three numerals and offers the rest', () => {
    const many = Array.from({ length: 5 }, (_, i) => ({
      numeral: `${i}`, canonical: `name ${i}`, canonical_count: 2,
      outliers: [{ name: `variant ${i}`, count: 1 }],
    }))
    render(<NumeralFindingList findings={many} status="verify" />)
    expect(screen.getByText('#0')).toBeTruthy()
    expect(screen.getByText('#2')).toBeTruthy()
    expect(screen.queryByText('#4')).toBeNull()
    // No i18n provider in this test, so react-i18next returns the KEY. The
    // point of the assertion is that an overflow affordance exists at all.
    expect(screen.getByText(/numeralFindings\.expand|Show all 5/)).toBeTruthy()
  })

  it('renders nothing for an empty or missing payload', () => {
    const { container: a } = render(<NumeralFindingList findings={[]} />)
    expect(a.textContent).toBe('')
    const { container: b } = render(<NumeralFindingList findings={undefined} />)
    expect(b.textContent).toBe('')
  })

  it('still supports the D3 shapes', () => {
    const { container } = render(
      <NumeralFindingList
        findings={[{ name: 'housing', numerals: ['10', '12'], refnum_count: 2 }]}
        status="amend"
      />,
    )
    expect(container.textContent).toContain('housing')
    expect(container.textContent).toContain('10, 12')
  })
})
