// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { FileSearch } from 'lucide-react'
import { useInView } from '../hooks/useInView'

export default function PageCTA() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [ref, isInView] = useInView()

  return (
    <section
      ref={ref}
      className="py-16 text-center"
      style={{
        opacity: isInView ? 1 : 0,
        transform: isInView ? 'translateY(0)' : 'translateY(24px)',
        transition: 'opacity 600ms ease, transform 600ms ease',
      }}
    >
      <h2 className="text-3xl font-bold text-foreground mb-3">
        {t('cta.heading')}
      </h2>
      <p className="text-muted-foreground mb-8 max-w-md mx-auto leading-relaxed">
        {t('cta.subtext')}
      </p>
      <button
        onClick={() => navigate('/')}
        className="cta-button inline-flex items-center gap-2 px-8 py-3 rounded-full bg-primary text-primary-foreground font-semibold text-base shadow-md hover:shadow-lg transition-all duration-200 cursor-pointer"
      >
        <FileSearch size={18} />
        {t('cta.button')}
      </button>

      <style>{`
        .cta-button {
          animation: cta-breathe 3s ease-in-out infinite;
        }
        .cta-button:hover {
          animation: none;
          transform: translateY(-2px);
        }
        @keyframes cta-breathe {
          0%, 100% { box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1); }
          50% { box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1); }
        }
      `}</style>
    </section>
  )
}
