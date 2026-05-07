# Trust audit checklist

PatentLint's primary trust claim is **No upload. No cloud processing. No AI.** Every change that touches the trust surfaces below should be sanity-checked against this list before shipping. The list is short on purpose — long checklists rot — but each item maps to a real bug class that has shipped at least once.

## Trust surfaces

- **DropZone trust badge** (`frontend/src/components/DropZone.jsx`) — the security headline + "verify it yourself" CTA.
- **AnalysisReport network dot** (`frontend/src/components/AnalysisReport.jsx` + `useNetworkMonitor`) — the green/red indicator on the results header.
- **NetworkWidget** (`frontend/src/components/NetworkWidget.jsx`) — the persistent bottom-right "Outgoing data" counter.
- **ProveItModal** (`frontend/src/components/ProveItModal.jsx`) — the airplane-mode demo + live activity log.
- **Update-check banner** (`frontend/src/hooks/useUpdateCheck.js`) — the toast that fires after tab returns from being hidden ≥ 5s.
- **Voluntary error-report pipeline** (`frontend/src/lib/feedback.js` + Vercel Edge Function `frontend/api/report.js` serving `/api/report`) — the only intentional outbound POST in the app.
- **Trust copy** — `security.*`, `widget.*`, `dropzone.notice*` keys in `frontend/src/i18n/locales/*.json`.

## Pre-ship checklist

Run before any push that touches the surfaces above, and at minimum monthly as a standing audit.

