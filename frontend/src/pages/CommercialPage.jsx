// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
//
// /commercial — pricing + tier cards + FAQ for enterprise-deployment
// licensing. Surface for the "PatentLint for enterprises" pitch (vector
// 1 of the commercialization plan; covers law firms and corporate IP
// departments alike).

import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Shield, Check, ChevronDown, ArrowRight } from 'lucide-react'
import { useInView } from '../hooks/useInView'
import { composeEnterprise } from '../lib/feedback'
import { useFeedback } from '../components/FeedbackPicker'
import { CHECKS_DISPLAY } from '../generated/stats'

/* ------------------------------------------------------------------ */
/*  Hero                                                               */
/* ------------------------------------------------------------------ */

function HeroSection({ onInquire }) {
  const { t } = useTranslation()
  const [ref, isInView] = useInView()

  return (
    <section
      ref={ref}
      className="flex flex-col items-center text-center py-16 gap-6"
      style={{
        opacity: isInView ? 1 : 0,
        transform: isInView ? 'translateY(0)' : 'translateY(24px)',
        transition: 'opacity 0.6s var(--ease-bounce), transform 0.6s var(--ease-bounce)',
      }}
    >
      <Shield
        size={72}
        className="text-blue-500"
        style={{ animation: 'spin-once 1.8s ease-in-out forwards' }}
      />

      <h1 className="text-4xl font-bold text-foreground">
        {t('commercial.hero.title')}
      </h1>

      <p className="text-lg text-muted-foreground max-w-2xl">
        {t('commercial.hero.subtitle')}
      </p>

      <p className="text-base text-muted-foreground max-w-2xl">
        {t('commercial.hero.body')}
      </p>

      <button
        onClick={onInquire}
        className="mt-2 inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold transition-colors"
      >
        {t('commercial.hero.cta')}
        <ArrowRight className="h-4 w-4" />
      </button>
    </section>
  )
}

/* ------------------------------------------------------------------ */
/*  Pricing                                                            */
/* ------------------------------------------------------------------ */

function PricingCard({ tier, onInquire, popular = false }) {
  const { t } = useTranslation()
  const [ref, isInView] = useInView()
  const features = t(`commercial.${tier}.features`, { returnObjects: true, count: CHECKS_DISPLAY }) || []

  return (
    <div
      ref={ref}
      className={`relative ${popular ? 'frost-card-hero' : 'frost-card-elevated'} p-6 sm:p-8 flex flex-col`}
      style={{
        opacity: isInView ? 1 : 0,
        transform: isInView ? 'translateY(0)' : 'translateY(16px)',
        transition: 'opacity 0.5s var(--ease-bounce), transform 0.5s var(--ease-bounce)',
      }}
    >
      {popular && (
        <span className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full bg-blue-600 text-white text-xs font-semibold">
          {t('commercial.popular')}
        </span>
      )}
      <h3 className="text-xl font-bold text-foreground">
        {t(`commercial.${tier}.name`)}
      </h3>
      <p className="text-sm text-muted-foreground mt-1">
        {t(`commercial.${tier}.size`)}
      </p>
      <p className="text-3xl font-bold text-foreground mt-4">
        {t(`commercial.${tier}.fee`)}
      </p>
      <p className="text-xs text-muted-foreground">
        {t('commercial.feeNote')}
      </p>

      <ul className="mt-6 space-y-2.5 flex-1">
        {Array.isArray(features) && features.map((feature, i) => (
          <li key={i} className="flex items-start gap-2 text-sm text-muted-foreground">
            <Check className="h-4 w-4 mt-0.5 shrink-0 text-blue-500" aria-hidden="true" />
            <span>{feature}</span>
          </li>
        ))}
      </ul>

      <button
        onClick={onInquire}
        className={`mt-6 inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg font-medium transition-colors ${
          popular
            ? 'bg-blue-600 hover:bg-blue-700 text-white'
            : 'bg-secondary hover:bg-secondary/80 text-foreground'
        }`}
      >
        {t(`commercial.${tier}.cta`)}
        <ArrowRight className="h-4 w-4" />
      </button>
    </div>
  )
}

function PricingSection({ onInquire }) {
  const { t } = useTranslation()
  const [ref, isInView] = useInView()

  return (
    <section
      ref={ref}
      className="py-12"
      style={{
        opacity: isInView ? 1 : 0,
        transform: isInView ? 'translateY(0)' : 'translateY(16px)',
        transition: 'opacity 0.6s var(--ease-bounce), transform 0.6s var(--ease-bounce)',
      }}
    >
      <h2 className="text-2xl sm:text-3xl font-bold text-foreground text-center">
        {t('commercial.pricing.heading')}
      </h2>
      <p className="text-center text-muted-foreground mt-2">
        {t('commercial.pricing.subheading')}
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-10 max-w-4xl mx-auto">
        <PricingCard tier="standalone" onInquire={onInquire} />
        <PricingCard tier="firm" onInquire={onInquire} popular />
      </div>

      <p className="text-center text-xs text-muted-foreground mt-6 max-w-2xl mx-auto">
        {t('commercial.pricing.footnote')}
      </p>
    </section>
  )
}

