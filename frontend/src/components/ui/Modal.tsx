import { useEffect } from 'react'
import { X } from 'lucide-react'

export default function Modal(props: {
  open: boolean
  title?: string
  onClose: () => void
  children: React.ReactNode
  widthClassName?: string
  footer?: React.ReactNode
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'full'
}) {
  const { open, onClose } = props

  const widthMap = {
    sm: 'max-w-sm',
    md: 'max-w-lg',
    lg: 'max-w-2xl',
    xl: 'max-w-4xl',
    full: 'max-w-[92vw]',
  }

  useEffect(() => {
    if (!open) return
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = ''
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center p-4 pt-[5vh]">
      {/* Backdrop */}
      <div
        className="absolute inset-0 modal-backdrop-in"
        style={{ backgroundColor: 'var(--modal-overlay)', backdropFilter: 'blur(4px)' }}
        onClick={onClose}
        aria-label="关闭弹窗"
      />
      {/* Dialog */}
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={props.title ? 'modal-title' : undefined}
        className={clsx(
          'relative glass rounded-2xl border border-border shadow-glass-lg w-full',
          'max-h-[88vh] flex flex-col overflow-hidden',
          'modal-animate-in',
          widthMap[props.size ?? 'xl']
        )}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 flex-shrink-0 border-b border-border bg-bg-elevated/80 backdrop-blur-sm">
          {props.title ? (
            <h2 id="modal-title" className="text-sm font-semibold text-text-primary tracking-tight">
              {props.title}
            </h2>
          ) : (
            <div />
          )}
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation()
              onClose()
            }}
            className={clsx(
              'flex items-center justify-center rounded-lg border border-border',
              'p-1.5 text-text-muted',
              'hover:bg-hover-overlay hover:text-text-primary hover:border-border-light',
              'transition-all duration-150 active:scale-95',
              'focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50'
            )}
            aria-label="关闭"
          >
            <X size={15} />
          </button>
        </div>
        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto px-5 py-4 min-h-0">
          <div className="space-y-3">{props.children}</div>
        </div>
        {/* Footer slot */}
        {props.footer && (
          <div className="flex-shrink-0 border-t border-border px-5 py-3 bg-bg-elevated/50 backdrop-blur-sm">
            {props.footer}
          </div>
        )}
      </div>
    </div>
  )
}

function clsx(...args: (string | boolean | undefined | null)[]): string {
  return args.filter(Boolean).join(' ')
}
