// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025-2026 Christopher Chen
//
// Test-only config. Deliberately separate from vite.config.js so nothing here
// can reach the production build: the shipped bundle must stay exactly what it
// was before a test runner existed. PatentLint's whole claim is that analysis
// runs in the browser with no upload and no cloud call, so test tooling lives
// in devDependencies, is never imported by src/, and is verified against a
// byte-for-byte diff of dist/ (see docs in the disposition-contract test).
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['src/**/*.test.{js,jsx}'],
  },
})
