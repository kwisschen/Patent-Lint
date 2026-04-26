// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
import { useTranslation } from 'react-i18next'
import { CHECKS_RAW } from '../generated/stats'

const SECTION_WEIGHTS = [
  { id: 'specification', weight: 20 },
  { id: 'drawings', weight: 10 },
  { id: 'claims', weight: 45 },
  { id: 'antecedent_spec_support', weight: 15 },
  { id: 'abstract', weight: 10 },
]

const GATE_RULES = [
  { fix: 0, letter: 'A' },
  { fix: 1, letter: 'A-' },
  { fix: 2, letter: 'B+' },
  { fix: 3, letter: 'B-' },
  { fix: 4, letter: 'C+' },
  { fix: 5, letter: 'C-' },
  { fix: 6, letter: 'D+' },
  { fix: 7, letter: 'F' },
]

function Section({ title, children }) {
  return (
    <section className="space-y-3">
      <h2 className="text-2xl font-semibold text-foreground border-b pb-2">{title}</h2>
      <div className="text-muted-foreground space-y-3 text-sm leading-relaxed">{children}</div>
    </section>
  )
}

export default function RubricPage() {
  const { t } = useTranslation()
  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-8 space-y-12">
      {/* Hero */}
      <header className="space-y-3 text-center">
        <h1 className="text-4xl font-bold text-foreground">{t('rubric.page.title')}</h1>
        <p className="text-lg text-muted-foreground">{t('rubric.page.subtitle')}</p>
      </header>

      {/* Section weights */}
      <Section title={t('rubric.page.weightsTitle')}>
        <p>{t('rubric.page.weightsIntro')}</p>
        <div className="rounded-lg border bg-card overflow-hidden">
          <table className="w-full text-sm">
            <tbody>
              {SECTION_WEIGHTS.map((row) => (
                <tr key={row.id} className="border-b last:border-0">
                  <td className="px-4 py-2 font-medium">{t(`rubric.section.${row.id}`)}</td>
                  <td className="px-4 py-2 text-right text-foreground font-semibold">
                    {row.weight}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {/* Gate logic */}
      <Section title={t('rubric.page.gateTitle')}>
        <p>{t('rubric.page.gateIntro')}</p>
        <div className="rounded-lg border bg-card overflow-hidden">
          <table className="w-full text-sm">
            <tbody>
              {GATE_RULES.map((row) => (
                <tr key={row.fix} className="border-b last:border-0">
                  <td className="px-4 py-2 font-mono">
                    {t('rubric.page.gateRule', { count: row.fix, letter: row.letter })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {/* Conditional sections */}
      <Section title={t('rubric.page.conditionalTitle')}>
        <p>{t('rubric.page.conditionalIntro')}</p>
      </Section>

      {/* Completeness */}
      <Section title={t('rubric.page.completenessTitle')}>
        <p>{t('rubric.page.completenessIntro')}</p>
      </Section>

      {/* Trust */}
      <Section title={t('rubric.page.trustTitle')}>
        <p>{t('rubric.page.trustIntro')}</p>
      </Section>

      {/* Report errors */}
      <Section title={t('rubric.page.reportTitle')}>
        <p>{t('rubric.page.reportIntro')}</p>
      </Section>

      {/* Disclaimer */}
      <Section title={t('rubric.page.disclaimerTitle')}>
        <p>{t('rubric.page.disclaimerIntro')}</p>
      </Section>

      {/* Version footer */}
      <footer className="text-center text-xs text-muted-foreground pt-4 border-t">
        {t('rubric.version', { version: '1.0', count: CHECKS_RAW })}
      </footer>
    </div>
  )
}
