// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025-2026 Christopher Chen
//
// The `explain.*` namespace is plain-language context rendered under a check.
// It is optional by design - a check with no explain key renders as before -
// but a key that exists in ONE locale and not the others silently shows an
// English string to a German or Japanese reader, which is worse than showing
// nothing. This pins parity across all six locales.
import { describe, it, expect } from 'vitest'
import en from '../i18n/locales/en.json'
import de from '../i18n/locales/de.json'
import ja from '../i18n/locales/ja.json'
import ko from '../i18n/locales/ko.json'
import zhCN from '../i18n/locales/zh-CN.json'
import zhTW from '../i18n/locales/zh-TW.json'

const LOCALES = { de, ja, ko, 'zh-CN': zhCN, 'zh-TW': zhTW }

function flatten(obj, prefix = '') {
  return Object.entries(obj).reduce((acc, [k, v]) => {
    const key = prefix ? `${prefix}.${k}` : k
    if (v && typeof v === 'object') Object.assign(acc, flatten(v, key))
    else acc[key] = v
    return acc
  }, {})
}

describe('explain namespace', () => {
  const enExplain = flatten(en.explain || {})
  const enKeys = Object.keys(enExplain)

  it('exists and is non-empty', () => {
    expect(enKeys.length).toBeGreaterThan(0)
  })

  it.each(Object.keys(LOCALES))('%s has every explain key en has', (loc) => {
    const got = Object.keys(flatten(LOCALES[loc].explain || {}))
    expect(got.sort()).toEqual(enKeys.sort())
  })

  it.each(Object.keys(LOCALES))('%s explain copy is not the English string', (loc) => {
    const other = flatten(LOCALES[loc].explain || {})
    // A copied-through English string means the locale was never authored.
    const identical = enKeys.filter((k) => other[k] === enExplain[k])
    expect(identical).toEqual([])
  })

  it('every explain key has a non-empty string in every locale', () => {
    for (const [loc, data] of Object.entries({ en, ...LOCALES })) {
      const flat = flatten(data.explain || {})
      for (const k of enKeys) {
        expect(typeof flat[k], `${loc}.${k}`).toBe('string')
        expect(flat[k].length, `${loc}.${k}`).toBeGreaterThan(10)
      }
    }
  })
})
