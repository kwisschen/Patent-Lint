// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025 Christopher Chen
import { useState, useEffect, useRef, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { WifiOff, FileText, CheckCircle, Activity, Check } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'

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
  const [entries, setEntries] = useState([])
  const [testSent, setTestSent] = useState(false)
  const [networkActive, setNetworkActive] = useState(false)
  const logRef = useRef(null)
  const timeoutRef = useRef(null)
  const entryIdRef = useRef(0)

  // Own local PerformanceObserver — starts fresh on mount
  useEffect(() => {
    if (!open) {
      setEntries([])
      setTestSent(false)
      setNetworkActive(false)
      return
    }

    const observer = new PerformanceObserver((list) => {
      const newEntries = list.getEntries().map((e) => {
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
        timeoutRef.current = setTimeout(() => setNetworkActive(false), 500)
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
    try {
      await fetch(`/favicon.ico?t=${Date.now()}`)
    } catch {
      // Expected to fail if offline — that's the point
    }
    setTestSent(true)
    setTimeout(() => setTestSent(false), 500)
  }, [])

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
    }, 150)
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
            return (
              <div
                key={panel.labelKey}
                className="flex items-start gap-3 rounded-lg border p-3 transition-all duration-300"
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
            <p className="text-sm font-semibold">{t('security.prove.testHeading')}</p>
            <p className="text-xs text-muted-foreground mt-0.5">{t('security.prove.testDescription')}</p>
          </div>

          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={handleTestRequest}
              className="relative overflow-hidden test-shimmer"
            >
              {testSent ? <Check className="h-4 w-4" /> : t('security.prove.testButton')}
            </Button>

            {/* Network indicator dot */}
            <div className="flex items-center gap-1.5">
              <span className={`w-2 h-2 rounded-full transition-colors duration-300 ${networkActive ? 'bg-red-500' : 'bg-green-500'}`} />
              <span className={`text-xs transition-colors duration-300 ${networkActive ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400'}`}>
                {networkActive ? t('security.results.networkActive') : t('security.results.networkIdle')}
              </span>
            </div>
          </div>

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
