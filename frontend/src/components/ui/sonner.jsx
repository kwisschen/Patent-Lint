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
          closeButton:
            'group-[.toast]:!bg-[var(--attention-bg)] group-[.toast]:!text-[var(--attention-text)] group-[.toast]:!border-[var(--attention-border)] group-[.toast]:opacity-70 hover:group-[.toast]:opacity-100',
        },
      }}
      {...props}
    />
  )
}
