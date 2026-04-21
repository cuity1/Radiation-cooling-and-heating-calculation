import clsx from 'clsx'

export default function Input(props: React.InputHTMLAttributes<HTMLInputElement> & { error?: boolean }) {
  return (
    <input
      {...props}
      className={clsx(
        'w-full rounded-field border px-3.5 py-2.5 text-sm text-text-primary transition-all duration-150',
        'placeholder:text-text-muted',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 focus-visible:border-accent/50',
        'hover:border-border-light',
        props.error
          ? 'border-danger/50 bg-danger/5 focus:border-danger/50'
          : 'border-border glass-light focus:bg-bg-elevated',
        props.disabled && 'opacity-50 cursor-not-allowed',
        props.className,
      )}
    />
  )
}

export function Textarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement> & { error?: boolean }) {
  return (
    <textarea
      {...props}
      className={clsx(
        'w-full rounded-field border px-3.5 py-2.5 text-sm text-text-primary transition-all duration-150 resize-none',
        'placeholder:text-text-muted',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 focus-visible:border-accent/50',
        'hover:border-border-light',
        props.error
          ? 'border-danger/50 bg-danger/5 focus:border-danger/50'
          : 'border-border glass-light focus:bg-bg-elevated',
        props.disabled && 'opacity-50 cursor-not-allowed',
        props.className,
      )}
    />
  )
}
