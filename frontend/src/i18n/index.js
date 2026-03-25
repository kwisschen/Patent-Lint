// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025 Christopher Chen
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './locales/en.json'
import zhTW from './locales/zh-TW.json'
import zhCN from './locales/zh-CN.json'
import ja from './locales/ja.json'

const stored = localStorage.getItem('patentlint-lang')

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    'zh-TW': { translation: zhTW },
    'zh-CN': { translation: zhCN },
    ja: { translation: ja },
  },
  lng: stored || 'en',
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
})

export default i18n
