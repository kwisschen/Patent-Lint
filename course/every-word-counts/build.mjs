// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025-2026 Christopher Chen
//
// Static generator for the "Every Word Counts" course skeleton.
//
//   node every-word-counts/build.mjs [siteDir]     (run from course/)
//
// Writes the whole site into siteDir (default: course/dist): the course under
// siteDir/every-word-counts/ and a site-wide 404.html. course/ is its own
// Vercel project served at https://learn.patentlint.com, a separate origin from
// the PatentLint product: separate deploys, rollbacks, headers and browser
// storage. Nothing in frontend/ imports, builds or serves any of this.
//
// The build uses only Node built-ins, so the Vercel build installs nothing and
// a registry outage cannot block a course deploy.

import { createHash } from 'node:crypto'
import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { EXTRAS, PARTS } from './pages.mjs'

const here = dirname(fileURLToPath(import.meta.url))
const courseDir = resolve(here, '..')

// FROZEN FOR THE SEMESTER. https://learn.patentlint.com/every-word-counts/ is
// registered with the course as its final URL, and every route below it is
// linked from outside. build.test.js pins ROOT and the route list; changing
// either breaks published links.
export const SITE = 'https://learn.patentlint.com'
export const DIR = 'every-word-counts'
export const ROOT = `/${DIR}/`

const STRINGS = JSON.parse(readFileSync(join(here, 'strings.json'), 'utf8'))
const EN = STRINGS.en

const esc = (s) =>
  String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

const fill = (s, args = {}) => s.replace(/\{(\w+)\}/g, (m, k) => (k in args ? args[k] : m))

// A translatable span. The English text is baked in so the page reads fully
// without JavaScript; course.js swaps it when the reader picks 中文.
function t(key, args) {
  if (!(key in EN)) throw new Error(`strings.json has no key "${key}"`)
  const a = args ? ` data-i18n-args="${esc(JSON.stringify(args))}"` : ''
  return `<span data-i18n="${key}"${a}>${esc(fill(EN[key], args))}</span>`
}

const href = (slug) => (slug ? `${ROOT}${slug}/` : ROOT)

function navHtml(current) {
  const item = (slug, key, extra = '') => {
    const cur = slug === current ? ' aria-current="page"' : ''
    return `<li><a href="${href(slug)}"${cur}>${t(key)}</a>${extra}</li>`
  }
  const parts = PARTS.map((p) =>
    item(p.slug, p.key, ` <span class="nav-time">${t('minutes', { min: p.minutes })}</span>`),
  ).join('\n')
  const more = EXTRAS.filter((e) => ['word-wall', 'ask'].includes(e.slug))
    .map((e) => item(e.slug, e.key))
    .join('\n')
  return `<nav id="course-nav" class="course-nav" aria-labelledby="course-nav-heading">
<h2 id="course-nav-heading" class="nav-heading">${t('navLabel')}</h2>
<ul class="nav-list">
${item('', 'home')}
</ul>
<h3 class="nav-subheading">${t('navParts')}</h3>
<ol class="nav-list" start="0">
${parts}
</ol>
<h3 class="nav-subheading">${t('navMore')}</h3>
<ul class="nav-list">
${more}
</ul>
</nav>`
}

