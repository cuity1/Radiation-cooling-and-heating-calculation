import { PropsWithChildren } from 'react'
import clsx from 'clsx'

export function Card({ className, children }: PropsWithChildren<{ className?: string }>) {
  return (
    <div
      className={clsx(
        'glass rounded-2xl border border-border p-5 shadow-glass transition-all duration-250',
        'hover:shadow-glass-lg hover:border-border-light card-lift',
        className,
      )}
    >
      {children}
    </div>
  )
}

export function CardHeader({ className, children }: PropsWithChildren<{ className?: string }>) {
  return <div className={clsx('mb-4', className)}>{children}</div>
}

export function CardTitle({ className, children }: PropsWithChildren<{ className?: string }>) {
  return (
    <div className={clsx('text-base font-semibold text-text-primary tracking-tight', className)}>
      {children}
    </div>
  )
}

export function CardDesc({ className, children }: PropsWithChildren<{ className?: string }>) {
  return (
    <div
      className={clsx(
        'mt-1.5 text-sm text-text-secondary leading-relaxed whitespace-pre-line',
        className,
      )}
    >
      {children}
    </div>
  )
}
