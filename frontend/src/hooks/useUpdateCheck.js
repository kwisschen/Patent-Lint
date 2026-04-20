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
// Session-scoped timestamp of the last check attempt. Used to throttle
// visibility-triggered checks so that returning to the tab doesn't
// flicker the network indicator on every focus event.
const LAST_CHECK_KEY = 'patentlint:update-last-check'
const TOAST_ID = 'patentlint-update-available'
// Minimum interval between automated version checks triggered by
// visibility events. Mount checks (fresh load / reload) always fire
// regardless. Long enough to suppress flicker on typical tab-switch
// cycles (Word ↔ PatentLint every few minutes = well under 15 min
// between returns = no flicker); short enough that users who push a
// deploy and tab-switch back within ~15 min see the update prompt.
// Previous value (60 min) was tuned for "zero flicker in normal use"
// but was too long for active-testing workflows where the user pushes
// then verifies within a few minutes.
const CHECK_THROTTLE_MS = 15 * 60 * 1000

/**
 * Fetches /version.json on page load and on tab focus, compares to the
 * bundled __BUILD_HASH__ constant, and shows a Sonner toast if they differ.
 *
 * Design notes:
 * - No polling, no background heartbeat. Version checks only fire on
 *   explicit user interaction (page load or tab focus) to preserve the
 *   zero-upload security story — a paranoid user watching DevTools will
 *   only see network activity when they actively engage with the site.
 * - Throttle applies to VISIBILITY events only. Mount-time checks
 *   (initial load, reload, locale-switch re-render) always fire, so a
 *   reload is the reliable user-facing escape hatch for "did a new
 *   version ship?" — matching what users already expect from reloading
 *   any web app. Throttling reloads would silently withhold updates
 *   from users who explicitly asked for fresh state.
 * - The visibility throttle suppresses the indicator flicker that would
 *   otherwise fire on every tab-switch return. When the throttle clears
 *   and a check does fire, the indicator still flashes truthfully — the
 *   throttle masks nothing, it just cuts the unnecessary re-checks.
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

  useEffect(() => {
    // Skip in dev — version.json is only generated in production builds
    if (import.meta.env.DEV) return

    const dismissedFor = () => sessionStorage.getItem(DISMISSED_KEY) || ''
    const lastCheckMs = () => {
      const v = sessionStorage.getItem(LAST_CHECK_KEY)
      return v ? Number(v) : 0
    }
    const isThrottled = () =>
      Date.now() - lastCheckMs() < CHECK_THROTTLE_MS

    const check = async () => {
      // Record the attempt BEFORE the fetch so transient failures don't
      // unthrottle and re-fire on the next visibility event. The user
      // will get a fresh attempt after CHECK_THROTTLE_MS or on reload.
      sessionStorage.setItem(LAST_CHECK_KEY, String(Date.now()))
      try {
        // Cache-bust the manifest fetch itself so we always see the latest.
        // This is safe to cache-bust aggressively: it's a tiny static JSON.
        const res = await fetch(`/version.json?t=${Date.now()}`, {
          cache: 'no-store',
        })
        if (!res.ok) return
        const data = await res.json()
        if (!data.buildHash || data.buildHash === __BUILD_HASH__) return

        // Version-scoped dismissal: only suppress if THIS specific
        // server build was already dismissed this session. A newer
        // deploy naturally breaks the suppression because the stored
        // hash no longer matches.
        if (data.buildHash === dismissedFor()) return

        // Capture in closure so dismiss callbacks store THIS build's
        // hash, not whatever the latest is at dismissal time (which
        // could race with a concurrent check).
        const targetHash = data.buildHash

        toast(t('updates.available'), {
          id: TOAST_ID,
          duration: Infinity,
          action: {
            label: t('updates.reload'),
            onClick: () => {
              // Belt-and-suspenders: clear Pyodide's Cache Storage before
              // reload. The query-param cache-busting from commit 1 should
              // make this unnecessary, but defense-in-depth protects users
              // whose browsers somehow cached the old URL.
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
                  .finally(() => window.location.reload())
              } else {
                window.location.reload()
              }
            },
          },
          cancel: {
            label: t('updates.dismiss'),
            onClick: () => {
              sessionStorage.setItem(DISMISSED_KEY, targetHash)
            },
          },
          onDismiss: () => {
            sessionStorage.setItem(DISMISSED_KEY, targetHash)
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

    // Run on tab focus, also throttled. Using visibilitychange instead
    // of focus because visibilitychange is more reliable across browsers
    // and doesn't fire on window focus that doesn't change tab visibility.
    const handleVisibilityChange = () => {
      if (document.visibilityState !== 'visible') return
      if (isThrottled()) return
      check()
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [t])
}
