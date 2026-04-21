import clsx from 'clsx'
import { Check } from 'lucide-react'

export default function CheckboxPill({
  checked,
  onChange,
  label,
  className,
}: {
  checked: boolean
  onChange: (v: boolean) => void
  label: string
  className?: string
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className={clsx(
        'inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold transition-all duration-150',
        'hover:scale-[1.02] active:scale-[0.98]',
        checked
          ? 'border-accent/50 bg-accent/15 text-text-primary shadow-[inset_0_1px_0_rgba(255,255,255,0.1)]'
          : 'border-border glass-light text-text-secondary hover:bg-bg-elevated hover:border-border-light',
        className,
      )}
    >
      <span
        className={clsx(
          'flex items-center justify-center h-3.5 w-3.5 rounded-full transition-all duration-150 shrink-0',
          checked ? 'bg-accent text-white scale-100' : 'bg-white/10 text-transparent scale-90',
        )}
      >
        {checked && <Check size={9} strokeWidth={3} />}
      </span>
      {label}
    </button>
  )
}
