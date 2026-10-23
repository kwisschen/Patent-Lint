// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025-2026 Christopher Chen
//
// The feedback context, provided by FeedbackProvider (components/
// FeedbackPicker.jsx). Kept apart from the provider so React fast refresh can
// treat that file as components only.
import { createContext, useContext } from 'react'

export const FeedbackContext = createContext(null)

export function useFeedback() {
  const ctx = useContext(FeedbackContext)
  if (!ctx) {
    throw new Error('useFeedback must be used within a FeedbackProvider')
  }
  return ctx
}
