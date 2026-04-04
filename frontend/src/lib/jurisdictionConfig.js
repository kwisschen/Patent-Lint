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
  },
  CN: {
    acceptedFormats: {
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'application/xml': ['.xml'],
      'text/xml': ['.xml'],
      'application/zip': ['.zip'],
    },
    cjkFont: 'zh-CN',
    showClaimTree: false,
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
  },
  TW: {
    acceptedFormats: {
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    },
    cjkFont: 'zh-TW',
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
  },
}

export function getJurisdictionConfig(jurisdiction) {
  return JURISDICTION_CONFIG[jurisdiction] || JURISDICTION_CONFIG.US
}

export default JURISDICTION_CONFIG
