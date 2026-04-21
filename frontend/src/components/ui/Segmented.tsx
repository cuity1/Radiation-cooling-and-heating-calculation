import clsx from 'clsx'

export type SegmentedOption<T extends string> = {
  value: T
  label: string
  description?: string
}

export default function Segmented<T extends string>({
  value,
  onChange,
  options,
  className,
}: {
  value: T
  onChange: (v: T) => void
  options: Array<SegmentedOption<T>>
  className?: string
}) {
  const cols = options.length === 2 ? 'grid-cols-2' : options.length === 3 ? 'grid-cols-3' : `grid-cols-${Math.min(options.length, 3)}`

  return (
    <div className={clsx('grid gap-2', cols, className)}>
      {options.map((o) => {
        const active = o.value === value
        return (
          <button
            key={o.value}
            type="button"
            onClick={() => onChange(o.value)}
            className={clsx(
              'relative rounded-xl border px-3 py-2.5 text-left transition-all duration-200',
              'hover:scale-[1.01] hover:z-10',
              active
                ? 'border-accent/50 bg-accent/15 text-text-primary shadow-[0_0_0_1px_var(--accent),inset_0_1px_0_rgba(255,255,255,0.1)]'
                : 'border-border glass-light hover:bg-bg-elevated hover:border-border-light text-text-secondary',
            )}
          >
            {active && (
              <div className="absolute inset-0 rounded-xl bg-accent/5 pointer-events-none" />
            )}
            <div className={clsx('text-sm font-semibold', active ? 'text-text-primary' : 'text-text-secondary')}>
              {o.label}
            </div>
            {o.description ? (
              <div className={clsx('mt-0.5 text-[11px]', active ? 'text-text-muted' : 'text-text-tertiary')}>
                {o.description}
              </div>
            ) : null}
          </button>
        )
      })}
    </div>
  )
}
