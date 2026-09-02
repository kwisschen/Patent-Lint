// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025-2026 Christopher Chen
//
// Viewport harness - the app rendered side by side at the widths that matter.
//
// WHY THIS EXISTS. Mobile was a standing blind spot: every UI change was
// verified at desktop width only, because resizing the browser window is not
// reliably available (the window is often managed, and `resize_window` silently
// does nothing). "It has flex-col sm:flex-row so it is probably fine" is not
// verification, and it is how the touch-hidden feedback control shipped - a
// control with `opacity-0` and no hover fallback, unreachable on a phone,
// which nothing at desktop width could reveal.
//
// An IFRAME establishes its own viewport, so CSS media queries inside it
// resolve against the iframe's width, not the window's. Rendering the real app
// in fixed-width frames therefore exercises the real breakpoints with real CSS
// in a real browser - no headless driver, no new dependency, and no reliance on
// being able to resize anything.
//
// DEV ONLY. The route is registered behind `import.meta.env.DEV`, so it is
// never reachable in the production bundle. PatentLint's whole claim is that
// nothing runs but the analysis; a debug surface must not ship with it.
import { useCallback, useEffect, useRef, useState } from 'react'

// The widths worth watching, and why each one is here.
const VIEWPORTS = [
  { id: 'iphone-se', label: 'iPhone SE', w: 375, h: 667,
    note: 'Narrowest phone still in common use. Below the sm: breakpoint.' },
  { id: 'iphone-pro', label: 'iPhone 15 Pro', w: 393, h: 852,
    note: 'The modern phone default. Also below sm:.' },
  { id: 'tablet', label: 'iPad portrait', w: 768, h: 1024,
    note: 'Exactly at the md: boundary - the row layouts flip here.' },
  { id: 'laptop', label: 'Laptop', w: 1280, h: 800,
    note: 'The width every change is already verified at.' },
]

// Horizontal overflow is THE mobile failure mode, and it is the one that is
// easiest to miss by eye: a single element a few pixels too wide makes the
// whole page scroll sideways, and at desktop width nothing looks wrong.
//
// Reading it from the frame turns the harness from "look at it and judge" into
// "it tells you", which is the difference between a debug page and a check.
function useOverflowProbe(ref, deps) {
  const [report, setReport] = useState(null)

  const measure = useCallback(() => {
    const doc = ref.current?.contentDocument
    if (!doc || !doc.documentElement) return
    const root = doc.documentElement
    const width = root.clientWidth
    if (!width) return
    const wide = Array.from(doc.querySelectorAll('body *'))
      .filter((n) => n.getBoundingClientRect().width > width + 1)
      .slice(0, 5)
      .map((n) => {
        const cls = typeof n.className === 'string' ? n.className.slice(0, 32) : ''
        return `${n.tagName.toLowerCase()}${cls ? '.' + cls.split(' ')[0] : ''}`
      })
    setReport({
      width,
      scrollWidth: root.scrollWidth,
      scrolls: root.scrollWidth > width + 1,
      wide,
    })
  }, [ref])

  useEffect(() => {
    const id = setInterval(measure, 1500)
    return () => clearInterval(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [measure, ...deps])

  return report
}


function Frame({ viewport, path }) {
  const ref = useRef(null)
  const report = useOverflowProbe(ref, [path])
  const bad = report?.scrolls || (report?.wide?.length ?? 0) > 0

  return (
    <figure className="shrink-0">
      <figcaption className="mb-1 text-xs">
        <span className="font-semibold">{viewport.label}</span>{' '}
        <span className="font-mono text-muted-foreground">{viewport.w}×{viewport.h}</span>
        {report && (
          <span
            className="ml-2 rounded px-1.5 py-0.5 text-[10px] font-bold uppercase"
            style={{
              backgroundColor: bad ? 'var(--amend-bg)' : 'var(--pass-bg)',
              color: bad ? 'var(--amend-tag-text)' : 'var(--pass-tag-text)',
            }}
            title={bad ? `scrollWidth ${report.scrollWidth} > ${report.width}` : 'no horizontal overflow'}
          >
            {bad ? 'overflows' : 'fits'}
          </span>
        )}
        <span
          className="block text-[11px] text-muted-foreground/80"
          style={{ maxWidth: `${viewport.w}px` }}
        >
          {viewport.note}
        </span>
        {bad && report.wide.length > 0 && (
          <span
            className="block font-mono text-[10px]"
            style={{ maxWidth: `${viewport.w}px`, color: 'var(--amend-text)' }}
          >
            wider than viewport: {report.wide.join(', ')}
          </span>
        )}
      </figcaption>
      <iframe
        ref={ref}
        title={`${viewport.label} ${viewport.w}px`}
        src={path}
        width={viewport.w}
        height={viewport.h}
        className="rounded-lg border border-border bg-background shadow-sm"
      />
    </figure>
  )
}


export default function ViewportHarness() {
  // Seed from the harness's OWN query string so a given view is shareable and
  // scriptable: /__viewports?path=/%3Ffixture%3DTestSpec1.docx
  const [path, setPath] = useState(
    () => new URLSearchParams(window.location.search).get('path') || '/',
  )
  const [only, setOnly] = useState('all')
  const shown = only === 'all' ? VIEWPORTS : VIEWPORTS.filter((v) => v.id === only)

  return (
    <div className="min-h-screen bg-background p-4 text-foreground">
      <div className="mb-4 space-y-2">
        <h1 className="text-lg font-bold">Viewport harness</h1>
        <p className="max-w-3xl text-xs text-muted-foreground">
          The real app in real viewports. Each frame establishes its own
          viewport, so media queries resolve against the frame width. Load a
          draft inside a frame and it analyses in that frame, exactly as a
          device would. Dev-only route.
        </p>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <label className="flex items-center gap-1">
            <span className="text-muted-foreground">Path</span>
            <input
              value={path}
              onChange={(e) => setPath(e.target.value)}
              className="rounded border border-border bg-card px-2 py-1 font-mono"
              size={20}
            />
          </label>
          <select
            value={only}
            onChange={(e) => setOnly(e.target.value)}
            className="rounded border border-border bg-card px-2 py-1"
          >
            <option value="all">All widths</option>
            {VIEWPORTS.map((v) => (
              <option key={v.id} value={v.id}>{v.label} ({v.w}px)</option>
            ))}
          </select>
        </div>
      </div>

      <div className="flex flex-wrap items-start gap-4">
        {shown.map((v) => (
          <Frame key={v.id} viewport={v} path={path} />
        ))}
      </div>
    </div>
  )
}

export { VIEWPORTS }
