// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025 Christopher Chen
import { useTranslation } from 'react-i18next'
import { Card, CardContent } from '@/components/ui/card'

function StatCard({ label, value, subtitle }) {
  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className="text-2xl font-bold mt-1">{value}</p>
        {subtitle && <p className="text-xs text-muted-foreground mt-0.5">{subtitle}</p>}
      </CardContent>
    </Card>
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

export default function SummaryBar({ data }) {
  const { t } = useTranslation()
  const abstractOutOfRange = data.abstract_word_count < 50 || data.abstract_word_count > 150
  const { method, apparatus } = getClaimCategorySplit(data.claim_trees)

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
      <StatCard
        label={t('summary.specParagraphs')}
        value={data.paragraph_count}
      />
      <Card>
        <CardContent className="p-4">
          <p className="text-sm text-muted-foreground">{t('summary.claims')}</p>
          <div className="mt-1 space-y-0.5">
            <p className="flex items-baseline">
              <span className="text-2xl font-bold">{data.independent_count}</span>
              <span className="text-sm text-muted-foreground ml-1.5">{t('summary.independent')}</span>
            </p>
            <p className="flex items-baseline">
              <span className="text-2xl font-bold">{data.dependent_count}</span>
              <span className="text-sm text-muted-foreground ml-1.5">{t('summary.dependent')}</span>
            </p>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="p-4">
          <p className="text-sm text-muted-foreground">{t('summary.claimCategories')}</p>
          <div className="mt-1 space-y-0.5">
            <p className="flex items-baseline">
              <span className="text-2xl font-bold">{method}</span>
              <span className="text-sm text-muted-foreground ml-1.5">{t('summary.method')}</span>
            </p>
            <p className="flex items-baseline">
              <span className="text-2xl font-bold">{apparatus}</span>
              <span className="text-sm text-muted-foreground ml-1.5">{t('summary.apparatus')}</span>
            </p>
          </div>
        </CardContent>
      </Card>
      <StatCard
        label={t('summary.figures')}
        value={data.figure_count}
      />
      <StatCard
        label={t('summary.abstractWords')}
        value={
          <span className={abstractOutOfRange ? 'text-[var(--amend-text)]' : ''}>
            {data.abstract_word_count}
          </span>
        }
        subtitle={abstractOutOfRange ? t('summary.outsideRange') : null}
      />
    </div>
  )
}
