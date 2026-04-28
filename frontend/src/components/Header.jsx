// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, Link } from 'react-router-dom'
import LogoIcon from './LogoIcon'
import ThemeToggle from './ThemeToggle'
import LanguageSwitcher from './LanguageSwitcher'

export default function Header({ onReset, canReset }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 10)
    window.addEventListener('scroll', handleScroll, { passive: true })
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  const handleLogoClick = () => {
    if (canReset) {
      onReset()
    }
    navigate('/')
  }

  return (
    <header
      className={`sticky top-0 z-50 w-full border-b transition-all duration-[var(--motion-duration-base)] ${
        scrolled
          ? 'frost-blur-md bg-background/70 supports-[backdrop-filter]:bg-background/60 shadow-[var(--frost-resting-shadow)] border-[var(--frost-resting-border)]'
          : 'bg-background border-border'
      }`}
    >
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
            <Link to="/security" className="hover:text-foreground transition-colors">{t('footer.security')}</Link>
            <Link to="/about" className="hover:text-foreground transition-colors">{t('footer.about')}</Link>
          </nav>
          <LanguageSwitcher />
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}
