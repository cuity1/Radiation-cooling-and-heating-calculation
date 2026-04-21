import clsx from 'clsx'

export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  loading = false,
  icon,
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'xs' | 'sm' | 'md' | 'lg'
  loading?: boolean
  icon?: React.ReactNode
}) {
  const base =
    'inline-flex items-center justify-center gap-2 rounded-field font-semibold transition-all duration-200 ' +
    'focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 focus-visible:ring-offset-2 focus-visible:ring-offset-bg ' +
    'disabled:opacity-35 disabled:cursor-not-allowed disabled:transform-none ' +
    'active:scale-[0.97] select-none'

  const variantClass = {
    primary:
      'bg-accent text-white border border-accent/40 ' +
      'hover:bg-accent/90 hover:border-accent/60 hover:shadow-glow ' +
      'shadow-sm',
    secondary:
      'glass-light text-text-primary border border-border ' +
      'hover:bg-bg-elevated hover:border-border-light hover:shadow-glass hover:scale-[1.01] ' +
      'shadow-sm',
    ghost:
      'bg-transparent text-text-secondary border border-transparent ' +
      'hover:bg-hover-overlay hover:text-text-primary hover:border-border hover:scale-[1.01]',
    danger:
      'bg-danger/15 text-text-primary border border-danger/40 ' +
      'hover:bg-danger/25 hover:border-danger/60 hover:shadow-[0_0_0_1px_rgba(255,69,58,0.2),0_4px_12px_rgba(255,69,58,0.1)] ' +
      'shadow-sm',
  }[variant]

  const sizeClass = {
    xs: 'px-2.5 py-1 text-[11px]',
    sm: 'px-3.5 py-1.5 text-xs',
    md: 'px-4.5 py-2.5 text-sm',
    lg: 'px-6 py-3 text-sm',
  }[size]

  return (
    <button
      className={clsx(base, variantClass, sizeClass, className)}
      disabled={props.disabled || loading}
      {...props}
    >
      {loading ? (
        <>
          <svg
            className="animate-spin h-3.5 w-3.5 shrink-0"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
            />
          </svg>
          <span>{children}</span>
        </>
      ) : (
        <>
          {icon && <span className="shrink-0">{icon}</span>}
          {children}
        </>
      )}
    </button>
  )
}
