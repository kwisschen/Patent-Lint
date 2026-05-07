/* global __BUILD_HASH__ */
import { useEffect, useRef } from 'react'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'

// Session-scoped version-specific dismissal key. Stores the buildHash
// that the user dismissed. The next time a check runs, we only suppress
// the toast if the current server buildHash matches the dismissed one —
// so dismissing version Y doesn't silence a toast for version Z. Without
// version-scoping, a single dismissal in the session permanently blocked
// all future update prompts, which broke the update flow for anyone who
// ever clicked "Later".
const DISMISSED_KEY = 'patentlint:update-dismissed'
// Companion key storing when the dismissal happened. Used to re-show
// the toast after a grace period so accidentally-dismissed updates
// don't silently hide. Newer versions still break the suppression
// immediately (via hash mismatch); this grace period only affects the
// "same version was dismissed recently" case.
const DISMISSED_AT_KEY = 'patentlint:update-dismissed-at'
const DISMISSAL_RESHOW_MS = 30 * 60 * 1000
const TOAST_ID = 'patentlint-update-available'
// Visibility check gate. On a visibility-visible event, fire a version
// check only if the tab was HIDDEN for at least this long. Models
// actual user behavior ("I walked away, now I'm back") better than a
// time-since-last-check throttle — rapid alt-tabbing (instant tab-flips)
// stays silent, but anything that looks like "I left and came back"
// triggers a check on return. The trust-copy claim ("Same request runs
// automatically when you return to the tab" / "離開分頁再回來時也會自動
//執行相同請求") needs to hold during a hiring-manager / patent-attorney
// demo where the user alt-tabs for 3-10 seconds to verify the claim.
// 5 seconds catches that demo pattern while still ignoring sub-second
// double-tabs and accidental focus loss.
//
// History: was 30 s — too long for demo verification (a 5-10 s alt-tab
// was below threshold and the claim appeared to fail). Was 15 min in
// an earlier iteration — Windows users with long-running tabs never
// hit the 15-min gap because they'd switched back in between, so the
// throttle never cleared.
const MIN_HIDDEN_MS_FOR_CHECK = 5 * 1000

/**
 * Fetches /version.json on page load and on tab focus, compares to the
 * bundled __BUILD_HASH__ constant, and shows a Sonner toast if they differ.
 *
 * Design notes:
 * - No polling, no background heartbeat. Version checks only fire on
 *   explicit user interaction (page load or tab focus) to preserve the
 *   zero-upload security story — a paranoid user watching DevTools will
 *   only see network activity when they actively engage with the site.
 * - Mount-time checks (initial load, reload) always fire. Locale-switch
 *   re-renders are gated by hasMountChecked so a pure UI-language change
 *   doesn't trigger a network call.
 * - Visibility-change checks gate on HIDDEN DURATION, not time-since-last-
 *   check. A visibility-visible event fires a check only if the tab was
 *   hidden for ≥ MIN_HIDDEN_MS_FOR_CHECK. This models the "I walked away
 *   and came back" case correctly (user pushes a deploy, switches back in
 *   2-3 min → check fires → sees toast) while keeping rapid alt-tabbing
 *   silent. Previous time-since-last-check throttle broke for Windows
 *   users with long-running tabs who never hit the throttle gap.
 * - No file-drop check. The moment the user entrusts a patent draft to
 *   the app must trigger zero network activity.
 * - Silently fails on fetch errors (offline, version.json missing, etc.)
 *   so "works offline after first load" claim holds.
 * - Dev mode is skipped entirely (version.json is build-only).
 */
