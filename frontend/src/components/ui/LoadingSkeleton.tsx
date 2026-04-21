import clsx from 'clsx'

export default function LoadingSkeleton({ className, lines = 1 }: { className?: string; lines?: number }) {
  if (lines === 1) {
    return <div className={clsx('skeleton-shimmer h-4 rounded', className)} />
  }
  return (
    <div className={clsx('space-y-2', className)}>
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className={clsx(
            'skeleton-shimmer h-4 rounded',
            i === lines - 1 ? 'w-3/4' : 'w-full',
          )}
        />
      ))}
    </div>
  )
}
