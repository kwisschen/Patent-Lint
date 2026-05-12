// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025–2026 Christopher Chen
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'
import { statSync } from 'fs'
import { computeContentBuildHash } from './scripts/build-hash.mjs'

// Compute build hash. In production (CI builds, deploys), use a content-
// based hash of frontend inputs (src/, public/, index.html, wheel) so
// docs-only commits (README, etc.) don't bump the hash and don't trigger
// spurious "new version" toasts for users with open tabs. emit-version.mjs
// uses the same helper, so the JS-baked __BUILD_HASH__ matches the served
// /version.json.
//
// In dev, use the wheel file's mtime so that rebuilding the wheel locally
// (without committing) produces a new cache-bust value and Pyodide's
// micropip cache actually re-fetches. Falls back to 'dev' if anything
// goes wrong.
const buildHash = (() => {
  if (process.env.NODE_ENV === 'production') {
    try {
      return computeContentBuildHash(__dirname)
    } catch (e) {
      return 'dev'
    }
  }
  try {
    const wheelPath = path.resolve(__dirname, 'public/patentlint-1.0.0-py3-none-any.whl')
    return `dev${statSync(wheelPath).mtimeMs}`
  } catch (e) {
    return 'dev'
  }
})()

export default defineConfig({
  plugins: [react(), tailwindcss()],
  define: {
    __BUILD_HASH__: JSON.stringify(buildHash),
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
  },
})
