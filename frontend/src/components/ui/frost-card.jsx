// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
//
// FrostCard — translucent layered surface used across PatentLint for
// cards, panels, and hero blocks. Backed by --frost-{tier}-* CSS tokens
// in index.css with full light + dark mode parity. Pair with the
// `frost-blur-*` utility classes for actual backdrop blur on supporting
// browsers.
//
// Usage:
//   <FrostCard tier="resting">…</FrostCard>            // most cards
//   <FrostCard tier="elevated">…</FrostCard>           // emphasized cards
//   <FrostCard tier="hero">…</FrostCard>               // top-of-page heroes
//   <FrostCard accent="amend">…</FrostCard>            // accented left border
//   <FrostCard tier="elevated" interactive>…</FrostCard>  // hover lift
import * as React from "react"
import { cva } from "class-variance-authority"

import { cn } from "@/lib/utils"

const frostCardVariants = cva(
  // Base — overflow-hidden contains the inner-light highlight, ring uses
  // the frost-border var so it tracks light/dark automatically.
  "relative overflow-hidden rounded-xl text-card-foreground transition-shadow duration-[var(--motion-duration-base)]",
  {
    variants: {
      tier: {
        resting:
          "bg-[image:var(--frost-resting-bg)] ring-1 ring-[var(--frost-resting-border)] shadow-[var(--frost-resting-shadow),var(--frost-resting-inner-light)]",
        elevated:
          "bg-[image:var(--frost-elevated-bg)] ring-1 ring-[var(--frost-elevated-border)] shadow-[var(--frost-elevated-shadow),var(--frost-elevated-inner-light)]",
        hero:
          "bg-[image:var(--frost-hero-bg)] ring-1 ring-[var(--frost-hero-border)] shadow-[var(--frost-hero-shadow),var(--frost-hero-inner-light)]",
      },
      accent: {
        none: "",
        pass:
          "before:pointer-events-none before:absolute before:inset-y-0 before:left-0 before:w-1 before:rounded-l-xl before:bg-[var(--pass-border)]",
        verify:
          "before:pointer-events-none before:absolute before:inset-y-0 before:left-0 before:w-1 before:rounded-l-xl before:bg-[var(--verify-border)]",
        amend:
          "before:pointer-events-none before:absolute before:inset-y-0 before:left-0 before:w-1 before:rounded-l-xl before:bg-[var(--amend-border)]",
        attention:
          "before:pointer-events-none before:absolute before:inset-y-0 before:left-0 before:w-1 before:rounded-l-xl before:bg-[var(--attention-border)]",
      },
      interactive: {
        true: "cursor-pointer hover:-translate-y-0.5 hover:shadow-[var(--frost-elevated-shadow),var(--frost-elevated-inner-light)]",
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
  asChild = false,
  ...props
}) {
  const Comp = asChild ? React.Fragment : "div"
  if (asChild) {
    return <>{props.children}</>
  }
  return (
    <Comp
      data-slot="frost-card"
      data-tier={tier || "resting"}
      data-accent={accent || "none"}
      className={cn(frostCardVariants({ tier, accent, interactive }), className)}
      {...props}
    />
  )
}

export { FrostCard, frostCardVariants }
