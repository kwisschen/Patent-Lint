// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025–2026 Christopher Chen
import mermaid from 'mermaid'

let preloaded = false
let preloadPromise = null

/**
 * Pre-load mermaid's flowchart-specific lazy chunks into the JS
 * module registry during the initial app loading phase.
 *
 * Why this exists: mermaid v11 internally lazy-loads diagram-type
 * modules (flowDiagram, cytoscape, cose-bilkent, layout helpers) on
 * the first call to mermaid.render(). Without pre-loading, those ~6
 * chunks fetch on the first analysis the moment ClaimDiagram renders
 * the claim tree — surfacing in DevTools' Network tab as a burst of
 * `https://patentlint.com/assets/*.js` entries the instant the user
 * drops their draft. The chunks are own-bundle assets (no user data
 * leaving), but the timing breaks the no-network-after-drop trust
 * signal: a non-technical user reads the burst as "PatentLint just
 * sent something out when I gave it my file." Ditto with WiFi off,
 * where the same chunks reappear as "(disk cache)" entries.
 *
 * By rendering a minimal flowchart during initial app boot, we shift
 * the lazy-load timeline forward — chunks land in the JS module
 * registry while Pyodide bootstraps. When ClaimDiagram later renders
 * the real diagram, every internal `import()` resolves from the
 * registry without any HTTP fetch (not even a disk-cache hit), so
 * DevTools stays quiet on drop.
 *
 * Cleanup: mermaid.render() can leave SVG nodes parked at body level
 * if a cleanup path partially fails (the bomb-icon class — see
 * 9cc4edd). We explicitly sweep any preload-id leftovers in finally.
 *
 * Idempotent: callable multiple times safely; only runs once.
 */
export async function preloadMermaidChunks() {
  if (preloaded) return preloadPromise
  preloaded = true
  preloadPromise = (async () => {
    try {
      const tempId = `mermaid-preload-${Date.now()}`
      await mermaid.render(tempId, 'flowchart TD\n  A --> B')
    } catch {
      // Preload failure is non-critical — first real render will
      // simply do the lazy-load itself, surfacing in Network tab on
      // drop (the pre-fix behavior). No user-visible breakage.
    } finally {
      document.querySelectorAll('[id^="mermaid-preload-"]').forEach((el) => el.remove())
    }
  })()
  return preloadPromise
}
