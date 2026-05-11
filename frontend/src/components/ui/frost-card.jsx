// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025–2026 Christopher Chen
//
// FrostCard — translucent layered surface used across PatentLint for
// cards, panels, and hero blocks. Apple LiquidGlass aesthetic adapted
// for web: backdrop blur + saturation boost so surfaces absorb hue
// from content behind them. Backed by the .frost-card-* utility
// classes in index.css (so the same look is available to non-React
// consumers via plain className).
//
// Usage:
//   <FrostCard tier="resting">…</FrostCard>            // most cards (light blur, GPU-friendly for repeats)
//   <FrostCard tier="elevated">…</FrostCard>           // emphasized cards
//   <FrostCard tier="hero">…</FrostCard>               // top-of-page hero, banner-modal heads
//   <FrostCard accent="amend">…</FrostCard>            // accented left border
//   <FrostCard tier="elevated" interactive>…</FrostCard>  // hover lift
import * as React from "react"
import { cva } from "class-variance-authority"

import { cn } from "@/lib/utils"

const frostCardVariants = cva(
  // Base — `relative` + `overflow-hidden` contains the inner-light highlight
  // and the accent ::before bar.
  "relative text-card-foreground transition-shadow duration-[var(--motion-duration-base)]",
  {
    variants: {
      tier: {
        resting: "frost-card",
        elevated: "frost-card-elevated",
        hero: "frost-card-hero",
      },
      accent: {
        none: "",
        pass:
          "before:pointer-events-none before:absolute before:inset-y-0 before:left-0 before:w-1 before:bg-[var(--pass-border)]",
        verify:
          "before:pointer-events-none before:absolute before:inset-y-0 before:left-0 before:w-1 before:bg-[var(--verify-border)]",
        amend:
          "before:pointer-events-none before:absolute before:inset-y-0 before:left-0 before:w-1 before:bg-[var(--amend-border)]",
        attention:
          "before:pointer-events-none before:absolute before:inset-y-0 before:left-0 before:w-1 before:bg-[var(--attention-border)]",
      },
      interactive: {
        true: "frost-card-interactive cursor-pointer",
        false: "",
      },
    },
    defaultVariants: {
      tier: "resting",
      accent: "none",
      interactive: false,
    },
  }
)

function FrostCard({
  className,
  tier,
  accent,
  interactive,
  ...props
}) {
  return (
    <div
      data-slot="frost-card"
      data-tier={tier || "resting"}
      data-accent={accent || "none"}
      className={cn(frostCardVariants({ tier, accent, interactive }), className)}
      {...props}
    />
  )
}

export { FrostCard, frostCardVariants }
