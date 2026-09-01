// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025-2026 Christopher Chen
//
// InfoTooltip - the hover/focus/tap explainer used on the status pill and the
// citation badge in a check row.
//
// WHY CONTROLLED. Base UI's Tooltip opens on hover and on keyboard focus, but
// deliberately not on tap - a tooltip is a pointer affordance by spec. The
// check list is explicitly a mobile target (CheckItem lays out `flex-col
// sm:flex-row`), so a tooltip a touch user can never open would be decoration.
// Holding `open` here lets one primitive serve all three input modes: hover and
// focus come from Base UI, tap comes from the trigger's own click handler.
//
// The trigger is a real <button type="button">, so it is tab-reachable and
// announces itself; `aria-label` carries the same text for screen readers,
// which never see a hover.
import * as React from "react"
import { Tooltip as TooltipPrimitive } from "@base-ui/react/tooltip"

import { cn } from "@/lib/utils"

// `delay` lives on Provider in this version of Base UI, not on Root - a
// `delay` prop passed to Root is silently ignored. Mount this once, high in
// the tree, so hover does not fire on an incidental pass over a badge.
export function InfoTooltipProvider({ children }) {
  return (
    <TooltipPrimitive.Provider delay={150} closeDelay={80}>
      {children}
    </TooltipPrimitive.Provider>
  )
}


export default function InfoTooltip({
  label,
  children,
  className,
  side = "top",
  triggerProps = {},
}) {
  const [open, setOpen] = React.useState(false)
  if (!label) return children

  return (
    <TooltipPrimitive.Root open={open} onOpenChange={setOpen}>
      <TooltipPrimitive.Trigger
        render={
          <button
            type="button"
            aria-label={label}
            onClick={(e) => {
              // Tap support. Also stops the click reaching a parent row that
              // may itself be clickable.
              e.preventDefault()
              e.stopPropagation()
              setOpen((v) => !v)
            }}
            className={cn(
              "cursor-help rounded-[3px] align-middle",
              "transition-colors duration-[var(--motion-duration-fast)]",
              "hover:brightness-[0.97] data-[popup-open]:brightness-[0.97]",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60",
              className,
            )}
            {...triggerProps}
          />
        }
      >
        {children}
      </TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Positioner
          side={side}
          sideOffset={6}
          // `align="start"` rather than the default centre: these triggers are
          // status pills and citation badges pinned to the LEFT edge of a check
          // row, so a centred popup overhangs the viewport and gets clipped -
          // observed on the REVIEW pill before this was set. Starting the popup
          // at the trigger's own left edge makes it grow rightwards into the
          // row instead. `collisionPadding` keeps it off the window edge on the
          // narrow-viewport layout.
          align="start"
          collisionPadding={8}
          className="z-50"
        >
          <TooltipPrimitive.Popup
            className={cn(
              "max-w-[min(20rem,calc(100vw-2rem))] rounded-md border border-border",
              "bg-popover px-2.5 py-1.5 text-xs leading-snug text-popover-foreground",
              "shadow-md",
              "data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95",
              "data-closed:animate-out data-closed:fade-out-0 data-closed:zoom-out-95",
            )}
          >
            {label}
          </TooltipPrimitive.Popup>
        </TooltipPrimitive.Positioner>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  )
}
