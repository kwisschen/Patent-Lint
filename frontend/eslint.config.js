// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025-2026 Christopher Chen
import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{js,jsx}'],
    extends: [
      js.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
      parserOptions: {
        ecmaVersion: 'latest',
        ecmaFeatures: { jsx: true },
        sourceType: 'module',
      },
    },
    rules: {
      'no-unused-vars': ['error', { varsIgnorePattern: '^[A-Z_]' }],
    },
  },
  // Node, not the browser: the Vercel function, the Vite config and the
  // build scripts.
  {
    files: ['api/**/*.js', 'scripts/**/*.{js,mjs}', 'vite.config.js'],
    languageOptions: { globals: globals.node },
  },
  // The Pyodide web worker: worker scope, plus the loader that
  // importScripts() brings in from the CDN.
  {
    files: ['public/pyodideWorker.js'],
    languageOptions: {
      globals: { ...globals.worker, loadPyodide: 'readonly' },
    },
  },
])
