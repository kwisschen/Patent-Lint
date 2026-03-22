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

function ClaimRow({ claimId, terms, claimText }) {
  const [expanded, setExpanded] = useState(false)
  const highlighted = claimText ? highlightTerms(claimText, terms) : null

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        className="flex items-center gap-2 px-3 py-2 rounded-md hover:bg-[var(--attention-bg)]/60 transition-colors cursor-pointer"
        onClick={() => setExpanded(!expanded)}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setExpanded(!expanded) } }}
      >
        {claimText && (
          <ChevronRight
            className={`h-3.5 w-3.5 shrink-0 transition-transform duration-200 ${expanded ? 'rotate-90' : ''}`}
            style={{ color: 'var(--attention-border)' }}
          />
        )}
        <span
          className="inline-flex items-center justify-center h-6 w-6 rounded-full text-xs font-bold shrink-0"
          style={{ backgroundColor: 'var(--attention-bg)', color: 'var(--attention-text)', border: '1.5px solid var(--attention-border)' }}
        >
          {claimId}
        </span>
        <span className="text-sm text-muted-foreground">
          {terms.map((term, i) => (
            <span key={i}>
              {i > 0 && ', '}
              <span className="font-medium" style={{ color: 'var(--attention-text)' }}>"{term}"</span>
            </span>
          ))}
        </span>
      </div>
      <div className={`overflow-hidden transition-all duration-200 ease-in-out ${expanded ? 'max-h-[600px] opacity-100' : 'max-h-0 opacity-0'}`}>
        {highlighted && Array.isArray(highlighted) && (
          <div className="mx-3 mb-2 px-3 py-2 rounded text-xs leading-relaxed border" style={{ borderColor: 'var(--attention-border)', backgroundColor: 'var(--attention-bg)' }}>
            {highlighted.map((part, i) =>
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
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default function AntecedentBasisCard({ issues, claimTrees }) {
  const { t } = useTranslation()

  if (!issues || issues.length === 0) return null

  // Group by claim_id
  const grouped = {}
  issues.forEach(({ claim_id, term }) => {
    if (!grouped[claim_id]) grouped[claim_id] = new Set()
    grouped[claim_id].add(term)
  })

  const claimIds = Object.keys(grouped).map(Number).sort((a, b) => a - b)
  const totalItems = issues.length

  // Build claim text lookup from claim trees
  const claimTextMap = {}
  if (claimTrees) {
    claimTrees.forEach((group) => {
      group.rows.forEach((row) => {
        claimTextMap[row.claim_id] = row.claim_text
      })
    })
  }

  return (
    <div
      className="mt-3 rounded-lg border-l-4 border bg-card overflow-hidden"
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
        {claimIds.map((id) => (
          <ClaimRow
            key={id}
            claimId={id}
            terms={[...grouped[id]]}
            claimText={claimTextMap[id] || ''}
          />
        ))}
      </div>
    </div>
  )
}
