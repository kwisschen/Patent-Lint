// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025–2026 Christopher Chen
import { useTranslation } from 'react-i18next'
import { FrostCard } from './ui/frost-card'
import { useCountUp } from '../hooks/useCountUp'
import { useInView } from '../hooks/useInView'
import { getJurisdictionConfig } from '../lib/jurisdictionConfig'

function StatCard({ label, value, subtitle }) {
  return (
    <FrostCard tier="resting" interactive className="p-4">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="text-2xl font-bold mt-1">{value}</p>
      {subtitle && <p className="text-xs text-muted-foreground mt-0.5">{subtitle}</p>}
    </FrostCard>
  )
}

function getClaimCategorySplit(claimTrees) {
  let method = 0
  let apparatus = 0
  if (claimTrees) {
    claimTrees.forEach((group) => {
      if (group.label === 'Method Claims') {
        method = group.rows.length
      } else {
        apparatus += group.rows.length
      }
    })
  }
  return { method, apparatus }
}

export default function SummaryBar({ data, animate = false }) {
  const { t } = useTranslation()
  const [ref, isInView] = useInView()
  const shouldAnimate = animate && isInView
  const jConfig = getJurisdictionConfig(data.jurisdiction)
  const noParagraphs = data.paragraph_count === 0
  const abstractOutOfRange = jConfig.abstractOutOfRange(data.abstract_word_count)
  const { method, apparatus } = getClaimCategorySplit(data.claim_trees)
  const patentTypeValue = data.patent_type === 'UTILITY_MODEL'
    ? t('summary.patentTypeUtilityModel')
    : t('summary.patentTypeInvention')

  const paragraphCount = useCountUp(data.paragraph_count, 600, shouldAnimate)
  const indepCount = useCountUp(data.independent_count, 600, shouldAnimate)
  const depCount = useCountUp(data.dependent_count, 600, shouldAnimate)
  const methodCount = useCountUp(method, 600, shouldAnimate)
  const apparatusCount = useCountUp(apparatus, 600, shouldAnimate)
  const figureCount = useCountUp(data.figure_count, 600, shouldAnimate)
  const abstractCount = useCountUp(data.abstract_word_count, 600, shouldAnimate)

  return (
    <div ref={ref} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
      {(data.jurisdiction === 'US' || data.jurisdiction === 'EPC') && data.claim_trees?.length > 0 && (
        <FrostCard tier="resting" interactive className="p-4">
          <p className="text-sm text-muted-foreground">{t('summary.claimCategories')}</p>
          <div className="mt-1 space-y-0.5">
            <p className="flex items-baseline">
              <span className="text-2xl font-bold">{methodCount}</span>
              <span className="text-sm text-muted-foreground ml-1.5">{t('summary.method')}</span>
            </p>
            <p className="flex items-baseline">
              <span className="text-2xl font-bold">{apparatusCount}</span>
              <span className="text-sm text-muted-foreground ml-1.5">{t('summary.apparatus')}</span>
            </p>
          </div>
        </FrostCard>
      )}
      {jConfig.showPatentType && (
        <StatCard
          label={t('summary.patentType')}
          value={patentTypeValue}
        />
      )}
      <FrostCard tier="resting" interactive className="p-4">
        <p className="text-sm text-muted-foreground">{t('summary.claims')}</p>
        <div className="mt-1 space-y-0.5">
          <p className="flex items-baseline">
            <span className="text-2xl font-bold">{indepCount}</span>
            <span className="text-sm text-muted-foreground ml-1.5">{t('summary.independent')}</span>
          </p>
          <p className="flex items-baseline">
            <span className="text-2xl font-bold">{depCount}</span>
            <span className="text-sm text-muted-foreground ml-1.5">{t('summary.dependent')}</span>
          </p>
        </div>
      </FrostCard>
      <StatCard
        label={t('summary.figures')}
        value={figureCount}
      />
      <StatCard
        label={t('summary.specParagraphs')}
        value={
          <span className={noParagraphs ? 'text-[var(--amend-text)]' : ''}>
            {paragraphCount}
          </span>
        }
        subtitle={noParagraphs ? t('summary.noParagraphs') : null}
      />
      <StatCard
        label={t(jConfig.abstractLabelKey)}
        value={
          <span className={abstractOutOfRange ? 'text-[var(--amend-text)]' : ''}>
            {abstractCount}
          </span>
        }
        subtitle={abstractOutOfRange ? t(jConfig.abstractRangeKey) : null}
      />
    </div>
  )
}
