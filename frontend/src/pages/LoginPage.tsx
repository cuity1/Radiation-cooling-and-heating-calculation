import { FormEvent, useState } from 'react'
import { useLocation, useNavigate, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../context/AuthContext'
import Button from '../components/ui/Button'
import { FlaskConical, Eye, EyeOff } from 'lucide-react'

export default function LoginPage() {
  const { t } = useTranslation()
  const { login, error } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const nav = useNavigate()
  const loc = useLocation() as any

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    try {
      await login(username, password)
      const from = loc.state?.from?.pathname ?? '/'
      nav(from, { replace: true })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12">
      {/* Background decoration */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 rounded-full opacity-[0.04]" style={{ background: 'radial-gradient(circle, var(--accent) 0%, transparent 70%)' }} />
        <div className="absolute bottom-1/4 right-1/4 w-80 h-80 rounded-full opacity-[0.03]" style={{ background: 'radial-gradient(circle, #BF5AF2 0%, transparent 70%)' }} />
      </div>

      <div className="w-full max-w-sm relative">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8 animate-fade-slide-up">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-accent/15 text-accent border border-accent/25 shadow-[0_0_0_1px_rgba(10,132,255,0.15),0_4px_20px_rgba(10,132,255,0.1)] mb-4">
            <FlaskConical size={28} />
          </div>
          <h1 className="text-xl font-bold text-text-primary tracking-tight">{t('auth.login')}</h1>
          <p className="text-sm text-text-muted mt-1">Sign in to your account</p>
        </div>

        {/* Card */}
        <div className="glass rounded-2xl border border-border shadow-glass-lg p-6 animate-scale-fade-in stagger-1">
          <form onSubmit={onSubmit} className="space-y-4">
            {/* Username */}
            <div>
              <label className="block text-xs font-semibold text-text-secondary mb-1.5">
                {t('auth.username')}
              </label>
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full rounded-field border border-border glass-light px-3.5 py-2.5 text-sm text-text-primary placeholder:text-text-muted transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 focus:border-accent/50 hover:border-border-light"
                placeholder={t('auth.enterUsername')}
                autoComplete="username"
              />
            </div>

            {/* Password */}
            <div>
              <label className="block text-xs font-semibold text-text-secondary mb-1.5">
                {t('auth.password')}
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-field border border-border glass-light px-3.5 py-2.5 text-sm text-text-primary placeholder:text-text-muted transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 focus:border-accent/50 hover:border-border-light pr-10"
                  placeholder={t('auth.enterPassword')}
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-secondary transition-colors p-0.5"
                >
                  {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>

            {/* Error */}
            {error ? (
              <div className="rounded-field border border-danger/30 bg-danger/10 p-2.5 text-xs text-text-secondary">
                {String(error)}
              </div>
            ) : null}

            {/* Actions */}
            <div className="flex items-center justify-between pt-1">
              <Button
                type="submit"
                variant="primary"
                loading={submitting}
                disabled={!username || !password}
                className="min-w-[100px]"
              >
                {submitting ? t('auth.loggingIn') : t('auth.login')}
              </Button>
              <Link to="/register" className="text-xs text-accent hover:text-accent/80 font-medium transition-colors">
                {t('auth.noAccount')}
              </Link>
            </div>
          </form>
        </div>

        {/* Security note */}
        <p className="text-center text-[11px] text-text-tertiary mt-5 animate-fade-slide-up stagger-2">
          {t('auth.securityNote')}
        </p>
      </div>
    </div>
  )
}
