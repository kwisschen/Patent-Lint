// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
//
// Anonymous error-report modal.
//
// UX flow
// -------
// 1. User clicks Report on a triage item.
// 2. Modal opens with the EXACT structural payload pre-rendered as
//    a monospace key:value list. Every field that would go over
//    the wire is visible.
// 3. User clicks "Send anonymously" → POST /api/report → toast.
// 4. OR user clicks "Cancel" → modal closes.
// 5. OR user clicks the tertiary mailto link → existing
//    FeedbackPicker mailto path (provided by parent via
//    onMailtoFallback prop).
//
// "Anonymous" appears in title, body, and primary button by design.

import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { buildReportPayload, FIELD_LABEL_KEYS } from '@/lib/feedback'

export default function ReportModal({
  open,
  onOpenChange,
  checkKey,
  jurisdiction,
  locale,
  diagnostics,
  onConfirm,
  onMailtoFallback,
}) {
  const { t } = useTranslation()
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState(null)

  useEffect(() => {
    if (open) {
      setSubmitting(false)
      setResult(null)
    }
  }, [open])

  // Build the exact wire payload using the same helper sendReport
  // uses. The user sees what's actually transmitted; no separate
  // "preview" rendering that could diverge.
  const payload = useMemo(
    () =>
      buildReportPayload({
        checkKey,
        jurisdiction,
        locale,
        diagnostics: diagnostics || {},
      }),
    [checkKey, jurisdiction, locale, diagnostics],
  )

  const entries = useMemo(
    () => Object.entries(payload).sort(([a], [b]) => a.localeCompare(b)),
    [payload],
  )

  const handleSend = async () => {
    setSubmitting(true)
    const outcome = await onConfirm()
    setSubmitting(false)
    if (outcome?.ok) {
      setResult('success')
      // Auto-close after a beat so the user sees the success state.
      setTimeout(() => onOpenChange(false), 1200)
    } else {
      setResult('failure')
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{t('feedback.reportModal.title')}</DialogTitle>
          <DialogDescription>
            {t('feedback.reportModal.body')}
          </DialogDescription>
        </DialogHeader>

        <div className="rounded-md border bg-muted/40 p-3">
          <p className="mb-2 text-xs font-medium text-muted-foreground">
            {t('feedback.reportModal.previewHeading')}
          </p>
          <pre className="overflow-x-auto text-xs font-mono leading-5 text-foreground/90 whitespace-pre-wrap break-all">
            {entries
              .map(([key, value]) => {
                const labelKey = FIELD_LABEL_KEYS[key]
                const label = labelKey ? t(labelKey) : key
                const colon = t('feedback.email.fieldColon')
                // Nested findings array: render as indented sub-block
                // so the user sees per-finding pinpoint detail (term,
                // matched_phrase, context windows, etc.) before they
                // consent to send.
                if (Array.isArray(value)) {
                  const lines = [`${label}${colon}`]
                  value.forEach((finding, i) => {
                    lines.push(`  [${i + 1}]`)
                    if (finding && typeof finding === 'object') {
                      Object.entries(finding).forEach(([k, v]) => {
                        if (v === null || v === undefined || v === '') return
                        const fLabelKey = FIELD_LABEL_KEYS[k]
                        const fLabel = fLabelKey ? t(fLabelKey) : k
                        const fv = typeof v === 'boolean' ? String(v) : (Array.isArray(v) ? v.join(', ') : v)
                        lines.push(`    ${fLabel}${colon}${fv}`)
                      })
                    } else {
                      lines.push(`    ${finding}`)
                    }
                  })
                  return lines.join('\n')
                }
                const v = typeof value === 'boolean' ? String(value) : value
                return `${label}${colon}${v}`
              })
              .join('\n')}
          </pre>
        </div>

        <p className="text-sm text-muted-foreground">
          {t('feedback.reportModal.deidNotice')}
        </p>

        {result === 'success' && (
          <p
            role="status"
            className="text-xs text-emerald-600 dark:text-emerald-400"
          >
            {t('feedback.reportModal.toastSuccess')}
          </p>
        )}
        {result === 'failure' && (
          <p
            role="alert"
            className="text-xs text-amber-700 dark:text-amber-400"
          >
            {t('feedback.reportModal.toastFailure')}
          </p>
        )}

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={submitting}
          >
            {t('feedback.reportModal.cancel')}
          </Button>
          <Button
            onClick={handleSend}
            disabled={submitting || result === 'success'}
          >
            {t('feedback.reportModal.send')}
          </Button>
        </DialogFooter>

        <button
          type="button"
          onClick={() => {
            onOpenChange(false)
            onMailtoFallback?.()
          }}
          className="mt-1 text-center text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
        >
          {t('feedback.reportModal.emailFallback')}
        </button>
      </DialogContent>
    </Dialog>
  )
}
