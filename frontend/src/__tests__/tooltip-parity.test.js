// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025-2026 Christopher Chen
//
// The `tooltip.*` namespace explains the two elements that repeat on every
// check row and are pure shorthand: the status pill (FIX / REVIEW / PASS) and
// the citation badge (`§ 112(b)`). Same contract as `explain.*` - a key present
// in one locale and missing in another silently shows English to a German or
// Japanese reader, which is worse than showing nothing.
import { describe, it, expect } from 'vitest'
import en from '../i18n/locales/en.json'
import de from '../i18n/locales/de.json'
import ja from '../i18n/locales/ja.json'
import ko from '../i18n/locales/ko.json'
import zhCN from '../i18n/locales/zh-CN.json'
import zhTW from '../i18n/locales/zh-TW.json'
import { getCitationTooltipKey } from '../components/CheckItem'

const LOCALES = { de, ja, ko, 'zh-CN': zhCN, 'zh-TW': zhTW }

function flatten(obj, prefix = '') {
  return Object.entries(obj).reduce((acc, [k, v]) => {
    const key = prefix ? `${prefix}.${k}` : k
    if (v && typeof v === 'object') Object.assign(acc, flatten(v, key))
    else acc[key] = v
    return acc
  }, {})
}

describe('tooltip namespace', () => {
  const enTip = flatten(en.tooltip || {})
  const enKeys = Object.keys(enTip)

  it('covers all three statuses', () => {
    for (const s of ['pass', 'verify', 'amend']) {
      expect(enTip[`status.${s}`], s).toBeTruthy()
    }
  })

  it.each(Object.keys(LOCALES))('%s has every tooltip key en has', (loc) => {
    const got = Object.keys(flatten(LOCALES[loc].tooltip || {}))
    expect(got.sort()).toEqual(enKeys.sort())
  })

  it.each(Object.keys(LOCALES))('%s tooltip copy is not the English string', (loc) => {
    const other = flatten(LOCALES[loc].tooltip || {})
    const identical = enKeys.filter((k) => other[k] === enTip[k])
    expect(identical).toEqual([])
  })

  it('every tooltip key is a non-empty string in every locale', () => {
    for (const [loc, data] of Object.entries({ en, ...LOCALES })) {
      const flat = flatten(data.tooltip || {})
      for (const k of enKeys) {
        expect(typeof flat[k], `${loc}.${k}`).toBe('string')
        expect(flat[k].length, `${loc}.${k}`).toBeGreaterThan(8)
      }
    }
  })

  // The badge text is the lookup key, so a typo in the map is silent - the
  // badge simply renders with no tooltip and nobody notices.
  it('every citation the map claims to cover resolves to real copy', () => {
    const badges = [
      '§ 112(a)', '§ 112(b)', '§ 112(d)', '§ 112(f)',
      '§ 101', '37 CFR 1.52(b)(6)',
      '§ 608.01', '§ 608.01(b)', '§ 608.01(c)',
      '§ 608.01(m)', '§ 608.01(n)', '§ 608.02',
      '§ 2117', '§ 2129', '§ 2173.01', '§ 2173.05(b)',
      '§ 2422',
    ]
    for (const badge of badges) {
      const key = getCitationTooltipKey(badge)
      expect(key, badge).toBeTruthy()
      expect(enTip[key.replace('tooltip.', '')], `${badge} -> ${key}`).toBeTruthy()
    }
  })

  it('an unmapped citation yields no tooltip rather than a broken key', () => {
    // CN / TW / EPC references already name their instrument, so they are
    // deliberately out of scope and must degrade to the plain badge.
    for (const c of ['Rule 43(4) EPC', '專利法施行細則 §18', 'MPEP § 608.01(g)', null]) {
      expect(getCitationTooltipKey(c)).toBeNull()
    }
  })
})
