// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025 Christopher Chen

// TODO: Browser compatibility verification before deployment (Phase 5)
// Test PatentLint end-to-end (Pyodide load + analysis + PDF export) on:
// - [ ] Chrome (latest, macOS)
// - [ ] Chrome (latest, Windows)
// - [ ] Firefox (latest, macOS)
// - [ ] Firefox (latest, Windows)
// - [ ] Safari (latest, macOS)
// - [ ] Edge (latest, Windows)
// - [ ] Safari (latest, iOS / iPadOS)
// - [ ] Chrome (latest, Android)
// If any browser fails, update the "any device with a browser" claim accordingly.

import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Shield, Check, ChevronDown } from 'lucide-react'
import { useInView } from '../hooks/useInView'
import PageCTA from '../components/PageCTA'

/* ------------------------------------------------------------------ */
/*  Section 1 — Hero                                                   */
/* ------------------------------------------------------------------ */

function HeroSection({ onShowProveIt }) {
  const { t } = useTranslation()
  const [ref, isInView] = useInView()

  return (
    <section
      ref={ref}
      className="flex flex-col items-center text-center py-16 gap-6"
      style={{
        opacity: isInView ? 1 : 0,
        transform: isInView ? 'translateY(0)' : 'translateY(24px)',
        transition: 'opacity 0.6s var(--ease-bounce), transform 0.6s var(--ease-bounce)',
      }}
    >
      <Shield
        size={72}
        className="text-green-500"
        style={{
          animation: 'spin-once 1.8s ease-in-out forwards',
        }}
      />

      <h1 className="text-4xl font-bold text-foreground">
        {t('security.page.heroTitle')}
      </h1>

      <p className="text-lg text-muted-foreground max-w-2xl">
        {t('security.page.heroSubtext')}
      </p>

      {/* TODO: Replace placeholder with actual airplane-mode screen recording GIF */}
      <div className="w-full max-w-2xl aspect-video rounded-xl border border-border flex items-center justify-center text-muted-foreground bg-muted/30">
        Airplane mode demo — coming soon
      </div>

      <button
        onClick={() => onShowProveIt?.()}
        className="mt-2 px-6 py-3 rounded-lg bg-green-600 hover:bg-green-700 text-white font-semibold transition-colors"
      >
        {t('security.page.tryIt')}
      </button>
    </section>
  )
}

/* ------------------------------------------------------------------ */
/*  Section 2 — Competitor Comparison Table                            */
/* ------------------------------------------------------------------ */

function ComparisonRow({ index, qKey }) {
  const { t } = useTranslation()
  const [ref, isInView] = useInView()

  return (
    <tr
      ref={ref}
      style={{
        opacity: isInView ? 1 : 0,
        transform: isInView ? 'translateY(0)' : 'translateY(12px)',
        transition: `opacity 0.5s var(--ease-bounce) ${index * 80}ms, transform 0.5s var(--ease-bounce) ${index * 80}ms`,
      }}
    >
      <td className="py-2 px-2 sm:py-3 sm:px-4 text-xs sm:text-sm text-foreground font-medium">
        {t(`security.compare.${qKey}.question`)}
      </td>
      <td className="py-2 px-2 sm:py-3 sm:px-4 text-xs sm:text-sm text-green-500 font-bold">
        <span className="inline-flex items-center gap-1.5">
          <Check
            size={16}
            style={{
              transform: isInView ? 'scale(1)' : 'scale(0)',
              transition: `transform 0.4s var(--ease-bounce) ${index * 80 + 200}ms`,
            }}
          />
          {t(`security.compare.${qKey}.patentlint`)}
        </span>
      </td>
      <td className="hidden sm:table-cell py-3 px-4 text-sm text-muted-foreground">
        {t(`security.compare.${qKey}.addin`)}
      </td>
      <td className="hidden sm:table-cell py-3 px-4 text-sm text-muted-foreground">
        {t(`security.compare.${qKey}.cloud`)}
      </td>
    </tr>
  )
}

