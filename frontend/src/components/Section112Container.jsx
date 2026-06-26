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
  // Fall back to a generic localized pass message if the specific key
  // isn't defined for this jurisdiction; never render the raw key as text.
  const msg = i18n.exists(messageKey) ? t(messageKey) : t('status.allChecksPassed')

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
        <h3 className="text-base font-bold text-foreground uppercase tracking-wide">
          {t(jConfig.section112TitleKey)}
        </h3>
        <div className="flex-1 border-t border-border/50" />
      </div>

      {/* Always-visible disclaimer — protects against user assuming the
          analysis is comprehensive even when the card surface is empty.
          Same i18n key was previously only rendered inside AntecedentBasisCard
          (i.e. only when there were findings); moved here so it shows
          regardless of finding state across all 4 jurisdictions. */}
      <p className="text-xs text-muted-foreground italic leading-relaxed">
        {t('antecedentBasis.disclaimer')}
      </p>

      {/* `id` + scroll-mt are the jump-to targets for the polished pills in
          the TriagePanel review items (so a long, dense §112 review line can be
          skipped in favour of a one-click jump down to the per-claim card). */}
      <div id="section112-antecedent" className="scroll-mt-20">
        {hasAntecedentIssues ? (
          <AntecedentBasisCard issues={antecedentBasisIssues} claimTrees={claimTrees} jurisdiction={jurisdiction} />
        ) : (
          <PassCard titleKey="antecedentBasis.title" messageKey={jConfig.section112PassKey} />
        )}
      </div>

      {/* Spec-support card. US/EPC/TW/CN all enable it (supportsSpecSupport).
          CN's ADR-138 gate (precision concerns on publication-doc fixtures) was
          mooted by the #314 advisory re-tier — it surfaces "terms to verify"
          with zero grade impact, so imprecision is bounded. */}
      {jConfig.supportsSpecSupport && (
        <div id="section112-specsupport" className="scroll-mt-20">
          {hasUnsupportedTerms ? (
            <SpecSupportCard unsupportedTerms={unsupportedTerms} claimTrees={claimTrees} jurisdiction={jurisdiction} />
          ) : (
            <PassCard titleKey={jConfig.specSupportTitleKey} messageKey={jConfig.specSupportPassKey} />
          )}
        </div>
      )}
    </FrostCard>
  )
}
