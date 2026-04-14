// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025 Christopher Chen
/* global __BUILD_HASH__ */
import { useState, useEffect, useRef, useCallback } from 'react';

export function usePyodide() {
    const [ready, setReady] = useState(false);
    const [loading, setLoading] = useState(true);
    const [progress, setProgress] = useState({ percent: 0, message: '' });
    const [error, setError] = useState(null);
    const workerRef = useRef(null);

    useEffect(() => {
        const worker = new Worker('/pyodideWorker.js');
        workerRef.current = worker;
        worker.postMessage({
          type: 'init',
          payload: {
            wheelUrl: `/patentlint-1.0.0-py3-none-any.whl?b=${__BUILD_HASH__}`,
          },
        });
        worker.onmessage = (e) => {
            if (e.data.type === 'progress') {
                setProgress({ percent: e.data.percent, message: e.data.message });
            }
            if (e.data.type === 'ready') {
                setReady(true);
                setLoading(false);
            }
            if (e.data.type === 'error') {
                setError(e.data.message);
                setLoading(false);
            }
        };
        worker.onerror = (e) => {
            setError(e.message || 'Failed to load analysis engine');
            setLoading(false);
        };
        return () => worker.terminate();
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