function ComparisonSection() {
  const { t } = useTranslation()
  const [ref, isInView] = useInView()

  const rows = ['q1', 'q2', 'q3', 'q4', 'q5', 'q6']

  return (
    <section
      ref={ref}
      className="py-16"
      style={{
        opacity: isInView ? 1 : 0,
        transform: isInView ? 'translateY(0)' : 'translateY(24px)',
        transition: 'opacity 0.6s var(--ease-bounce), transform 0.6s var(--ease-bounce)',
      }}
    >
      <h2 className="text-3xl font-bold text-foreground text-center mb-8">
        {t('security.page.compareTitle')}
      </h2>

      <div className="rounded-lg border border-border">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b border-border bg-muted/30">
              <th className="py-2 px-2 sm:py-3 sm:px-4 text-left text-xs sm:text-sm text-muted-foreground font-semibold">
                {t('security.compare.colQuestion')}
              </th>
              <th className="py-2 px-2 sm:py-3 sm:px-4 text-left text-xs sm:text-sm text-green-500 font-semibold sm:w-48">
                {t('security.compare.colPatentLint')}
              </th>
              <th className="hidden sm:table-cell py-3 px-4 text-left text-sm text-muted-foreground font-semibold w-48">
                {t('security.compare.colAddin')}
              </th>
              <th className="hidden sm:table-cell py-3 px-4 text-left text-sm text-muted-foreground font-semibold w-48">
                {t('security.compare.colCloud')}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map((qKey, i) => (
              <ComparisonRow key={qKey} index={i} qKey={qKey} />
            ))}
          </tbody>
        </table>
      </div>

      <p className="mt-6 text-xs text-muted-foreground text-center">
        {t('security.page.compareDisclaimer')}
      </p>
    </section>
  )
}

/* ------------------------------------------------------------------ */
/*  Section 3 — Technical Details (collapsible)                        */
/* ------------------------------------------------------------------ */

const techSections = [
  'architecture',
  'network',
  'pdf',
  'ai',
  'telemetry',
  'selfHosted',
]

function TechDetailsSection() {
  const { t } = useTranslation()
  const [ref, isInView] = useInView()
  const [open, setOpen] = useState(false)

  return (
    <section
      ref={ref}
      className="py-16"
      style={{
        opacity: isInView ? 1 : 0,
        transform: isInView ? 'translateY(0)' : 'translateY(24px)',
        transition: 'opacity 0.6s var(--ease-bounce), transform 0.6s var(--ease-bounce)',
      }}
    >
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between text-left px-4 py-4 rounded-lg border border-border hover:bg-muted/40 transition-colors"
      >
        <span className="text-xl font-bold text-foreground">
          {t('security.page.techTitle')}
        </span>
        <ChevronDown
          size={20}
          className="text-muted-foreground transition-transform duration-300"
          style={{
            transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
          }}
        />
      </button>

      <div
        style={{
          maxHeight: open ? '2000px' : '0px',
          opacity: open ? 1 : 0,
          overflow: 'hidden',
          transition: 'max-height 0.5s ease-in-out, opacity 0.4s ease-in-out',
        }}
      >
        <div className="pt-6 space-y-6 px-4">
          {techSections.map((key) => (
            <div key={key}>
              <h3 className="text-lg font-semibold text-foreground mb-1">
                {t(`security.tech.${key}Title`)}
              </h3>
              <p className="text-muted-foreground leading-relaxed">
                {t(`security.tech.${key}`)}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function SecurityPage({ onShowProveIt }) {
  useEffect(() => { window.scrollTo(0, 0) }, [])

  return (
    <div className="max-w-4xl mx-auto">
      <style>{`
        @keyframes spin-once {
          from { transform: rotate(0deg); }
          to   { transform: rotate(360deg); }
        }
      `}</style>

      <HeroSection onShowProveIt={onShowProveIt} />
      <ComparisonSection />
      <TechDetailsSection />
      <PageCTA />
    </div>
  )
}