export function useUpdateCheck() {
  const { t } = useTranslation()
  // Tracks whether the mount-time check has already fired in this tab
  // session. Persists across effect re-runs (e.g., when [t] changes due
  // to a locale switch) so locale switching does NOT trigger a fresh
  // network call — that would flicker the honest network indicator
  // during a pure UI-language change and betray the trust property.
  const hasMountChecked = useRef(false)
  // Timestamp of the last visibility-hidden event. Used to measure how
  // long the tab was hidden before becoming visible again; the check
  // fires only if that duration ≥ MIN_HIDDEN_MS_FOR_CHECK.
  const lastHiddenMs = useRef(0)

  useEffect(() => {
    // Scrub the ?_r=<ts> cache-bust query param that the Reload action
    // appends to the HTML document URL. Without this, the address bar
    // retains the timestamp after reload (bookmark-ugly, not a privacy
    // concern — the ts is a pure cache-buster, same class as ?t=<ts> on
    // version.json). Runs unconditionally; cheap no-op when absent.
    if (typeof window !== 'undefined' && window.location.search.includes('_r=')) {
      const url = new URL(window.location.href)
      url.searchParams.delete('_r')
      const cleaned = url.pathname + (url.search ? url.search : '') + url.hash
      window.history.replaceState({}, '', cleaned)
    }

    // Skip in dev — version.json is only generated in production builds
    if (import.meta.env.DEV) return

    const dismissedFor = () => sessionStorage.getItem(DISMISSED_KEY) || ''
    const dismissedAtMs = () => Number(sessionStorage.getItem(DISMISSED_AT_KEY) || 0)
    const recordDismissal = (buildHash) => {
      sessionStorage.setItem(DISMISSED_KEY, buildHash)
      sessionStorage.setItem(DISMISSED_AT_KEY, String(Date.now()))
    }

    const check = async () => {
      try {
        // Cache-bust the manifest fetch itself so we always see the latest.
        // This is safe to cache-bust aggressively: it's a tiny static JSON.
        const res = await fetch(`/version.json?t=${Date.now()}`, {
          cache: 'no-store',
        })
        if (!res.ok) return
        const data = await res.json()
        if (!data.buildHash || data.buildHash === __BUILD_HASH__) return

        // Version-scoped dismissal with time-bounded grace period:
        // suppress only if THIS specific server build was dismissed
        // within the last DISMISSAL_RESHOW_MS. After the grace period,
        // re-show so accidentally-dismissed updates don't silently hide.
        // A newer deploy breaks the suppression immediately via hash
        // mismatch — the time window only affects "same hash" suppression.
        if (
          data.buildHash === dismissedFor() &&
          Date.now() - dismissedAtMs() < DISMISSAL_RESHOW_MS
        ) {
          return
        }

        // Capture in closure so dismiss callbacks store THIS build's
        // hash, not whatever the latest is at dismissal time (which
        // could race with a concurrent check).
        const targetHash = data.buildHash
        // Sonner's onDismiss fires on ANY dismissal — including the
        // action button click that triggers Reload. If we let onDismiss
        // unconditionally call recordDismissal, clicking Reload silently
        // stores the NEW hash as "dismissed", and a stale-HTML reload
        // loop then re-surfaces the toast after the grace period. This
        // flag scopes recordDismissal to implicit dismissals only (swipe
        // / programmatic). Cancel still records explicitly.
        let explicitlyHandled = false

        toast(t('updates.available'), {
          id: TOAST_ID,
          duration: Infinity,
          action: {
            label: t('updates.reload'),
            onClick: () => {
              explicitlyHandled = true
              // Force a fresh HTML fetch. window.location.reload() may
              // serve a cached document (browser or CDN edge), which
              // would re-execute the old bundle with the stale build
              // hash baked in — the toast then reappears on the next
              // check. A replace() with a one-shot cache-bust query
              // forces the document request to bypass HTTP cache.
              const reloadWithCacheBust = () => {
                const url = new URL(window.location.href)
                url.searchParams.set('_r', String(Date.now()))
                window.location.replace(url.toString())
              }
              // Belt-and-suspenders: clear Pyodide's Cache Storage
              // before reload. New deploys often ship a new Pyodide
              // wheel, so the old cached WASM wouldn't match.
              if ('caches' in window) {
                caches
                  .keys()
                  .then((keys) =>
                    Promise.all(
                      keys
                        .filter((k) => k.toLowerCase().includes('pyodide'))
                        .map((k) => caches.delete(k))
                    )
                  )
                  .finally(reloadWithCacheBust)
              } else {
                reloadWithCacheBust()
              }
            },
          },
          cancel: {
            label: t('updates.dismiss'),
            onClick: () => {
              explicitlyHandled = true
              recordDismissal(targetHash)
            },
          },
          onDismiss: () => {
            if (explicitlyHandled) return
            recordDismissal(targetHash)
          },
        })
      } catch (e) {
        // Silent fail — offline, version.json missing, CORS, etc.
      }
    }

    // Run on TRUE mount only. Initial load / reload starts a fresh React
    // tree, so hasMountChecked.current is false → check fires. Effect
    // re-runs from a locale switch (where [t] changed but the component
    // didn't remount) hit the ref guard and skip — locale changes must
    // not trigger a network call, otherwise the network indicator would
    // flicker red on a pure UI-language change and mislead the user.
    if (!hasMountChecked.current) {
      hasMountChecked.current = true
      check()
    }

    // Visibility-change: fire a check when the tab becomes visible IF
    // it was hidden for at least MIN_HIDDEN_MS_FOR_CHECK. Models both
    // the "I walked away and came back" case (push a deploy, wait for
    // CI, switch back → check fires → toast if mismatch) AND the demo
    // verification case (a hiring manager / patent attorney alt-tabs
    // for 3-10 seconds to check that the trust-copy claim holds — at
    // 5s threshold, that demo reliably fires). Sub-second tab-flips
    // and accidental focus loss stay silent (no flicker).
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        lastHiddenMs.current = Date.now()
        return
      }
      // visibilityState === 'visible'
      if (lastHiddenMs.current === 0) return
      if (Date.now() - lastHiddenMs.current >= MIN_HIDDEN_MS_FOR_CHECK) {
        check()
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [t])
}
