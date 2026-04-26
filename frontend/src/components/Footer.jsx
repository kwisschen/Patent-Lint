// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
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
  // alongside Email — that's where users go for that context.
  const externalLinks = [
    { label: t('footer.feedback'), href: '#', onClick: handleFeedbackClick },
  ]

  return (
    <footer className="border-t border-gray-200 dark:border-gray-800 py-6 px-4">
      <div className="mx-auto max-w-5xl flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-gray-500 dark:text-gray-400">
        <span>{t('footer.builtBy')}</span>
        <nav className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2" aria-label="Footer">
          <Link
            to="/terms"
            className="footer-link hover:text-foreground transition-colors duration-200"
          >
            {t('footer.terms')}
          </Link>
          <Link
            to="/privacy"
            className="footer-link hover:text-foreground transition-colors duration-200"
          >
            {t('footer.privacy')}
          </Link>
          <Link
            to="/rubric"
            className="footer-link hover:text-foreground transition-colors duration-200"
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
              className="footer-link hover:text-foreground transition-colors duration-200"
            >
              {label}
            </a>
          ))}
        </nav>
      </div>
    </footer>
  )
}
