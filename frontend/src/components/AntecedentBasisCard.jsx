import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { AlertTriangle, ChevronRight } from 'lucide-react'

function highlightTerms(text, terms) {
  if (!terms.length) return text

  const escaped = terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  const pattern = new RegExp(`\\b(the|said)\\s+(${escaped.join('|')})\\b`, 'gi')

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
function formatClaimRange(ids) {
  if (ids.length === 0) return ''
  if (ids.length === 1) return `Claim ${ids[0]}`

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

  return `Claims ${ranges.join(', ')}`
}

function ClaimGroupRow({ claimIds, terms, claimTextMap, t }) {
  const [expanded, setExpanded] = useState(false)
  const label = formatClaimRange(claimIds)
  const termCount = terms.length
  const hasText = claimIds.some((id) => claimTextMap[id])

  return (
    <div>
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
        <span className="text-sm text-muted-foreground flex-1 truncate">
          {terms.map((term, i) => (
            <span key={i}>
              {i > 0 && ', '}
              "{term}"
            </span>
          ))}
        </span>
        <span
          className="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold"
          style={{ backgroundColor: 'var(--attention-bg)', color: 'var(--attention-text)', border: '1px solid var(--attention-border)' }}
        >
          {termCount} {termCount === 1 ? t('antecedentBasis.item') : t('antecedentBasis.items')}
        </span>
      </div>
      <div className={`overflow-hidden transition-all duration-200 ease-in-out ${expanded ? 'max-h-[2000px] opacity-100' : 'max-h-0 opacity-0'}`}>
        {claimIds.map((id) => {
          const text = claimTextMap[id]
          if (!text) return null
          const highlighted = highlightTerms(text, terms)
          return (
            <div
              key={id}
              className="mx-3 mb-1.5 px-3 py-2 rounded text-xs leading-relaxed border"
              style={{ borderColor: 'var(--attention-border)', backgroundColor: 'var(--attention-bg)' }}
            >
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
          )
        })}
      </div>
    </div>
  )
}

export default function AntecedentBasisCard({ issues, claimTrees }) {
  const { t } = useTranslation()

  if (!issues || issues.length === 0) return null

  // Group by claim_id → Set of terms
  const byClaim = {}
  issues.forEach(({ claim_id, term }) => {
    if (!byClaim[claim_id]) byClaim[claim_id] = new Set()
    byClaim[claim_id].add(term)
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

  // Super-group: claims sharing the exact same term set → one row
  const termKeyToGroup = {}
  for (const [claimId, termSet] of Object.entries(byClaim)) {
    const key = [...termSet].sort().join('\0')
    if (!termKeyToGroup[key]) {
      termKeyToGroup[key] = { claimIds: [], terms: [...termSet].sort() }
    }
    termKeyToGroup[key].claimIds.push(Number(claimId))
  }

  // Sort groups by first claim ID
  const groups = Object.values(termKeyToGroup)
  groups.forEach((g) => g.claimIds.sort((a, b) => a - b))
  groups.sort((a, b) => a.claimIds[0] - b.claimIds[0])

  const totalItems = issues.length

  return (
    <div
      className="rounded-lg border-l-4 border bg-card overflow-hidden"
      style={{ borderLeftColor: 'var(--attention-border)' }}
    >
      <div className="flex items-center gap-3 px-4 py-3">
        <AlertTriangle className="h-5 w-5 shrink-0" style={{ color: 'var(--attention-border)' }} />
        <h3 className="text-sm font-semibold flex-1">{t('antecedentBasis.title')}</h3>
        <span
          className="rounded-full px-2.5 py-0.5 text-xs font-bold"
          style={{ backgroundColor: 'var(--attention-bg)', color: 'var(--attention-text)', border: '1px solid var(--attention-border)' }}
        >
          {totalItems} {totalItems !== 1 ? t('antecedentBasis.items') : t('antecedentBasis.item')}
        </span>
      </div>
      <div className="border-t px-1 py-1">
        {groups.map((group, i) => (
          <ClaimGroupRow
            key={i}
            claimIds={group.claimIds}
            terms={group.terms}
            claimTextMap={claimTextMap}
            t={t}
          />
        ))}
      </div>
    </div>
  )
}
