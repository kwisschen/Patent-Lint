// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025–2026 Christopher Chen
import { useState, useEffect, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { FilePlus2, ShieldCheck } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { getJurisdictionConfig } from '../lib/jurisdictionConfig'

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
      setRejectMsg(t(jConfig.rejectKey))
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
    // `w-full max-w-lg` follows suit — making the box visibly wider in DE.
    // Capping the column makes the dropzone box width identical across locales.
    <div className="flex flex-col items-center gap-3 w-full max-w-lg">
      <div
        {...getRootProps()}
        className={`
          shine-on-hover
          flex flex-col items-center justify-center gap-4
          w-full min-h-[280px] p-6 md:p-12 rounded-xl
          border-2 cursor-pointer
          transition-all duration-[var(--motion-duration-base)]
          ${isDragActive
            ? 'border-solid border-[var(--pass-border)] bg-blue-50/50 dark:bg-blue-950/30 scale-[1.015] shadow-[var(--frost-elevated-shadow)]'
            : 'border-dashed border-gray-300 dark:border-gray-600 hover:border-muted-foreground/50 dropzone-breathe shadow-[var(--frost-resting-shadow)]'
          }
        `}
        style={{
          backgroundImage: isDragActive ? undefined : 'var(--frost-resting-bg)',
          ...(isDragActive ? { transitionTimingFunction: 'var(--ease-bounce)' } : {}),
        }}
      >
        <input {...getInputProps()} />
        <FilePlus2 className={`h-12 w-12 transition-colors duration-200 ${isDragActive ? 'text-[var(--pass-text)]' : 'text-muted-foreground'}`} />
        <div className="text-center">
          <p className="text-base font-medium">{t(jConfig.titleKey)}</p>
          <p className="text-sm text-muted-foreground mt-1">{t('dropzone.subtitle')}</p>
          <p className="text-xs text-muted-foreground mt-2">{t(jConfig.noticeKey)}</p>
        </div>
      </div>

      {/* Security badge — bold headline (static) + clickable CTA on the
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
