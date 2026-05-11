// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025–2026 Christopher Chen
import { useTranslation } from 'react-i18next'
import { CheckCircle } from 'lucide-react'
import AntecedentBasisCard from './AntecedentBasisCard'
import SpecSupportCard from './SpecSupportCard'
import { getJurisdictionConfig } from '../lib/jurisdictionConfig'
import { StatusPill } from './ui/status-pill'
import { FrostCard } from './ui/frost-card'

// Visual parallel to AntecedentBasisCard / SpecSupportCard, but in the
// pass palette. Keeps both sub-checks visible as their own containers even
// when clean — avoids the pass line appearing as a footnote under whichever
// sibling card happens to have findings.
function PassCard({ titleKey, messageKey }) {
  const { t, i18n } = useTranslation()
  const msg = i18n.exists(messageKey) ? t(messageKey) : messageKey

  return (
    <FrostCard tier="resting" accent="pass">
      <div className="flex items-center gap-3 px-4 py-3 pl-5">
        <CheckCircle className="h-5 w-5 shrink-0" style={{ color: 'var(--pass-border)' }} />
        <h3 className="text-sm font-semibold flex-1">{t(titleKey)}</h3>
        <StatusPill status="pass" shape="pill">{t('status.pass')}</StatusPill>
      </div>
      <div className="border-t border-border/40 px-4 py-3 pl-5">
        <p className="text-sm leading-relaxed" style={{ color: 'var(--pass-text)' }}>{msg}</p>
      </div>
    </FrostCard>
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

  return (
    <FrostCard tier="resting" className="mt-4 p-4 space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
          {t(jConfig.section112TitleKey)}
        </span>
        <div className="flex-1 border-t border-border/50" />
      </div>

      {hasAntecedentIssues ? (
        <AntecedentBasisCard issues={antecedentBasisIssues} claimTrees={claimTrees} jurisdiction={jurisdiction} />
      ) : (
        <PassCard titleKey="antecedentBasis.title" messageKey={jConfig.section112PassKey} />
      )}

      {/* ADR-138: TW now renders SpecSupportCard alongside US. CN stays
          gated off via supportsSpecSupport=false pending real drafter corpus. */}
      {jConfig.supportsSpecSupport && (hasUnsupportedTerms ? (
        <SpecSupportCard unsupportedTerms={unsupportedTerms} claimTrees={claimTrees} jurisdiction={jurisdiction} />
      ) : (
        <PassCard titleKey={jConfig.specSupportTitleKey} messageKey={jConfig.specSupportPassKey} />
      ))}
    </FrostCard>
  )
}
