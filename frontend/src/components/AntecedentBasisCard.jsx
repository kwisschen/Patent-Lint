// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025–2026 Christopher Chen
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ListChecks, ChevronRight, Flag, Check, RotateCcw } from 'lucide-react'
import { Button } from './ui/button'
import { FrostCard } from './ui/frost-card'
import { StatusPill } from './ui/status-pill'
import { composeFeedback, sendReport, excerptAroundReference, SAMPLE_SIZE } from '../lib/feedback'
import { useFeedback } from './FeedbackPicker'
import ReportModal from './ReportModal'

// CJK reference-form prefixes used by the TW walker (該/所述/前述/該等/該些).
// Matched without word boundaries because CJK text has no whitespace
// breaks; the regex relies on the prefix character itself as the anchor.
// 2026-06-01: added Simplified Chinese variants (该等 / 该些 / 该).
// Without these CN finding terms fell through to the English-wrap
// regex branch (`(?:the|said)\s+...`) which never matches CJK text →
// no highlights appeared on CN drafts. 所述 / 前述 are identical
// across Traditional/Simplified so they cover both already.
const CJK_REF_PREFIXES = ['該等', '該些', '该等', '该些', '所述', '前述', '該', '该']

function isCjkRefForm(term) {
  return CJK_REF_PREFIXES.some((p) => term.startsWith(p))
}

// R63 (2026-05-05): Arabic↔CJK ordinal map. Walker normalizes 第1→第一
// at emit-time, so finding terms always carry CJK ordinals; raw claim
// text may have either form. To highlight correctly in both directions,
// every term-side ordinal token gets a regex alternation matching either
// form. Symmetric with `normalize_arabic_ordinal_to_cjk` in tw_claims.py.
const _ORDINAL_PAIRS = [
  ['一', '1'], ['二', '2'], ['三', '3'], ['四', '4'], ['五', '5'],
  ['六', '6'], ['七', '7'], ['八', '8'], ['九', '9'], ['十', '10'],
]

function expandOrdinalVariants(escaped) {
  // For each `第<CJK>` or `第<Arabic>` substring, replace with regex
  // alternation matching either form. Escape was already applied; we
  // only inject alternation tokens which are regex-safe.
  let out = escaped
  for (const [cjk, ar] of _ORDINAL_PAIRS) {
    // Replace literal `第<cjk>` with `第(?:<cjk>|<ar>)`
    out = out.replaceAll(`第${cjk}`, `第(?:${cjk}|${ar})`)
    // Replace literal `第<ar>` with `第(?:<cjk>|<ar>)`
    out = out.replaceAll(`第${ar}`, `第(?:${cjk}|${ar})`)
  }
  return out
}

function highlightTerms(text, terms) {
  if (!terms.length) return text

  // Split terms by language family. CJK reference forms are matched
  // verbatim (no word boundaries, no the/said synthesis); English/Latin
  // terms keep the original ``the X`` / ``said X`` synthesis path.
  const cjkParts = []
  const refFormParts = []
  const bareParts = []
  for (const t of terms) {
    const escaped = t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    if (isCjkRefForm(t)) {
      // Expand ordinal variants so 第一 also matches 第1 in claim text
      cjkParts.push(expandOrdinalVariants(escaped))
    } else if (/^(?:the|said)\s+/i.test(t)) {
      refFormParts.push(escaped)
    } else {
      bareParts.push(escaped)
    }
  }
  // 2026-06-01: sort alternatives by length DESCENDING. JavaScript
  // regex alternation is leftmost (first matching alternative wins),
  // not longest. Without this sort, a finding for `the two` would
  // shadow the longer `the two clamping members respectively move`
  // finding — only the `the two` prefix would highlight, leaving the
  // rest of the longer term unhighlighted. Same bug class for CJK.
  const byLengthDesc = (a, b) => b.length - a.length
  const sortedCjk = [...cjkParts].sort(byLengthDesc)
  const sortedRefForm = [...refFormParts].sort(byLengthDesc)
  const sortedBare = [...bareParts].sort(byLengthDesc)
  const englishAlternatives = [...sortedRefForm]
  if (sortedBare.length) {
    englishAlternatives.push(`(?:the|said)\\s+(?:${sortedBare.join('|')})`)
  }

  // Build a single combined pattern: CJK alternatives match verbatim
  // (no \b around them because \b doesn't fire between CJK chars in
  // JavaScript regex), English alternatives are wrapped in word
  // boundaries via a non-capturing alternation branch.
  const cjkBranch = sortedCjk.length ? `(?:${sortedCjk.join('|')})` : null
  const englishBranch = englishAlternatives.length
    ? `(?:\\b(?:${englishAlternatives.join('|')})\\b)`
    : null
  const branches = [cjkBranch, englishBranch].filter(Boolean)
  if (!branches.length) return text
  const pattern = new RegExp(branches.join('|'), 'gi')

  const parts = []
  let lastIndex = 0
  let match

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ text: text.slice(lastIndex, match.index), highlight: false })
    }
    parts.push({ text: match[0], highlight: true })
    lastIndex = pattern.lastIndex
  }

  if (lastIndex < text.length) {
    parts.push({ text: text.slice(lastIndex), highlight: false })
  }

  return parts
}