### 0. Vercel project-setting audit (do once, then on every Vercel plan/integration change)
- Confirm in **Vercel dashboard → patent-lint project → Settings**:
  - **Web Analytics**: must be **disabled** (not installed). When enabled, Vercel injects `https://va.vercel-scripts.com/v1/script.debug.js` (dev) or production equivalents into HTML, which would violate the no-telemetry trust posture. Verifiable: `curl -s https://patentlint.com/ | grep -c va.vercel` must return 0.
  - **Speed Insights**: must be **disabled** (not installed). Same reasoning — injects a `@vercel/speed-insights` beacon script. Verifiable: `curl -s https://patentlint.com/ | grep -c vercel-insights` must return 0.
  - **Firewall** rules: enabling the platform-wide firewall is fine (request-level, no script injection); enabling **Bot management challenges** would inject JS — leave at default. Verifiable: `curl -s https://patentlint.com/ | grep -c cdn-cgi` must return 0 (Vercel doesn't use this path; this checks against accidental migration back to a Cloudflare-style provider).
- Vercel doesn't add `Report-To` / `NEL` headers by default (verified 2026-05-08). If a future Vercel feature toggles these on, audit and disable.

### 1. Cold-start drop test
- Hard-reload the page (Cmd+Shift+R).
- Take a screenshot (Cmd+Shift+4) — this seeds the macOS screencaptureui temp directory, which is the trigger condition for the file:// drag-preview class of bug.
- **Open DevTools → Network tab BEFORE dropping** and let the loading screen finish.
- Drop a real `.docx` into the dropzone.
- Confirm: AnalysisReport network dot stays **green** during analysis, while the report renders, and after the claim tree fully draws. The bottom-right widget counter stays at **0**.
- **Confirm: zero new Network tab entries** appear from the drop event onward. Mermaid's flowchart chunks should already be in the JS module registry from `preloadMermaidChunks()` (called during initial mount). If you see chunks like `flowDiagram-*.js` or `cose-bilkent-*.js` fetch on drop, the pre-load racing condition is back — see `lib/preloadMermaid.js`.
- Also watch the network dot during the next visibility-return ≥5s — `/version.json` GET (initiatorType `fetch`) SHOULD legitimately flash the dot briefly. That's correct behavior, not a bug.
- If the dot turns red during analysis without the user explicitly sending a report, that's a violation. See `scripts/check_trust_observers.sh` for the related code-level gate.

### 2. Airplane-mode test
- Disable WiFi + cellular on the host machine.
- Hard-reload the page. The app should serve from cache and remain functional.
- Drop a `.docx`. Analysis should complete normally. Indicator stays green.
- Open ProveItModal. Click "Test outgoing request." The log should record either nothing or an entry with no `responseStart` (filtered out — the dot must NOT flash red).
- Re-enable network. The update-check toast should fire on the next visibility change ≥5s.

### 3. Network egress audit
- Open DevTools → Network tab. Hard-reload.
- Expected entries (in this order, approximately):
  1. App bundle: `index.html`, JS chunks, CSS.
  2. Pyodide CDN: `pyodide.js`, runtime WASM, packages (lxml, pydantic, micropip).
  3. `patentlint-1.0.0-py3-none-any.whl` (the analyzer wheel).
  4. CJK font from `fonts.gstatic.com` (only when picker is set to a CJK jurisdiction).
  5. `version.json` (mount-time + on every tab-return ≥5s).
- Drop a `.docx`. Confirm: **no new network entries should appear** during or after analysis. (file:// entries from drag preview are browser-internal and not trust-relevant — see `lib/trustObserver.js`.)
- Click "Send anonymous report" inside ReportModal. Confirm one POST to `/api/report`, the widget counter increments by 1, dot flashes red briefly.

### 4. Trust copy regression
- For each of en / de / zh-TW / zh-CN / ja / ko:
  - DropZone trust badge headline + CTA.
  - Security page hero + tech details.
  - About page architecture description.
  - NetworkWidget label + endpoint description.
  - ProveItModal description.
- Watch for: stale claims (e.g., "no AI" when AI was added; "no cloud" when a cloud tier was announced); calque phrasing (e.g., zh "對內" / 「対象」-style transliterations); claim drift between locales (e.g., en says "X" but de says "X + Y").

### 5. Code-level invariants

These are enforced automatically — listed here for awareness.

- **Trust-observer filter** — every `new PerformanceObserver` on `type: 'resource'` must filter entries through `isTrustRelevantResource` (see `frontend/src/lib/trustObserver.js`). Enforced by `scripts/check_trust_observers.sh`, which runs as both a pre-commit hook and a CI step.
- **Wheel staleness** — wheel must be rebuilt whenever `src/patentlint/**/*.py` changes. Enforced by `.githooks/pre-commit` (Block A) and the `wheel-verify` CI job.
- **i18n key parity** — all locales must have the same keys. Enforced by `scripts/i18n_presence_check.mjs`.

## Bug history

Trust violations that shipped and the audit gap each one revealed. New entries land at the top.

- **2026-05-08 / hosting migration Cloudflare Pages → Vercel.** Cloudflare's free-plan zone-level **JavaScript Detections (JSD)** was injecting `/cdn-cgi/challenge-platform/scripts/jsd/main.js` into every HTML response — bot-detection telemetry that fingerprinted the browser and phoned home to Cloudflare on every visit. Independent of Bot Fight Mode (the JSD toggle was gated to Pro+). Plus default `Report-To` / `NEL` headers pointing to `a.nel.cloudflare.com`. Both were latent zone-level injections that `_worker.js` couldn't intercept (edge processing runs after Worker). **Audit gap closed:** migrated production hosting to Vercel (commits `afd880a` + `7fba442` + `5b349ed` + `bcb5035` + `189c0a9`). Vercel ships clean by default — `cdn-cgi` count: 0, `vercel-insights` count: 0, `va.vercel` count: 0, no Report-To, no NEL. DNS at Cloudflare points apex + www to Vercel via CNAME (DNS-only, grey cloud). Trust copy in 6 locales now strictly accurate. § 0 of this checklist now covers Vercel-side equivalents (Web Analytics, Speed Insights — both disabled).
- **2026-05-07 / `deba456` — mermaid chunks lazy-loading on drop.** `5fe9ecc` made the indicator stay green by filtering `initiatorType: 'script'`, but the chunks STILL appeared in DevTools' Network tab on drop because mermaid's flowchart modules (flowDiagram, cose-bilkent, cytoscape, layout helpers) lazy-loaded the first time `ClaimDiagram` rendered the claim tree. With WiFi off the same entries reappeared as "(disk cache)" hits. Latent since `acb7986` (Apr 17, default-collapsed → default-expanded). **Audit gap closed:** added `lib/preloadMermaid.js` invoked from `App.jsx` during initial mount. Mermaid renders a minimal flowchart in parallel with Pyodide bootstrap, parking all flowchart-related modules in the JS module registry before the user can drop. Subsequent renders resolve locally with no fetch (not even a cache hit).
- **2026-05-07 / `5fe9ecc` — passive-bundle-load leak.** `f3f6575`'s `^https?:` filter was too lenient: HTTPS-but-not-trust-relevant requests (mermaid's ~50 lazy-loaded diagram-type chunks, vite code-split bundles, fonts loaded via CSS) still flashed the dot red during the first analysis when ClaimDiagram first rendered. **Audit gap closed:** added `initiatorType` filter — only `fetch` and `xmlhttprequest` count as trust-relevant. Same trustObserver helper, one-line addition.
- **2026-05-07 / `f3f6575` + `4d2669a` — `file://` drag-preview leak.** PerformanceObserver in `useNetworkMonitor` and `ProveItModal` surfaced macOS screencaptureui screenshot loads as "network active." Triggered for the first time after weeks of LinkedIn-prep screenshotting kept the temp directory hot. **Audit gap closed:** centralized the filter into `lib/trustObserver.js`; added `check_trust_observers.sh` running as pre-commit + CI gate.
- **2026-04-30 / `1e2aa6f` — offline-failed-fetch leak in ProveItModal.** PerformanceObserver counted entries with `responseStart === 0` (browser attempted, network unreachable). User in airplane mode clicking "test outgoing request" saw the indicator flash red. **Audit gap closed:** the same `responseStart > 0` filter is now part of `isTrustRelevantResource` and applied consistently.

## When to add to this list

Add a new bug-history entry whenever a trust violation ships to production. Add a new pre-ship checklist item whenever a bug class slips through that the existing items wouldn't have caught. Resist adding speculative items — three checklist items everyone runs is more valuable than fifteen no one reads.
