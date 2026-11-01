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

const P5 = 'part-5-filing-ready'
const DRAFT = 'Filing-Ready-Draft-Self-Watering-Planter.docx'
const TEMPLATE = 'Note-to-a-Colleague-Template.docx'

// What happens after a Part 5 submission. Shown on the Part 5 page and on the
// page the form opens after submitting.
const AFTER_SUBMIT = `<ul>
<li><strong>Day 6:</strong> the answer key and a short debrief video open for the whole cohort. In the video I walk through the problems most of the cohort missed. Compare the key with your tracked changes.</li>
<li><strong>By the end of Day 7:</strong> I reply to your note as the reader you chose, with your rubric levels. If something in your note is unclear, I tell you what I would need to know, as that reader would.</li>
<li><strong>Part 6:</strong> you talk one of your changes through with a colleague in any role. They ask you why you made it. If they could act on your note, they confirm it with one click.</li>
</ul>`

// Part 5 submission form, hosted by Tally. Paste the form ID from Tally's
// Share tab (the part after tally.so/r/). Empty = placeholder until the form
// exists. The page loads no Tally script: course.js listens for the iframe's
// "Tally.FormSubmitted" message and opens the answer key.
export const TALLY_FORM_ID = 'aO9BP9'

function submitForm() {
  if (!TALLY_FORM_ID) {
    return ph('Submission form', 'The upload form will appear here.')
  }
  const id = encodeURIComponent(TALLY_FORM_ID)
  return `<div class="form-embed">
<iframe src="https://tally.so/embed/${id}?alignLeft=1&amp;hideTitle=1&amp;transparentBackground=1" title="Part 5 submission form" loading="lazy" height="1100" data-done="{{root}}${P5}/submitted/"></iframe>
</div>
<p>If the form does not load (some office browsers block it), <a href="https://tally.so/r/${id}" target="_blank" rel="noopener">open the form in a new tab</a>.</p>`
}

const checkYourself = ph('Self-check questions', 'Three short questions with feedback on each answer.')

