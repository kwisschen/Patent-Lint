// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
//
// StatusPill — single source of truth for PASS / REVIEW / FIX / attention
// chips across PatentLint. Replaces 7 inline implementations that all
// derived from the same --pass-* / --verify-* / --amend-* / --attention-*
// CSS-variable families with subtly different sizes and paddings.
//
// Usage:
//   <StatusPill status="pass">PASS</StatusPill>
//   <StatusPill status="amend" count={3}>FIX</StatusPill>
//   <StatusPill status="verify" size="sm" icon={<CheckCircle />}>OK</StatusPill>
//   <StatusPill status="muted">MPEP § 608.01(p)</StatusPill>   // citation-style
//
// Status meanings:
//   pass     = blue   (PatentLint's "passed check" hue)
//   verify   = green  (REVIEW — practitioner discretion)
//   amend    = red    (FIX — substantive issue)
//   attention= amber  (warnings, banner accents)
//   muted    = neutral (citation badges, non-status labels)
import * as React from "react"
import { cva } from "class-variance-authority"

import { cn } from "@/lib/utils"

const statusPillVariants = cva(
  "inline-flex items-center gap-1 font-semibold transition-colors duration-[var(--motion-duration-fast)] whitespace-nowrap",
  {
    variants: {
      status: {
        pass:
          "border bg-[var(--pass-bg)] text-[var(--pass-tag-text)] border-[var(--pass-border)]",
        verify:
          "border bg-[var(--verify-bg)] text-[var(--verify-tag-text)] border-[var(--verify-border)]",
        amend:
          "border bg-[var(--amend-bg)] text-[var(--amend-tag-text)] border-[var(--amend-border)]",
        attention:
          "border bg-[var(--attention-bg)] text-[var(--attention-tag-text)] border-[var(--attention-border)]",
        muted:
          "border bg-muted/60 text-muted-foreground border-border/60",
      },
      size: {
        xs: "rounded px-1.5 py-0.5 text-[10px] leading-none",
        sm: "rounded-md px-2 py-0.5 text-[11px] leading-tight",
        default: "rounded-md px-2.5 py-0.5 text-xs leading-tight",
        lg: "rounded-md px-3 py-1 text-sm leading-tight",
      },
      shape: {
        rounded: "",
        pill: "!rounded-full",
      },
    },
    defaultVariants: {
      status: "muted",
      size: "default",
      shape: "rounded",
    },
  }
)

function StatusPill({
  className,
  status,
  size,
  shape,
  icon,
  count,
  children,
  ...props
}) {
  return (
    <span
      data-slot="status-pill"
      data-status={status || "muted"}
      className={cn(statusPillVariants({ status, size, shape }), className)}
      {...props}
    >
      {icon ? <span className="flex shrink-0 items-center" aria-hidden="true">{icon}</span> : null}
      {children ? <span>{children}</span> : null}
      {typeof count === "number" ? (
        <span className="font-bold tabular-nums">{count}</span>
      ) : null}
    </span>
  )
}

export { StatusPill, statusPillVariants }
