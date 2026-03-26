// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025 Christopher Chen
import { useState, useEffect } from 'react';

export function useCountUp(target, duration = 800, shouldStart = false) {
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (!shouldStart) return;
    let start = null;
    const step = (timestamp) => {
      if (!start) start = timestamp;
      const progress = Math.min((timestamp - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setCount(Math.round(eased * target));
      if (progress < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }, [target, duration, shouldStart]);

  return count;
}
