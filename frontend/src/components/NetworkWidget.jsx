// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
import { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { ChevronUp, ChevronDown } from 'lucide-react'
import { subscribeOutgoing, getOutgoingHistory } from '../lib/outgoingRequests'

// Persistent bottom-right widget surfacing outgoing-data network
// calls (POST/PUT/etc.) only — never GET requests for asset loads,
// version checks, or internal SPA navigation. The only thing that
// can ever increment the counter is a network call that PatentLint
// itself emits via outgoingRequests.emitOutgoing — currently only
// /api/report when the user clicks "Send anonymously" on a Report
// modal. That's the trust property: surfaced network activity is
// always activity the user themselves chose to initiate.
//
// Mounted only after pyodide.ready === true so initial-load fetches
// (Pyodide CDN, fonts, app bundle) happen before the subscriber
// exists. Different scope from ProveItModal's PerformanceObserver,
// which surfaces every request including GETs as a comprehensive
// observer demonstration; the widget here is the continuous trust
// signal during normal use. Labels disambiguate: widget says
// "Outgoing data" / "對外傳輸" etc., modal says "Live activity log"
// / 即時網路活動.

export default function NetworkWidget({ pyodideReady }) {
  const { t } = useTranslation()
  const [count, setCount] = useState(0)
  const [flashing, setFlashing] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [events, setEvents] = useState([])
  const flashTimerRef = useRef(null)

  useEffect(() => {
    if (!pyodideReady) return
    const initial = getOutgoingHistory()
    setEvents(initial)
    setCount(initial.length)
    const unsubscribe = subscribeOutgoing((event) => {
      setEvents((prev) => [...prev, event])
      setCount((c) => c + 1)
      setFlashing(true)
      clearTimeout(flashTimerRef.current)
      flashTimerRef.current = setTimeout(() => setFlashing(false), 200)
    })
    return () => {
      unsubscribe()
      clearTimeout(flashTimerRef.current)
    }
  }, [pyodideReady])

  if (!pyodideReady) return null

  return (
    <div className="fixed bottom-4 right-4 z-30 frost-card rounded-lg shadow-md text-xs select-none">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 px-3 py-2 hover:bg-foreground/5 transition-colors w-full"
        aria-label={expanded ? t('widget.collapse') : t('widget.expand')}
        aria-expanded={expanded}
      >
        <span
          className={`w-2 h-2 rounded-full transition-colors duration-150 ${
            flashing ? 'bg-red-500' : 'bg-green-500'
          }`}
        />
        <span className="font-mono">{t('widget.outgoing', { count })}</span>
        {expanded ? (
          <ChevronDown className="w-3 h-3 opacity-60" />
        ) : (
          <ChevronUp className="w-3 h-3 opacity-60" />
        )}
      </button>
      {expanded && (
        <div className="border-t border-border/40 px-3 py-2 max-h-32 overflow-y-auto">
          {events.length === 0 ? (
            <p className="text-muted-foreground">{t('widget.empty')}</p>
          ) : (
            <ul className="space-y-1">
              {events.map((event, i) => (
                <li key={i} className="font-mono text-[10px]">
                  <span className="text-muted-foreground mr-2">
                    {new Date(event.timestamp).toLocaleTimeString()}
                  </span>
                  {event.endpoint}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
