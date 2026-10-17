// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025-2026 Christopher Chen
//
// Gates the course skeleton's hard constraints on the GENERATED pages, not on
// the source: every route exists, carries noindex and the draft banner, has the
// landmarks and a single h1, links only to pages that exist, mentions
// PatentLint only where allowed, and loads nothing but its own two assets.
// The deploy step tolerates a course build failure so the product always
// ships; this test is what stops a broken course from merging.
import { mkdtempSync, readFileSync, readdirSync, existsSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { build, ROOT } from './build.mjs'
import STRINGS from './strings.json'

const ROUTES = [
  '', 'start-here', 'part-1-anatomy', 'part-2-specification', 'part-3-claims',
  'part-4-find-it-fix-it', 'part-5-filing-ready', 'part-6-wrap-up',
  'word-wall', 'ask', 'sources', 'accessibility', 'about',
]

const out = mkdtempSync(join(tmpdir(), 'ewc-'))
const slugs = build(out)
const pages = Object.fromEntries(
  slugs.map((s) => {
    const html = readFileSync(join(out, s, 'index.html'), 'utf8')
    return [s, { html, doc: new DOMParser().parseFromString(html, 'text/html') }]
  }),
)

describe('course skeleton', () => {
  it('builds exactly the routes in the handoff', () => {
    expect([...slugs].sort()).toEqual([...ROUTES].sort())
  })

  it('has the same keys in every language', () => {
    expect(Object.keys(STRINGS['zh-Hant']).sort()).toEqual(Object.keys(STRINGS.en).sort())
  })

  it('inlines the strings into course.js', () => {
    const js = readFileSync(join(out, 'course.js'), 'utf8')
    expect(js).not.toContain('/*__STRINGS__*/')
    expect(js).toContain(STRINGS['zh-Hant'].draft)
  })

  describe.each(ROUTES)('page "%s"', (slug) => {
    const { html, doc } = pages[slug]

    it('is noindex, lang=en, with the draft banner', () => {
      expect(doc.documentElement.getAttribute('lang')).toBe('en')
      expect(doc.querySelector('meta[name="robots"]').getAttribute('content')).toBe('noindex')
      expect(doc.querySelector('.draft-banner').textContent).toContain(STRINGS.en.draft)
    })

    it('has landmarks, a skip link, and exactly one h1', () => {
      for (const sel of ['header', 'nav#course-nav', 'main#main', 'footer']) {
        expect(doc.querySelector(sel), sel).not.toBeNull()
      }
      expect(doc.querySelector('body > a.skip-link').getAttribute('href')).toBe('#main')
      expect(doc.querySelectorAll('h1')).toHaveLength(1)
    })

    it('never skips a heading level', () => {
      let prev = 0
      for (const h of doc.querySelectorAll('h1, h2, h3, h4, h5, h6')) {
        const level = Number(h.tagName[1])
        expect(level - prev, h.textContent).toBeLessThanOrEqual(1)
        prev = level
      }
    })

    it('marks all Chinese text with lang="zh-Hant"', () => {
      const walker = doc.createTreeWalker(doc.body, NodeFilter.SHOW_TEXT)
      for (let n = walker.nextNode(); n; n = walker.nextNode()) {
        if (/[一-鿿]/.test(n.data)) {
          expect(n.parentElement.closest('[lang="zh-Hant"]'), n.data).not.toBeNull()
        }
      }
    })

    it('links only to course pages that exist', () => {
      for (const a of doc.querySelectorAll('a[href]')) {
        const href = a.getAttribute('href')
        if (href.startsWith('#')) {
          expect(doc.getElementById(href.slice(1)), href).not.toBeNull()
        } else if (!href.startsWith('https://')) {
          expect(href.startsWith(ROOT), href).toBe(true)
          expect(existsSync(join(out, href.slice(ROOT.length), 'index.html')), href).toBe(true)
        }
      }
    })

    it('loads only its own stylesheet and script, and collects nothing', () => {
      const srcs = [...doc.querySelectorAll('script[src], link[href]')].map(
        (el) => el.getAttribute('src') || el.getAttribute('href'),
      )
      expect(srcs.map((s) => s.split('?')[0]).sort()).toEqual([`${ROOT}course.css`, `${ROOT}course.js`])
      expect(doc.querySelectorAll('script:not([src])')).toHaveLength(0)
      for (const f of doc.querySelectorAll('form')) {
        expect(f.hasAttribute('action'), 'forms must not submit anywhere').toBe(false)
        expect(f.querySelector('fieldset[disabled]')).not.toBeNull()
      }
    })

    it('mentions PatentLint only in the footer disclosure and the Part 4 tool slot', () => {
      const clone = doc.body.cloneNode(true)
      clone.querySelectorAll('.disclosure, .embed-slot').forEach((el) => el.remove())
      expect(clone.textContent).not.toMatch(/PatentLint/)
      expect(html).not.toMatch(/pricing|sign up|subscribe|upgrade|free trial/i)
    })

    it('uses no em or en dashes', () => {
      expect(html).not.toMatch(/[\u2013\u2014]/)
    })
  })

  it('chains Part 0 through Part 6 with next links', () => {
    const order = ROUTES.slice(1, 8)
    order.forEach((slug, i) => {
      const next = pages[slug].doc.querySelector('.pager-next').getAttribute('href')
      expect(next).toBe(i + 1 < order.length ? `${ROOT}${order[i + 1]}/` : ROOT)
    })
    expect(pages[''].doc.querySelector('a.button').getAttribute('href')).toBe(`${ROOT}start-here/`)
  })

  it('writes nothing outside its own directory', () => {
    expect(readdirSync(out).sort()).toEqual(['course.css', 'course.js', 'index.html', ...ROUTES.filter(Boolean)].sort())
  })
})
