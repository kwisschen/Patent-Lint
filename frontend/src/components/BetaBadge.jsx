// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
import { useTranslation } from 'react-i18next'

export default function BetaBadge() {
  const { t } = useTranslation()
  return (
    <span
      className="inline-flex items-center px-1 py-px text-[8px] font-bold tracking-wider leading-none rounded-sm border uppercase shadow-sm"
      style={{
        color: 'var(--attention-text)',
        borderColor: 'var(--attention-text)',
        backgroundColor: 'var(--background)',
      }}
      title={t('common.betaBadge.tooltip')}
      aria-label={t('common.betaBadge.tooltip')}
    >
      {t('common.betaBadge.label')}
    </span>
  )
}
