// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025–2026 Christopher Chen
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import en from './locales/en.json'
import de from './locales/de.json'
import zhCN from './locales/zh-CN.json'
import zhTW from './locales/zh-TW.json'
import ja from './locales/ja.json'
import ko from './locales/ko.json'

// Migrate from old localStorage key if present
const oldKey = 'patentlint-lang'
const newKey = 'i18nextLng'
const oldLang = localStorage.getItem(oldKey)
if (oldLang && !localStorage.getItem(newKey)) {
  localStorage.setItem(newKey, oldLang)
}
if (oldLang) {
  localStorage.removeItem(oldKey)
}

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      de: { translation: de },
      'zh-CN': { translation: zhCN },
      'zh-TW': { translation: zhTW },
      ja: { translation: ja },
      ko: { translation: ko },
    },
    supportedLngs: ['en', 'de', 'zh-CN', 'zh-TW', 'ja', 'ko'],
    fallbackLng: 'en',
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
      lookupLocalStorage: newKey,
      convertDetectedLanguage: (lng) => {
        // Map locale variants to supported locales
        if (!lng) return lng
        const lower = lng.toLowerCase()
        if (lower === 'zh' || lower === 'zh-hant') return 'zh-TW'
        if (lower === 'zh-hans') return 'zh-CN'
        if (lower === 'de' || lower.startsWith('de-')) return 'de'
        return lng
      },
    },
    interpolation: { escapeValue: false },
  })

function syncHtmlLang(lng) {
  if (typeof document !== 'undefined' && lng) {
    document.documentElement.lang = lng
  }
}
syncHtmlLang(i18n.resolvedLanguage || i18n.language)
i18n.on('languageChanged', syncHtmlLang)

export default i18n
