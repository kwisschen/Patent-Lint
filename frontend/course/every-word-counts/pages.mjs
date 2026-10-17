// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025-2026 Christopher Chen
//
// Page content for the "Every Word Counts" course skeleton. Everything here is
// placeholder text except the structure, which is real. Interface strings live
// in strings.json; this file holds only page bodies, which stay English until
// the full translation pass.

const ph = (label, detail = '') =>
  `<div class="placeholder"><p class="placeholder-label"><span data-i18n="placeholder">Placeholder</span>: ${label}</p>${
    detail ? `<p>${detail}</p>` : ''
  }</div>`

// A link that does not exist yet. Rendered as text, not as a dead <a>, so it is
// never a keyboard stop that goes nowhere.
const stub = (label) =>
  `<span class="stub">${label} (<span data-i18n="comingSoon">coming soon</span>)</span>`

const checkYourself = ph('Self-check questions', 'Three short questions with feedback on each answer.')

// The seven parts, in course order. `key` names the title in strings.json.
export const PARTS = [
  {
    slug: 'start-here', n: 0, key: 'p0', minutes: 25,
    why: '<p>This part shows you how the course works and how to set it up for the way you learn best.</p>',
    learn: `${ph('Welcome video', 'A short video from the instructor.')}
<p>${stub('Transcript')}</p>
<h3>How this course works</h3>
<p>The course has six parts after this one. Each part has the same four sections: why the topic matters, a short lesson, an activity to try, and a self-check. You can take the course with a one-week cohort or alone at any time.</p>`,
    try: `<h3>Settings tour</h3>
<p>Use the <strong>EN / <span lang="zh-Hant">中文</span></strong> buttons at the top of the page to switch the interface language. Interface labels and glossary entries change; lesson text stays in English for now.</p>
${ph('Text size setting', 'A control to make all course text larger or smaller.')}
<h3>Icebreaker</h3>
<p>Think of one word or format detail that once caused a problem in a patent document you worked on. Later, you will be able to post it on the <a href="{{root}}word-wall/">Word Wall</a>.</p>`,
    check: checkYourself,
  },
  {
    slug: 'part-1-anatomy', n: 1, key: 'p1', minutes: 60,
    why: '<p>Every U.S. patent application follows the same order of sections. Knowing that order helps you find problems fast.</p>',
    learn: ph('Lesson', 'The required sections of a U.S. application and the order they appear in.'),
    try: `${ph('Section-ordering activity', 'Put the sections of an application in the correct order.')}
${ph('Label a real published patent', 'Mark each section on a real published U.S. patent.')}`,
    check: checkYourself,
  },
  {
    slug: 'part-2-specification', n: 2, key: 'p2', minutes: 50,
    why: '<p>The specification must describe the invention in clear, consistent words. One part with two names can cause real trouble.</p>',
    learn: ph('Lesson', 'How terms are introduced and used in the specification.'),
    try: `${ph('Trace a term', 'Follow one term from its first use through the whole specification.')}
<h3>Word Wall prompt</h3>
<p>Have you seen the same part called by two different names? Share it on the <a href="{{root}}word-wall/">Word Wall</a>.</p>`,
    check: checkYourself,
  },
  {
    slug: 'part-3-claims', n: 3, key: 'p3', minutes: 75,
    why: '<p>Claims set the limits of the patent. A single word in a claim can change what is protected.</p>',
    learn: `${ph('Lesson', 'Claim structure, antecedent basis, and common claim words.')}
<details class="panel">
<summary>Optional: U.S. and Taiwan claims compared</summary>
${ph('Comparison panel', 'How U.S. claim language compares with Taiwan practice.')}
</details>`,
    try: `${ph('Activity 1', 'Description to come.')}
${ph('Activity 2', 'Description to come.')}
${ph('Activity 3', 'Description to come.')}`,
    check: checkYourself,
  },
  {
    slug: 'part-4-find-it-fix-it', n: 4, key: 'p4', minutes: 60,
    why: '<p>This practice assessment lets you use what you learned on a full sample application. It does not count toward a grade.</p>',
    learn: `<p>Download the sample application, find as many errors as you can, then compare your list with the answer key.</p>
<p>${stub('Sample application (Word file)')}</p>`,
    try: `<div class="embed-slot" role="note">
<p class="placeholder-label"><span data-i18n="placeholder">Placeholder</span>: PatentLint tool</p>
<p>The PatentLint checker will appear here. It is optional: you can do every step without it.</p>
</div>
<p>To work without the tool, use the printable checklist: ${stub('Manual checklist')}</p>
<fieldset class="mock-form" disabled>
<legend>Tick the errors you found (<span data-i18n="comingSoon">coming soon</span>)</legend>
<div class="field-check"><input type="checkbox" id="err-1"><label for="err-1">Error 1 (placeholder)</label></div>
<div class="field-check"><input type="checkbox" id="err-2"><label for="err-2">Error 2 (placeholder)</label></div>
<div class="field-check"><input type="checkbox" id="err-3"><label for="err-3">Error 3 (placeholder)</label></div>
</fieldset>`,
    check: ph('Cohort results', 'How your answers compare with other learners in your cohort.'),
  },
  {
    slug: 'part-5-filing-ready', n: 5, key: 'p5', minutes: 75,
    why: '<p>This graded assessment asks you to prepare a short application section so that it is ready to file.</p>',
    learn: `${ph('Instructions', 'What to submit and how it will be graded.')}
<h3 id="rubric-heading">Rubric</h3>
<div class="table-wrap" role="region" aria-labelledby="rubric-heading" tabindex="0">
<table>
<thead><tr><th scope="col">Criterion</th><th scope="col">What we look for</th><th scope="col">Points</th></tr></thead>
<tbody>
<tr><th scope="row">Accuracy</th><td>Placeholder description.</td><td>[points]</td></tr>
<tr><th scope="row">Completeness</th><td>Placeholder description.</td><td>[points]</td></tr>
<tr><th scope="row">Source citation</th><td>Placeholder description.</td><td>[points]</td></tr>
<tr><th scope="row">Clarity of the note</th><td>Placeholder description.</td><td>[points]</td></tr>
</tbody>
</table>
</div>`,
    try: ph('Submission', 'A place to upload your work.'),
    check: checkYourself,
  },
  {
    slug: 'part-6-wrap-up', n: 6, key: 'p6', minutes: 25,
    why: '<p>This part helps you turn what you learned into a checklist you can use at work.</p>',
    learn: `${ph('Personal checklist', 'Build your own checklist from the course.')}
<p>${stub('Talk-through guide')}</p>`,
    try: ph('"Letters Patent" badge', 'A course completion badge.'),
    check: checkYourself,
  },
]

