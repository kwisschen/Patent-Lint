// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025-2026 Christopher Chen
import { useState, useEffect, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { FilePlus2, ShieldCheck } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { getJurisdictionConfig } from '../lib/jurisdictionConfig'
import { describeRejectedFile } from '../lib/analysisError'

export default function DropZone({ onFile, onShowProveIt, jurisdiction = 'US' }) {
  const { t } = useTranslation()
  const [badgeVisible, setBadgeVisible] = useState(false)
  const [rejectMsg, setRejectMsg] = useState('')

  useEffect(() => {
    const timer = setTimeout(() => setBadgeVisible(true), 500)
    return () => clearTimeout(timer)
  }, [])

  const jConfig = getJurisdictionConfig(jurisdiction)

  const onDrop = useCallback((acceptedFiles, rejectedFiles) => {
    setRejectMsg('')
    if (acceptedFiles.length > 0) {
      onFile(acceptedFiles[0])
      return
    }
    const hasTypeError = rejectedFiles.some(r => r.errors.some(e => e.code === 'file-invalid-type'))
    if (rejectedFiles.length > 1 && hasTypeError) {
      setRejectMsg(t(jConfig.rejectMultipleTypeKey))
    } else if (rejectedFiles.length > 1) {
      setRejectMsg(t('dropzone.rejectMultiple'))
    } else {
      // A file with a real .doc/.pdf/.rtf extension never reaches the engine
      // (this filter rejects it first), so the magic-byte detection in
      // parser/file_format.py cannot fire. Name the actual mistake here using
      // the same error.input.* copy, and fall back to the generic message
      // when the file is not one we recognise.
      const specific = hasTypeError
        ? describeRejectedFile(rejectedFiles[0]?.file, t)
        : null
      setRejectMsg(specific || t(jConfig.rejectKey))
    }
  }, [onFile, t, jConfig])

  const acceptedTypes = jConfig.acceptedFormats

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: acceptedTypes,
    maxFiles: 1,
  })

  return (
    // Parent column gets the same width cap as the dropzone (`w-full max-w-lg`)
    // so the column doesn't widen to fit a longer headline/trust-line below.
    // Without this, German's longer `Kein Upload. Keine Cloud-Verarbeitung.
    // Keine KI.` headline (~48 chars) pulls the column wider than zh-TW's
    // `無上傳。無雲端處理。無 AI。` (~14 visual units), and the dropzone's
    // `w-full max-w-lg` follows suit - making the box visibly wider in DE.
    // Capping the column makes the dropzone box width identical across locales.
    <div className="flex flex-col items-center gap-3 w-full max-w-lg">
      <div
        {...getRootProps()}
        className={`
          group shine-on-hover
          flex flex-col items-center justify-center gap-4
          w-full min-h-[280px] p-6 md:p-12 rounded-xl
          border-2 cursor-pointer
          transition-all duration-[var(--motion-duration-base)]
          ${isDragActive
            ? 'border-solid border-[var(--pass-border)] bg-blue-50/50 dark:bg-blue-950/30 scale-[1.015] shadow-[var(--frost-elevated-shadow)]'
            : 'border-dashed border-brand/35 hover:border-brand/60 dropzone-breathe shadow-[var(--frost-resting-shadow)] hover:-translate-y-0.5 hover:shadow-lg hover:shadow-brand/10 motion-reduce:hover:translate-y-0'
          }
        `}
        style={{
          backgroundImage: isDragActive ? undefined : 'var(--frost-resting-bg)',
          ...(isDragActive ? { transitionTimingFunction: 'var(--ease-bounce)' } : {}),
        }}
      >
        <input {...getInputProps()} />
        {/* Vivid gradient icon chip (brand to cyan) that springs on hover -
            the focal point, matching the sister project's icon treatment. */}
        <span
          className={`flex size-16 items-center justify-center rounded-2xl text-white shadow-lg transition-all duration-300 ease-[var(--ease-spring)] ${
            isDragActive
              ? 'scale-110 bg-[var(--pass-text)]'
              : 'bg-gradient-to-br from-brand to-accent-cyan shadow-brand/30 group-hover:scale-110 group-hover:-rotate-6 motion-reduce:group-hover:scale-100 motion-reduce:group-hover:rotate-0'
          }`}
        >
          <FilePlus2 className="h-7 w-7" />
        </span>
        <div className="text-center">
          <p className="text-base font-medium">{t(jConfig.titleKey)}</p>
          <p className="text-sm text-muted-foreground mt-1">{t('dropzone.subtitle')}</p>
          <p className="text-xs text-muted-foreground mt-2">{t(jConfig.noticeKey)}</p>
        </div>
      </div>

      {/* Security badge - bold headline (static) + clickable CTA on the
          line below. Two-line layout: the headline is the claim, the CTA
          underneath invites verification (links to airplane-mode demo via
          ProveItModal). The dropzone box's width is independent of these
          lines because the parent flex column is capped at `max-w-lg`. */}
      <div
        className="flex flex-col gap-1.5 text-sm text-green-600 dark:text-green-400 transition-opacity duration-500"
        style={{ opacity: badgeVisible ? 1 : 0 }}
      >
        <div className="flex items-start gap-2">
          <ShieldCheck className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <div className="flex flex-col gap-1">
            <strong>{t('security.badge.headline')}</strong>
            <button
              onClick={(e) => { e.stopPropagation(); onShowProveIt?.() }}
              className="text-xs text-left underline underline-offset-2 hover:text-green-700 dark:hover:text-green-300 focus-visible:text-green-700 dark:focus-visible:text-green-300 transition-colors"
            >
              {t('security.badge.proveIt')}
            </button>
          </div>
        </div>
      </div>

      {rejectMsg && (
        <p className="text-sm text-[var(--amend-text)]">
          {rejectMsg}
        </p>
      )}
    </div>
  )
}
