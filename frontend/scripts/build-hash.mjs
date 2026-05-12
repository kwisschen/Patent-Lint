// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025–2026 Christopher Chen
//
// scripts/build-hash.mjs
// Shared content-based build-hash computation. Used by both
// emit-version.mjs (writes public/version.json) and vite.config.js
// (injects __BUILD_HASH__ at compile time).
//
// Hashes the files that actually go into the production bundle:
//   - frontend/src/**           (JS + JSX + CSS + locale JSONs)
//   - frontend/public/**        (static assets, wheel)
//   - frontend/index.html       (entry point)
//
// Excludes:
//   - node_modules, dist, .vite, __pycache__ (build artifacts)
//   - hidden dotfiles
//   - version.json (self-reference — this script writes it)
//   - .DS_Store
//
// Effect: docs-only commits (README.md, etc.) do not change the hash,
// so users with open tabs don't see a spurious "new version" toast.
// Real source changes (any *.js/*.jsx/*.css/*.json/*.html/wheel) bump
// the hash and correctly trigger the update toast.

import { createHash } from 'crypto'
import { existsSync, readFileSync, readdirSync, statSync } from 'fs'
import { join, relative } from 'path'

const SKIP_DIRS = new Set([
  'node_modules',
  'dist',
  '.vite',
  '__pycache__',
  '.cache',
])
const SKIP_FILES = new Set([
  'version.json',  // self-reference
  '.DS_Store',
])

function walkInputs(dir, frontendDir, inputs) {
  if (!existsSync(dir)) return
  for (const f of readdirSync(dir)) {
    if (SKIP_DIRS.has(f) || f.startsWith('.')) continue
    if (SKIP_FILES.has(f)) continue
    const fp = join(dir, f)
    const st = statSync(fp)
    if (st.isDirectory()) {
      walkInputs(fp, frontendDir, inputs)
    } else {
      inputs.push(relative(frontendDir, fp))
    }
  }
}

export function computeContentBuildHash(frontendDir) {
  const inputs = []
  walkInputs(join(frontendDir, 'src'), frontendDir, inputs)
  walkInputs(join(frontendDir, 'public'), frontendDir, inputs)
  const indexHtml = join(frontendDir, 'index.html')
  if (existsSync(indexHtml)) {
    inputs.push(relative(frontendDir, indexHtml))
  }
  // Deterministic order across operating systems
  inputs.sort()
  const hash = createHash('sha256')
  for (const relPath of inputs) {
    // Mix the path in too, so renames change the hash even if content moves
    hash.update(relPath)
    hash.update('\0')
    hash.update(readFileSync(join(frontendDir, relPath)))
    hash.update('\0')
  }
  return hash.digest('hex').slice(0, 8)
}
