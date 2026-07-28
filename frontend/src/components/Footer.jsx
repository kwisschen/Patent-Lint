// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025-2026 Christopher Chen
/* global __BUILD_HASH__ */
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { composeFooterFeedback } from '../lib/feedback'
import { useFeedback } from './FeedbackPicker'

export default function Footer() {
  const { t } = useTranslation()
  const { sendFeedback } = useFeedback()

  // Feedback link: click triggers the picker modal (on first use) or
  // dispatches via the user's remembered method. href is '#' so the
  // browser doesn't navigate; onClick + preventDefault takes over.
  const handleFeedbackClick = (e) => {
    e.preventDefault()
    sendFeedback(composeFooterFeedback(t))
  }

  // Footer is reserved for legal / product links. Personal-credibility
  // links (GitHub / LinkedIn) live on the AboutPage Background section
  // alongside Email - that's where users go for that context.
  const externalLinks = [
    { label: t('footer.feedback'), href: '#', onClick: handleFeedbackClick },
  ]

  // pb-16 (not py-6) gives the footer content clearance above the fixed
  // NetworkWidget pill (bottom-4, ~52px tall). Without it the rightmost
  // footer link (now the PatentNode cross-link) sits under the pill at
  // scroll-bottom on short pages / ~1280px laptops.
  return (
    <footer className="border-t border-gray-200 dark:border-gray-800 pt-6 pb-16 px-4">
      <div className="mx-auto max-w-5xl flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-gray-500 dark:text-gray-400">
        <span>
          {t('footer.builtBy')}
          <span className="opacity-50 ml-2 text-xs">· Build <span className="font-mono">{__BUILD_HASH__.slice(0, 8)}</span></span>
        </span>
        <nav className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2" aria-label="Footer">
          <Link
            to="/terms"
            className="footer-link transition-colors duration-200 hover:text-brand"
          >
            {t('footer.terms')}
          </Link>
          <Link
            to="/privacy"
            className="footer-link transition-colors duration-200 hover:text-brand"
          >
            {t('footer.privacy')}
          </Link>
          <Link
            to="/rubric"
            className="footer-link transition-colors duration-200 hover:text-brand"
          >
            {t('footer.rubric')}
          </Link>
          {externalLinks.map(({ label, href, onClick }) => (
            <a
              key={label}
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              onClick={onClick}
              className="footer-link transition-colors duration-200 hover:text-brand"
            >
              {label}
            </a>
          ))}
          {/* Sister-product cross-link - funnels filed-application users to
              PatentNode for OA responses. Brand-tinted + arrow so it reads
              as an outbound product pointer, not another legal link. */}
          <a
            href="https://patentnode.com"
            target="_blank"
            rel="noopener noreferrer"
            className="group inline-flex items-center gap-1 font-medium text-brand transition-colors duration-200 hover:text-accent-cyan"
          >
            {t('footer.sister')}
            <span aria-hidden className="transition-transform duration-200 group-hover:translate-x-0.5">→</span>
          </a>
        </nav>
      </div>
    </footer>
  )
}
