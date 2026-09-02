// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025-2026 Christopher Chen
import { useState, useEffect, useRef, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { ChevronDown, GitBranch, ZoomIn, ZoomOut, Maximize2, Minimize2, Scan } from 'lucide-react'
import { createPortal } from 'react-dom'
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

// REMOVED 2026-05-01: a module-level IIFE used to call
// `mermaid.render('init-check', 'flowchart TD\n  A["init"]')` to "force the
// dynamic import" - but mermaid is statically imported at line 6 above, so
// the bundle is already in the chunk. The IIFE was a no-op for the stated
// purpose, AND on failure (or partial cleanup-miss in mermaid v11+ ID
// naming), it left behind a visible "Syntax error in text" bomb-icon SVG
// at the bottom of every page (including the homepage where no claim
// diagram is needed). User saw it on iPhone Safari prod build 6746b7d.
// First ClaimDiagram render below works fine without pre-warming because
// mermaid is already loaded statically.

function ZoomControl({ onClick, disabled, label, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={label}
      aria-label={label}
      className="rounded p-1 text-muted-foreground transition-colors hover:bg-foreground/[0.06]
                 hover:text-foreground disabled:pointer-events-none disabled:opacity-40
                 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
    >
      {children}
    </button>
  )
}


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

// Edge draw is intentionally longer than node fade: the line-extension motion
// is the hero of this reveal and needs to be perceptible when users first
// land on the results page. Total duration is bounded so large claim sets
// don't take 5+s.
const NODE_STAGGER_MS = 45
const NODE_STAGGER_CAP_MS = 600
const EDGE_STAGGER_MS = 75
const EDGE_STAGGER_CAP_MS = 1200
const EDGE_DRAW_DURATION_MS = 1300
const EDGE_DRAW_DELAY_BASE_MS = 220

// Light-mode defaults, used if getComputedStyle returns an empty var() lookup
// (e.g. inside an iframe, or if the stylesheet hasn't parsed yet).
const FALLBACK_TOKENS = {
  '--pl-indep-start': '#f0f7ff',
  '--pl-indep-mid': '#dbeafe',
  '--pl-indep-end': '#a9c9f5',
  '--pl-dep-start': '#ffffff',
  '--pl-dep-mid': '#f5f7fa',
  '--pl-dep-end': '#dfe6ef',
  '--pl-shadow-color': '#0f172a',
  '--pl-shadow-opacity': '0.18',
  '--pl-edge-stroke': '#94a3b8',
  '--pl-label-indep': '#1e3a8a',
  '--pl-label-dep': '#334155',
  '--pl-indep-stroke': '#2563eb',
  '--pl-dep-stroke': '#cbd5e1',
}

function readTokens(el) {
  const cs = getComputedStyle(el)
  const out = {}
  for (const [k, fallback] of Object.entries(FALLBACK_TOKENS)) {
    const v = cs.getPropertyValue(k).trim()
    out[k] = v || fallback
  }
  return out
}

// Appends gradient + shadow defs, restyles nodes/edges, adds draw-in animation.
// Defs IDs are scoped by `suffix` so multiple diagrams on a page don't collide.
// Tokens are resolved to literal hex at render-time via getComputedStyle -
// `var(--x)` inside inline SVG style attributes is flaky across engines.
function enhanceSvg(svgEl, suffix, surfaceEl) {
  if (!svgEl || !surfaceEl) return

  const tokens = readTokens(surfaceEl)

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
      <stop offset="0%" stop-color="${tokens['--pl-indep-start']}"/>
      <stop offset="45%" stop-color="${tokens['--pl-indep-mid']}"/>
      <stop offset="100%" stop-color="${tokens['--pl-indep-end']}"/>
    </linearGradient>
    <linearGradient id="${gradDep}" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="${tokens['--pl-dep-start']}"/>
      <stop offset="45%" stop-color="${tokens['--pl-dep-mid']}"/>
      <stop offset="100%" stop-color="${tokens['--pl-dep-end']}"/>
    </linearGradient>
    <filter id="${shadow}" x="-30%" y="-30%" width="160%" height="160%">
      <feDropShadow dx="0" dy="2" stdDeviation="3"
        flood-color="${tokens['--pl-shadow-color']}"
        flood-opacity="${tokens['--pl-shadow-opacity']}"/>
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
      rect.style.setProperty('stroke', isIndep ? tokens['--pl-indep-stroke'] : tokens['--pl-dep-stroke'], 'important')
      rect.style.setProperty('stroke-width', isIndep ? '1.5' : '1', 'important')
    }

    const labelColor = isIndep ? tokens['--pl-label-indep'] : tokens['--pl-label-dep']
    g.querySelectorAll('text, tspan, .nodeLabel, .label').forEach((t) => {
      t.style.setProperty('fill', labelColor, 'important')
      t.style.setProperty('color', labelColor, 'important')
    })

    if (!reduceMotion) {
      const delay = Math.min(i * NODE_STAGGER_MS, NODE_STAGGER_CAP_MS)
      g.style.animation = `pl-diagram-node-fade 280ms cubic-bezier(0.25, 0.1, 0.25, 1) ${delay}ms both`
    }
  })

  const paths = svgEl.querySelectorAll('.edgePath path, path.flowchart-link')
  paths.forEach((path, i) => {
    path.style.setProperty('stroke', tokens['--pl-edge-stroke'], 'important')
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
      // Unusual path shapes can throw on getTotalLength - skip animation for those.
    }
  })

  svgEl.querySelectorAll('marker path, marker polygon').forEach((m) => {
    m.style.setProperty('fill', tokens['--pl-edge-stroke'], 'important')
    m.style.setProperty('stroke', tokens['--pl-edge-stroke'], 'important')
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
        enhanceSvg(
          containerRef.current.querySelector('svg'),
          String(renderCounter),
          containerRef.current,
        )
      }
    } catch (err) {
      console.error('Mermaid render error:', err)
      // Defensive cleanup: mermaid may leave temporary DOM elements at the
      // body level when render fails partway through (the bomb-icon error
      // SVG it renders before throwing). Remove any orphaned containers
      // using both the id we passed and mermaid v11's d-prefix convention
      // so the user sees ONLY the localized renderError message inside
      // containerRef, never the library default bomb at body level.
      document.getElementById(id)?.remove()
      document.querySelector(`[id^="d${id}"]`)?.remove()
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

  // Re-render on theme toggle so the gradient stops + label colors pick up
  // the new .dark tokens. Tokens are baked into the SVG at render-time
  // (for cross-engine reliability), so a live CSS-var swap won't reach them.
  useEffect(() => {
    if (!showDiagram) return
    const root = document.documentElement
    let wasDark = root.classList.contains('dark')
    const observer = new MutationObserver(() => {
      const isDark = root.classList.contains('dark')
      if (isDark !== wasDark) {
        wasDark = isDark
        renderDiagram()
      }
    })
    observer.observe(root, { attributes: true, attributeFilter: ['class'] })
    return () => observer.disconnect()
  }, [showDiagram, renderDiagram])

  // Zoom. Mermaid caps the rendered SVG at 100% of its container, so a wide
  // dependency tree is shrunk until the node labels are unreadable - the
  // diagram was legible only for small claim sets. The SVG is vector, so
  // scaling its width past the container costs nothing in sharpness; the
  // surface already scrolls horizontally.
  const ZOOM_STEPS = [0.75, 1, 1.25, 1.5, 2, 3]
  const [zoom, setZoom] = useState(1)
  const [expanded, setExpanded] = useState(false)

  // Apply zoom by setting the SVG width and clearing the max-width mermaid
  // bakes in. Done as an effect rather than at render time because the SVG is
  // injected via innerHTML and replaced on every re-render (theme toggle).
  useEffect(() => {
    const svg = containerRef.current?.querySelector('svg')
    if (!svg) return
    svg.style.maxWidth = 'none'
    svg.style.width = `${zoom * 100}%`
    svg.style.height = 'auto'
  }, [zoom, showDiagram, expanded, claimTrees])

  // Going full screen moves the surface into a PORTAL, so React remounts the
  // container div and the innerHTML-injected SVG is lost with it. Re-render on
  // the toggle rather than trying to move the DOM node by hand.
  const didMountExpand = useRef(false)
  useEffect(() => {
    if (!showDiagram) return
    if (!didMountExpand.current) { didMountExpand.current = true; return }
    renderDiagram()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expanded])

  // Escape leaves full screen - a fullscreen surface with no keyboard exit is
  // a trap for anyone not using a mouse.
  useEffect(() => {
    if (!expanded) return
    const onKey = (e) => { if (e.key === 'Escape') setExpanded(false) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [expanded])

  const stepZoom = (dir) => {
    const i = ZOOM_STEPS.indexOf(zoom)
    const next = i === -1 ? 1 : Math.min(ZOOM_STEPS.length - 1, Math.max(0, i + dir))
    setZoom(ZOOM_STEPS[next])
  }

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
      {showDiagram && (() => {
        const panel = (
          <>
          {expanded && (
            <div
              className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
              onClick={() => setExpanded(false)}
              aria-hidden
            />
          )}
          <div className={expanded
            ? 'fixed inset-3 z-50 flex flex-col rounded-lg border bg-card shadow-xl sm:inset-6'
            : 'mt-3'}>
            <div className="flex items-center gap-1 px-2 py-1.5">
              <ZoomControl
                onClick={() => stepZoom(-1)}
                disabled={zoom === ZOOM_STEPS[0]}
                label={t('diagram.zoomOut')}
              >
                <ZoomOut className="h-3.5 w-3.5" />
              </ZoomControl>
              <span className="min-w-[3.5rem] text-center text-[11px] tabular-nums text-muted-foreground">
                {t('diagram.zoomLevel', { pct: Math.round(zoom * 100) })}
              </span>
              <ZoomControl
                onClick={() => stepZoom(1)}
                disabled={zoom === ZOOM_STEPS[ZOOM_STEPS.length - 1]}
                label={t('diagram.zoomIn')}
              >
                <ZoomIn className="h-3.5 w-3.5" />
              </ZoomControl>
              <ZoomControl onClick={() => setZoom(1)} label={t('diagram.fit')}>
                <Scan className="h-3.5 w-3.5" />
              </ZoomControl>
              <div className="flex-1" />
              <ZoomControl
                onClick={() => setExpanded((v) => !v)}
                label={expanded ? t('diagram.collapse') : t('diagram.expand')}
              >
                {expanded
                  ? <Minimize2 className="h-3.5 w-3.5" />
                  : <Maximize2 className="h-3.5 w-3.5" />}
              </ZoomControl>
            </div>
            <div
              ref={containerRef}
              className={
                'claim-diagram-surface overflow-auto rounded-lg border bg-card p-4 '
                + '[&_svg]:mx-auto animate-in fade-in-0 slide-in-from-top-1 duration-300 '
                + (expanded ? 'min-h-0 flex-1' : '')
              }
            />
          </div>
          </>
        )
        // PORTAL when expanded. An ancestor in AnalysisReport carries
        // `transform: translateY(0) scale(1)` for its entrance cascade, and a
        // non-none transform makes that element the containing block for
        // `position: fixed` AND traps z-index in its stacking context - so the
        // full-screen panel rendered UNDERNEATH the rest of the report. Only
        // escaping to document.body fixes it; a bigger z-index cannot.
        return expanded ? createPortal(panel, document.body) : panel
      })()}
    </div>
  )
}
