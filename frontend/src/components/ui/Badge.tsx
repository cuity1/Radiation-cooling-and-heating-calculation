import clsx from 'clsx'

const STATUS_DOT: Record<string, string> = {
  queued: 'bg-accent',
  started: 'bg-warning',
  succeeded: 'bg-success',
  failed: 'bg-danger',
  cancelled: 'bg-text-muted',
}

export default function Badge({
  children,
  tone = 'neutral',
  size = 'md',
  showDot = false,
  className,
}: {
  children: React.ReactNode
  tone?: 'neutral' | 'info' | 'success' | 'warning' | 'danger'
  size?: 'sm' | 'md'
  showDot?: boolean
  className?: string
}) {
  const toneClass = {
    neutral: 'bg-white/[0.06] text-text-secondary border-white/10',
    info:    'bg-accent/15 text-text-primary border-accent/30',
    success: 'bg-success/15 text-text-primary border-success/30',
    warning: 'bg-warning/15 text-text-primary border-warning/30',
    danger:  'bg-danger/15  text-text-primary border-danger/30',
  }[tone]

  const sizeClass = size === 'sm'
    ? 'px-2 py-0.5 text-[10px]'
    : 'px-2.5 py-1 text-xs'

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-full border font-semibold tracking-tight',
        'transition-all duration-150 hover:brightness-110',
        toneClass,
        sizeClass,
        className,
      )}
    >
      {showDot && (
        <span className={clsx('h-1.5 w-1.5 rounded-full shrink-0', STATUS_DOT[tone] ?? 'bg-text-muted')} />
      )}
      {children}
    </span>
  )
}
