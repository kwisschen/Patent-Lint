// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
/* global __BUILD_HASH__ */
import { useState, useEffect, useRef, useCallback } from 'react';

// Between each real stage signal from the worker (15 / 40 / 65 / 85 / 100)
// the bar sits at the same percent for as long as the underlying work
// takes — loadPyodide in particular is a ~6MB WASM fetch + CPython init
// that can take 3-15s on a cold cache. A stuck bar reads as broken.
// Solution: between stages, creep smoothly toward the next stage's
// floor minus a small gap, using an ease-out curve sized to the typical
// duration of each phase. Real stage signal from the worker overwrites
// the creep the instant it arrives.
const CREEP_TARGETS = {
    15: { to: 38, durationMs: 10000 }, // runtime: ~6MB WASM + CPython init
    40: { to: 63, durationMs: 5000 },  // wasm packages: micropip/lxml/pydantic
    65: { to: 83, durationMs: 3000 },  // pure-python: docx, snowballstemmer
    85: { to: 98, durationMs: 1000 },  // patentlint wheel (tiny, fast)
};

export function usePyodide() {
    const [ready, setReady] = useState(false);
    const [loading, setLoading] = useState(true);
    const [progress, setProgress] = useState({ percent: 0, message: '' });
    const [error, setError] = useState(null);
    const workerRef = useRef(null);
    const creepRef = useRef(null);

    useEffect(() => {
        // Cache-bust the worker URL too (not just the wheel) so users on a
        // cached old worker get the new behavior — includes the creep
        // logic itself once it ships entirely via the worker, but also
        // any future worker-side fixes.
        const worker = new Worker(`/pyodideWorker.js?b=${__BUILD_HASH__}`);
        workerRef.current = worker;
        worker.postMessage({
          type: 'init',
          payload: {
            wheelUrl: `/patentlint-1.0.0-py3-none-any.whl?b=${__BUILD_HASH__}`,
          },
        });

        const stopCreep = () => {
            if (creepRef.current) {
                clearInterval(creepRef.current);
                creepRef.current = null;
            }
        };

        const startCreep = (from, to, durationMs) => {
            stopCreep();
            const start = Date.now();
            creepRef.current = setInterval(() => {
                const elapsed = Date.now() - start;
                const t = Math.min(elapsed / durationMs, 1);
                // Ease-out quadratic: fast start, gentle asymptote. Bar
                // appears responsive but never overshoots the next real
                // stage marker.
                const eased = 1 - Math.pow(1 - t, 2);
                const percent = from + (to - from) * eased;
                setProgress((p) => ({ ...p, percent }));
                if (t >= 1) stopCreep();
            }, 100);
        };

        worker.onmessage = (e) => {
            if (e.data.type === 'progress') {
                stopCreep();
                setProgress({ percent: e.data.percent, message: e.data.message });
                const target = CREEP_TARGETS[e.data.percent];
                if (target) startCreep(e.data.percent, target.to, target.durationMs);
            }
            if (e.data.type === 'ready') {
                stopCreep();
                setReady(true);
                setLoading(false);
            }
            if (e.data.type === 'error') {
                stopCreep();
                setError(e.data.message);
                setLoading(false);
            }
        };
        worker.onerror = (e) => {
            stopCreep();
            setError(e.message || 'Failed to load analysis engine');
            setLoading(false);
        };
        return () => {
            stopCreep();
            worker.terminate();
        };
    }, []);

    const analyze = useCallback((file, jurisdiction) => {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => {
                const handler = (e) => {
                    if (e.data.type === 'result') {
                        workerRef.current.removeEventListener('message', handler);
                        resolve(e.data.payload);
                    }
                    if (e.data.type === 'error') {
                        workerRef.current.removeEventListener('message', handler);
                        reject(new Error(e.data.message));
                    }
                };
                workerRef.current.addEventListener('message', handler);
                workerRef.current.postMessage(
                    { type: 'analyze', payload: reader.result, filename: file.name, jurisdiction: jurisdiction || 'US' },
                    [reader.result]  // Transfer ArrayBuffer (zero-copy)
                );
            };
            reader.readAsArrayBuffer(file);
        });
    }, []);

    return { ready, loading, progress, error, analyze };
}
