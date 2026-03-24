import { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { ShieldCheck, FileSearch, GitBranch, Globe } from 'lucide-react'

const FEATURES = [
  { icon: ShieldCheck, titleKey: 'loading.feature1_title', descKey: 'loading.feature1_desc' },
  { icon: FileSearch, titleKey: 'loading.feature2_title', descKey: 'loading.feature2_desc' },
  { icon: GitBranch, titleKey: 'loading.feature3_title', descKey: 'loading.feature3_desc' },
  { icon: Globe, titleKey: 'loading.feature4_title', descKey: 'loading.feature4_desc' },
]

const STAGGER_MS = 700
const READY_PAUSE_MS = 600
const FADE_DURATION_MS = 300

export default function LoadingOnboard({ progress, onReady }) {
  const { t } = useTranslation()
  const [visible, setVisible] = useState(true)
  const [fading, setFading] = useState(false)
  const [revealCount, setRevealCount] = useState(0)
  const mountTime = useRef(Date.now())

  // Staggered reveal: show one more feature every STAGGER_MS
  useEffect(() => {
    const id = setInterval(() => {
      setRevealCount(c => {
        if (c >= FEATURES.length) {
          clearInterval(id)
          return c
        }
        return c + 1
      })
    }, STAGGER_MS)
    return () => clearInterval(id)
  }, [])

  // Handle ready state: pause → fade out → signal parent
  useEffect(() => {
    if (progress.percent < 100) return

    // Reveal any remaining features immediately
    setRevealCount(FEATURES.length)

    const t1 = setTimeout(() => {
      setFading(true)
      const t2 = setTimeout(() => {
        setVisible(false)
        onReady?.()
      }, FADE_DURATION_MS)
      return () => clearTimeout(t2)
    }, READY_PAUSE_MS)
    return () => clearTimeout(t1)
  }, [progress.percent, onReady])

  if (!visible) return null

  const isReady = progress.percent >= 100

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-background/95 backdrop-blur-sm"
      style={{
        opacity: fading ? 0 : 1,
        transition: `opacity ${FADE_DURATION_MS}ms ease`,
      }}
    >
      <div className="flex flex-col items-center gap-6 max-w-md px-6 text-center">
        {/* Logo */}
        <h1 className="text-3xl font-bold tracking-tight">PatentLint</h1>

        {/* Progress bar */}
        <div className="w-full">
          <div className="w-full h-2.5 rounded-full bg-muted overflow-hidden">
            <div
              className="h-full rounded-full"
              style={{
                width: `${progress.percent}%`,
                transition: 'width 0.3s ease',
                background: isReady
                  ? 'var(--color-green-500, #22c55e)'
                  : 'linear-gradient(90deg, var(--color-blue-500, #3b82f6), var(--color-cyan-500, #06b6d4))',
              }}
            />
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            {isReady
              ? `✓ ${t('loading.ready')}`
              : `${t(`loading.${stageKey(progress.message)}`)} ${progress.percent}%`}
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
  )
}

function stageKey(message) {
  if (message?.includes('Python runtime')) return 'runtime'
  if (message?.includes('document parser')) return 'parser'
  if (message?.includes('analysis engine')) return 'engine'
  if (message?.includes('PatentLint')) return 'patentlint'
  return 'runtime'
}
