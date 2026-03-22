import { useTranslation } from 'react-i18next'

export default function CheckItem({ status, message, message_key, details }) {
  const { t, i18n } = useTranslation()
  const displayMessage = message_key && i18n.exists(message_key) ? t(message_key) : message

  return (
    <div
      className="py-2 px-3 border-l-[3px]"
      style={{ borderLeftColor: `var(--${status}-border)` }}
    >
      <div className="flex items-center gap-2">
        <span
          className="inline-block rounded px-1.5 py-0.5 text-[10px] font-bold uppercase leading-none"
          style={{
            backgroundColor: `var(--${status}-bg)`,
            color: `var(--${status}-tag-text)`,
          }}
        >
          {t(`status.${status}`)}
        </span>
        <span className="text-sm">{displayMessage}</span>
      </div>
      {details && (
        <p className="text-xs text-muted-foreground mt-1 ml-[52px]">{details}</p>
      )}
    </div>
  )
}
