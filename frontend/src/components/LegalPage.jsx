// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
//
// Shared layout primitives for /terms and /privacy. Mirrors the
// AboutPage / SecurityPage visual language: shadcn/ui + Tailwind
// tokens, IntersectionObserver fade-in per section, dark/light theme
// aware. Narrower max-width than AboutPage (max-w-3xl) for legal-doc
// reading comfort.

import { useTranslation } from 'react-i18next'
import { Info } from 'lucide-react'
import { useInView } from '../hooks/useInView'

export function LegalPageContainer({ children }) {
  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-12 sm:py-16 space-y-12">
      {children}
    </div>
  )
}

// Translation disclaimer banner — rendered only when a non-empty
// `translationNote` key exists in the current locale. English locale
// omits the key entirely; non-English locales carry a short note that
// the English version is authoritative in case of translation drift.
// Pattern is standard for international SaaS legal docs.
export function TranslationNote({ noteKey }) {
  const { t, i18n } = useTranslation()
  const [ref, isInView] = useInView()
  if (!i18n.exists(noteKey)) return null
  const text = t(noteKey)
  if (!text || text === noteKey) return null
  return (
    <aside
      ref={ref}
      role="note"
      className="rounded-md border border-border/60 bg-muted/40 px-4 py-3 flex items-start gap-2.5 text-xs sm:text-sm text-muted-foreground italic"
      style={{
        opacity: isInView ? 1 : 0,
        transform: isInView ? 'translateY(0)' : 'translateY(8px)',
        transition: 'opacity 0.5s var(--ease-bounce), transform 0.5s var(--ease-bounce)',
      }}
    >
      <Info className="h-4 w-4 shrink-0 mt-0.5 not-italic" aria-hidden="true" />
      <span>{text}</span>
    </aside>
  )
}

export function LegalPageHeader({ titleKey, lastUpdatedKey, introKey, accentClass = 'text-green-600 dark:text-green-400' }) {
  const { t } = useTranslation()
  const [ref, isInView] = useInView()

  return (
    <header
      ref={ref}
      className="space-y-4 border-b border-border/60 pb-8"
      style={{
        opacity: isInView ? 1 : 0,
        transform: isInView ? 'translateY(0)' : 'translateY(16px)',
        transition: 'opacity 0.6s var(--ease-bounce), transform 0.6s var(--ease-bounce)',
      }}
    >
      <h1 className="text-3xl sm:text-4xl font-bold text-foreground tracking-tight">
        {t(titleKey)}
      </h1>
      <p className={`text-xs sm:text-sm font-semibold uppercase tracking-wider ${accentClass}`}>
        {t(lastUpdatedKey)}
      </p>
      {introKey && (
        <p className="text-base sm:text-lg text-muted-foreground leading-relaxed pt-2">
          {t(introKey)}
        </p>
      )}
    </header>
  )
}

export function LegalSection({ number, titleKey, children, delay = 0 }) {
  const { t } = useTranslation()
  const [ref, isInView] = useInView()

  return (
    <section
      ref={ref}
      className="scroll-mt-20 space-y-4"
      id={`section-${number}`}
      style={{
        opacity: isInView ? 1 : 0,
        transform: isInView ? 'translateY(0)' : 'translateY(16px)',
        transition: `opacity 0.5s var(--ease-bounce) ${delay}ms, transform 0.5s var(--ease-bounce) ${delay}ms`,
      }}
    >
      <h2 className="text-lg sm:text-xl font-bold text-foreground flex items-baseline gap-2 sm:gap-3">
        <span className="text-xs sm:text-sm font-mono font-semibold text-muted-foreground shrink-0 tabular-nums">
          §&nbsp;{number}
        </span>
        <span className="leading-tight">{t(titleKey)}</span>
      </h2>
      <div className="text-sm sm:text-base text-muted-foreground leading-relaxed space-y-4 [&_strong]:text-foreground [&_strong]:font-semibold [&_a]:text-foreground [&_a]:underline [&_a]:underline-offset-2 [&_a:hover]:text-primary [&_ul]:list-disc [&_ul]:pl-5 sm:[&_ul]:pl-6 [&_ul]:space-y-2 [&_li]:leading-relaxed [&_code]:bg-muted [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:rounded [&_code]:text-xs [&_code]:font-mono">
        {children}
      </div>
    </section>
  )
}

export function LegalPageFooter({ children }) {
  const [ref, isInView] = useInView()

  return (
    <footer
      ref={ref}
      className="pt-8 border-t border-border/60 text-xs sm:text-sm text-muted-foreground space-y-2"
      style={{
        opacity: isInView ? 1 : 0,
        transform: isInView ? 'translateY(0)' : 'translateY(8px)',
        transition: 'opacity 0.5s var(--ease-bounce), transform 0.5s var(--ease-bounce)',
      }}
    >
      {children}
    </footer>
  )
}
