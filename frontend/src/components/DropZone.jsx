// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2025 Christopher Chen
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
    <div className="flex flex-col items-center gap-3">
      <div
        {...getRootProps()}
        className={`
          flex flex-col items-center justify-center gap-4
          w-full max-w-lg p-12 rounded-lg
          border-2 cursor-pointer
          transition-all duration-200
          ${isDragActive
            ? 'border-solid border-[var(--pass-border)] bg-blue-50/50 dark:bg-blue-950/30 scale-[1.015]'
            : 'border-dashed border-gray-300 dark:border-gray-600 hover:border-muted-foreground/50 dropzone-breathe'
          }
        `}
        style={isDragActive ? { transitionTimingFunction: 'var(--ease-bounce)' } : undefined}
      >
        <input {...getInputProps()} />
        <FilePlus2 className={`h-10 w-10 transition-colors duration-200 ${isDragActive ? 'text-[var(--pass-text)]' : 'text-muted-foreground'}`} />
        <div className="text-center">
          <p className="text-base font-medium">{t(jConfig.titleKey)}</p>
          <p className="text-sm text-muted-foreground mt-1">{t('dropzone.subtitle')}</p>
          <p className="text-xs text-muted-foreground mt-2">{t(jConfig.noticeKey)}</p>
        </div>
      </div>

      {/* Security badge */}
      <div
        className="flex flex-col gap-1.5 text-sm text-green-600 dark:text-green-400 transition-opacity duration-500"
        style={{ opacity: badgeVisible ? 1 : 0 }}
      >
        <div className="flex items-start gap-2">
          <ShieldCheck className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <div className="flex flex-col gap-1">
            <strong>{t('security.badge.headline')}</strong>
            <span className="text-xs text-green-600/80 dark:text-green-400/80">
              {t('security.badge.description')}{' '}
              <button
                onClick={(e) => { e.stopPropagation(); onShowProveIt?.() }}
                className="underline underline-offset-2 hover:text-green-700 dark:hover:text-green-300 transition-colors"
              >
                {t('security.badge.proveIt')}
              </button>
            </span>
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