// The seven parts, in course order. `key` names the title in strings.json.
export const PARTS = [
  {
    slug: 'start-here', n: 0, key: 'p0', minutes: 25,
    why: '<p>This part shows you how the course works and how to set it up for the way you learn best.</p>',
    learn: `${ph('Welcome video', 'A short video from the instructor.')}
<p>${stub('Transcript')}</p>
<h3>How this course works</h3>
<p>The course has six parts after this one. Each part has the same four sections: why the topic matters, a short lesson, an activity to try, and a self-check. You take the course with a cohort. The cohort starts together and has one week to finish, and you choose when to work within that week.</p>`,
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
    check: `<h3>Reflection</h3>
<p>After you check the answer key, answer these three questions for yourself:</p>
<ol>
<li>What did you catch that the checker missed?</li>
<li>What did the checker catch that you missed?</li>
<li>Explain one fix in two sentences and name its rule. (This is practice for the note you will write in Part 5.)</li>
</ol>
${ph('Cohort results', 'How your answers compare with other learners in your cohort.')}`,
  },
  {
    slug: 'part-5-filing-ready', n: 5, key: 'p5', minutes: 75,
    why: `<p>This is the work you will do on Monday. At the office, nobody gives you a list of errors. You read the document as a whole and catch the problems before the examiner does. Then you explain them so the next person can act. That second step matters as much as the first. A correct fix that nobody understands is often undone.</p>
<p>This graded assessment brings together Parts 1 to 4. When you finish, you will have shown that you can:</p>
<ul>
<li>read a draft as one document and find its format and language problems</li>
<li>fix them correctly, and flag the ones that need a drafter's decision</li>
<li>explain a change to a colleague clearly and respectfully, with the rule behind it</li>
</ul>`,
    learn: `<p class="part-meta">About 75 minutes · Individual · Not timed · You can do it across several sittings · Best on a computer</p>
<details class="panel" lang="zh-Hant">
<summary>中文摘要</summary>
<p>這份評量模擬事務所的真實工作：同事交給你一份即將送件的專利申請草稿（自動給水花盆），請你把它修正到可以送件的狀態，並寫一段給同事的說明。</p>
<ul>
<li>要交兩份檔案：開啟「追蹤修訂」的修正後草稿，以及約 150 字的英文說明，解釋你最重要的三項修改。</li>
<li>草稿中約有 10 個格式與用語問題，類型都和第 4 部分練習過的相同。</li>
<li>如果修改會改變請求項的範圍（例如 comprising 與 consisting of），請不要直接修改，而是加上註解詢問撰稿人。適當的提問也算答對。</li>
<li>說明中的每項修改都要寫出：改了什麼、為什麼重要、依據哪一條規定。</li>
<li>另外回答一個問題：你最沒把握的是哪一項修改？為什麼？</li>
<li>請在梯次第 5 天結束前提交。第 6 天公布解答與檢討影片；第 7 天結束前，我會以你所選讀者的角度回覆你的說明，並附上評分。</li>
</ul>
<p>全程約 75 分鐘，不計時，可以分次完成。說明請用英文撰寫，本摘要僅供參考。</p>
</details>
<h3>What you will do</h3>
<p>A colleague has handed you a draft application for a new invention, a self-watering planter. It needs to be filed soon. Your job is to make it filing-ready, and then to tell a colleague what you changed and why.</p>
<p>You will hand in two things:</p>
<ol>
<li>the corrected draft, with Track Changes turned on</li>
<li>a short note to a colleague (about 150 words) explaining your three most important changes</li>
</ol>
<h3>Before you start</h3>
<ul class="downloads">
<li><a href="{{root}}${P5}/${DRAFT}" download>Filing-Ready draft: Self-Watering Planter</a> <span class="nav-time">Word file</span></li>
<li><a href="{{root}}${P5}/${TEMPLATE}" download>Note to a colleague: template</a> <span class="nav-time">Word file</span></li>
</ul>
<p>Keep these open: <a href="{{root}}sources/">Rules &amp; Sources</a>, the glossary on the <a href="{{root}}">course home</a>, and your answer key from <a href="{{root}}part-4-find-it-fix-it/">Part 4</a>. Read the rubric below first. There are no surprises in it.</p>
<h3>Step by step</h3>
<ol class="steps">
<li><strong>Read the whole draft once</strong> without changing anything (about 8 minutes).</li>
<li><strong>Turn on Track Changes and fix what you find</strong> (about 35 minutes). The draft has about 10 problems. They are the same kinds you met in Part 4. Nothing is new.</li>
<li><strong>Flag, don't decide, scope questions.</strong> If fixing something would change what a claim covers (for example, "comprising" versus "consisting of"), do not change it. Add a Word comment that names the issue and asks the drafter. A good flag counts as a correct answer.</li>
<li><strong>Use the checker from Part 4 after your own pass.</strong> If it flags something, check the rule before you change anything. It will not find every problem in this draft. That is on purpose.</li>
<li><strong>Write your note</strong> (about 150 words, about 18 minutes). Choose your reader: a drafter, someone on the filing team, a client liaison, or another colleague. For each of your three changes, say what you changed, why it matters, and which rule applies (for example, 37 CFR 1.75(f)). Write in English. Plain sentences are better than legal-sounding ones.</li>
<li><strong>Answer one question:</strong> which change are you least sure of, and why? (about 7 minutes). There is no wrong answer. It tells me where to focus my reply.</li>
<li><strong>Submit</strong> (about 5 minutes).</li>
</ol>
<p>Using a screen reader, or is Track Changes hard for you? Use the change-log table at the end of the note template instead. It counts the same.</p>
<p>You may use the checker, the glossary, and any other tool to check your work, as you would at the office. The changes and the note must be yours. If a tool changed your mind about something, say so in the note.</p>
<h3 id="rubric-heading">How your work is evaluated</h3>
<div class="table-wrap" role="region" aria-labelledby="rubric-heading" tabindex="0">
<table>
<thead><tr><th scope="col">Criterion</th><th scope="col">Ready to file</th><th scope="col">Almost there</th><th scope="col">Not yet</th></tr></thead>
<tbody>
<tr><th scope="row">1. Accuracy</th><td>Every change is correct, and no new errors were introduced.</td><td>Most changes are correct. One or two need another look, or create a small new problem.</td><td>Several changes are incorrect or create new problems.</td></tr>
<tr><th scope="row">2. Completeness</th><td>You fixed or flagged 9 or 10 of the planted problems.</td><td>You fixed or flagged 6 to 8.</td><td>You fixed or flagged 5 or fewer.</td></tr>
<tr><th scope="row">3. Rule citations</th><td>All three changes in your note name the correct rule.</td><td>Two do, or one citation is close but not exact.</td><td>One or none do.</td></tr>
<tr><th scope="row">4. Clarity of the note</th><td>Your reader could act on it without asking you anything. It says what changed, where, and why it matters, in plain, respectful language.</td><td>Your reader would need to ask you one question.</td><td>Your reader would need to come back to you to understand it.</td></tr>
</tbody>
</table>
</div>
<p>I use this rubric when I reply to you. The levels are feedback, not a pass or fail. You earn the Letters Patent badge by submitting both parts and completing Part 6, the same way in every role. A "Not yet" tells you exactly what to practice next.</p>`,
    try: `<h3>Submit your work</h3>
<p>Upload your corrected draft and your note (Word files, under 10 MB each), and answer the "least sure" question. Your work is due by the end of Day 5 of your cohort week.</p>
<p>Please use only the course files. Never upload client documents. Uploaded files are deleted 90 days after you submit.</p>
${submitForm()}`,
    check: `<h3>What happens after you submit</h3>
${AFTER_SUBMIT}
<p>Take your time. Precision matters more than speed here. Every word counts. Christopher</p>`,
  },
  {
    slug: 'part-6-wrap-up', n: 6, key: 'p6', minutes: 25,
    why: '<p>This part helps you turn what you learned into a checklist you can use at work.</p>',
    learn: `${ph('Personal checklist', 'Build your own checklist from the course.')}
${ph('Talk-through guide', 'Ten minutes with any colleague: explain one change from your Part 5 note. Your colleague asks why you made it, then confirms if they could act on it.')}`,
    try: `${ph('"Letters Patent" badge', 'A course completion badge.')}
${ph('Caught It board', 'After the course, share an error you caught in your own work (fictional details only). Each cohort debrief features one catch.')}`,
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
<p>About six hours in total, spread over one cohort week. You choose when to work within that week.</p>`,
  },
  {
    slug: 'sources', key: 'sources',
    body: `<p>The course is based on these rules. Each lesson links to the rule it teaches. When this page and a rule disagree, the rule wins.</p>
<h2>Statute</h2>
<ul>
<li><a href="https://www.law.cornell.edu/uscode/text/35/112">35 U.S.C. § 112</a>: the specification; (d) a dependent claim refers to a claim previously set forth</li>
</ul>
<h2>Regulations (37 CFR)</h2>
<ul>
<li><a href="https://www.law.cornell.edu/cfr/text/37/1.52">37 CFR 1.52</a>: language, paper, writing, margins</li>
<li><a href="https://www.law.cornell.edu/cfr/text/37/1.71">37 CFR 1.71(a)</a>: the specification in full, clear, concise, and exact terms</li>
<li><a href="https://www.law.cornell.edu/cfr/text/37/1.72">37 CFR 1.72(b)</a>: the abstract, on a separate page, preferably 150 words or fewer</li>
<li><a href="https://www.law.cornell.edu/cfr/text/37/1.75">37 CFR 1.75</a>: claims; (c) dependent form, (f) consecutive numbering, (h) claims start on a separate page</li>
<li><a href="https://www.law.cornell.edu/cfr/text/37/1.77">37 CFR 1.77(b)</a>: the order of sections in the specification</li>
<li><a href="https://www.law.cornell.edu/cfr/text/37/1.84">37 CFR 1.84(p)(4)</a>: one part, one reference numeral</li>
</ul>
<h2>Manual of Patent Examining Procedure (MPEP)</h2>
<ul>
<li><a href="https://www.uspto.gov/web/offices/pac/mpep/s608.html">MPEP 608</a>: disclosure, including 608.01(b) abstract, 608.01(m) form of claims (each claim is one sentence), and 608.01(n) dependent claims</li>
<li><a href="https://www.bitlaw.com/source/mpep/2111-03.html">MPEP 2111.03</a>: transitional phrases ("comprising," "consisting of")</li>
<li><a href="https://www.bitlaw.com/source/mpep/2173-05-e.html">MPEP 2173.05(e)</a>: lack of antecedent basis</li>
</ul>
<p>Verified on: 31 October 2026</p>
<p>This course teaches formal requirements. It is not legal advice.</p>`,
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
  {
    slug: 'part-5-filing-ready/answer-key', key: 'p5',
    title: 'Part 5 answer key and model answer',
    body: `<p class="part-meta">Draft version A · This page opens on Day 6 of each cohort week, after the submission deadline.</p>
<p class="lede">Compare this key with your tracked changes. Where they differ, read the rule again before you move on.</p>
${ph('Debrief video', 'A short video in which I walk through the problems most of the cohort missed.')}
<p><a href="{{root}}${P5}/">Back to Part 5</a></p>
<h2 id="key-heading">The 10 planted problems</h2>
<div class="table-wrap" role="region" aria-labelledby="key-heading" tabindex="0">
<table>
<thead><tr><th scope="col">#</th><th scope="col">Where</th><th scope="col">Problem</th><th scope="col">What to do</th><th scope="col">Rule</th></tr></thead>
<tbody>
<tr><td>1</td><td>Section order</td><td>The Detailed Description comes before the Brief Description of the Drawings.</td><td>Fix: move the Brief Description of the Drawings above the Detailed Description, then renumber the paragraphs.</td><td>37 CFR 1.77(b)</td></tr>
<tr><td>2</td><td>Abstract</td><td>About 210 words.</td><td>Fix: cut it to 150 words or fewer. Keep the key parts (housing, reservoir, inner pot, wick) and drop sizes and materials.</td><td>37 CFR 1.72(b)</td></tr>
<tr><td>3</td><td>Claims heading</td><td>The claims start on the same page as the description.</td><td>Fix: insert a page break so the claims start on a new page.</td><td>37 CFR 1.75(h)</td></tr>
<tr><td>4</td><td>Paragraph [0007]</td><td>"water reservoir 16." Numeral 16 is the inner pot.</td><td>Fix: "water reservoir 14."</td><td>37 CFR 1.84(p)(4)</td></tr>
<tr><td>5</td><td>Paragraph [0009]</td><td>"feed strip 18." Everywhere else, part 18 is the wick.</td><td>Fix: "wick 18."</td><td>37 CFR 1.71(a)</td></tr>
<tr><td>6</td><td>Claim 3</td><td>"the drainage tray" with no earlier "a drainage tray."</td><td>Fix: "further comprising a drainage tray removably attached to a bottom of the outer housing."</td><td>MPEP 2173.05(e)</td></tr>
<tr><td>7</td><td>Claim 4</td><td>Depends on claim 8, which comes after it.</td><td>Fix: move it after the water-level indicator claim and make it depend on that claim.</td><td>35 U.S.C. 112(d); MPEP 608.01(n)</td></tr>
<tr><td>8</td><td>Claim numbers</td><td>The numbers skip from 5 to 7.</td><td>Fix: number the claims 1 to 8 and update every "of claim" reference.</td><td>37 CFR 1.75(f)</td></tr>
<tr><td>9</td><td>Claim 7</td><td>Written as two sentences.</td><td>Fix: one sentence: "..., the fill tube having an inner diameter of at least 10 millimeters."</td><td>MPEP 608.01(m)</td></tr>
<tr><td>10</td><td>Claim 1</td><td>"Consisting of" is closed. The specification describes optional parts, and claims 3, 7, and 8 add parts.</td><td>Flag, do not fix: a comment asking the drafter whether "comprising" was intended. This is a scope decision.</td><td>MPEP 2111.03</td></tr>
</tbody>
</table>
</div>
<p>Problems 1, 2, 3, 4, 8, and 9 are pure format. Problems 5, 6, 7, and 10 need you to read the claims and the specification together. Not every problem is one the checker from Part 4 can find.</p>
<h2>Model claims after correction</h2>
<ol class="claims">
<li>A self-watering planter, consisting of: an outer housing; a water reservoir formed in a lower portion of the outer housing; an inner pot supported in the outer housing above the water reservoir, the inner pot having a bottom opening; and a wick extending through the bottom opening from the water reservoir into the inner pot. <em>[Comment to drafter: "consisting of" may exclude the tray, fill tube, and indicator added in claims 3, 5, and 6. Did you mean "comprising"?]</em></li>
<li>The self-watering planter of claim 1, wherein the wick is made of cotton or polyester fiber.</li>
<li>The self-watering planter of claim 1, further comprising a drainage tray removably attached to a bottom of the outer housing.</li>
<li>The self-watering planter of claim 1, wherein the outer housing has an overflow hole positioned at a top of the water reservoir.</li>
<li>The self-watering planter of claim 1, further comprising a fill tube extending from a top of the outer housing into the water reservoir, the fill tube having an inner diameter of at least 10 millimeters.</li>
<li>The self-watering planter of claim 1, further comprising a water-level indicator having a float disposed in the water reservoir and a window formed in the outer housing.</li>
<li>The self-watering planter of claim 6, wherein the float has a colored top that is visible through the window.</li>
<li>The self-watering planter of claim 2, wherein the wick has a width of 5 to 15 millimeters.</li>
</ol>
<p>Other correct answers exist. For example, you may keep the claim order and fix only the reference in old claim 4, as long as every dependent claim refers to a claim before it.</p>
<h2>Model note</h2>
<blockquote class="model-note">
<p><strong>To:</strong> Filing team<br><strong>About:</strong> Self-Watering Planter draft</p>
<p><strong>1. Claim numbers.</strong> The draft skipped claim 6, and old claim 4 referred to claim 8, which came after it. I renumbered the claims 1 to 8. Old claim 4 is now claim 7 and depends on claim 6. Please use the new numbers when you count claims for fees. Rules: 37 CFR 1.75(f); 35 U.S.C. 112(d).</p>
<p><strong>2. Claim 3.</strong> "The drainage tray" had no earlier "a drainage tray," so an examiner could reject the claim as unclear. It now says "further comprising a drainage tray." Rule: MPEP 2173.05(e).</p>
<p><strong>3. Claim 1 (not changed).</strong> It says "consisting of," which may shut out the tray and indicator that later claims add. That is a scope choice, so I left a comment for the drafter. Rule: MPEP 2111.03.</p>
<p>Everything else is in Track Changes.</p>
</blockquote>
<h2>Why this note works</h2>
<ul>
<li>It names its reader and tells them what to do with the change (count claims by the new numbers).</li>
<li>Each change says where, what, why it matters, and the rule.</li>
<li>It flags the scope question for the person who owns that decision, instead of deciding it.</li>
<li>It is plain and short: about 150 words.</li>
</ul>
<p>Next: <a href="{{root}}part-6-wrap-up/">Part 6, Wrap-Up</a>, where you talk one change through with a colleague.</p>`,
  },
  {
    slug: 'part-5-filing-ready/submitted', key: 'p5',
    title: 'Part 5: your work is in',
    body: `<p class="lede">Thank you. Your work is in.</p>
<h2>What happens next</h2>
${AFTER_SUBMIT}
<p>You can start <a href="{{root}}part-6-wrap-up/">Part 6</a> now. Your note is ready for the talk-through.</p>
<p><a href="{{root}}${P5}/">Back to Part 5</a></p>`,
  },
]
