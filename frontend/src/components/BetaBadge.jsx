// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025 Christopher Chen
import { useTranslation } from 'react-i18next'

export default function BetaBadge() {
  const { t } = useTranslation()
  return (
    <span
      className="ml-1.5 inline-flex items-center px-1.5 py-0.5 text-[10px] font-semibold tracking-wider leading-none rounded-sm border uppercase align-middle"
      style={{
        color: 'var(--attention-text)',
        borderColor: 'var(--attention-text)',
        backgroundColor: 'transparent',
      }}
      title={t('common.betaBadge.tooltip')}
      aria-label={t('common.betaBadge.tooltip')}
    >
      {t('common.betaBadge.label')}
    </span>
  )
}