// Pages outside the part sequence. `body` follows the page's single h1.
export const EXTRAS = [
  {
    slug: 'word-wall', key: 'wordWall',
    body: `<p>The Word Wall collects words and format details that caused real problems. This page is a static preview.</p>
<form class="mock-form" aria-labelledby="ww-form-heading">
<h2 id="ww-form-heading">Add an entry (<span data-i18n="comingSoon">coming soon</span>)</h2>
<fieldset disabled>
<legend class="visually-hidden">New Word Wall entry</legend>
<div class="field"><label for="ww-word">The word or format detail</label><input type="text" id="ww-word"></div>
<div class="field"><label for="ww-wrong">What went wrong</label><textarea id="ww-wrong" rows="3"></textarea></div>
<div class="field"><label for="ww-cost">What it cost (optional)</label><textarea id="ww-cost" rows="2"></textarea></div>
<button type="submit">Post</button>
</fieldset>
</form>
<h2>Sample entries</h2>
<ul class="entries">
<li><p class="entry-word">"said" and "the"</p><p>Placeholder: a claim used both words for the same part.</p><p class="entry-count">7 people said "me too"</p></li>
<li><p class="entry-word">Figure numbers</p><p>Placeholder: a figure was cited by the wrong number.</p><p class="entry-count">4 people said "me too"</p></li>
<li><p class="entry-word">Line spacing</p><p>Placeholder: the specification did not use 1.5 or double line spacing.</p><p class="entry-count">2 people said "me too"</p></li>
</ul>`,
  },
  {
    slug: 'ask', key: 'ask',
    title: 'Ask a question and FAQ',
    body: `<form class="mock-form" aria-labelledby="ask-form-heading">
<h2 id="ask-form-heading">Ask a question (<span data-i18n="comingSoon">coming soon</span>)</h2>
<fieldset disabled>
<legend class="visually-hidden">Your question</legend>
<div class="field"><label for="ask-q">Your question</label><textarea id="ask-q" rows="4"></textarea></div>
<button type="submit">Send</button>
</fieldset>
</form>
<h2>Frequently asked questions</h2>
<h3>Do I need any software to take this course?</h3>
<p>No. A checking tool is offered in some activities, but every activity also works with a printable manual checklist.</p>
<h3>How long does the course take?</h3>
<p>About six hours in total. You can take it over one week with a cohort or alone at your own pace.</p>`,
  },
  {
    slug: 'sources', key: 'sources',
    body: `<p>The course is based on these rules. Each lesson links to the rule it teaches.</p>
<ul>
<li><a href="https://www.law.cornell.edu/uscode/text/35/112">35 U.S.C. § 112</a>: the specification</li>
<li><a href="https://www.ecfr.gov/current/title-37/section-1.52">37 CFR 1.52</a>: language, paper, writing, margins</li>
<li><a href="https://www.ecfr.gov/current/title-37/chapter-I/subchapter-A/part-1">37 CFR 1.71 to 1.77</a>: the specification, claims, abstract, and order of sections</li>
<li><a href="https://www.uspto.gov/web/offices/pac/mpep/s608.html">MPEP 608</a>: disclosure</li>
</ul>
<p>Verified on: [date to be added]</p>`,
  },
  {
    slug: 'accessibility', key: 'accessibility',
    body: `<p>This course aims to meet the Web Content Accessibility Guidelines (WCAG) 2.2 at level AA. You should be able to use every page with a keyboard, a screen reader, or text zoom, and on a screen as narrow as 320 pixels.</p>
<p>If something makes the course hard for you to use, please tell us: ${stub('Tell us what would help you')}</p>`,
  },
  {
    slug: 'about', key: 'about',
    body: ph('Instructor bio', 'A short biography of the instructor.'),
  },
]
