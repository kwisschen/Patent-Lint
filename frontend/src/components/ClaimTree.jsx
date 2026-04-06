// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025 Christopher Chen
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ChevronRight, Eye, EyeOff } from 'lucide-react'

function buildTree(rows) {
  const independents = []
  const dependentsByRoot = {}

  rows.forEach((row) => {
    if (row.claim_type === 'Independent') {
      independents.push(row)
      dependentsByRoot[row.claim_id] = []
    }
  })

  rows.forEach((row) => {
    if (row.claim_type === 'Dependent') {
      const parts = row.chain.split('←').map((s) => parseInt(s.trim(), 10))
      const root = parts[parts.length - 1]
      if (dependentsByRoot[root]) {
        dependentsByRoot[root].push(row)
      }
    }
  })

  return { independents, dependentsByRoot }
}

function ClaimNode({ row, isIndependent, t }) {
  const [showText, setShowText] = useState(false)

  const typeLabel = isIndependent ? t('tree.independent') : t('tree.dependent')

  return (
    <div className={`flex-1 min-w-0 py-1.5 ${isIndependent ? '' : 'ml-6'}`}>
      <div className="flex items-center gap-2">
        {!isIndependent && (
          <div className="w-4 border-l-2 border-b-2 border-border h-4 -mt-3 rounded-bl-sm" />
        )}
        <span
          className={`
            inline-flex items-center justify-center rounded-full text-xs font-bold shrink-0
            ${isIndependent ? 'h-7 w-7 bg-primary text-primary-foreground' : 'h-6 w-6 bg-secondary text-secondary-foreground'}
          `}
        >
          {row.claim_id}
        </span>
        <span className="text-sm">{typeLabel}</span>
        {!isIndependent && (
          <span className="text-xs text-muted-foreground ml-1">{row.chain}</span>
        )}
        {row.claim_text && (
          <button
            className="ml-auto p-0.5 text-muted-foreground hover:text-foreground transition-colors"
            onClick={(e) => { e.stopPropagation(); setShowText(!showText) }}
          >
            {showText ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
          </button>
        )}
      </div>
      <div
        className={`overflow-hidden transition-all duration-200 ease-in-out ${showText ? 'max-h-96 opacity-100' : 'max-h-0 opacity-0'}`}
      >
        <p className="text-xs text-muted-foreground mt-1.5 ml-9 pl-2 border-l-2 border-border leading-relaxed">
          {row.claim_text}
        </p>
      </div>
    </div>
  )
}

function ClaimGroup({ group, t }) {
  const { independents, dependentsByRoot } = buildTree(group.rows)
  const [expandedRoots, setExpandedRoots] = useState(() => {
    const initial = {}
    independents.forEach((ind) => { initial[ind.claim_id] = true })
    return initial
  })

  const toggleRoot = (id) => {
    setExpandedRoots((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  const groupLabel = group.label === 'Method Claims'
    ? t('tree.methodClaims')
    : group.label === 'Claims'
      ? t('tree.claims')
      : t('tree.apparatusClaims')

  return (
    <div className="mt-3">
      <h4 className="text-sm font-semibold mb-2">{groupLabel}</h4>
      <div className="space-y-0.5">
        {independents.map((ind) => {
          const deps = dependentsByRoot[ind.claim_id] || []
          const isExpanded = expandedRoots[ind.claim_id]

          return (
            <div key={ind.claim_id}>
              <div
                role="button"
                tabIndex={0}
                className="flex items-center gap-1 w-full text-left hover:bg-accent/50 rounded px-1 transition-colors cursor-pointer"
                onClick={() => toggleRoot(ind.claim_id)}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleRoot(ind.claim_id) } }}
              >
                {deps.length > 0 && (
                  <ChevronRight
                    className={`h-3.5 w-3.5 text-muted-foreground transition-transform duration-200 ${isExpanded ? 'rotate-90' : ''}`}
                  />
                )}
                {deps.length === 0 && <span className="w-3.5" />}
                <ClaimNode row={ind} isIndependent t={t} />
                {deps.length > 0 && (
                  <span className="text-xs text-muted-foreground ml-auto shrink-0">
                    {deps.length} {deps.length !== 1 ? t('tree.deps') : t('tree.dep')}
                  </span>
                )}
              </div>
              <div
                className={`overflow-hidden transition-all duration-300 ease-in-out ${isExpanded && deps.length > 0 ? 'max-h-[5000px] opacity-100' : 'max-h-0 opacity-0'}`}
              >
                <div className="ml-5 border-l-2 border-border pl-1">
                  {deps.map((dep) => (
                    <ClaimNode key={dep.claim_id} row={dep} isIndependent={false} t={t} />
                  ))}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default function ClaimTree({ claimTrees }) {
  const { t } = useTranslation()

  if (!claimTrees || claimTrees.length === 0) return null

  return (
    <div className="mt-2 pt-2 border-t">
      {claimTrees.map((group, i) => (
        <ClaimGroup key={i} group={group} t={t} />
      ))}
    </div>
  )
}
