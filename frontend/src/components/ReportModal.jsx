// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025–2026 Christopher Chen
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
import {
  buildReportPayload,
  FIELD_LABEL_KEYS,
  USER_COMMENT_MAX_CHARS,
} from '@/lib/feedback'

export default function ReportModal({
  open,
  onOpenChange,
  checkKey,
  jurisdiction,
  locale,
  diagnostics,
  onConfirm,
  onMailtoFallback,
  initialDisposition,
  batchMode = false,
  batchCount = 0,
}) {
  const { t } = useTranslation()
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState(null)
  const [userComment, setUserComment] = useState('')
  // Disposition makes the feedback a first-class LABEL (ADR-159): the reporter
  // says whether this flag is a false positive or a confirmed real issue.
  // Starts UNSET — the button now reads "Send feedback" (not "Looks wrong"),
  // so we don't pre-bias toward false_positive; the reporter must choose, which
  // keeps the confirmed-catch (TP) gold honest.
  const [disposition, setDisposition] = useState(null)

  useEffect(() => {
    if (open) {
      setSubmitting(false)
      setResult(null)
      setUserComment('')
      setDisposition(initialDisposition || null)
    }
  }, [open, initialDisposition])

  // Build the exact wire payload using the same helper sendReport
  // uses. The user sees what's actually transmitted; no separate
  // "preview" rendering that could diverge. The user-comment field
  // re-renders on every keystroke so the preview reflects the wire
  // payload at all times.
  const payload = useMemo(
    () =>
      buildReportPayload({
        checkKey,
        jurisdiction,
        locale,
        diagnostics: diagnostics || {},
        userComment,
        disposition,
      }),
    [checkKey, jurisdiction, locale, diagnostics, userComment, disposition],
  )

  // Preview omits the comment from the JSON-style list — it's rendered
  // separately in its own block so the user can see their input
  // verbatim (more honest than dropping it into a sorted key:value list).
  const entries = useMemo(
    () => Object.entries(payload)
      .filter(([k]) => k !== 'user_comment')
      .sort(([a], [b]) => a.localeCompare(b)),
    [payload],
  )

  const trimmedComment = userComment.trim()
  const commentCharsLeft = USER_COMMENT_MAX_CHARS - userComment.length

  const handleSend = async () => {
    setSubmitting(true)
    const outcome = await onConfirm(trimmedComment || null, disposition)
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

        {batchMode ? (
          // Batch (section-level) report: a single blanket FP/TP verdict would
          // mislabel the mixed real/false findings in a §112 section, so batch
          // sends carry NO disposition — each finding is triaged on its merits.
          <div className="rounded-md border border-border/60 bg-muted/40 px-3 py-2 text-xs leading-snug text-muted-foreground">
            {t('feedback.reportModal.batchNote', { count: batchCount })}
          </div>
        ) : (
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-muted-foreground">
            {t('feedback.reportModal.dispositionHeading')}
          </p>
          <div className="grid grid-cols-2 gap-2">
            {['false_positive', 'confirmed_defect'].map((d) => {
              const active = disposition === d
              // Faint red (false positive) / green (correct catch) tints carry
              // the meaning without X / check glyphs — cleaner and
              // language-agnostic. The tint deepens + gains a ring when active.
              const tint = d === 'false_positive'
                ? (active
                    ? 'border-red-400 bg-red-50 ring-1 ring-red-300 dark:border-red-700 dark:bg-red-950/40 dark:ring-red-800'
                    : 'border-red-200/70 bg-red-50/40 hover:bg-red-50/80 dark:border-red-900/40 dark:bg-red-950/15 dark:hover:bg-red-950/30')
                : (active
                    ? 'border-emerald-500 bg-emerald-50 ring-1 ring-emerald-300 dark:border-emerald-700 dark:bg-emerald-950/40 dark:ring-emerald-800'
                    : 'border-emerald-200/70 bg-emerald-50/40 hover:bg-emerald-50/80 dark:border-emerald-900/40 dark:bg-emerald-950/15 dark:hover:bg-emerald-950/30')
              return (
                <button
                  key={d}
                  type="button"
                  onClick={() => setDisposition(d)}
                  disabled={submitting || result === 'success'}
                  aria-pressed={active}
                  className={`rounded-md border px-3 py-2 text-left text-xs transition-colors ${tint}`}
                >
                  <span className="block font-medium text-foreground">
                    {t(`feedback.reportModal.disposition.${d}.label`)}
                  </span>
                  <span className="mt-0.5 block text-[11px] leading-snug text-muted-foreground">
                    {t(`feedback.reportModal.disposition.${d}.hint`)}
                  </span>
                </button>
              )
            })}
          </div>
          <p className="text-[11px] leading-snug text-muted-foreground">
            {t('feedback.reportModal.dispositionWhy')}
          </p>
        </div>
        )}

        <div className="frost-card !rounded-md p-3">
          <p className="mb-2 text-xs font-medium text-muted-foreground">
            {t('feedback.reportModal.previewHeading')}
          </p>
          <pre className="max-h-72 overflow-y-auto overflow-x-auto text-xs font-mono leading-5 text-foreground/90 whitespace-pre-wrap break-all">
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

        {/* Optional free-form user comment. Wire payload is the
            de-identified diagnostic; this box is the ONE field that
            carries user-authored text. The notice immediately below
            makes the not-de-identified nature explicit so the user can
            decide whether to type. */}
        <div className="space-y-1">
          <label
            htmlFor="report-modal-user-comment"
            className="text-xs font-medium text-muted-foreground"
          >
            {t('feedback.reportModal.commentLabel')}
          </label>
          <textarea
            id="report-modal-user-comment"
            value={userComment}
            onChange={(e) => setUserComment(e.target.value.slice(0, USER_COMMENT_MAX_CHARS))}
            disabled={submitting || result === 'success'}
            maxLength={USER_COMMENT_MAX_CHARS}
            rows={6}
            placeholder={t('feedback.reportModal.commentPlaceholder')}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-y min-h-[7rem] max-h-[60vh]"
          />
          <div className="flex justify-between text-[11px] text-muted-foreground">
            <span>{t('feedback.reportModal.commentNotice')}</span>
            {userComment.length > 0 && (
              <span className={commentCharsLeft < 200 ? 'text-amber-700 dark:text-amber-400' : ''}>
                {commentCharsLeft}
              </span>
            )}
          </div>
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
            disabled={submitting || result === 'success' || (!disposition && !batchMode)}
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
