// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025 Christopher Chen
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import en from './locales/en.json'
import zhTW from './locales/zh-TW.json'
import zhCN from './locales/zh-CN.json'
import ja from './locales/ja.json'

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
      'zh-TW': { translation: zhTW },
      'zh-CN': { translation: zhCN },
      ja: { translation: ja },
    },
    supportedLngs: ['en', 'zh-TW', 'zh-CN', 'ja'],
    fallbackLng: 'en',
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
      lookupLocalStorage: newKey,
      convertDetectedLanguage: (lng) => {
        // Map Chinese variants to specific locales
        if (lng === 'zh' || lng === 'zh-Hant') return 'zh-TW'
        if (lng === 'zh-Hans') return 'zh-CN'
        return lng
      },
    },
    interpolation: { escapeValue: false },
  })

export default i18n
