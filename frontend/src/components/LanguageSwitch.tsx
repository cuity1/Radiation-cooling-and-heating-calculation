import { useTranslation } from 'react-i18next'
import clsx from 'clsx'

const LANGS: Array<{ code: 'zh' | 'en'; label: string }> = [
  { code: 'zh', label: '中文' },
  { code: 'en', label: 'EN' },
]

export default function LanguageSwitch() {
  const { i18n } = useTranslation()
  const current = (i18n.language || 'zh') as 'zh' | 'en'

  return (
    <div className="flex items-center glass-light rounded-field border border-border p-0.5">
      {LANGS.map((l) => {
        const active = l.code === current
        return (
          <button
            key={l.code}
            type="button"
            onClick={() => i18n.changeLanguage(l.code)}
            className={clsx(
              'rounded-lg px-3 py-1.5 text-xs font-semibold transition-all duration-150',
              active
                ? 'bg-accent/20 text-text-primary border border-accent/30 shadow-[inset_0_1px_0_rgba(255,255,255,0.1)]'
                : 'text-text-secondary hover:bg-white/[0.04] hover:text-text-primary',
            )}
          >
            {l.label}
          </button>
        )
      })}
    </div>
  )
}
