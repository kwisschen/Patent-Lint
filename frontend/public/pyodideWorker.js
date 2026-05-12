// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025–2026 Christopher Chen
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

            // Stage 2: Load pre-compiled WASM packages (micropip + pydantic).
            // lxml is intentionally deferred — it's only needed for CNIPA XML/ZIP
            // uploads (a niche format <5% of users). DOCX inputs (the common case)
            // never need it. When a user uploads an XML/ZIP file, the analyze
            // handler below detects the extension and pulls lxml lazily before
            // calling into the Python pipeline. Saves ~1.7 MB raw / ~700 KB
            // compressed on first load for the typical DOCX user. Trust posture
            // unchanged: this is a static-library fetch from the same Pyodide
            // CDN we already use at boot, not a file-upload path — the user's
            // document never leaves their browser. (Same pattern as the existing
            // Noto Sans CJK font lazy-fetch on first localized-PDF export.)
            self.postMessage({ type: 'progress', stage: 'wasm_packages', percent: 40, message: 'Loading document parser...' });
            await pyodide.loadPackage(['micropip', 'pydantic']);

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
            // payload is ArrayBuffer of the user's file (.docx / .xml / .zip)
            const uint8 = new Uint8Array(payload);
            const jurisdiction = event.data.jurisdiction || 'US';
            const filename = (event.data.filename || '').toLowerCase();

            // Lazy-load lxml only when the file is CNIPA XML or ZIP.
            // Detection: filename extension is the primary signal; we also
            // sniff the first 5 bytes for "<?xml" as a defense for renamed
            // files. DOCX (= ZIP starting with "PK\x03\x04") is excluded from
            // the lxml path even though it's technically a ZIP — CN's XML-in-
            // ZIP wrapper has a different inner layout that the docx_loader
            // doesn't touch. Only Jurisdiction.CN + .xml or .zip extension
            // routes through xml_loader (per pipeline.py CN branch).
            const looksXml = filename.endsWith('.xml')
                || (filename.endsWith('.zip') && jurisdiction === 'CN')
                || (uint8.length >= 5 && new TextDecoder().decode(uint8.slice(0, 5)) === '<?xml');
            if (looksXml) {
                self.postMessage({ type: 'progress', stage: 'lxml', percent: 50, message: 'Loading XML parser...' });
                await pyodide.loadPackage('lxml');
            }

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