/* ------------------------------------------------------------------ */
/*  FAQ                                                                */
/* ------------------------------------------------------------------ */

function FAQItem({ qKey, aKey, delay = 0 }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [ref, isInView] = useInView()

  return (
    <div
      ref={ref}
      className="border-b border-border/60 last:border-0"
      style={{
        opacity: isInView ? 1 : 0,
        transform: isInView ? 'translateY(0)' : 'translateY(8px)',
        transition: `opacity 0.4s var(--ease-bounce) ${delay}ms, transform 0.4s var(--ease-bounce) ${delay}ms`,
      }}
    >
      <button
        onClick={() => setOpen(!open)}
        className="w-full py-4 flex items-center justify-between gap-4 text-left hover:text-foreground"
        aria-expanded={open}
      >
        <span className="font-medium text-foreground">{t(qKey)}</span>
        <ChevronDown
          className={`h-4 w-4 shrink-0 transition-transform ${open ? 'rotate-180' : ''}`}
          aria-hidden="true"
        />
      </button>
      {open && (
        <p className="pb-4 text-sm text-muted-foreground leading-relaxed">
          {t(aKey, { count: CHECKS_DISPLAY })}
        </p>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Trust verify cross-reference                                       */
/* ------------------------------------------------------------------ */

function TrustVerifySection() {
  const { t } = useTranslation()
  const [ref, isInView] = useInView()

  return (
    <section
      ref={ref}
      className="py-8 text-center"
      style={{
        opacity: isInView ? 1 : 0,
        transform: isInView ? 'translateY(0)' : 'translateY(12px)',
        transition: 'opacity 500ms ease, transform 500ms ease',
      }}
    >
      <p className="text-sm text-muted-foreground mb-3">
        {t('commercial.trustVerify.body')}
      </p>
      <div className="flex justify-center gap-6 text-sm">
        <Link
          to="/security"
          className="inline-flex items-center gap-1 text-primary hover:text-primary/80 transition-colors"
        >
          {t('commercial.trustVerify.security')}
          <ArrowRight className="h-3 w-3" aria-hidden="true" />
        </Link>
        <Link
          to="/privacy"
          className="inline-flex items-center gap-1 text-primary hover:text-primary/80 transition-colors"
        >
          {t('commercial.trustVerify.privacy')}
          <ArrowRight className="h-3 w-3" aria-hidden="true" />
        </Link>
      </div>
    </section>
  )
}

function FAQSection() {
  const { t } = useTranslation()
  const [ref, isInView] = useInView()

  // Eight Q&A pairs, all keys under commercial.faq.q1..q8
  const items = [1, 2, 3, 4, 5, 6, 7, 8]

  return (
    <section
      ref={ref}
      className="py-12 max-w-3xl mx-auto"
      style={{
        opacity: isInView ? 1 : 0,
        transform: isInView ? 'translateY(0)' : 'translateY(16px)',
        transition: 'opacity 0.6s var(--ease-bounce), transform 0.6s var(--ease-bounce)',
      }}
    >
      <h2 className="text-2xl sm:text-3xl font-bold text-foreground text-center mb-8">
        {t('commercial.faq.heading')}
      </h2>
      <div className="space-y-1">
        {items.map((n, i) => (
          <FAQItem
            key={n}
            qKey={`commercial.faq.q${n}.q`}
            aKey={`commercial.faq.q${n}.a`}
            delay={i * 50}
          />
        ))}
      </div>
    </section>
  )
}

/* ------------------------------------------------------------------ */
/*  Page shell                                                         */
/* ------------------------------------------------------------------ */

export default function CommercialPage() {
  const { t } = useTranslation()
  const { sendFeedback } = useFeedback()

  const handleInquire = () => {
    sendFeedback(composeEnterprise(t))
  }

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-8">
      <HeroSection onInquire={handleInquire} />
      <PricingSection onInquire={handleInquire} />
      <FAQSection />
      <TrustVerifySection />

      {/* Final CTA */}
      <section className="py-12 text-center">
        <p className="text-base text-muted-foreground mb-4">
          {t('commercial.finalCta.body')}
        </p>
        <button
          onClick={handleInquire}
          className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold transition-colors"
        >
          {t('commercial.finalCta.button')}
          <ArrowRight className="h-4 w-4" />
        </button>
      </section>
    </div>
  )
}
