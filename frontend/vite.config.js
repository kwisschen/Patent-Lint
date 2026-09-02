// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025-2026 Christopher Chen
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'
import { statSync, createReadStream } from 'fs'
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

// Expose the repo root to the DEV-only fixture loader used by the viewport
// harness, so it can fetch tests/fixtures/* through Vite's /@fs/ route without
// anything being copied into public/ or bundled.
const REPO_ROOT = path.resolve(__dirname, '..')

// DEV-ONLY fixture route for the viewport harness (/__viewports). Serves
// tests/fixtures/<name> at /__fixtures/<name>.
//
// A middleware rather than Vite's /@fs/ route: /@fs needs an absolute path
// baked into the client, and `define` does NOT substitute into
// `import.meta.env.*` in dev, so that approach silently fetched a bogus path.
// `apply: 'serve'` means it cannot exist in a build at all - there is no guard
// to get wrong. Filename is restricted to a bare name so the route can never
// walk out of the fixtures directory.
function devFixtureRoute() {
  return {
    name: 'patentlint-dev-fixtures',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use('/__fixtures/', (req, res, next) => {
        const name = decodeURIComponent((req.url || '').replace(/^\//, '').split('?')[0])
        if (!/^[\w.-]+$/.test(name) || name.includes('..')) return next()
        const file = path.join(REPO_ROOT, 'tests', 'fixtures', name)
        if (!file.startsWith(path.join(REPO_ROOT, 'tests', 'fixtures'))) return next()
        try {
          statSync(file)
        } catch {
          return next()
        }
        res.setHeader(
          'Content-Type',
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        )
        createReadStream(file).pipe(res)
      })
    },
  }
}

export default defineConfig({
  plugins: [devFixtureRoute(), react(), tailwindcss()],
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
