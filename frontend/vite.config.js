// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025 Christopher Chen
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'
import { execSync } from 'child_process'
import { statSync } from 'fs'

// Compute build hash. In production (CI builds, deploys), use git SHA
// for stable cache keys tied to commits. In dev, use the wheel file's
// mtime so that rebuilding the wheel locally (without committing)
// produces a new cache-bust value and Pyodide's micropip cache actually
// re-fetches. Falls back to 'dev' if git/stat unavailable.
const buildHash = (() => {
  if (process.env.NODE_ENV === 'production') {
    try {
      return execSync('git rev-parse --short HEAD', { encoding: 'utf-8' }).trim()
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
