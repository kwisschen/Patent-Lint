// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2025 Christopher Chen
import { useTranslation } from 'react-i18next'
import { CheckCircle } from 'lucide-react'
import AntecedentBasisCard from './AntecedentBasisCard'
import SpecSupportCard from './SpecSupportCard'
import { getJurisdictionConfig } from '../lib/jurisdictionConfig'

function PassConfirmation({ messageKey }) {
  const { t, i18n } = useTranslation()
  const msg = i18n.exists(messageKey) ? t(messageKey) : messageKey

  return (
    <div className="flex items-center gap-2 px-3 py-2">
      <CheckCircle className="h-4 w-4 shrink-0" style={{ color: 'var(--pass-border)' }} />
      <span className="text-sm" style={{ color: 'var(--pass-text)' }}>{msg}</span>
    </div>
  )
}

export default function Section112Container({
  hasAntecedentIssues,
  hasUnsupportedTerms,
  antecedentBasisIssues,
  unsupportedTerms,
  claimTrees,
  jurisdiction,
}) {
  const { t } = useTranslation()
  const jConfig = getJurisdictionConfig(jurisdiction)
  const isUS = jurisdiction === 'US'

  return (
    <div className="mt-4 rounded-lg border border-border/50 bg-muted/20 dark:bg-muted/30 p-3 space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
          {t(jConfig.section112TitleKey)}
        </span>
        <div className="flex-1 border-t border-border/50" />
      </div>

      {hasAntecedentIssues ? (
        <AntecedentBasisCard issues={antecedentBasisIssues} claimTrees={claimTrees} />
      ) : (
        <PassConfirmation messageKey={jConfig.section112PassKey} />
      )}

      {isUS && (hasUnsupportedTerms ? (
        <SpecSupportCard unsupportedTerms={unsupportedTerms} />
      ) : (
        <PassConfirmation messageKey="checks.spec_support_pass" />
      ))}
    </div>
  )
}
