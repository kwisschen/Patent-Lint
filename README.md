# PatentLint

[![CI](https://github.com/kwisschen/Patent-Lint/actions/workflows/ci.yml/badge.svg)](https://github.com/kwisschen/Patent-Lint/actions/workflows/ci.yml)
[![Live Demo](https://img.shields.io/badge/demo-patentlint.com-blue)](https://patentlint.com)
[![Tests](https://img.shields.io/badge/tests-2497-brightgreen)](#)
[![License: PolyForm-Strict-1.0.0](https://img.shields.io/badge/license-PolyForm--Strict--1.0.0-orange)](LICENSE)

**No account. No install. No upload.**

PatentLint checks U.S., Chinese, Taiwanese, and European (EPC) patent application drafts against USPTO, CNIPA, TIPO, and EPO drafting rules — entirely in your browser. Your file never leaves your device.

**[Try it →](https://patentlint.com)**

## Status

PatentLint is currently maintained as an open-source portfolio project by Christopher Chen during an AI-engineering job search. The hosted demo at [patentlint.com](https://patentlint.com) remains free for individual practitioners and for organizations evaluating the tool. The source is published under [PolyForm-Strict-1.0.0](LICENSE) — commercial deployment under § 4 of the [Terms](https://patentlint.com/terms) remains available, but commercial customers are not actively being onboarded during this period. Inquiries welcome at the contact link below.

![PatentLint analysis results](https://patentlint.com/screenshot-hero.png)

### Zero-Trust Proof

> Your documents never leave your browser — verifiable in airplane mode.

[Watch the demo →](https://patentlint.com/security)

---

## How It Works

1. **Drop** a patent draft into the browser (.docx for US/TW/EPC, .docx/.xml/.zip for CN)
2. **Analyze** — 144 checks run instantly via WebAssembly (no server, no upload)
3. **Report** — download a PDF or copy a summary to clipboard

---

## Security

PatentLint's analysis engine is compiled to WebAssembly and runs entirely in your browser tab. No server receives your file. No network requests are made during analysis.

**You don't have to take our word for it.** Turn on airplane mode after your first visit, drop a file, and watch it work. [See the proof →](https://patentlint.com/security)

---

## What It Checks

144 automated checks across four jurisdictions, each classified as **PASS**, **REVIEW**, or **FIX**.

> **EPC support is v1 beta.** The full 30-check EPC catalog runs end-to-end via CLI and REST API. The frontend jurisdiction picker integration and real-corpus FP tuning are next on the roadmap.

### U.S. Patent Applications (42 checks)

| Section | Checks | Reference |
|---------|--------|-----------|
| **Specification** | Required sections, paragraph numbering, restrictive wording, sequence listing, prior art citations, figure cross-reference consistency | MPEP § 608.01(a)(m)(p), § 2173.01 |
| **Drawings** | Figure count, sequential numbering, single-figure format, prior art labeling, reference numeral consistency (spec ↔ drawings) | MPEP § 608.02 |
| **Claims** | Numbering, dependencies, periods, punctuation, indefinite terms, transitional phrases, means-plus-function (§ 112(f)), antecedent basis (§ 112(b)), preamble consistency (§ 112(d)), specification support (§ 112(a)), claim similarity, special formats (Jepson / CRM / Markush / omnibus) | 35 U.S.C. § 101, § 112; MPEP § 2117–2173 |
| **Abstract** | Word count (50–150), single paragraph, legal phraseology, implied phrases, self-praising language | MPEP § 608.01(b) |

### Chinese Patent Applications (33 checks)

| Section | Checks | Reference |
|---------|--------|-----------|
| **Specification** | Required sections, section ordering, paragraph numbering/ending, figure reference consistency, patent type terminology, title, claim references in spec | 专利法实施细则 §17, 审查指南 |
| **Claims** | Sequential numbering, dependency format, self/forward dependencies, single sentence, reference numeral parentheses, subject consistency, transition phrases, Taiwan terminology, spec/drawing references, chained multi-dependencies, dependent ordering, connection relationships, antecedent basis (BFS walker) | 专利法实施细则 §22, 审查指南 |
| **Abstract** | Character count (≤300), title match, commercial language | 专利法实施细则 §23 |
| **Drawings** | Figures sequential, figure count | 审查指南 |

### Taiwanese Patent Applications (39 checks)

| Section | Checks | Reference |
|---------|--------|-----------|
| **Specification** | Required sections, section ordering, paragraph numbering (【NNNN】 format), paragraph ending, figure reference consistency, patent type terminology (本發明 vs 本新型), title, spec-claim references, 符號說明 presence + consistency, bracket format (【】) | 專利法施行細則 §17, 專利審查基準 |
| **Claims** | Sequential, dependency format (§18), self / forward / circular dependency, single sentence (§18), reference numeral parens (§19), subject consistency, transition phrase (其特徵在於), CN-term contamination guard, spec/drawing refs, multi-dep on multi-dep, multi-dep alternative form, title-subject match, 符號說明 consistency, **antecedent basis (先行詞) — ancestor-chain walker**, **specification support (說明書支持) — §26 第3項**, connection relationships, 代表圖 vs 符號說明 consistency | 專利法 §26 第3項, 專利法施行細則 §17–§21, 專利審查基準 |
| **Abstract** | Character count (≤250), title match, commercial language, representative drawing (代表圖) designation | 專利法施行細則 §21 |
| **Drawings** | Figures sequential, figure count | 專利法施行細則 §17 |

### European (EPC) Patent Applications — English drafts (30 checks, v1 beta)

| Section | Checks | Reference |
|---------|--------|-----------|
| **Specification** | Required sections, section ordering (Rule 42(1) sub-section order), paragraph numbering (advisory), paragraph ending, title required, figure-reference consistency, reference-numeral consistency, claim-reference-in-spec | Art. 78 + Rule 41 + Rule 42 + Rule 43(7) + Rule 46(2)(h) EPC; Guidelines F-II + F-IV § 4.3 |
| **Drawings** | Figures sequential, single-figure label, prior-art labeling, figure count | Rule 46(2)(a) + Rule 46(2)(h) EPC; Guidelines F-V § 1.2 |
| **Claims** | Sequential numbering, dependency format, self/forward dependency, single sentence per claim, reference signs in parens, subject consistency, transitional phrase, claim-spec reference, multi-dep on multi-dep, Markush format, independent-claim count per category, two-part form (advisory), **antecedent basis — Art. 84 walker**, **specification support — Art. 84 walker**, restrictive absolutes, claim punctuation | Art. 84 EPC; Rule 43 EPC; Guidelines F-IV § 3.4, § 4.5, § 4.7, § 4.10, § 4.13, § 4.20 |
| **Abstract** | Word count (50–150), structure (single paragraph, no claim-style phraseology, no merit language) | Rule 47(2) EPC; Guidelines F-II § 2.3 |

EPC English input only at v1 (DE/FR check engines deferred). The English-language jurisdiction-mismatch banner detects EPC vs US tells ("characterised in that", "any preceding claim", Article 84 citations) and routes accordingly.

Supported input: `.docx` for US, TW, and EPC; `.docx`, CNIPA filing XML (`.xml`), and `.zip` archives for CN.

Full inventory: [CHECKS.md](CHECKS.md)

---

## Deployment Tiers

| Tier | Analysis | PDF | Server? | Trust Model |
|------|----------|-----|---------|-------------|
| **Web** (default) | Pyodide/WASM in browser | pdfmake (client-side) | No — static hosting | Zero-trust: airplane mode verifiable |
| **Docker** | Local FastAPI | weasyprint | Yes (your machine) | On-premise |
| **Cloud API** (future) | Hosted FastAPI | weasyprint | Yes (our infra) | Process + discard |

---

## Architecture

```
                         ┌──────────────────────┐
                         │   React Frontend     │
                         │  (Vite + shadcn/ui)  │
                         └─────┬──────────┬─────┘
               Web (default)   │          │   Docker / CLI
          ┌────────────────────┘          └──────────────────┐
          ▼                                                  ▼
┌──────────────────┐                              ┌──────────────────┐
│  Pyodide/WASM    │                              │  FastAPI (app.py) │
│  (in-browser     │                              └────────┬─────────┘
│   analysis)      │                                       │
└────────┬─────────┘                              ┌────────▼─────────┐
         │                                        │  pipeline.py     │
         │         ┌───────────────────────┐      │  analyze_file()  │
         └────────►│  parser/ + analysis/  │◄─────┘  analyze_bytes() │
                   │  (pure Python, zero   │      └──────────────────┘
                   │   framework deps)     │
                   └───────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │   pdfmake    │ │  weasyprint  │ │  Click CLI   │
    │ (web, client)│ │ (Docker/CLI) │ │  (cli.py)    │
    └──────────────┘ └──────────────┘ └──────────────┘
```

```
src/patentlint/
├── models.py        # Pydantic models (Claim, AnalysisResult, ReportData)
├── pipeline.py      # Analysis pipeline (zero web-framework deps)
├── cli.py           # Click CLI (analyze, batch)
├── i18n.py          # Locale bundle loader + i18next-style translator
├── parser/          # Section extraction, claim parsing, .docx/.xml/.zip loading
├── analysis/        # Rule checks (US + CN + TW + EPC) — all pure functions, independently testable
├── report/          # PDF report generation (Jinja2 + weasyprint; locale-aware)
└── api/             # FastAPI REST endpoints

frontend/
├── src/components/  # DropZone, ClaimTree, TriagePanel, Section112Container, …
├── src/lib/         # pdfExport.js (client-side PDF via pdfmake), detailsFormatter.js
├── src/pages/       # SecurityPage, AboutPage, TermsPage, PrivacyPage, CommercialPage, RubricPage
├── src/hooks/       # usePyodide, useNetworkMonitor
└── src/i18n/        # Locale files (en, de, zh-TW, zh-CN, ja, ko) — shared with Python
```

The `parser/` and `analysis/` packages have **zero framework dependencies** — they run identically in Pyodide (browser), FastAPI (Docker), and Click (CLI). The same engine handles US, CN, TW, and EPC jurisdictions; `pipeline.py` routes to the appropriate parser and check modules.

---

## Quick Start

### Web (recommended)

Visit **[patentlint.com](https://patentlint.com)** — nothing to install.

### Local Development

**Prerequisites:** Python 3.12+, Node.js 22+, pango (`brew install pango` on macOS)

```bash
# Backend
pip install -e ".[api,dev]"
pytest -v                    # 2497 tests
uvicorn patentlint.api.app:app --port 8000 --reload

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
# → http://localhost:5173
```

### CLI

```bash
patentlint analyze patent-draft.docx                                          # US (default)
patentlint analyze filing.xml --jurisdiction cn                               # CN filing XML
patentlint analyze tw-draft.docx --jurisdiction tw                            # TW .docx
patentlint analyze epc-draft.docx --jurisdiction epc                          # EPC English .docx (v1 beta)
patentlint analyze patent-draft.docx -o report.json                           # JSON to file
patentlint analyze patent-draft.docx --format pdf -o report.pdf               # PDF report
patentlint analyze tw-draft.docx --format pdf --locale zh-TW -o report.pdf    # Localized PDF
patentlint batch ./patents/ --output ./reports/                               # Batch mode
```

Exit codes: `0` clean, `1` findings, `2` error.

### Docker

```bash
docker build -t patentlint .
docker run -p 8000:8000 patentlint
# → http://localhost:8000 (web UI + API)
```

### REST API

```bash
curl -X POST http://localhost:8000/api/analyze -F "file=@draft.docx"
curl -X POST http://localhost:8000/api/analyze?format=report -F "file=@draft.docx"
curl -X POST http://localhost:8000/api/analyze/report -F "file=@draft.docx" -o report.pdf
curl -X POST "http://localhost:8000/api/analyze/report?locale=zh-TW" -F "file=@draft.docx" -o report.pdf
curl http://localhost:8000/api/health
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Analysis Engine | Python 3.12 (pure functions, zero framework deps) |
| Client-Side Runtime | Pyodide 0.27.7 (CPython → WebAssembly) |
| Backend | FastAPI, Pydantic (Docker/CLI tier) |
| Frontend | React 18, Vite 6, Tailwind CSS v4, shadcn/ui |
| PDF | pdfmake (web) · weasyprint (Docker/CLI) |
| CLI | Click |
| Testing | pytest (2497 tests) |
| CI/CD | GitHub Actions (test, lint, wheel-verify, docker) + Vercel auto-deploy |
| i18n | react-i18next (English, Deutsch, 繁體中文, 简体中文, 日本語, 한국어) — shared locale bundles across frontend + weasyprint PDF |

---

## Languages

PatentLint's UI is available in six languages. Patent-specific terms follow official terminology from each jurisdiction's patent office.

| Language | Patent Office | Terminology Standard |
|----------|--------------|---------------------|
| English | USPTO + EPO | MPEP + EPC / EPO Guidelines |
| Deutsch | EPA / DPMA | EPÜ / PatG |
| 繁體中文 | TIPO (經濟部智慧財產局) | 專利審查基準 |
| 简体中文 | CNIPA (国家知识产权局) | 专利审查指南 |
| 日本語 | JPO (特許庁) | 特許・実用新案審査基準 |
| 한국어 | KIPO (특허청) | 특허·실용신안 심사기준 |

EPC drafts must be in English at v1; DE/FR EPC check engines are deferred. The jurisdiction-mismatch detector recognises EPC-specific tells ("characterised in that", Article citations, "any preceding claim") and routes accordingly.

---

## Disclaimer

This tool does not constitute legal advice. All findings should be reviewed by a qualified patent professional before filing.

## License

PatentLint is source-available under **PolyForm-Strict-1.0.0** — see [LICENSE](LICENSE) for the full terms.

**Permitted uses:**

- Reading and studying the source code
- Evaluating whether to license it ("acceptance testing")
- Personal use (for yourself, not as part of a commercial activity)
- Use by charitable / educational / public-research / public-safety / government organizations (per the license's "Noncommercial Organizations" clause)

**Uses requiring a separate commercial license:**

- Deploying PatentLint internally at a firm, company, or organization (including for client matters)
- Offering PatentLint as a hosted service to third parties
- Redistributing PatentLint (modified or unmodified)
- Making changes or new works based on PatentLint

The patentlint.com hosted service is free for individual evaluation. Commercial deployment or redistribution requires a separate license — [contact Christopher Chen](mailto:kwisschen@gmail.com) to discuss terms. See also the [Terms of Service](https://patentlint.com/terms) for the hosted site and the source-code license.

Copyright © 2025–2026 Christopher Chen. All rights reserved.
