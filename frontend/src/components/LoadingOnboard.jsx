// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025–2026 Christopher Chen
import { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { ShieldCheck, FileSearch, Globe } from 'lucide-react'

const FEATURES = [
  { icon: FileSearch, titleKey: 'loading.feature2_title', descKey: 'loading.feature2_desc' },
  { icon: ShieldCheck, titleKey: 'loading.feature1_title', descKey: 'loading.feature1_desc' },
  { icon: Globe, titleKey: 'loading.feature4_title', descKey: 'loading.feature4_desc' },
]

const STAGGER_MS = 700
const READY_PAUSE_MS = 600
const FADE_DURATION_MS = 300
// After this long on the runtime stage, show the "first visit is slow,
// cached next time" hint. Covers users whose cold-cache WASM fetch is
// running longer than the typical feature-reveal window, who'd
// otherwise wonder if it's stuck.
const RUNTIME_HINT_DELAY_MS = 3000

export default function LoadingOnboard({ progress, onReady }) {
  const { t } = useTranslation()
  const [visible, setVisible] = useState(true)
  const [fading, setFading] = useState(false)
  const [revealCount, setRevealCount] = useState(0)
  const [showRuntimeHint, setShowRuntimeHint] = useState(false)
  const revealRef = useRef(0)
  const intervalRef = useRef(null)

  // Show the first-visit hint if we've been on the runtime stage longer
  // than RUNTIME_HINT_DELAY_MS. Resets on stage change.
  useEffect(() => {
    setShowRuntimeHint(false)
    const isRuntimeStage = progress.message?.includes('Python runtime')
    if (!isRuntimeStage) return
    const t = setTimeout(() => setShowRuntimeHint(true), RUNTIME_HINT_DELAY_MS)
    return () => clearTimeout(t)
  }, [progress.message])

  // Staggered reveal: first card after 500ms, then every STAGGER_MS
  useEffect(() => {
    const initialTimer = setTimeout(() => {
      revealRef.current = 1
      setRevealCount(1)
      intervalRef.current = setInterval(() => {
        if (revealRef.current >= FEATURES.length) {
          clearInterval(intervalRef.current)
          return
        }
        revealRef.current += 1
        setRevealCount(revealRef.current)
      }, STAGGER_MS)
    }, 500)
    return () => { clearTimeout(initialTimer); clearInterval(intervalRef.current) }
  }, [])

  // Handle ready state: stop interval → finish staggered reveal → fade out → signal parent
  useEffect(() => {
    if (progress.percent < 100) return

    // Stop the interval so it doesn't race with our scheduled timeouts
    clearInterval(intervalRef.current)

    // Schedule remaining features at consistent STAGGER_MS intervals, then fade out
    const remaining = FEATURES.length - revealRef.current
    const timers = []
    for (let i = 0; i < remaining; i++) {
      timers.push(setTimeout(() => {
        revealRef.current += 1
        setRevealCount(revealRef.current)
      }, STAGGER_MS * (i + 1)))
    }
    const fadeDelay = STAGGER_MS * remaining + READY_PAUSE_MS
    timers.push(setTimeout(() => setFading(true), fadeDelay))
    timers.push(setTimeout(() => { setVisible(false); onReady?.() }, fadeDelay + FADE_DURATION_MS))
    return () => timers.forEach(clearTimeout)
  }, [progress.percent >= 100])

  if (!visible) return null

  // Cap displayed progress so the bar stays in sync with the feature reveal.
  // It reaches 100% only when all features are visible.
  const allRevealed = revealCount >= FEATURES.length
  const displayPercent = allRevealed
    ? progress.percent
    : Math.min(progress.percent, 15 + (revealCount / FEATURES.length) * 75)
  const isReady = allRevealed && progress.percent >= 100

  return (
    <div
      className="fixed inset-0 z-50 overflow-y-auto bg-background/95 backdrop-blur-sm"
      style={{
        opacity: fading ? 0 : 1,
        transition: `opacity ${FADE_DURATION_MS}ms ease`,
      }}
    >
      <div className="min-h-full flex items-center justify-center py-8 md:py-0 md:pb-[20vh]">
        <div className="flex flex-col items-center gap-6 max-w-md px-6 text-center">
        {/* Logo */}
        <h1 className="text-3xl font-bold tracking-tight">PatentLint</h1>

        {/* Progress bar */}
        <div className="w-full">
          <div className="w-full h-2.5 rounded-full bg-muted overflow-hidden">
            <div
              className="h-full rounded-full"
              style={{
                width: `${displayPercent}%`,
                transition: 'width 0.7s cubic-bezier(0.4, 0, 0.2, 1)',
                background: isReady
                  ? 'var(--color-green-500, #22c55e)'
                  : 'linear-gradient(90deg, var(--color-blue-500, #3b82f6), var(--color-cyan-500, #06b6d4))',
              }}
            />
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            {isReady
              ? `✓ ${t('loading.ready')}`
              : `${t(`loading.${stageKey(progress.message)}`)} ${Math.round(displayPercent)}%`}
          </p>
          <p
            className="mt-1 text-xs text-muted-foreground/70 leading-snug"
            style={{
              opacity: showRuntimeHint && !isReady ? 1 : 0,
              transition: 'opacity 0.4s ease',
              minHeight: '1rem',
            }}
            aria-live="polite"
          >
            {showRuntimeHint && !isReady ? t('loading.firstVisitHint') : ' '}
          </p>
        </div>

        {/* Feature list — time-staggered reveal */}
        <div className="w-full flex flex-col gap-3 text-left">
          {FEATURES.map(({ icon: Icon, titleKey, descKey }, i) => {
            const show = i < revealCount
            return (
              <div
                key={i}
                className="flex items-start gap-3 rounded-lg px-3 py-2"
                style={{
                  opacity: show ? 1 : 0,
                  transform: show ? 'translateY(0)' : 'translateY(8px)',
                  transition: 'opacity 0.4s ease, transform 0.4s ease',
                }}
              >
                <Icon className="h-5 w-5 mt-0.5 shrink-0 text-muted-foreground" />
                <div>
                  <p className="text-sm font-medium leading-tight">{t(titleKey)}</p>
                  <p className="text-xs text-muted-foreground mt-0.5 leading-snug">{t(descKey)}</p>
                </div>
              </div>
            )
          })}
        </div>

        {/* Offline note */}
        <p className="text-xs text-muted-foreground/60">{t('loading.offline_note')}</p>
        </div>
      </div>
    </div>
  )
}

function stageKey(message) {
  if (message?.includes('Python runtime')) return 'runtime'
  if (message?.includes('document parser')) return 'parser'
  if (message?.includes('analysis engine')) return 'engine'
  if (message?.includes('PatentLint')) return 'patentlint'
  return 'runtime'
}