function layout({ slug, title, main, assets }) {
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>${esc(title)} | Every Word Counts</title>
<link rel="icon" href="${ROOT}favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="${ROOT}course.css?v=${assets.css}">
<script src="${ROOT}course.js?v=${assets.js}" defer></script>
</head>
<body>
<a class="skip-link" href="#main">${t('skip')}</a>
<header class="site-header">
<div class="draft-banner" role="note"><strong>${t('draft')}</strong></div>
<div class="header-inner">
<a class="course-title" href="${ROOT}">${t('courseTitle')}</a>
<div class="header-tools">
<a class="menu-jump" href="#course-nav">${t('menuJump')}</a>
<div class="lang-toggle" role="group" aria-labelledby="lang-group-label" hidden>
<span id="lang-group-label" class="visually-hidden">${t('langGroup')}</span>
<button type="button" data-lang="en" lang="en" aria-pressed="true">EN</button>
<button type="button" data-lang="zh-Hant" lang="zh-Hant" aria-pressed="false">中文</button>
</div>
</div>
</div>
</header>
<div class="page">
<main id="main" tabindex="-1">
${main}
</main>
${navHtml(slug)}
</div>
<footer class="site-footer">
<nav aria-label="${esc(EN.footerLabel)}" data-i18n-aria="footerLabel">
<ul class="footer-links">
<li><a href="${href('sources')}">${t('sources')}</a></li>
<li><a href="${href('accessibility')}">${t('accessibility')}</a></li>
<li><a href="${href('about')}">${t('about')}</a></li>
</ul>
</nav>
<p class="disclosure">${t('disclosure')}</p>
</footer>
</body>
</html>
`
}

function homeMain() {
  const total = PARTS.reduce((n, p) => n + p.minutes, 0)
  const list = PARTS.map(
    (p) =>
      `<li><a href="${href(p.slug)}">${t(p.key)}</a> <span class="nav-time">${t('minutes', { min: p.minutes })}</span></li>`,
  ).join('\n')
  return `<h1>Every Word Counts: The Format and Language of a U.S. Patent Application</h1>
<p class="subtitle" lang="zh-Hant">一字千金：美國專利申請文件的格式與用語</p>
<p class="lede">A self-paced unit of about six hours for anyone who works on U.S. patent applications: engineers, formalities and filing staff, paralegals, translators, and attorneys new to U.S. practice. You can take it with a one-week cohort or alone at any time.</p>
<p><a class="button" href="${href(PARTS[0].slug)}">${t('start')}</a></p>
<h2>The seven parts</h2>
<ol class="part-list" start="0">
${list}
</ol>
<p class="total">Total: about ${Math.round(total / 60)} hours (${total} minutes).</p>
<aside class="glossary" aria-labelledby="glossary-heading">
<h2 id="glossary-heading">${t('glossaryLabel')}</h2>
<p>${t('glossary')}</p>
</aside>`
}

function partMain(p, i) {
  const prev = i === 0 ? { slug: '', key: 'home' } : PARTS[i - 1]
  const next = PARTS[i + 1]
  const sections = [
    ['why', 'secWhy', p.why],
    ['learn', 'secLearn', p.learn],
    ['try', 'secTry', p.try],
    ['check', 'secCheck', p.check],
  ]
    .map(
      ([id, key, body], n) => `<section class="part-section" aria-labelledby="sec-${id}">
<h2 id="sec-${id}"><span class="sec-num" aria-hidden="true">${n + 1}</span> ${t(key)}</h2>
${body}
</section>`,
    )
    .join('\n')
  const pagerLink = (target, dir) =>
    target
      ? `<a class="pager-${dir}" href="${href(target.slug)}"><span class="pager-dir">${t(dir)}</span> ${t(target.key)}</a>`
      : ''
  return `<p class="part-meta">${t('partOf', { n: p.n })} <span aria-hidden="true">·</span> ${t('time', { min: p.minutes })}</p>
<h1>${t(p.key)}</h1>
${sections}
<nav class="pager" aria-label="${esc(EN.pager)}" data-i18n-aria="pager">
${pagerLink(prev, 'prev')}
${next ? pagerLink(next, 'next') : pagerLink({ slug: '', key: 'home' }, 'next')}
</nav>`
}

const hash = (s) => createHash('sha256').update(s).digest('hex').slice(0, 8)

// The course's own tab icon: a teal page with a folded corner. Never the
// product's favicon.
const FAVICON = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><path d="M6 2h14l6 6v22H6z" fill="#146157"/><path d="M20 2v6h6" fill="#299e8f"/><path d="M10 14h12M10 19h12M10 24h8" stroke="#fff" stroke-width="2"/></svg>
`

const notFoundMain = () => `<h1>Page not found</h1>
<p>This page does not exist. It may have moved while the course is in development.</p>
<p><a href="${ROOT}">${t('home')}</a></p>`

export function build(siteDir) {
  const outDir = join(siteDir, DIR)
  const css = readFileSync(join(here, 'course.css'), 'utf8')
  // The client script gets the whole strings file inlined, so the toggle needs
  // no second request and strings.json stays the single source of truth.
  const js = readFileSync(join(here, 'course.js'), 'utf8').replace(
    '/*__STRINGS__*/null',
    JSON.stringify(STRINGS),
  )
  if (js.includes('/*__STRINGS__*/')) throw new Error('course.js strings marker not replaced')
  const assets = { css: hash(css), js: hash(js) }

  rmSync(siteDir, { recursive: true, force: true })
  mkdirSync(outDir, { recursive: true })
  writeFileSync(join(outDir, 'course.css'), css)
  writeFileSync(join(outDir, 'course.js'), js)
  writeFileSync(join(outDir, 'favicon.svg'), FAVICON)
  writeFileSync(join(siteDir, '404.html'), layout({ slug: null, title: 'Page not found', main: notFoundMain(), assets }))

  const pages = [{ slug: '', title: EN.home, main: homeMain() }]
  PARTS.forEach((p, i) => pages.push({ slug: p.slug, title: EN[p.key], main: partMain(p, i) }))
  for (const e of EXTRAS) {
    const title = e.title || EN[e.key]
    pages.push({ slug: e.slug, title, main: `<h1>${e.title ? esc(title) : t(e.key)}</h1>\n${e.body}` })
  }
  for (const pg of pages) {
    const html = layout({ ...pg, assets }).replaceAll('{{root}}', ROOT)
    const dir = join(outDir, pg.slug)
    mkdirSync(dir, { recursive: true })
    writeFileSync(join(dir, 'index.html'), html)
  }
  return pages.map((p) => p.slug)
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const site = resolve(courseDir, process.argv[2] || 'dist')
  const slugs = build(site)
  console.log(`course: wrote ${slugs.length} pages to ${join(site, DIR)}`)
}
