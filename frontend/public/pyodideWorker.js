// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
let pyodide = null;

self.onmessage = async (event) => {
    const { type, payload } = event.data;

    if (type === 'init') {
        try {
            // Accept wheelUrl from main thread (for cache-busting with ?v=hash).
            // Fall back to hardcoded URL for backwards compatibility.
            const wheelUrl = payload?.wheelUrl || '/patentlint-1.0.0-py3-none-any.whl';

            // Load Pyodide script from CDN
            importScripts('https://cdn.jsdelivr.net/pyodide/v0.27.7/full/pyodide.js');

            // Stage 1: Load CPython WASM runtime
            self.postMessage({ type: 'progress', stage: 'runtime', percent: 15, message: 'Loading Python runtime...' });
            pyodide = await loadPyodide({
                indexURL: 'https://cdn.jsdelivr.net/pyodide/v0.27.7/full/'
            });

            // Stage 2: Load pre-compiled WASM packages (micropip, lxml, pydantic, pydantic-core)
            self.postMessage({ type: 'progress', stage: 'wasm_packages', percent: 40, message: 'Loading document parser...' });
            await pyodide.loadPackage(['micropip', 'lxml', 'pydantic']);

            // Stage 3: Install pure-Python packages via micropip
            self.postMessage({ type: 'progress', stage: 'packages', percent: 65, message: 'Loading analysis engine...' });
            await pyodide.runPythonAsync(`
                import micropip
                await micropip.install(['python-docx', 'snowballstemmer'])
            `);

            // Stage 4: Load patentlint wheel (built and hosted as static asset)
            self.postMessage({ type: 'progress', stage: 'patentlint', percent: 85, message: 'Loading PatentLint...' });
            pyodide.globals.set('patentlint_wheel_url', wheelUrl);
            await pyodide.runPythonAsync(`
                import micropip
                await micropip.install(patentlint_wheel_url)
            `);

            self.postMessage({ type: 'progress', stage: 'ready', percent: 100, message: 'Ready!' });
            self.postMessage({ type: 'ready' });
        } catch (error) {
            self.postMessage({ type: 'error', message: error.message });
        }
    }

    if (type === 'analyze') {
        try {
            // payload is ArrayBuffer of the .docx file
            const uint8 = new Uint8Array(payload);
            const jurisdiction = event.data.jurisdiction || 'US';
            // Pass bytes to Python
            pyodide.globals.set('docx_bytes', pyodide.toPy(uint8));
            pyodide.globals.set('filename', event.data.filename);
            pyodide.globals.set('jurisdiction_str', jurisdiction);

            const resultJson = await pyodide.runPythonAsync(`
                from patentlint.pipeline import analyze_bytes
                from patentlint.models import Jurisdiction

                j = Jurisdiction(jurisdiction_str)
                result = analyze_bytes(bytes(docx_bytes), filename, jurisdiction=j)
                report_data = result.to_report_data()
                report_data.model_dump_json()
            `);

            self.postMessage({ type: 'result', payload: JSON.parse(resultJson) });
        } catch (error) {
            self.postMessage({ type: 'error', message: error.message });
        }
    }
};
