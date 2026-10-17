// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025-2026 Christopher Chen
//
// Gates the course's hard constraints on the GENERATED pages, not on the
// source: the frozen URL and routes, noindex and the draft banner, landmarks
// and a single h1, links only to pages that exist, PatentLint named only where
// allowed, and nothing loaded or submitted anywhere. Runs in the course's own
// CI workflow (.github/workflows/course.yml), never in the product's.
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, mkdtempSync, readFileSync, readdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JSDOM } from 'jsdom'
import { build, DIR, ROOT, SITE } from './build.mjs'

const STRINGS = JSON.parse(readFileSync(new URL('./strings.json', import.meta.url), 'utf8'))

// FROZEN FOR THE SEMESTER: these URLs are published. Do not edit this list to
// make a failing test pass; a failure here means a live link would break.
const FROZEN_SITE = 'https://learn.patentlint.com'
const FROZEN_ROOT = '/every-word-counts/'
const ROUTES = [
  '', 'start-here', 'part-1-anatomy', 'part-2-specification', 'part-3-claims',
  'part-4-find-it-fix-it', 'part-5-filing-ready', 'part-6-wrap-up',
  'word-wall', 'ask', 'sources', 'accessibility', 'about',
]

const site = mkdtempSync(join(tmpdir(), 'ewc-'))
const out = join(site, DIR)
const slugs = build(site)
const parse = (html) => new JSDOM(html).window.document
const pages = Object.fromEntries(
  slugs.map((s) => {
    const html = readFileSync(join(out, s, 'index.html'), 'utf8')
    return [s, { html, doc: parse(html) }]
  }),
)
pages['404'] = (() => {
  const html = readFileSync(join(site, '404.html'), 'utf8')
  return { html, doc: parse(html) }
})()

describe('site', () => {
  it('keeps the frozen URL and route list', () => {
    assert.equal(SITE, FROZEN_SITE)
    assert.equal(ROOT, FROZEN_ROOT)
    assert.deepEqual([...slugs].sort(), [...ROUTES].sort())
  })

  it('has the same string keys in every language', () => {
    assert.deepEqual(Object.keys(STRINGS['zh-Hant']).sort(), Object.keys(STRINGS.en).sort())
  })

  it('inlines the strings into course.js', () => {
    const js = readFileSync(join(out, 'course.js'), 'utf8')
    assert.ok(!js.includes('/*__STRINGS__*/'))
    assert.ok(js.includes(STRINGS['zh-Hant'].draft))
  })

  it('writes only the course directory and the 404 page', () => {
    assert.deepEqual(readdirSync(site).sort(), ['404.html', DIR])
    assert.deepEqual(
      readdirSync(out).sort(),
      ['course.css', 'course.js', 'favicon.svg', 'index.html', ...ROUTES.filter(Boolean)].sort(),
    )
  })

  it('chains Part 0 through Part 6 with next links', () => {
    const order = ROUTES.slice(1, 8)
    order.forEach((slug, i) => {
      const next = pages[slug].doc.querySelector('.pager-next').getAttribute('href')
      assert.equal(next, i + 1 < order.length ? `${ROOT}${order[i + 1]}/` : ROOT)
    })
    assert.equal(pages[''].doc.querySelector('a.button').getAttribute('href'), `${ROOT}start-here/`)
  })
})

for (const slug of [...ROUTES, '404']) {
  describe(`page "${slug}"`, () => {
    const { html, doc } = pages[slug]

    it('is noindex, lang=en, with the draft banner', () => {
      assert.equal(doc.documentElement.getAttribute('lang'), 'en')
      assert.equal(doc.querySelector('meta[name="robots"]').getAttribute('content'), 'noindex')
      assert.ok(doc.querySelector('header .draft-banner').textContent.includes(STRINGS.en.draft))
    })

    it('has landmarks, a skip link, and exactly one h1', () => {
      for (const sel of ['header', 'nav#course-nav', 'main#main', 'footer']) {
        assert.ok(doc.querySelector(sel), sel)
      }
      assert.equal(doc.querySelector('body > a.skip-link').getAttribute('href'), '#main')
      assert.equal(doc.querySelectorAll('h1').length, 1)
    })

    it('never skips a heading level', () => {
      let prev = 0
      for (const h of doc.querySelectorAll('h1, h2, h3, h4, h5, h6')) {
        const level = Number(h.tagName[1])
        assert.ok(level - prev <= 1, h.textContent)
        prev = level
      }
    })

    it('marks all Chinese text with lang="zh-Hant"', () => {
      const walker = doc.createTreeWalker(doc.body, 4 /* SHOW_TEXT */)
      for (let n = walker.nextNode(); n; n = walker.nextNode()) {
        if (/[一-鿿]/.test(n.data)) {
          assert.ok(n.parentElement.closest('[lang="zh-Hant"]'), n.data)
        }
      }
    })

    it('links only to course pages that exist', () => {
      for (const a of doc.querySelectorAll('a[href]')) {
        const href = a.getAttribute('href')
        if (href.startsWith('#')) {
          assert.ok(doc.getElementById(href.slice(1)), href)
        } else if (!href.startsWith('https://')) {
          assert.ok(href.startsWith(ROOT), href)
          assert.ok(existsSync(join(out, href.slice(ROOT.length), 'index.html')), href)
        }
      }
    })

    it('loads only its own files, and collects nothing', () => {
      const srcs = [...doc.querySelectorAll('script[src], link[href]')].map(
        (el) => (el.getAttribute('src') || el.getAttribute('href')).split('?')[0],
      )
      assert.deepEqual(srcs.sort(), [`${ROOT}course.css`, `${ROOT}course.js`, `${ROOT}favicon.svg`])
      assert.equal(doc.querySelectorAll('script:not([src])').length, 0)
      for (const f of doc.querySelectorAll('form')) {
        assert.ok(!f.hasAttribute('action'), 'forms must not submit anywhere')
        assert.ok(f.querySelector('fieldset[disabled]'))
      }
    })

    it('mentions PatentLint only in the footer disclosure and the Part 4 tool slot', () => {
      const clone = doc.body.cloneNode(true)
      clone.querySelectorAll('.disclosure, .embed-slot').forEach((el) => el.remove())
      assert.doesNotMatch(clone.textContent, /PatentLint/)
      assert.doesNotMatch(html, /pricing|sign up|subscribe|upgrade|free trial/i)
    })

    it('uses no em or en dashes', () => {
      assert.doesNotMatch(html, /[–—]/)
    })
  })
}