/**
 * Format a sorted list of claim IDs into a compact range string.
 * e.g. [2,3,4,5,8,10,11,12] → "Claims 2–5, 8, 10–12"
 */
function formatClaimRange(ids, t) {
  if (ids.length === 0) return ''
  if (ids.length === 1) return t('claimDiagram.claimLabel', { id: ids[0] })

  const ranges = []
  let start = ids[0]
  let end = ids[0]

  for (let i = 1; i < ids.length; i++) {
    if (ids[i] === end + 1) {
      end = ids[i]
    } else {
      ranges.push(start === end ? `${start}` : `${start}–${end}`)
      start = ids[i]
      end = ids[i]
    }
  }
  ranges.push(start === end ? `${start}` : `${start}–${end}`)

  return t('claimDiagram.claimsLabel', { range: ranges.join(', ') })
}

function ClaimGroupRow({ claimIds, terms, findings, claimTextMap, t, i18n, jurisdiction, reviewed, onToggleReviewed }) {
  // Advisory triage: a reviewed row collapses to a calm "reviewed" state and
  // drops out of the header's "to verify" count. Default-expanded for
  // un-reviewed rows so the did-you-mean hint + claim text surface without an
  // extra click; a reviewed row starts collapsed.
  const [expanded, setExpanded] = useState(!reviewed)
  const [reportModalOpen, setReportModalOpen] = useState(false)
  const [reportContext, setReportContext] = useState(null)
  const { sendFeedback } = useFeedback()
  const label = formatClaimRange(claimIds, t)

  // Build the per-claim payload + diagnostics dict shared by both the
  // anonymous send and the mailto fallback, so the modal preview matches
  // what the email body would otherwise contain.
  const buildReportContext = (claimId) => {
    const claimFindings = findings.filter((f) => f.claim_id === claimId)
    if (claimFindings.length === 0) return null

    const claimText = claimTextMap[claimId] || ''
    const claimTextCharlen = claimText.length

    // Mirror diagnostic_extractors.extract_antecedent_basis output shape so
    // the per-claim payload matches what the Python section-level extractor
    // produces, filtered to this claim only. Triage tooling already keys on
    // `findings: [...]` — no special-case handling needed.
    const findingsList = claimFindings.slice(0, SAMPLE_SIZE).map((f) => {
      const { context_before, context_after, char_offset } = excerptAroundReference(
        claimText, f.term || '', f.reference_form || null)
      const suggested = f.suggested_match || {}
      return {
        claim_id: f.claim_id,
        term: f.term || null,
        reference_form: f.reference_form || null,
        did_you_mean: suggested.term || null,
        did_you_mean_claim_id: suggested.claim_id || null,
        category: f.category || null,
        char_offset,
        context_before,
        context_after,
        claim_text_charlen: claimTextCharlen,
      }
    })

    // Walker-level fingerprints from the first finding (these are stable
    // across findings within the same claim group).
    const baseDx = claimFindings[0]?.diagnostics || {}
    return {
      claimId,
      diagnostics: {
        flagged_claim_id: claimId,
        findings_in_group: claimFindings.length,
        findings: findingsList,
        ...(baseDx.intros_pool_size !== undefined && { intros_pool_size: baseDx.intros_pool_size }),
        ...(baseDx.suggested_cross_branch !== undefined && { suggested_cross_branch: baseDx.suggested_cross_branch }),
      },
    }
  }

  const handleReport = (claimId) => {
    setReportContext(buildReportContext(claimId))
    setReportModalOpen(true)
  }

  const handleAnonymousConfirm = (userComment, disposition) => {
    if (!reportContext) return { ok: false, reason: 'no_context' }
    return sendReport({
      checkKey: 'antecedentBasis',
      jurisdiction: jurisdiction || 'unknown',
      locale: i18n.language,
      diagnostics: reportContext.diagnostics,
      userComment,
      disposition,
    })
  }

  const handleMailtoFallback = () => {
    if (!reportContext) return
    const baseDx = reportContext.diagnostics || null
    sendFeedback(
      composeFeedback(
        {
          check_key: 'antecedentBasis',
          claim_id: reportContext.claimId,
          terms: terms.join(', '),
          jurisdiction: jurisdiction || 'unknown',
          diagnostics: baseDx,
        },
        t,
        { locale: i18n.language },
      ),
      { verb: 'report' },
    )
  }
  // Row badge counts findings (one per claim-term pair), not distinct terms.
  // A row that groups claims 1/2/3/5 all sharing the single term 該使用者介面
  // represents 4 findings, not 1 — the header total must reconcile with the
  // sum of row badges.
  const findingCount = findings.length
  const hasText = claimIds.some((id) => claimTextMap[id])

  // Hint lines (did-you-mean + cross-ref) live on individual findings.
  // Aggregate by display label so each row in the expanded panel can render
  // the hints applicable to its term once.
  const hintsByLabel = {}
  for (const f of findings) {
    const label = f.reference_form || f.term
    if (!hintsByLabel[label]) hintsByLabel[label] = { didYouMean: null, crossRef: null }
    if (f.suggested_match && !hintsByLabel[label].didYouMean) {
      hintsByLabel[label].didYouMean = f.suggested_match
    }
    if (f.cross_ref === 'spec_support') {
      hintsByLabel[label].crossRef = 'spec_support'
    }
  }

  // 2026-06-25: the per-finding "Higher confidence" badge was REMOVED. It
  // ranked findings by `confidence_score`, but the confidence discriminator was
  // subsequently proven dead (no deterministic runtime feature separates a
  // benign §112 reference from a real defect — AUC ~0.60 with authoritative
  // examiner labels + nonlinear models; see project_fp_class_campaign). Showing
  // a "Higher confidence" chip on advisory findings we cannot actually rank
  // projects false confidence and discourages the verification these heuristic
  // findings require — the opposite of the advisory framing's intent.

  return (
    <div className={`transition-opacity duration-200 ${reviewed ? 'opacity-55' : ''}`}>
      <div
        role="button"
        tabIndex={0}
        className="flex items-center gap-2 px-3 py-2 rounded-md hover:bg-[var(--attention-bg)]/60 transition-colors cursor-pointer"
        onClick={() => setExpanded(!expanded)}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setExpanded(!expanded) } }}
      >
        {hasText && (
          <ChevronRight
            className={`h-3.5 w-3.5 shrink-0 transition-transform duration-200 ${expanded ? 'rotate-90' : ''}`}
            style={{ color: 'var(--attention-border)' }}
          />
        )}
        {!hasText && <span className="w-3.5 shrink-0" />}
        <span className="text-sm font-medium shrink-0" style={{ color: 'var(--attention-text)' }}>
          {label}
        </span>
        <span className={`text-sm text-muted-foreground flex-1 truncate ${reviewed ? 'line-through' : ''}`}>
          {terms.map((term, i) => (
            <span key={i}>
              {i > 0 && ', '}
              "{term}"
            </span>
          ))}
        </span>
        {!reviewed && (
          <span
            className="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold"
            style={{ backgroundColor: 'var(--attention-bg)', color: 'var(--attention-text)', border: '1px solid var(--attention-border)' }}
          >
            {findingCount} {findingCount === 1 ? t('antecedentBasis.finding') : t('antecedentBasis.findings')}
          </span>
        )}
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onToggleReviewed() }}
          className="shrink-0 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium border transition-colors hover:bg-[var(--attention-bg)]"
          style={{ color: 'var(--attention-text)', borderColor: 'var(--attention-border)' }}
          aria-pressed={reviewed}
          title={reviewed ? t('antecedentBasis.undoReviewed') : t('antecedentBasis.markReviewed')}
        >
          {reviewed ? <RotateCcw className="h-3 w-3" /> : <Check className="h-3 w-3" />}
          <span>{reviewed ? t('antecedentBasis.undoReviewed') : t('antecedentBasis.markReviewed')}</span>
        </button>
      </div>
      <div className={`overflow-hidden transition-all duration-200 ease-in-out ${expanded ? 'max-h-[2000px] opacity-100' : 'max-h-0 opacity-0'}`}>
        {claimIds.map((id) => {
          const rawText = claimTextMap[id]
          if (!rawText) return null
          // Strip leading "N. " / "N．" / "N、" the parser preserved on
          // claim.text. Without this, the rendered line duplicates the
          // claim number: the component's {id}. label + the claim-text
          // leading N. produce "1. 1. 一種...".
          const leadingNum = new RegExp(`^\\s*${id}\\s*[.．、][\\s\\u3000]*`)
          const text = rawText.replace(leadingNum, '')
          const highlighted = highlightTerms(text, terms)
          return (
            <div
              key={id}
              className="mx-3 mb-1.5 px-3 py-2 rounded text-xs leading-relaxed border flex items-start gap-2"
              style={{ borderColor: 'var(--attention-border)', backgroundColor: 'var(--attention-bg)' }}
            >
              <div className="flex-1 min-w-0">
                <span className="font-bold mr-1.5" style={{ color: 'var(--attention-text)' }}>
                  {id}.
                </span>
                {Array.isArray(highlighted) ? (
                  highlighted.map((part, i) =>
                    part.highlight ? (
                      <mark
                        key={i}
                        className="rounded px-0.5 font-semibold"
                        style={{ backgroundColor: 'var(--attention-mark-bg)', color: 'var(--attention-mark-text)' }}
                      >
                        {part.text}
                      </mark>
                    ) : (
                      <span key={i}>{part.text}</span>
                    )
                  )
                ) : (
                  <span>{text}</span>
                )}
              </div>
              <Button
                variant="ghost"
                size="xs"
                onClick={() => handleReport(id)}
                title={t('feedback.reportProblem')}
                aria-label={t('feedback.reportProblem')}
                className="shrink-0"
              >
                <Flag />
                <span className="hidden sm:inline">{t('feedback.report')}</span>
              </Button>
            </div>
          )
        })}
        {/* Did-you-mean / cross-ref hints render BELOW the claim highlights:
            the user reads the flagged claim text first, then the suggestion. */}
        {terms.map((label) => {
          const hints = hintsByLabel[label]
          if (!hints || (!hints.didYouMean && !hints.crossRef)) return null
          return (
            <div
              key={`hints-${label}`}
              className="mx-3 mb-1.5 mt-1.5 px-3 py-1.5 text-[11px] leading-snug italic"
              style={{ color: 'var(--attention-text)' }}
            >
              <div className="font-medium not-italic mb-0.5">"{label}"</div>
              {hints.didYouMean && (() => {
                const dymTerm = hints.didYouMean.term
                const refBare = label.replace(/^(?:the|said)\s+/i, '').toLowerCase()
                const isCrossBranch = hints.didYouMean.cross_branch === true
                const isExactCrossBranch =
                  isCrossBranch && dymTerm.toLowerCase() === refBare
                const messageKey = isExactCrossBranch
                  ? 'antecedent.crossBranchAntecedent'
                  : isCrossBranch
                  ? 'antecedent.didYouMeanCrossBranch'
                  : 'antecedent.didYouMean'
                return (
                  <div>
                    {t(messageKey, {
                      term: dymTerm,
                      claim_id: hints.didYouMean.claim_id,
                    })}
                  </div>
                )
              })()}
              {hints.crossRef === 'spec_support' && (
                <div>{t('antecedent.crossRefSpecSupport')}</div>
              )}
            </div>
          )
        })}
      </div>
      <ReportModal
        open={reportModalOpen}
        onOpenChange={setReportModalOpen}
        checkKey="antecedentBasis"
        jurisdiction={jurisdiction || 'unknown'}
        locale={i18n.language}
        diagnostics={reportContext?.diagnostics || {}}
        onConfirm={handleAnonymousConfirm}
        onMailtoFallback={handleMailtoFallback}
      />
    </div>
  )
}

