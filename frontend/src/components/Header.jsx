// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025–2026 Christopher Chen
import { useTranslation } from 'react-i18next'
import { useNavigate, Link } from 'react-router-dom'
import LogoIcon from './LogoIcon'
import ThemeToggle from './ThemeToggle'
import LanguageSwitcher from './LanguageSwitcher'

export default function Header({ onReset, canReset }) {
  const { t } = useTranslation()
  const navigate = useNavigate()

  const handleLogoClick = () => {
    if (canReset) {
      onReset()
    }
    navigate('/')
  }

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/60 bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/70">
      <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4">
        <div
          role="button"
          tabIndex={0}
          className="cursor-pointer select-none logo-hover"
          onClick={handleLogoClick}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleLogoClick() } }}
        >
          <h1 className="text-lg font-bold tracking-tight flex items-center gap-2">
            <LogoIcon className="w-6 h-6" />
            {t('header.title')}
          </h1>
          <p className="hidden sm:block text-xs text-muted-foreground -mt-1">{t('header.subtitle')}</p>
        </div>
        <div className="flex items-center gap-1">
          <nav className="flex items-center gap-4 text-sm text-muted-foreground mr-3">
            <Link to="/security" className="relative transition-colors hover:text-brand after:pointer-events-none after:absolute after:-bottom-1 after:left-0 after:h-px after:w-full after:origin-left after:scale-x-0 after:bg-brand after:transition-transform after:duration-200 hover:after:scale-x-100">{t('footer.security')}</Link>
            <Link to="/about" className="relative transition-colors hover:text-brand after:pointer-events-none after:absolute after:-bottom-1 after:left-0 after:h-px after:w-full after:origin-left after:scale-x-0 after:bg-brand after:transition-transform after:duration-200 hover:after:scale-x-100">{t('footer.about')}</Link>
          </nav>
          <LanguageSwitcher />
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}
