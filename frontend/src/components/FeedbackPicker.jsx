// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
//
// Email picker modal + provider + hook. One shared modal lives at the
// app root via <FeedbackProvider>; any component calls
// `useFeedback().sendFeedback(email)` and the provider decides whether
// to (a) dispatch directly using the user's remembered method, or
// (b) open the picker modal for the user to choose.
//
// Design notes:
// - "Remember my choice" checkbox defaults to CHECKED. First-click is
//   one tap (pick method, it auto-saves, subsequent clicks skip the
//   modal entirely). Maximum-frictionless UX for the common case.
// - Three methods in V1: Gmail (compose URL), Outlook (compose URL),
//   and Copy to clipboard. The clipboard path works for everyone
//   regardless of email provider — universal escape hatch.
// - Clipboard write also fires for Gmail / Outlook methods (silent
//   safety net) — even a Gmail user who closes the tab by accident
//   can paste elsewhere.
// - Preference persists in localStorage across tab sessions.
import { createContext, useCallback, useContext, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { AtSign, Clipboard, Lock, Mail } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from './ui/dialog'
import { Button } from './ui/button'
import {
  dispatchFeedback,
  getFeedbackMethod,
  setFeedbackMethod,
  MAINTAINER_EMAIL,
} from '../lib/feedback'

const FeedbackContext = createContext(null)

export function FeedbackProvider({ children }) {
  const { t } = useTranslation()
  // `pending` is either null (no picker open) or `{ email, verb }` —
  // the composed email plus the action verb for button labels. verb is
  // 'report' for per-finding error flows, 'send' for footer feedback
  // and enterprise inquiries. Default 'send' if caller doesn't specify.
  const [pending, setPending] = useState(null)
  // Unchecked by default — user opts in explicitly. Avoids accidentally
  // locking users into a method they picked once but didn't love.
  const [remember, setRemember] = useState(false)

  // Dispatch + show a confirmation toast that surfaces the
  // clipboard-fallback path. Critical for `mailto:` on systems with no
  // registered protocol handler (e.g. Windows desktop without Outlook /
  // Mail / Thunderbird) — anchor click silently no-ops, modal closes,
  // and without a toast the user has no signal that anything happened.
  // For `clipboard` method the toast is the only visible confirmation.
  // Gmail / Outlook web open in a new tab so the new-tab itself is the
  // confirmation — toast still useful as a parallel signal that the
  // body has been copied (in case the tab is closed accidentally).
  const dispatchAndConfirm = useCallback((method, email) => {
    dispatchFeedback(method, email)
    if (method === 'mailto' || method === 'clipboard') {
      const titleKey = method === 'mailto'
        ? 'feedback.toast.mailto'
        : 'feedback.toast.clipboard'
      const descKey = method === 'mailto'
        ? 'feedback.toast.mailtoDescription'
        : 'feedback.toast.clipboardDescription'
      toast(t(titleKey), {
        description: t(descKey, { email: MAINTAINER_EMAIL }),
        duration: 8000,
        action: {
          label: t('feedback.toast.copyEmail'),
          onClick: () => {
            try {
              navigator.clipboard?.writeText(MAINTAINER_EMAIL)
            } catch {
              // best-effort; clipboard may be unavailable in some contexts
            }
          },
        },
      })
    }
  }, [t])

  const sendFeedback = useCallback((email, options = {}) => {
    const saved = getFeedbackMethod()
    if (saved) {
      // User previously picked + chose to remember. Dispatch directly.
      dispatchAndConfirm(saved, email)
      return
    }
    const verb = options.verb === 'report' ? 'report' : 'send'
    setPending({ email, verb })
  }, [dispatchAndConfirm])

  const handlePick = useCallback((method) => {
    if (!pending) return
    if (remember) {
      setFeedbackMethod(method)
    }
    dispatchAndConfirm(method, pending.email)
    setPending(null)
  }, [pending, remember, dispatchAndConfirm])

  const handleOpenChange = useCallback((open) => {
    if (!open) setPending(null)
  }, [])

  const verb = pending?.verb || 'send'

  return (
    <FeedbackContext.Provider value={{ sendFeedback }}>
      {children}
      <Dialog open={!!pending} onOpenChange={handleOpenChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base sm:text-lg leading-snug">
              <Lock className="h-4 w-4 shrink-0 text-green-600 dark:text-green-400" aria-hidden="true" />
              <span>{t('feedback.picker.title')}</span>
            </DialogTitle>
            <DialogDescription>
              {t(`feedback.picker.${verb}.description`)}
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-2">
            <PickerButton
              onClick={() => handlePick('mailto')}
              icon={<Mail />}
              label={t(`feedback.picker.${verb}.mailto`)}
            />
            <PickerButton
              onClick={() => handlePick('gmail')}
              icon={<AtSign />}
              label={t(`feedback.picker.${verb}.gmail`)}
            />
            <PickerButton
              onClick={() => handlePick('clipboard')}
              icon={<Clipboard />}
              label={t('feedback.picker.clipboard')}
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer mt-1">
            <input
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
              className="h-4 w-4 rounded border-border"
            />
            {t('feedback.picker.remember')}
          </label>
        </DialogContent>
      </Dialog>
    </FeedbackContext.Provider>
  )
}

function PickerButton({ onClick, icon, label }) {
  return (
    <Button
      variant="outline"
      onClick={onClick}
      className="h-auto justify-start gap-3 px-4 py-3 text-sm"
    >
      <span className="text-muted-foreground">{icon}</span>
      <span>{label}</span>
    </Button>
  )
}

export function useFeedback() {
  const ctx = useContext(FeedbackContext)
  if (!ctx) {
    throw new Error('useFeedback must be used within a FeedbackProvider')
  }
  return ctx
}
