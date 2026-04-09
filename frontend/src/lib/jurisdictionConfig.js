// SPDX-License-Identifier: AGPL-3.0-only
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
    section112TitleKey: 'section112.title',
    section112PassKey: 'check.claims.antecedentBasis.pass',
    pdfHeaderKey: 'pdf.header',
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
    section112TitleKey: 'section112.titleTw',
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
  },
}

export const JURISDICTION_COLORS = { US: '#2563EB', CN: '#DC2626', TW: '#0D9488' }

export function getJurisdictionConfig(jurisdiction) {
  return JURISDICTION_CONFIG[jurisdiction] || JURISDICTION_CONFIG.US
}

export default JURISDICTION_CONFIG
