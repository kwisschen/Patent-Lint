// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
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
import { Mail, Inbox, AtSign, Clipboard } from 'lucide-react'
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
} from '../lib/feedback'

const FeedbackContext = createContext(null)

export function FeedbackProvider({ children }) {
  const { t } = useTranslation()
  // `pending` is either null (no picker open) or the composed email
  // waiting for the user's method choice.
  const [pending, setPending] = useState(null)
  const [remember, setRemember] = useState(true)

  const sendFeedback = useCallback((email) => {
    const saved = getFeedbackMethod()
    if (saved) {
      // User previously picked a method AND chose to remember. Dispatch
      // directly — no modal, one-click UX.
      dispatchFeedback(saved, email, t)
      return
    }
    // No saved preference: open the picker.
    setPending(email)
  }, [t])

  const handlePick = useCallback((method) => {
    if (!pending) return
    if (remember) {
      setFeedbackMethod(method)
    }
    dispatchFeedback(method, pending, t)
    setPending(null)
  }, [pending, remember, t])

  const handleOpenChange = useCallback((open) => {
    if (!open) setPending(null)
  }, [])

  return (
    <FeedbackContext.Provider value={{ sendFeedback }}>
      {children}
      <Dialog open={!!pending} onOpenChange={handleOpenChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('feedback.picker.title')}</DialogTitle>
            <DialogDescription>
              {t('feedback.picker.description')}
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-2">
            <PickerButton
              onClick={() => handlePick('gmail')}
              icon={<Mail />}
              label={t('feedback.picker.gmail')}
            />
            <PickerButton
              onClick={() => handlePick('outlook')}
              icon={<Inbox />}
              label={t('feedback.picker.outlook')}
            />
            <PickerButton
              onClick={() => handlePick('mailto')}
              icon={<AtSign />}
              label={t('feedback.picker.mailto')}
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
