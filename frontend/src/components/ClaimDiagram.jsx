// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
import { useState, useEffect, useRef, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { ChevronDown, GitBranch } from 'lucide-react'
import mermaid from 'mermaid'

let renderCounter = 0

const GEIST_STACK =
  "'Geist Variable', system-ui, -apple-system, BlinkMacSystemFont, " +
  "'Segoe UI', 'Helvetica Neue', Arial, " +
  "'PingFang SC', 'PingFang TC', 'Hiragino Sans', 'Microsoft YaHei', " +
  "'Microsoft JhengHei', 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif"

mermaid.initialize({
  startOnLoad: false,
  theme: 'neutral',
  fontFamily: GEIST_STACK,
  themeVariables: { fontFamily: GEIST_STACK, fontSize: '13px' },
  flowchart: {
    curve: 'basis',
    padding: 14,
    nodeSpacing: 44,
    rankSpacing: 60,
    htmlLabels: false,
  },
})

;(async () => {
  try {
    await mermaid.render('init-check', 'flowchart TD\n  A["init"]')
    document.getElementById('init-check')?.remove()
    document.querySelector('[id^="dinit-check"]')?.remove()
  } catch {
    // Ignore — this just forces the dynamic import
  }
})()

function buildMermaidSyntax(claimTrees, t) {
  const lines = [
    'flowchart TD',
    'classDef plIndependent fill:#dbeafe,stroke:#2563eb,color:#1e40af',
    'classDef plDependent fill:#ffffff,stroke:#cbd5e1,color:#334155',
  ]

  claimTrees.forEach((group) => {
    group.rows.forEach((row) => {
      const nodeId = `c${row.claim_id}`
      const typeLabel = row.claim_type === 'Independent'
        ? t('claimDiagram.independent')
        : t('claimDiagram.dependent')
      const label = `${t('claimDiagram.claimLabel', { id: row.claim_id })} - ${typeLabel}`
      lines.push(`  ${nodeId}["${label}"]`)
      const cls = row.claim_type === 'Independent' ? 'plIndependent' : 'plDependent'
      lines.push(`  class ${nodeId} ${cls}`)
    })

    group.rows.forEach((row) => {
      if (row.claim_type === 'Dependent') {
        const parts = row.chain.split('←').map((s) => parseInt(s.trim(), 10))
        if (parts.length >= 2) {
          const parent = parts[1]
          lines.push(`  c${parent} --> c${row.claim_id}`)
        }
      }
    })
  })

  return lines.join('\n')
}

const SVG_NS = 'http://www.w3.org/2000/svg'

// Keep total reveal duration bounded so 100-claim patents don't take 5+s to draw.
// Edge draw is intentionally longer than node fade: the line-extension motion
// is the hero of this reveal and needs to be perceptible when users first
// land on the results page.
const NODE_STAGGER_MS = 45
const NODE_STAGGER_CAP_MS = 600
const EDGE_STAGGER_MS = 75
const EDGE_STAGGER_CAP_MS = 1200
const EDGE_DRAW_DURATION_MS = 1300
const EDGE_DRAW_DELAY_BASE_MS = 220

// Appends gradient + shadow defs, restyles nodes/edges, adds draw-in animation.
// Defs IDs are scoped by `suffix` so multiple diagrams on a page don't collide
// (document-scope `url(#id)` resolution picks whichever def appears first).
// Inline-important styles are used because mermaid's injected stylesheet has
// higher specificity than SVG attribute defaults.
function enhanceSvg(svgEl, suffix) {
  if (!svgEl) return

  const gradIndep = `pl-grad-indep-${suffix}`
  const gradDep = `pl-grad-dep-${suffix}`
  const shadow = `pl-shadow-${suffix}`

  let defs = svgEl.querySelector('defs')
  if (!defs) {
    defs = document.createElementNS(SVG_NS, 'defs')
    svgEl.insertBefore(defs, svgEl.firstChild)
  }

  const extras = `
    <linearGradient id="${gradIndep}" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color: var(--pl-indep-start)"/>
      <stop offset="100%" style="stop-color: var(--pl-indep-end)"/>
    </linearGradient>
    <linearGradient id="${gradDep}" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color: var(--pl-dep-start)"/>
      <stop offset="100%" style="stop-color: var(--pl-dep-end)"/>
    </linearGradient>
    <filter id="${shadow}" x="-30%" y="-30%" width="160%" height="160%">
      <feDropShadow dx="0" dy="2" stdDeviation="3"
        style="flood-color: var(--pl-shadow-color); flood-opacity: var(--pl-shadow-opacity)"/>
    </filter>
  `
  const holder = document.createElementNS(SVG_NS, 'g')
  holder.innerHTML = extras
  while (holder.firstChild) defs.appendChild(holder.firstChild)

  const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

  svgEl.querySelectorAll('g.node').forEach((g, i) => {
    const isIndep = g.classList.contains('plIndependent')
    const isDep = g.classList.contains('plDependent')
    if (!isIndep && !isDep) return

    const rect = g.querySelector('rect')
    if (rect) {
      rect.setAttribute('rx', '10')
      rect.setAttribute('ry', '10')
      rect.style.setProperty('fill', isIndep ? `url(#${gradIndep})` : `url(#${gradDep})`, 'important')
      rect.style.setProperty('filter', `url(#${shadow})`, 'important')
      rect.style.setProperty('stroke', isIndep ? 'var(--pl-indep-stroke)' : 'var(--pl-dep-stroke)', 'important')
      rect.style.setProperty('stroke-width', isIndep ? '1.5' : '1', 'important')
    }

    const labelColor = isIndep ? 'var(--pl-label-indep)' : 'var(--pl-label-dep)'
    g.querySelectorAll('text, tspan').forEach((t) => {
      t.style.setProperty('fill', labelColor, 'important')
    })

    if (!reduceMotion) {
      const delay = Math.min(i * NODE_STAGGER_MS, NODE_STAGGER_CAP_MS)
      g.style.animation = `pl-diagram-node-fade 280ms cubic-bezier(0.25, 0.1, 0.25, 1) ${delay}ms both`
    }
  })

  const paths = svgEl.querySelectorAll('.edgePath path, path.flowchart-link')
  paths.forEach((path, i) => {
    path.style.setProperty('stroke', 'var(--pl-edge-stroke)', 'important')
    path.style.setProperty('stroke-width', '1.5', 'important')
    try {
      const length = path.getTotalLength?.() ?? 180
      path.style.strokeDasharray = String(length)
      if (reduceMotion) {
        path.style.strokeDashoffset = '0'
      } else {
        path.style.strokeDashoffset = String(length)
        const delay = Math.min(EDGE_DRAW_DELAY_BASE_MS + i * EDGE_STAGGER_MS, EDGE_STAGGER_CAP_MS)
        path.style.animation = `pl-diagram-draw ${EDGE_DRAW_DURATION_MS}ms cubic-bezier(0.22, 0.61, 0.36, 1) ${delay}ms forwards`
      }
    } catch {
      // Unusual path shapes can throw on getTotalLength — skip animation for those.
    }
  })

  svgEl.querySelectorAll('marker path, marker polygon').forEach((m) => {
    m.style.setProperty('fill', 'var(--pl-edge-stroke)', 'important')
    m.style.setProperty('stroke', 'var(--pl-edge-stroke)', 'important')
  })
}

export default function ClaimDiagram({ claimTrees }) {
  const { t } = useTranslation()
  const [showDiagram, setShowDiagram] = useState(true)
  const containerRef = useRef(null)

  const renderDiagram = useCallback(async () => {
    if (!containerRef.current || !claimTrees?.length) return

    const syntax = buildMermaidSyntax(claimTrees, t)
    renderCounter += 1
    const id = `mermaid-diagram-${renderCounter}`

    const stale = document.getElementById(id)
    if (stale) stale.remove()

    try {
      const { svg } = await mermaid.render(id, syntax)
      if (containerRef.current) {
        containerRef.current.innerHTML = svg
        enhanceSvg(containerRef.current.querySelector('svg'), String(renderCounter))
      }
    } catch (err) {
      console.error('Mermaid render error:', err)
      if (containerRef.current) {
        containerRef.current.innerHTML =
          `<p class="text-sm text-muted-foreground">${t('claimDiagram.renderError')}</p>`
      }
    }
  }, [claimTrees, t])

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
          className="claim-diagram-surface mt-3 overflow-x-auto rounded-lg border bg-card p-4 [&_svg]:mx-auto animate-in fade-in-0 slide-in-from-top-1 duration-300"
        />
      )}
    </div>
  )
}
