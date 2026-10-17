// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025-2026 Christopher Chen
//
// Test-only config. Deliberately separate from vite.config.js so nothing here
// can reach the production build: the shipped bundle must stay exactly what it
// was before a test runner existed. PatentLint's whole claim is that analysis
// runs in the browser with no upload and no cloud call, so test tooling lives
// in devDependencies, is never imported by src/, and is verified against a
// byte-for-byte diff of dist/ (see docs in the disposition-contract test).
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

const here = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [react()],
  // Mirror the `@` alias vite.config.js gives the app. Without it a test that
  // imports a component transitively pulling `@/lib/utils` fails to resolve,
  // which would quietly push tests towards duplicating source constants
  // instead of importing them - the exact drift the tooltip-parity test exists
  // to prevent.
  resolve: {
    alias: { '@': path.resolve(here, './src') },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['src/**/*.test.{js,jsx}'],
  },
})
