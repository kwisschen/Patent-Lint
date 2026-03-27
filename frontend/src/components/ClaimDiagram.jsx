// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025 Christopher Chen
import { useState, useEffect, useRef, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { ChevronDown, GitBranch } from 'lucide-react'
import mermaid from 'mermaid'

let renderCounter = 0

mermaid.initialize({
  startOnLoad: false,
  theme: 'neutral',
  flowchart: { curve: 'basis', padding: 10 },
})

function buildMermaidSyntax(claimTrees) {
  const lines = ['flowchart TD']

  claimTrees.forEach((group) => {
    group.rows.forEach((row) => {
      const nodeId = `c${row.claim_id}`
      const label = row.claim_type === 'Independent'
        ? `Claim ${row.claim_id} - Independent`
        : `Claim ${row.claim_id} - Dependent`
      lines.push(`  ${nodeId}["${label}"]`)

      if (row.claim_type === 'Independent') {
        lines.push(`  style ${nodeId} fill:#dbeafe,stroke:#2563eb,color:#1e40af`)
      } else {
        lines.push(`  style ${nodeId} fill:#f5f5f5,stroke:#d1d5db,color:#333`)
      }
    })

    group.rows.forEach((row) => {
      if (row.claim_type === 'Dependent') {
        const parts = row.chain.split('\u2190').map((s) => parseInt(s.trim(), 10))
        if (parts.length >= 2) {
          const parent = parts[1]
          lines.push(`  c${parent} --> c${row.claim_id}`)
        }
      }
    })
  })

  return lines.join('\n')
}

export default function ClaimDiagram({ claimTrees }) {
  const { t } = useTranslation()
  const [showDiagram, setShowDiagram] = useState(false)
  const containerRef = useRef(null)

  const renderDiagram = useCallback(async () => {
    if (!containerRef.current || !claimTrees?.length) return

    const syntax = buildMermaidSyntax(claimTrees)
    renderCounter += 1
    const id = `mermaid-diagram-${renderCounter}`

    const stale = document.getElementById(id)
    if (stale) stale.remove()

    try {
      const { svg } = await mermaid.render(id, syntax)
      if (containerRef.current) {
        containerRef.current.innerHTML = svg
      }
    } catch (err) {
      console.error('Mermaid render error:', err)
      if (containerRef.current) {
        containerRef.current.innerHTML =
          '<p class="text-sm text-muted-foreground">Could not render diagram</p>'
      }
    }
  }, [claimTrees])

  useEffect(() => {
    if (showDiagram) {
      renderDiagram()
    }
  }, [showDiagram, renderDiagram])

  if (!claimTrees || claimTrees.length === 0) return null

  return (
    <div className="mt-3 border-t pt-3">
      <button
        className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        onClick={() => setShowDiagram(!showDiagram)}
      >
        <GitBranch className="h-3.5 w-3.5" />
        <span>{showDiagram ? t('diagram.hide') : t('diagram.show')}</span>
        <ChevronDown className={`h-3.5 w-3.5 transition-transform duration-200 ${showDiagram ? 'rotate-180' : ''}`} />
      </button>
      {showDiagram && (
        <div
          ref={containerRef}
          className="mt-3 overflow-x-auto rounded-lg border bg-card p-4 [&_svg]:mx-auto animate-in fade-in-0 slide-in-from-top-1 duration-300"
        />
      )}
    </div>
  )
}
