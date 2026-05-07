// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
import { useState, useEffect, useRef, useCallback } from 'react';

export function useNetworkMonitor() {
  const [active, setActive] = useState(false);
  const [entries, setEntries] = useState([]);
  const timeoutRef = useRef(null);

  useEffect(() => {
    const observer = new PerformanceObserver((list) => {
      const newEntries = list.getEntries()
        // Drop non-HTTP(S) entries: file://, blob:, data:. Dragging a
        // .docx into the browser causes macOS / the browser to load a
        // drag-preview thumbnail off disk via file:// (often a recent
        // screencaptureui screenshot in /var/folders/.../TemporaryItems/).
        // PerformanceObserver surfaces it as a resource entry, but it's
        // a local disk read — NOT network egress. Without this filter,
        // the trust dot flashes red and the indicator labels match what
        // a user sees in DevTools' Network tab (a file:// off their
        // own machine), reading as "PatentLint just touched my files."
        .filter((e) => /^https?:/i.test(e.name))
        // Drop failed fetches (offline, blocked). PerformanceResourceTiming
        // entries fire even when the browser only ATTEMPTED the request.
        // Failed entries have responseStart === 0; only count entries
        // where a response actually arrived.
        .filter((e) => e.responseStart > 0)
        .map((e) => ({
          url: e.name,
          timestamp: new Date().toLocaleTimeString(),
          duration: Math.round(e.duration),
        }));
      if (newEntries.length > 0) {
        setActive(true);
        setEntries((prev) => [...prev, ...newEntries]);
        clearTimeout(timeoutRef.current);
        timeoutRef.current = setTimeout(() => setActive(false), 500);
      }
    });
    observer.observe({ type: 'resource', buffered: false });
    return () => {
      observer.disconnect();
      clearTimeout(timeoutRef.current);
    };
  }, []);

  const clearEntries = useCallback(() => setEntries([]), []);

  return { active, entries, clearEntries };
}
