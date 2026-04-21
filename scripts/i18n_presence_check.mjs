#!/usr/bin/env node
// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
//
// Phase A — i18n presence check.
//
// Walks every leaf string key in frontend/src/i18n/locales/en.json and, for
// each of zh-TW / zh-CN / ja / ko, reports three drift classes:
//
//   missing  — key present in EN but absent in the target locale.
//   empty    — key present but value is "" (or whitespace only).
//   identical— value character-for-character identical to EN. Often means
//              untranslated; sometimes legitimate (brand names, MPEP §
//              anchors, Latin acronyms) — surface for review, don't
//              auto-rewrite.
//
// Exits non-zero on any drift. Reporter only — does not mutate any locale
// file. Used to gate the 94-check locale audit (Phase C).
//
// Usage:
//   node scripts/i18n_presence_check.mjs

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const REPO_ROOT = resolve(__dirname, "..");
const LOCALES_DIR = resolve(REPO_ROOT, "frontend/src/i18n/locales");

const BASE = "en";
const TARGETS = ["zh-TW", "zh-CN", "ja", "ko"];

// Keys where EN-identical values are legitimate (brand names, legal markers
// that must be preserved verbatim in patent drafts, English MPEP/section
// anchors) per ADR-085. Each entry is a JSONPath-like string matching a leaf
// path. Prefixes are matched with "startsWith" semantics so a subtree can be
// exempted at once.
const EN_IDENTICAL_ALLOWLIST = [
    // Brand / header
    "header.title",
    // ADR-085: English-preserved USPTO artifacts (wherein, FIG., §, non-transitory, Jepson, Markush).
    // Section / legal anchors that embed English abbreviations.
    "jurisdiction.us",
    "jurisdiction.cn",
    "jurisdiction.tw",
];

function loadLocale(name) {
    const path = resolve(LOCALES_DIR, `${name}.json`);
    return JSON.parse(readFileSync(path, "utf8"));
}

function walk(obj, prefix, out) {
    if (obj === null || obj === undefined) return;
    if (typeof obj === "string") {
        out.set(prefix, obj);
        return;
    }
    if (Array.isArray(obj)) {
        // Arrays of strings flatten to prefix.0, prefix.1, ...
        obj.forEach((v, i) => walk(v, `${prefix}.${i}`, out));
        return;
    }
    if (typeof obj === "object") {
        for (const [k, v] of Object.entries(obj)) {
            const next = prefix === "" ? k : `${prefix}.${k}`;
            walk(v, next, out);
        }
    }
}

function flatLeaves(locale) {
    const map = new Map();
    walk(locale, "", map);
    return map;
}

function isAllowlisted(path) {
    return EN_IDENTICAL_ALLOWLIST.some((pfx) => path === pfx || path.startsWith(`${pfx}.`));
}

function classify(target, enLeaves) {
    const out = { missing: [], empty: [], identical: [] };
    const tLeaves = flatLeaves(target);
    for (const [path, enValue] of enLeaves) {
        if (!tLeaves.has(path)) {
            out.missing.push(path);
            continue;
        }
        const tValue = tLeaves.get(path);
        if (typeof tValue !== "string" || tValue.trim() === "") {
            out.empty.push(path);
            continue;
        }
        if (tValue === enValue && !isAllowlisted(path)) {
            out.identical.push(path);
        }
    }
    return out;
}

function printReport(locale, report, enLeafCount) {
    const total = report.missing.length + report.empty.length + report.identical.length;
    const clean = total === 0;
    const line = `── ${locale} ` + "─".repeat(Math.max(2, 40 - locale.length));
    console.log(line);
    console.log(
        `  keys checked: ${enLeafCount}   ` +
            `missing: ${report.missing.length}   ` +
            `empty: ${report.empty.length}   ` +
            `identical-to-EN: ${report.identical.length}   ` +
            (clean ? "(clean)" : "(drift)"),
    );
    for (const [label, items] of [
        ["missing", report.missing],
        ["empty", report.empty],
        ["identical-to-EN", report.identical],
    ]) {
        if (items.length === 0) continue;
        console.log(`  ${label}:`);
        const SHOW = 12;
        for (const p of items.slice(0, SHOW)) console.log(`    ${p}`);
        if (items.length > SHOW) console.log(`    …and ${items.length - SHOW} more`);
    }
}

function main() {
    const en = loadLocale(BASE);
    const enLeaves = flatLeaves(en);
    console.log(`i18n presence check — base: ${BASE} (${enLeaves.size} leaf keys)`);
    console.log();

    let anyDrift = false;
    for (const locale of TARGETS) {
        const target = loadLocale(locale);
        const report = classify(target, enLeaves);
        const drift =
            report.missing.length > 0 ||
            report.empty.length > 0 ||
            report.identical.length > 0;
        if (drift) anyDrift = true;
        printReport(locale, report, enLeaves.size);
    }

    console.log();
    if (anyDrift) {
        console.log("result: drift detected");
        process.exit(1);
    }
    console.log("result: clean");
    process.exit(0);
}

main();
