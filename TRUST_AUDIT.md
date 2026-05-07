# Trust audit checklist

PatentLint's primary trust claim is **No upload. No cloud processing. No AI.** Every change that touches the trust surfaces below should be sanity-checked against this list before shipping. The list is short on purpose — long checklists rot — but each item maps to a real bug class that has shipped at least once.

## Trust surfaces

- **DropZone trust badge** (`frontend/src/components/DropZone.jsx`) — the security headline + "verify it yourself" CTA.
- **AnalysisReport network dot** (`frontend/src/components/AnalysisReport.jsx` + `useNetworkMonitor`) — the green/red indicator on the results header.
- **NetworkWidget** (`frontend/src/components/NetworkWidget.jsx`) — the persistent bottom-right "Outgoing data" counter.
- **ProveItModal** (`frontend/src/components/ProveItModal.jsx`) — the airplane-mode demo + live activity log.
- **Update-check banner** (`frontend/src/hooks/useUpdateCheck.js`) — the toast that fires after tab returns from being hidden ≥ 5s.
- **Voluntary error-report pipeline** (`frontend/src/lib/feedback.js` + Pages Function `/api/report`) — the only intentional outbound POST in the app.
- **Trust copy** — `security.*`, `widget.*`, `dropzone.notice*` keys in `frontend/src/i18n/locales/*.json`.

## Pre-ship checklist

Run before any push that touches the surfaces above, and at minimum monthly as a standing audit.

### 1. Cold-start drop test
- Hard-reload the page (Cmd+Shift+R).
- Take a screenshot (Cmd+Shift+4) — this seeds the macOS screencaptureui temp directory, which is the trigger condition for the file:// drag-preview class of bug.
- Drop a real `.docx` into the dropzone.
- Confirm: AnalysisReport network dot stays **green** during analysis, while the report renders, and after the claim tree fully draws. The bottom-right widget counter stays at **0**.
- Specifically watch the moment ClaimDiagram first renders — mermaid lazy-loads ~50 diagram-type chunks the first time you see the tree. Those are own-bundle script loads (initiatorType `script`) and should NOT register as network-active. If the dot flashes red here, something regressed in the `initiatorType` filter — see `lib/trustObserver.js`.
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

- **2026-05-07 / `5fe9ecc` — passive-bundle-load leak.** `f3f6575`'s `^https?:` filter was too lenient: HTTPS-but-not-trust-relevant requests (mermaid's ~50 lazy-loaded diagram-type chunks, vite code-split bundles, fonts loaded via CSS) still flashed the dot red during the first analysis when ClaimDiagram first rendered. **Audit gap closed:** added `initiatorType` filter — only `fetch` and `xmlhttprequest` count as trust-relevant. Same trustObserver helper, one-line addition.
- **2026-05-07 / `f3f6575` + `4d2669a` — `file://` drag-preview leak.** PerformanceObserver in `useNetworkMonitor` and `ProveItModal` surfaced macOS screencaptureui screenshot loads as "network active." Triggered for the first time after weeks of LinkedIn-prep screenshotting kept the temp directory hot. **Audit gap closed:** centralized the filter into `lib/trustObserver.js`; added `check_trust_observers.sh` running as pre-commit + CI gate.
- **2026-04-30 / `1e2aa6f` — offline-failed-fetch leak in ProveItModal.** PerformanceObserver counted entries with `responseStart === 0` (browser attempted, network unreachable). User in airplane mode clicking "test outgoing request" saw the indicator flash red. **Audit gap closed:** the same `responseStart > 0` filter is now part of `isTrustRelevantResource` and applied consistently.

## When to add to this list

Add a new bug-history entry whenever a trust violation ships to production. Add a new pre-ship checklist item whenever a bug class slips through that the existing items wouldn't have caught. Resist adding speculative items — three checklist items everyone runs is more valuable than fifteen no one reads.
