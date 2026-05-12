#!/usr/bin/env node
// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025–2026 Christopher Chen
//
// scripts/emit-version.mjs
// Generates public/version.json at build time with a content-based hash.
// Called by `npm run build` between build:wheel and vite build.
//
// Hash is derived from the actual bundle inputs (src/, public/, index.html)
// rather than git SHA — so README-only / docs-only commits don't trigger
// the update-toast for users with open tabs.

import { writeFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, join } from 'path'
import { computeContentBuildHash } from './build-hash.mjs'

const __dirname = dirname(fileURLToPath(import.meta.url))
const frontendDir = join(__dirname, '..')
const publicDir = join(frontendDir, 'public')

function getBuildHash() {
  try {
    return computeContentBuildHash(frontendDir)
  } catch (e) {
    console.warn('[emit-version] content-hash failed, using "dev" as fallback:', e.message)
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
