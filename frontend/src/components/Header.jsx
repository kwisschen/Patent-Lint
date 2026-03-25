// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025 Christopher Chen
import { useTranslation } from 'react-i18next'
import ThemeToggle from './ThemeToggle'
import LanguageSwitcher from './LanguageSwitcher'

export default function Header({ onReset, canReset }) {
  const { t } = useTranslation()

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4">
        <div
          role={canReset ? 'button' : undefined}
          tabIndex={canReset ? 0 : undefined}
          className={canReset ? 'cursor-pointer select-none' : undefined}
          onClick={canReset ? onReset : undefined}
          onKeyDown={canReset ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onReset() } } : undefined}
        >
          <h1 className="text-lg font-bold tracking-tight">{t('header.title')}</h1>
          <p className="text-xs text-muted-foreground -mt-1">{t('header.subtitle')}</p>
        </div>
        <div className="flex items-center gap-1">
          <LanguageSwitcher />
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}
