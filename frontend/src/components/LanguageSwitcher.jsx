// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
import { useState, useRef, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Globe } from 'lucide-react'
import { Button } from '@/components/ui/button'

const LANGUAGES = ['en', 'zh-CN', 'zh-TW', 'ja', 'ko']

export default function LanguageSwitcher() {
  const { t, i18n } = useTranslation()
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const switchLang = (code) => {
    i18n.changeLanguage(code)
    setOpen(false)
  }

  return (
    <div className="relative" ref={ref}>
      <Button variant="ghost" size="icon" onClick={() => setOpen(!open)} aria-label={t('common.changeLanguage')}>
        <Globe className="h-4 w-4" />
      </Button>
      {open && (
        <div className="absolute right-0 top-full mt-1 z-50 min-w-[140px] rounded-md border bg-popover p-1 shadow-md animate-in fade-in-0 zoom-in-95 duration-100">
          {LANGUAGES.map((code) => (
            <button
              key={code}
              className={`w-full rounded-sm px-3 py-1.5 text-left text-sm transition-colors hover:bg-accent ${i18n.language === code ? 'font-semibold text-foreground' : 'text-muted-foreground'}`}
              onClick={() => switchLang(code)}
            >
              {t(`lang.${code}`)}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
