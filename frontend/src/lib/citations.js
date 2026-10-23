// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025-2026 Christopher Chen
//
// Statute citations and explain-copy keys for a check's message_key. Shared by
// CheckItem, TriagePanel and the tooltip-parity test; kept out of the
// component file so React fast refresh can treat CheckItem as a component.

const CITATION_MAP = {
  'check.spec.restrictiveWording': '§ 112(b)',
  // Re-pinned in #464 after verifying the primary source: MPEP § 608.01
  // quotes 37 CFR 1.52(b)(6) for paragraph numbering, and § 608.01(p) is a
  // different subject entirely. This badge kept showing the old citation
  // after that PR corrected models.py, the six locale files and CHECKS.md -
  // a fourth surface nobody thought to grep. Cross-check every citation
  // surface when re-pinning one.
  'check.spec.paragraphSequential': '37 CFR 1.52(b)(6)',
  // paragraphEnding carries NO citation: verified against the primary
  // source (report #600) that MPEP § 608.01 states no paragraph-punctuation
  // requirement at all. It had cited § 608.01(p), which is Completeness of
  // Specification. The reporter proposed § 608.01(m), which is Form of
  // Claims and governs claims, not specification paragraphs. Both are wrong,
  // so the badge is dropped rather than re-pinned - this is a drafting
  // convention, and the AboutPage already labels the EPC twin as hygiene.
  'check.spec.sequenceListing': '§ 2422',
  'check.spec.crossReference': '§ 608.01',
  'check.spec.priorArt': '§ 608.01(c)',
  'check.spec.drawings': '§ 608.02',
  'check.claims.restrictiveAbsolutes': '§ 2173.01',
  'check.claims.indefiniteWording': '§ 2173.05(b)',
  'check.claims.sequential': '§ 608.01(m)',
  'check.claims.multipleDependent': '§ 608.01(n)',
  'check.claims.selfDependent': '§ 112(d)',
  'check.claims.missingPeriod': '§ 608.01(m)',
  'check.claims.extraPeriod': '§ 608.01(m)',
  'check.claims.whereinComma': '§ 608.01(m)',
  'check.claims.meansFunction': '§ 112(f)',
  'check.claims.antecedentBasis': '§ 112(b)',
  'check.claims.preamble': '§ 112(d)',
  'checks.preamble_noun_mismatch': '§ 112(d)',
  'checks.preamble_cross_category_mismatch': '§ 112(d)',
  'checks.preamble_indefinite_article': '§ 608.01(m)',
  'checks.preamble_cross_category_pass': '§ 112(d)',
  'check.claims.missingTransition': '§ 112(b)',
  'check.claims.transitionsPresent': '§ 112(b)',
  'claims.missingPeriod': '§ 608.01(m)',
  'claims.extraPeriod': '§ 608.01(m)',
  'claims.whereinComma': '§ 608.01(m)',
  'claims.punctuationPass': '§ 608.01(m)',
  'claims.jepsonPriorArt': '§ 2129',
  'claims.crmNonTransitory': '§ 101',
  'claims.markushOpenTransition': '§ 2117',
  'claims.omnibusClaim': '§ 112(b)',
  'checks.spec_support_unsupported_terms': '§ 112(a)',
  'check.abstract.legalPhraseology': '§ 608.01(b)',
  'check.abstract.meritLanguage': '§ 608.01(b)',
  'check.abstract.structure': '§ 608.01(b)',
  'check.abstract.impliedPhrases': '§ 608.01(b)',
  'check.abstract.wordCount': '§ 608.01(b)',
  'check.drawings.singleFigure': '§ 608.02',
  'check.drawings.priorArt': '§ 608.02',
  'check.drawings.sequential': '§ 608.02',
  'check.drawings.count': '§ 608.02',
}

// Citation badges are bare section numbers - `§ 112(b)`, `§ 2129`, `§ 101` -
// which say nothing on their own to a reader who does not already know the
// number. This maps the badge text to a `tooltip.citation.*` key carrying the
// instrument and the section's subject.
//
// SCOPED TO THE US SHORTHAND ON PURPOSE. The CN / TW / EPC references this
// component also renders already name their instrument (`專利法施行細則 §18`,
// `Rule 43(4) EPC`, `EPO Guidelines F-II § 2.3`), so a tooltip there would
// restate what is already on screen. A citation with no entry renders exactly
// as before, with no trigger and no affordance.
//
// Every title below was verified against the USPTO primary source rather than
// recalled - this file has already shipped a wrong citation twice (#464, #600).
const CITATION_TOOLTIP_KEY = {
  '35 U.S.C. \u00a7 112(a)': '112a',
  '\u00a7 112(a)': '112a',
  '\u00a7 112(b)': '112b',
  '\u00a7 112(d)': '112d',
  '\u00a7 112(f)': '112f',
  '\u00a7 101': '101',
  '37 CFR 1.52(b)(6)': 'cfr1526',
  '\u00a7 608.01': '60801',
  '\u00a7 608.01(b)': '60801b',
  '\u00a7 608.01(c)': '60801c',
  '\u00a7 608.01(m)': '60801m',
  '\u00a7 608.01(n)': '60801n',
  '\u00a7 608.02': '60802',
  '\u00a7 2117': '2117',
  '\u00a7 2129': '2129',
  '\u00a7 2173.01': '217301',
  '\u00a7 2173.05(b)': '217305b',
  '\u00a7 2422': '2422',
}

export function getCitationTooltipKey(citation) {
  const slug = citation && CITATION_TOOLTIP_KEY[citation.trim()]
  return slug ? `tooltip.citation.${slug}` : null
}

// Optional plain-language explainer for a check, keyed `explain.<base>` where
// <base> is the message key with its .pass/.verify/.amend suffix stripped.
// Exists because several checks are correct but opaque without domain context:
// "No special claim format issues detected" does not tell a drafter WHICH
// formats were examined. Purely additive - a check with no explain key renders
// exactly as before.
export function getExplainKey(messageKey) {
  if (!messageKey) return null
  return `explain.${messageKey.replace(/\.(pass|verify|amend|missing)$/, '')}`
}

export function getCitation(messageKey) {
  if (!messageKey) return null
  // Try exact match first, then strip .pass/.verify/.amend suffix
  if (CITATION_MAP[messageKey]) return CITATION_MAP[messageKey]
  const base = messageKey.replace(/\.(pass|verify|amend)$/, '')
  return CITATION_MAP[base] || null
}
