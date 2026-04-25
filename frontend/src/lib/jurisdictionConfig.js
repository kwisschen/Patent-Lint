// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen

/**
 * Jurisdiction-specific configuration for frontend components.
 * Centralises branching logic so components don't need isCN/isTW checks.
 */
const JURISDICTION_CONFIG = {
  US: {
    acceptedFormats: {
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    },
    cjkFont: null,
    showPatentType: false,
    showClaimTree: true,
    abstractUnit: 'words',
    abstractOutOfRange: (count) => count < 50 || count > 150,
    consolidateClaimsChecks: true,
    filterInternalSpecChecks: true,
    filterInternalDrawingsChecks: true,
    taglineKey: 'dropzone.tagline',
    titleKey: 'dropzone.title',
    noticeKey: 'dropzone.notice',
    rejectKey: 'dropzone.reject',
    rejectMultipleTypeKey: 'dropzone.rejectMultipleType',
    abstractLabelKey: 'summary.abstractWords',
    abstractRangeKey: 'summary.outsideRange',
    pdfAbstractKey: 'pdf.abstractWordCount',
    specSectionKey: 'section.specification',
    claimsSectionKey: 'section.claims',
    drawingsSectionKey: 'section.drawings',
    drawingsShortKey: 'section.drawingsShort',
    abstractSectionKey: 'section.abstract',
    section112TitleKey: 'section112.title',
    section112PassKey: 'check.claims.antecedentBasis.pass',
    pdfHeaderKey: 'pdf.header',
    // ADR-138: spec-support rendering is US-enabled (primary reference
    // implementation). Keys point at the existing § 112(a) copy.
    supportsSpecSupport: true,
    specSupportTitleKey: 'specSupport.title',
    specSupportPassKey: 'checks.spec_support_pass',
    specSupportReferenceCite: 'MPEP § 2163',
  },
  CN: {
    acceptedFormats: {
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'application/xml': ['.xml'],
      'text/xml': ['.xml'],
      'application/zip': ['.zip'],
    },
    cjkFont: 'zh-CN',
    showPatentType: true,
    showClaimTree: true,
    abstractUnit: 'chars',
    abstractOutOfRange: (count) => count > 300,
    consolidateClaimsChecks: false,
    filterInternalSpecChecks: false,
    filterInternalDrawingsChecks: false,
    taglineKey: 'dropzone.taglineCn',
    titleKey: 'dropzone.titleCn',
    noticeKey: 'dropzone.noticeCn',
    rejectKey: 'dropzone.rejectCn',
    rejectMultipleTypeKey: 'dropzone.rejectMultipleTypeCn',
    abstractLabelKey: 'summary.abstractChars',
    abstractRangeKey: 'summary.outsideRangeCn',
    pdfAbstractKey: 'pdf.abstractCharCount',
    specSectionKey: 'section.cn.specification',
    claimsSectionKey: 'section.cn.claims',
    drawingsSectionKey: 'section.cn.drawings',
    drawingsShortKey: 'section.cn.drawingsShort',
    abstractSectionKey: 'section.cn.abstract',
    // CN mirrors TW: heading is 先行詞分析 / Antecedent Basis Analysis,
    // not "§ 112 Analysis" (§ 112 is a USPTO-specific citation).
    section112TitleKey: 'section112.titleTw',
    section112PassKey: 'check.claims.antecedentBasis.pass',
    pdfHeaderKey: 'pdf.header',
    // CN spec-support (说明书支持分析) — CN port of TW ADR-138 feature.
    // Statute anchor: 专利法 §26 第4款 + 审查指南 第二部分第二章 §3.2.1.
    // 3-tier matcher (no symbol-table whitelist — CN has no 符号说明).
    supportsSpecSupport: true,
    specSupportTitleKey: 'specSupport.title',
    specSupportPassKey: 'check.cn.claims.specSupport.pass',
    specSupportReferenceCite: '专利法 §26 第4款',
  },
  TW: {
    acceptedFormats: {
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    },
    cjkFont: 'zh-TW',
    cjkFontLocaleAware: true,
    showPatentType: true,
    showClaimTree: true,
    abstractUnit: 'chars',
    abstractOutOfRange: (count) => count > 250,
    consolidateClaimsChecks: false,
    filterInternalSpecChecks: false,
    filterInternalDrawingsChecks: false,
    taglineKey: 'dropzone.taglineTw',
    titleKey: 'dropzone.titleTw',
    noticeKey: 'dropzone.noticeTw',
    rejectKey: 'dropzone.rejectTw',
    rejectMultipleTypeKey: 'dropzone.rejectMultipleTypeTw',
    abstractLabelKey: 'summary.abstractChars',
    abstractRangeKey: 'summary.outsideRangeTw',
    pdfAbstractKey: 'pdf.abstractCharCount',
    specSectionKey: 'section.tw.specification',
    claimsSectionKey: 'section.tw.claims',
    drawingsSectionKey: 'section.tw.drawings',
    drawingsShortKey: 'section.tw.drawingsShort',
    abstractSectionKey: 'section.tw.abstract',
    // ADR-138 follow-up: the container now holds two cards
    // (先行詞 + 說明書支持), both sub-requirements of 專利法 §26 第3項.
    // Switched from 先行詞分析 (accurate only for antecedent-only) to
    // a statute-level umbrella matching the US "§ 112 Analysis" pattern.
    section112TitleKey: 'section112.titleTwSpec',
    section112PassKey: 'check.tw.claims.antecedentBasis.pass',
    pdfHeaderKey: 'pdf.headerTw',
    // Phase 8b walker escape hatch (ADR-095). Default False: walker
    // treats 該X / 所述X / 該等X / 該些X as number-neutral and accepts a
    // singular intro for a plural reference. Strict True: walker also
    // flags references that explicitly mark plural antecedence when the
    // matched intro was singular. Plumbed through pipeline in Commit 6.
    strict_plural_reference_matching: false,
    // Phase 8b walker escape hatch (ADR-095 addendum 2026-04-09).
    // Default False: walker strips leading qualifiers (對應X, 相應X,
    // 前一X, ...) so qualified references resolve against the bare-noun
    // antecedent. Strict True: qualifier strip is disabled and
    // qualified references must have their own explicit antecedent.
    // For firms with stricter house rules. Plumbed through pipeline.
    strict_qualifier_matching: false,
    // ADR-138: TW spec-support (說明書支持分析) renders as a second
    // card under Section112Container alongside 先行詞分析. specSupport.title
    // is jurisdiction-neutral across the 5 locales; specSupportPassKey points
    // at a TW-native pass message introduced alongside i18n cleanup in the
    // following commit (authority cite: 專利法 §26 第3項, not § 112(a)).
    supportsSpecSupport: true,
    specSupportTitleKey: 'specSupport.title',
    specSupportPassKey: 'check.tw.claims.specSupport.pass',
    specSupportReferenceCite: '專利法 §26 第3項',
  },
}

export const JURISDICTION_COLORS = { US: '#2563EB', CN: '#DC2626', TW: '#0D9488' }

export function getJurisdictionConfig(jurisdiction) {
  return JURISDICTION_CONFIG[jurisdiction] || JURISDICTION_CONFIG.US
}

export default JURISDICTION_CONFIG
