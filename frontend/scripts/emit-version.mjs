#!/usr/bin/env node
// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025–2026 Christopher Chen
//
// scripts/emit-version.mjs
// Generates public/version.json at build time with the current git hash.
// Called by `npm run build` between build:wheel and vite build.
// See docs/cc-prompt-item1-implementation.md for the design.

import { execSync } from 'child_process'
import { writeFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, join } from 'path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const publicDir = join(__dirname, '..', 'public')

function getBuildHash() {
  try {
    return execSync('git rev-parse --short HEAD', { encoding: 'utf-8' }).trim()
  } catch (e) {
    console.warn('[emit-version] git rev-parse failed, using "dev" as fallback')
    return 'dev'
  }
}

const manifest = {
  buildHash: getBuildHash(),
  builtAt: new Date().toISOString(),
  wheelVersion: '1.0.0',
}

const outPath = join(publicDir, 'version.json')
writeFileSync(outPath, JSON.stringify(manifest, null, 2) + '\n')

console.log(`[emit-version] Wrote ${outPath} with buildHash=${manifest.buildHash}`)
