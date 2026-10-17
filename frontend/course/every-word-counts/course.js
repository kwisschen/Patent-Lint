// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025-2026 Christopher Chen
//
// EN / 中文 interface toggle for the course pages. build.mjs inlines
// strings.json in place of the marker below. Pages are complete in English
// without this script; it only swaps [data-i18n] text and [data-i18n-aria]
// labels. The chosen language is remembered in this browser only.
;(function () {
  var STRINGS = /*__STRINGS__*/null
  var KEY = 'ewc-lang'

  function fill(s, args) {
    return s.replace(/\{(\w+)\}/g, function (m, k) {
      return args && k in args ? args[k] : m
    })
  }

  function apply(lang) {
    var dict = STRINGS[lang] || STRINGS.en
    var zh = lang === 'zh-Hant'
    document.querySelectorAll('[data-i18n]').forEach(function (el) {
      var s = dict[el.getAttribute('data-i18n')]
      if (s == null) return
      var raw = el.getAttribute('data-i18n-args')
      el.textContent = fill(s, raw ? JSON.parse(raw) : null)
      if (zh) el.setAttribute('lang', 'zh-Hant')
      else el.removeAttribute('lang')
    })
    document.querySelectorAll('[data-i18n-aria]').forEach(function (el) {
      var s = dict[el.getAttribute('data-i18n-aria')]
      if (s != null) el.setAttribute('aria-label', s)
    })
    document.querySelectorAll('.lang-toggle button').forEach(function (b) {
      b.setAttribute('aria-pressed', String(b.getAttribute('data-lang') === lang))
    })
  }

  function init() {
    var toggle = document.querySelector('.lang-toggle')
    if (!toggle || !STRINGS) return
    toggle.hidden = false
    var saved = null
    try {
      saved = window.localStorage.getItem(KEY)
    } catch (e) {
      saved = null
    }
    if (saved && STRINGS[saved] && saved !== 'en') apply(saved)
    toggle.addEventListener('click', function (ev) {
      var b = ev.target.closest('button[data-lang]')
      if (!b) return
      var lang = b.getAttribute('data-lang')
      apply(lang)
      try {
        window.localStorage.setItem(KEY, lang)
      } catch (e) {
        // Storage blocked: the toggle still works for this page.
      }
    })
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init)
  else init()
})()
