/* global __BUILD_HASH__ */
import { useEffect } from 'react'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'

// Session-scoped dismissal key. If the user clicks "Later", we stop
// showing the toast for the rest of the session. Reappears next session
// if a newer version is still available.
const DISMISSED_KEY = 'patentlint:update-dismissed'
// Session-scoped timestamp of the last check attempt. Used to throttle
// visibility-triggered checks so that returning to the tab doesn't
// flicker the network indicator on every focus event.
const LAST_CHECK_KEY = 'patentlint:update-last-check'
const TOAST_ID = 'patentlint-update-available'
// Minimum interval between automated version checks (mount + visibility).
// Long enough to suppress the per-tab-switch indicator flicker that the
// honest network-monitor surfaces — a typical 30-90 min session sees
// zero flickers from this hook. Cost of erring long: a user who keeps a
// tab open across a deploy may not see the update prompt until next
// reload, which is acceptable (they keep using the previous working
// version, and pick up the update on next mount).
const CHECK_THROTTLE_MS = 60 * 60 * 1000

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

  useEffect(() => {
    // Skip in dev — version.json is only generated in production builds
    if (import.meta.env.DEV) return

    const isDismissed = () => sessionStorage.getItem(DISMISSED_KEY) === '1'
    const lastCheckMs = () => {
      const v = sessionStorage.getItem(LAST_CHECK_KEY)
      return v ? Number(v) : 0
    }
    const isThrottled = () =>
      Date.now() - lastCheckMs() < CHECK_THROTTLE_MS

    const check = async () => {
      if (isDismissed()) return
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
              sessionStorage.setItem(DISMISSED_KEY, '1')
            },
          },
          onDismiss: () => {
            sessionStorage.setItem(DISMISSED_KEY, '1')
          },
        })
      } catch (e) {
        // Silent fail — offline, version.json missing, CORS, etc.
      }
    }

    // Run on mount unconditionally. Initial load, reload, and locale-switch
    // re-render all fire a fresh check — reloading the page is how users
    // expect to "force a refresh" of any web app, and throttling that would
    // silently withhold updates from users explicitly asking for fresh state.
    // The occasional extra check on locale switch (rare mid-session) is the
    // accepted cost of this simpler policy.
    check()

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
