// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
import { useState, useEffect, useRef, useCallback } from 'react';

export function useNetworkMonitor() {
  const [active, setActive] = useState(false);
  const [entries, setEntries] = useState([]);
  const timeoutRef = useRef(null);

  useEffect(() => {
    const observer = new PerformanceObserver((list) => {
      const newEntries = list.getEntries().map((e) => ({
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