export default function AntecedentBasisCard({ issues, claimTrees, jurisdiction }) {
  const { t, i18n } = useTranslation()
  // 2026-05-05: removed `highConfOnly` filter. Empirical measurement on
  // TW supplement_v2 showed the conf≥65 bucket is mildly walker-bug
  // enriched (75.3% statutory precision vs 78.8% whole-corpus) — the
  // filter was misleading users into a slightly worse subset at 96%
  // recall loss. Default-show-all is correct UX.

  if (!issues || issues.length === 0) return null

  // Group by claim_id → Set of display labels (reference_form when available, else term)
  const byClaim = {}
  issues.forEach((issue) => {
    const { claim_id, term, reference_form } = issue
    if (!byClaim[claim_id]) byClaim[claim_id] = new Set()
    byClaim[claim_id].add(reference_form || term)
  })

  // Build claim text lookup
  const claimTextMap = {}
  if (claimTrees) {
    claimTrees.forEach((group) => {
      group.rows.forEach((row) => {
        claimTextMap[row.claim_id] = row.claim_text
      })
    })
  }

  // Super-group: claims sharing the exact same term set → one row.
  // Each group also collects the underlying findings so the expanded
  // panel can render did-you-mean and cross-reference hints.
  const termKeyToGroup = {}
  for (const [claimId, termSet] of Object.entries(byClaim)) {
    const key = [...termSet].sort().join('\0')
    if (!termKeyToGroup[key]) {
      termKeyToGroup[key] = { claimIds: [], terms: [...termSet].sort(), findings: [] }
    }
    termKeyToGroup[key].claimIds.push(Number(claimId))
  }
  for (const issue of issues) {
    const claimSet = byClaim[issue.claim_id]
    if (!claimSet) continue
    const key = [...claimSet].sort().join('\0')
    if (termKeyToGroup[key]) {
      termKeyToGroup[key].findings.push(issue)
    }
  }

  // Sort groups by first claim ID
  const groups = Object.values(termKeyToGroup)
  groups.forEach((g) => g.claimIds.sort((a, b) => a - b))
  groups.sort((a, b) => a.claimIds[0] - b.claimIds[0])

  const visibleGroups = groups
  // Stable per-group key (claim ids + term set) for the session-only review
  // state. No persistence / no server — matches the no-upload trust model;
  // refresh clears it.
  const groupKey = (g) => `${g.claimIds.join(',')}|${g.terms.join(' ')}`
  const [reviewed, setReviewed] = useState(() => new Set())
  const toggleReviewed = (key) =>
    setReviewed((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })

  const reviewedCount = visibleGroups.filter((g) => reviewed.has(groupKey(g))).length
  const openCount = visibleGroups.length - reviewedCount
  const allReviewed = openCount === 0

  return (
    <FrostCard tier="resting" accent="attention">
      <div className="flex items-start gap-3 px-4 py-3 pl-5">
        <ListChecks className="h-5 w-5 shrink-0 mt-0.5" style={{ color: 'var(--attention-border)' }} />
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold">{t('antecedentBasis.title')}</h3>
          <p className="text-[11px] leading-snug text-muted-foreground mt-0.5">
            {t('antecedentBasis.advisorySubtitle')}
          </p>
        </div>
        <StatusPill status={allReviewed ? 'pass' : 'attention'} shape="pill">
          {allReviewed
            ? t('antecedentBasis.allReviewedPill')
            : `${openCount} ${t('antecedentBasis.toVerify')}`}
        </StatusPill>
      </div>
      {reviewedCount > 0 && !allReviewed && (
        <div className="px-5 pb-1 -mt-1 text-[11px] text-muted-foreground">
          {t('antecedentBasis.reviewedCount', { count: reviewedCount })}
        </div>
      )}
      <div className="border-t border-border/40 px-1 py-1">
        {visibleGroups.map((group, i) => {
          const key = groupKey(group)
          return (
            <ClaimGroupRow
              key={i}
              claimIds={group.claimIds}
              terms={group.terms}
              findings={group.findings}
              claimTextMap={claimTextMap}
              t={t}
              i18n={i18n}
              jurisdiction={jurisdiction}
              reviewed={reviewed.has(key)}
              onToggleReviewed={() => toggleReviewed(key)}
            />
          )
        })}
      </div>
    </FrostCard>
  )
}
