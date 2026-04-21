// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
//
// /terms — Terms of Service for patentlint.com.
// Pairs with /privacy. Both ship as part of ADR-139 (license migration
// to PolyForm-Strict-1.0.0). Localized across en / zh-TW / zh-CN /
// ja / ko via the shared frontend/src/i18n/locales bundles.

import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation, Trans } from 'react-i18next'
import {
  LegalPageContainer,
  LegalPageFooter,
  LegalPageHeader,
  LegalSection,
} from '../components/LegalPage'

export default function TermsPage() {
  const { t } = useTranslation()
  useEffect(() => { window.scrollTo(0, 0) }, [])

  return (
    <LegalPageContainer>
      <LegalPageHeader
        titleKey="terms.title"
        lastUpdatedKey="terms.lastUpdated"
        introKey="terms.intro"
        accentClass="text-green-600 dark:text-green-400"
      />

      <LegalSection number="1" titleKey="terms.s1.title">
        <p>{t('terms.s1.p1')}</p>
        <ul>
          <li>
            <strong>{t('terms.s1.siteLabel')}</strong> {t('terms.s1.siteDesc')}
          </li>
          <li>
            <strong>{t('terms.s1.softwareLabel')}</strong> {t('terms.s1.softwareDesc')}
          </li>
        </ul>
        <p>{t('terms.s1.p2')}</p>
      </LegalSection>

      <LegalSection number="2" titleKey="terms.s2.title">
        <p>{t('terms.s2.p1')}</p>
        <ul>
          <li>{t('terms.s2.may1')}</li>
          <li>{t('terms.s2.may2')}</li>
          <li>{t('terms.s2.may3')}</li>
        </ul>
        <p>{t('terms.s2.p2')}</p>
        <ul>
          <li>{t('terms.s2.maynot1')}</li>
          <li>{t('terms.s2.maynot2')}</li>
          <li>{t('terms.s2.maynot3')}</li>
          <li>{t('terms.s2.maynot4')}</li>
        </ul>
      </LegalSection>

      <LegalSection number="3" titleKey="terms.s3.title">
        <p>{t('terms.s3.p1')}</p>
        <p>{t('terms.s3.p2')}</p>
        <p className="text-xs sm:text-sm italic">
          <Trans i18nKey="terms.s3.privacyLink">
            See the <Link to="/privacy">Privacy Policy</Link> for the full data-handling disclosure.
          </Trans>
        </p>
      </LegalSection>

      <LegalSection number="4" titleKey="terms.s4.title">
        <p>
          <Trans i18nKey="terms.s4.p1">
            The Software is source-available under PolyForm-Strict-1.0.0. The full license text is at <a href="https://polyformproject.org/licenses/strict/1.0.0" target="_blank" rel="noopener noreferrer">polyformproject.org/licenses/strict/1.0.0</a> and in the LICENSE file of the Software repository.
          </Trans>
        </p>
        <p><strong>{t('terms.s4.permittedHeading')}</strong></p>
        <ul>
          <li>{t('terms.s4.permitted1')}</li>
          <li>{t('terms.s4.permitted2')}</li>
          <li>{t('terms.s4.permitted3')}</li>
          <li>{t('terms.s4.permitted4')}</li>
        </ul>
        <p><strong>{t('terms.s4.requiresHeading')}</strong></p>
        <ul>
          <li>{t('terms.s4.requires1')}</li>
          <li>{t('terms.s4.requires2')}</li>
          <li>{t('terms.s4.requires3')}</li>
          <li>{t('terms.s4.requires4')}</li>
        </ul>
        <p>
          <Trans i18nKey="terms.s4.contact">
            Contact <a href="mailto:kwisschen@gmail.com">kwisschen@gmail.com</a> to discuss commercial licensing terms. Pricing and terms are negotiated case-by-case based on deployment model, scope, and organization size.
          </Trans>
        </p>
      </LegalSection>

      <LegalSection number="5" titleKey="terms.s5.title">
        <p>{t('terms.s5.p1')}</p>
      </LegalSection>

      <LegalSection number="6" titleKey="terms.s6.title">
        <p>{t('terms.s6.p1')}</p>
        <p>{t('terms.s6.p2')}</p>
      </LegalSection>

      <LegalSection number="7" titleKey="terms.s7.title">
        <p>{t('terms.s7.p1')}</p>
      </LegalSection>

      <LegalSection number="8" titleKey="terms.s8.title">
        <p>{t('terms.s8.p1')}</p>
      </LegalSection>

      <LegalSection number="9" titleKey="terms.s9.title">
        <p>{t('terms.s9.p1')}</p>
      </LegalSection>

      <LegalSection number="10" titleKey="terms.s10.title">
        <p>{t('terms.s10.p1')}</p>
      </LegalSection>

      <LegalSection number="11" titleKey="terms.s11.title">
        <p>{t('terms.s11.p1')}</p>
        <ul>
          <li>
            <strong>{t('terms.s11.nameLabel')}</strong> {t('terms.s11.name')}
          </li>
          <li>
            <strong>{t('terms.s11.emailLabel')}</strong>{' '}
            <a href="mailto:kwisschen@gmail.com">kwisschen@gmail.com</a>
          </li>
          <li>
            <strong>{t('terms.s11.githubLabel')}</strong>{' '}
            <a href="https://github.com/kwisschen" target="_blank" rel="noopener noreferrer">
              github.com/kwisschen
            </a>
          </li>
        </ul>
      </LegalSection>

      <LegalPageFooter>
        <p>{t('terms.copyright')}</p>
        <p>
          <Trans i18nKey="terms.crossLinks">
            See also: <Link to="/privacy">Privacy Policy</Link> · <Link to="/security">Security</Link>
          </Trans>
        </p>
      </LegalPageFooter>
    </LegalPageContainer>
  )
}
