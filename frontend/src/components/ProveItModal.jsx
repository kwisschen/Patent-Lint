// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
import { useState, useEffect, useRef, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { WifiOff, FileText, CheckCircle, Activity, Check } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import LogoIcon from './LogoIcon'

const PANELS = [
  { icon: WifiOff, colorClass: 'text-amber-500', labelKey: 'security.prove.label1', textKey: 'security.prove.step1' },
  { icon: FileText, colorClass: 'text-blue-500', labelKey: 'security.prove.label2', textKey: 'security.prove.step2' },
  { icon: CheckCircle, colorClass: 'text-green-500', labelKey: 'security.prove.label3', textKey: 'security.prove.step3' },
  { icon: Activity, colorClass: 'text-green-500', labelKey: 'security.prove.label4', textKey: 'security.prove.step4' },
]

function LogEntry({ entry, isNew }) {
  const [fresh, setFresh] = useState(isNew)

  useEffect(() => {
    if (!isNew) return
    const timer = setTimeout(() => setFresh(false), 500)
    return () => clearTimeout(timer)
  }, [isNew])

  const urlPath = (() => {
    try {
      const url = new URL(entry.url)
      return url.pathname + url.search
    } catch {
      return entry.url
    }
  })()

  return (
    <div
      className="flex items-center gap-2 text-xs font-mono animate-in slide-in-from-left-2 duration-200"
      style={{ animationTimingFunction: 'var(--ease-bounce)' }}
    >
      <span className={`w-1.5 h-1.5 rounded-full shrink-0 transition-colors duration-500 ${fresh ? 'bg-red-500' : 'bg-gray-500'}`} />
      <span className="text-gray-400">{entry.timestamp}</span>
      <span className="text-gray-300">GET</span>
      <span className="text-gray-100 truncate">{urlPath}</span>
    </div>
  )
}

export default function ProveItModal({ open, onOpenChange }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [entries, setEntries] = useState([])
  const [testSent, setTestSent] = useState(false)
  const [networkActive, setNetworkActive] = useState(false)
  const [noActivityDetected, setNoActivityDetected] = useState(false)
  const logRef = useRef(null)
  const timeoutRef = useRef(null)
  const noActivityTimeoutRef = useRef(null)
  const noActivityClearRef = useRef(null)
  const entryIdRef = useRef(0)

  // Own local PerformanceObserver — starts fresh on mount
  useEffect(() => {
    if (!open) {
      setEntries([])
      setTestSent(false)
      setNetworkActive(false)
      setNoActivityDetected(false)
      clearTimeout(noActivityTimeoutRef.current)
      clearTimeout(noActivityClearRef.current)
      return
    }

    const observer = new PerformanceObserver((list) => {
      const newEntries = list.getEntries()
        .filter((e) => !e.name.includes('favicon.svg'))
        .map((e) => {
          entryIdRef.current += 1
          return {
            id: entryIdRef.current,
            url: e.name,
            timestamp: new Date().toLocaleTimeString(),
            duration: Math.round(e.duration),
          }
        })
      if (newEntries.length > 0) {
        setNetworkActive(true)
        setEntries((prev) => [...prev, ...newEntries])
        clearTimeout(timeoutRef.current)
        timeoutRef.current = setTimeout(() => setNetworkActive(false), 800)
      }
    })
    observer.observe({ type: 'resource', buffered: false })
    return () => {
      observer.disconnect()
      clearTimeout(timeoutRef.current)
    }
  }, [open])

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [entries])

  const handleTestRequest = useCallback(async () => {
    const lengthBefore = entries.length
    setNoActivityDetected(false)
    clearTimeout(noActivityTimeoutRef.current)
    clearTimeout(noActivityClearRef.current)
    try {
      // Fetch /version.json — the same endpoint the update check uses
      // when the tab returns from a ≥30s-hidden state. Reusing it in the
      // Prove It test means users see the EXACT request pattern they'll
      // later see in normal use, building recognition/trust instead of
      // creating a "what was that?" moment.
      //
      // The PerformanceObserver above catches the fetch automatically
      // and appends the entry to the log, so we DON'T manually push
      // here — doing so would produce two rows per click (one from the
      // observer, one manual). The old favicon path manually added
      // because the observer was filtering favicon.svg out; version.json
      // isn't filtered, so the observer is the single source of truth.
      await fetch(`/version.json?t=${Date.now()}`, { cache: 'no-store' })
    } catch {
      // Offline — no entry added, which is correct
    }
    setTestSent(true)
    setTimeout(() => setTestSent(false), 500)
    noActivityTimeoutRef.current = setTimeout(() => {
      setEntries((current) => {
        if (current.length === lengthBefore) {
          setNoActivityDetected(true)
          noActivityClearRef.current = setTimeout(() => setNoActivityDetected(false), 3000)
        }
        return current
      })
    }, 800)
  }, [entries.length])

  // Stagger panels
  const [visiblePanels, setVisiblePanels] = useState(0)
  useEffect(() => {
    if (!open) {
      setVisiblePanels(0)
      return
    }
    let count = 0
    const interval = setInterval(() => {
      count++
      setVisiblePanels(count)
      if (count >= 4) clearInterval(interval)
    }, 250)
    return () => clearInterval(interval)
  }, [open])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{t('security.badge.headline')}</DialogTitle>
        </DialogHeader>

        {/* 4-panel grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {PANELS.map((panel, i) => {
            const Icon = panel.icon
            const visible = i < visiblePanels
            const isDropCard = i === 1

            const handleDropCardClick = () => {
              onOpenChange(false)
              navigate('/')
            }

            return (
              <div
                key={panel.labelKey}
                role={isDropCard ? 'button' : undefined}
                tabIndex={isDropCard ? 0 : undefined}
                onClick={isDropCard ? handleDropCardClick : undefined}
                onKeyDown={isDropCard ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleDropCardClick() } } : undefined}
                className={`flex items-start gap-3 rounded-lg border p-3 transition-all duration-300 ${
                  isDropCard
                    ? 'cursor-pointer border-blue-300 dark:border-blue-700 bg-blue-50/50 dark:bg-blue-950/30 hover:border-blue-400 dark:hover:border-blue-500 hover:shadow-md hover:shadow-blue-500/10 hover:scale-[1.02] active:scale-[0.98]'
                    : ''
                }`}
                style={{
                  opacity: visible ? 1 : 0,
                  transform: visible ? 'translateY(0) scale(1)' : 'translateY(8px) scale(0.95)',
                  transitionTimingFunction: 'var(--ease-bounce)',
                }}
              >
                <Icon className={`w-5 h-5 shrink-0 mt-0.5 ${panel.colorClass}`} />
                <div>
                  <p className="text-sm font-semibold">{t(panel.labelKey)}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">{t(panel.textKey)}</p>
                  {isDropCard && (
                    <p className="text-xs font-medium text-blue-600 dark:text-blue-400 mt-1.5">
                      {t('security.prove.tryNow')}
                    </p>
                  )}
                </div>
              </div>
            )
          })}
        </div>

        {/* Divider */}
        <div className="border-t" />

        {/* Interactive proof section */}
        <div className="space-y-3">
          <div>
            <p className="text-sm font-semibold flex items-center gap-2">
              {t('security.prove.testHeading')}
              <LogoIcon className="w-5 h-5" />
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">{t('security.prove.testDescription')}</p>
          </div>

          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={handleTestRequest}
              className="relative overflow-hidden test-shimmer min-w-[200px]"
            >
              {testSent ? <Check className="h-4 w-4" /> : t('security.prove.testButton')}
            </Button>

            {/* Network indicator dot */}
            <div className="flex items-center gap-1.5">
              <span className={`w-2 h-2 rounded-full transition-colors duration-75 ${networkActive ? 'bg-red-500' : 'bg-green-500'}`} />
              <span className={`text-xs transition-colors duration-75 ${networkActive ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400'}`}>
                {networkActive ? t('security.results.networkActive') : t('security.results.networkIdle')}
              </span>
            </div>
          </div>

          <p
            className="text-xs text-muted-foreground transition-opacity duration-300"
            style={{ opacity: noActivityDetected ? 1 : 0, height: noActivityDetected ? 'auto' : 0, overflow: 'hidden' }}
          >
            {t('security.prove.noActivity')}
          </p>

          {/* Live activity log */}
          <div
            ref={logRef}
            className="bg-gray-950 dark:bg-gray-900 rounded-lg p-3 max-h-[150px] overflow-y-auto min-h-[60px]"
          >
            {entries.length === 0 ? (
              <p className="text-xs text-gray-600 font-mono">{t('security.prove.logEmpty')}</p>
            ) : (
              <div className="space-y-1">
                {entries.map((entry) => (
                  <LogEntry key={entry.id} entry={entry} isNew />
                ))}
              </div>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
