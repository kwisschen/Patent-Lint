// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025–2026 Christopher Chen
import { Toaster as Sonner } from 'sonner'

// Manual shadcn-style wrapper for Sonner. Uses PatentLint's --attention-*
// CSS variables (amber/warm, already defined in index.css with dark-mode
// overrides). Dark mode auto-adapts via the CSS variables — no theme prop
// needed. Not generated via `npx shadcn@latest add sonner` to avoid pulling
// in next-themes or other unwanted dependencies.
export function Toaster({ ...props }) {
  return (
    <Sonner
      className="toaster group"
      position="bottom-right"
      expand
      toastOptions={{
        classNames: {
          toast:
            'group toast group-[.toaster]:bg-[var(--attention-bg)] group-[.toaster]:text-[var(--attention-text)] group-[.toaster]:border group-[.toaster]:border-[var(--attention-border)] group-[.toaster]:shadow-lg',
          title: 'group-[.toast]:font-medium',
          description: 'group-[.toast]:opacity-90',
          actionButton:
            'group-[.toast]:bg-[var(--attention-text)] group-[.toast]:text-[var(--attention-bg)] group-[.toast]:rounded-md group-[.toast]:px-3 group-[.toast]:py-1.5 group-[.toast]:font-medium group-[.toast]:text-sm group-[.toast]:ml-auto',
          cancelButton:
            'group-[.toast]:bg-transparent group-[.toast]:text-[var(--attention-text)] group-[.toast]:opacity-70 hover:group-[.toast]:opacity-100 group-[.toast]:px-3 group-[.toast]:py-1.5 group-[.toast]:text-sm',
          // Monochrome close button — neutral B&W contrast against the
          // warm/amber toast palette so it reads as a system control,
          // not part of the toast's content. Inverse colors auto-flip
          // between light and dark mode via CSS variables (foreground
          // is dark in light mode + light in dark mode; background is
          // the reverse). Filled-inverse is "eye-catching enough"
          // without competing with the toast's amber attention.
          closeButton:
            'group-[.toast]:!bg-[var(--foreground)] group-[.toast]:!text-[var(--background)] group-[.toast]:!border-transparent group-[.toast]:opacity-90 hover:group-[.toast]:opacity-100 group-[.toast]:transition-opacity',
        },
      }}
      {...props}
    />
  )
}
