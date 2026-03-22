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

function getClaimTypeSplit(claimTrees) {
  let method = 0
  let product = 0
  if (claimTrees) {
    claimTrees.forEach((group) => {
      if (group.label === 'Method Claims') {
        method = group.rows.length
      } else {
        product += group.rows.length
      }
    })
  }
  return { method, product }
}

export default function SummaryBar({ data }) {
  const { t } = useTranslation()
  const abstractOutOfRange = data.abstract_word_count < 50 || data.abstract_word_count > 150
  const { method, product } = getClaimTypeSplit(data.claim_trees)

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
      <StatCard
        label={t('summary.specParagraphs')}
        value={data.paragraph_count}
      />
      <StatCard
        label={t('summary.totalClaims')}
        value={data.total_claims}
        subtitle={`${data.independent_count}i / ${data.dependent_count}d`}
      />
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
      <StatCard
        label={t('summary.claimTypes')}
        value={`${method + product}`}
        subtitle={`${method} ${t('summary.method')} / ${product} ${t('summary.product')}`}
      />
    </div>
  )
}
