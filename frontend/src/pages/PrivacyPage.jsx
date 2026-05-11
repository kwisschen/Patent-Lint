// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025–2026 Christopher Chen
//
// /privacy — Privacy Policy for patentlint.com.
// Pairs with /terms. Both ship as part of ADR-139 (license migration
// to PolyForm-Strict-1.0.0). Localized across en / de / zh-TW / zh-CN /
// ja / ko via the shared frontend/src/i18n/locales bundles.
//
// PatentLint's data posture is near-zero (in-browser WASM analysis,
// no analytics, no cookies). The Privacy Policy formalizes that
// posture as statutory disclosure for enterprise vendor review and
// GDPR Art. 4(7) data-controller compliance for Vercel-edge IP
// logging (production hosting moved Cloudflare Pages → Vercel
// 2026-05-08; Privacy § 3 reflects this).

import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation, Trans } from 'react-i18next'
import {
  LegalPageContainer,
  LegalPageFooter,
  LegalPageHeader,
  LegalSection,
  TranslationNote,
} from '../components/LegalPage'

export default function PrivacyPage() {
  const { t } = useTranslation()
  useEffect(() => { window.scrollTo(0, 0) }, [])

  return (
    <LegalPageContainer>
      <LegalPageHeader
        titleKey="privacy.title"
        lastUpdatedKey="privacy.lastUpdated"
        introKey="privacy.intro"
        accentClass="text-blue-600 dark:text-blue-400"
      />

      <TranslationNote noteKey="privacy.translationNote" />

      <LegalSection number="1" titleKey="privacy.s1.title">
        <p>{t('privacy.s1.p1')}</p>
        <p>{t('privacy.s1.p2')}</p>
      </LegalSection>

      <LegalSection number="2" titleKey="privacy.s2.title">
        <p>{t('privacy.s2.p1')}</p>
        <p>{t('privacy.s2.p2')}</p>
        <ul>
          <li>{t('privacy.s2.never1')}</li>
          <li>{t('privacy.s2.never2')}</li>
          <li>{t('privacy.s2.never3')}</li>
        </ul>
        <p>
          <Trans i18nKey="privacy.s2.verify">
            You can verify this in airplane mode — see the <Link to="/security">Security</Link> page for the live demonstration.
          </Trans>
        </p>
        <p>{t('privacy.s2.p3')}</p>
      </LegalSection>

      <LegalSection number="3" titleKey="privacy.s3.title">
        <p>{t('privacy.s3.p1')}</p>
        <ul>
          <li>{t('privacy.s3.log1')}</li>
          <li>{t('privacy.s3.log2')}</li>
          <li>{t('privacy.s3.log3')}</li>
          <li>{t('privacy.s3.log4')}</li>
        </ul>
        <p>{t('privacy.s3.p2')}</p>
        <p>{t('privacy.s3.p3')}</p>
      </LegalSection>

      <LegalSection number="4" titleKey="privacy.s4.title">
        <p>{t('privacy.s4.p1')}</p>
        <ul>
          <li>{t('privacy.s4.no1')}</li>
          <li>{t('privacy.s4.no2')}</li>
          <li>{t('privacy.s4.no3')}</li>
          <li>{t('privacy.s4.no4')}</li>
        </ul>
        <p>{t('privacy.s4.p2')}</p>
      </LegalSection>

      <LegalSection number="5" titleKey="privacy.s5.title">
        <p>{t('privacy.s5.p1')}</p>
        <p>{t('privacy.s5.p2')}</p>
      </LegalSection>

      <LegalSection number="6" titleKey="privacy.s6.title">
        <p>{t('privacy.s6.p1')}</p>
        <p>{t('privacy.s6.p2')}</p>
        <p>{t('privacy.s6.p3')}</p>
        <p>{t('privacy.s6.p4')}</p>
      </LegalSection>

      <LegalSection number="7" titleKey="privacy.s7.title">
        <p>{t('privacy.s7.p1')}</p>
        <ul>
          <li>
            <strong>{t('privacy.s7.vercelLabel')}</strong> {t('privacy.s7.vercel')}
          </li>
          <li>
            <strong>{t('privacy.s7.pyodideLabel')}</strong> {t('privacy.s7.pyodide')}
          </li>
          <li>
            <strong>{t('privacy.s7.fontsLabel')}</strong> {t('privacy.s7.fonts')}
          </li>
          <li>
            <strong>{t('privacy.s7.githubLabel')}</strong> {t('privacy.s7.github')}
          </li>
        </ul>
        <p>{t('privacy.s7.p2')}</p>
      </LegalSection>

      <LegalSection number="8" titleKey="privacy.s8.title">
        <p>{t('privacy.s8.p1')}</p>
        <ul>
          <li>
            <strong>{t('privacy.s8.accessLabel')}</strong> {t('privacy.s8.access')}
          </li>
          <li>
            <strong>{t('privacy.s8.deletionLabel')}</strong> {t('privacy.s8.deletion')}
          </li>
          <li>
            <strong>{t('privacy.s8.portabilityLabel')}</strong> {t('privacy.s8.portability')}
          </li>
          <li>
            <strong>{t('privacy.s8.objectLabel')}</strong> {t('privacy.s8.object')}
          </li>
        </ul>
        <p>
          <Trans i18nKey="privacy.s8.exercise">
            Exercise these rights by emailing <a href="mailto:kwisschen@gmail.com">kwisschen@gmail.com</a>. We respond within 30 days. Note: because we collect almost nothing about you, most requests will simply confirm we have nothing to access, delete, or export.
          </Trans>
        </p>
      </LegalSection>

      <LegalSection number="9" titleKey="privacy.s9.title">
        <p>{t('privacy.s9.p1')}</p>
      </LegalSection>

      <LegalSection number="10" titleKey="privacy.s10.title">
        <p>{t('privacy.s10.p1')}</p>
      </LegalSection>

      <LegalSection number="11" titleKey="privacy.s11.title">
        <p>{t('privacy.s11.p1')}</p>
        <ul>
          <li>
            <strong>{t('privacy.s11.nameLabel')}</strong> {t('privacy.s11.name')}
          </li>
          <li>
            <strong>{t('privacy.s11.emailLabel')}</strong>{' '}
            <a href="mailto:kwisschen@gmail.com">kwisschen@gmail.com</a>
          </li>
        </ul>
      </LegalSection>

      <LegalPageFooter>
        <p>{t('privacy.copyright')}</p>
        <p>
          <Trans i18nKey="privacy.crossLinks">
            See also: <Link to="/terms">Terms of Service</Link> · <Link to="/security">Security</Link>
          </Trans>
        </p>
      </LegalPageFooter>
    </LegalPageContainer>
  )
}
