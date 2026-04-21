import { PropsWithChildren, useState, useEffect } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { FlaskConical, Home, ListChecks, Snowflake, Flame, Settings, Wrench, Upload, Map, MessageCircle, BotMessageSquare, Info, ChevronDown, ChevronRight, LogOut } from 'lucide-react'
import clsx from 'clsx'
import LanguageSwitch from '../components/LanguageSwitch'
import ThemeSwitch from '../components/ThemeSwitch'
import Button from '../components/ui/Button'
import { useAuth } from '../context/AuthContext'
import { redeemCdk, changePassword } from '../services/auth'

function NavItem(props: { to: string; label: string; icon: React.ReactNode; badge?: string; onClick?: () => void }) {
  const loc = useLocation()
  const toPath = props.to.split('?')[0]
  const toSearchParams = props.to.includes('?') ? new URLSearchParams(props.to.split('?')[1]) : null
  const currentSearchParams = new URLSearchParams(loc.search)

  let active = loc.pathname === toPath
  if (active && toSearchParams) {
    for (const [key, value] of toSearchParams.entries()) {
      if (currentSearchParams.get(key) !== value) {
        active = false
        break
      }
    }
  }

  const isClickable = props.onClick !== undefined

  return (
    <Link
      to={props.to}
      onClick={isClickable ? props.onClick : undefined}
      className={clsx(
        'group flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm transition-all duration-200',
        active
          ? 'bg-accent/15 text-text-primary border border-accent/30 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]'
          : 'text-text-secondary hover:bg-white/[0.04] hover:text-text-primary border border-transparent',
      )}
    >
      <span className={clsx(
        'transition-all duration-200',
        active ? 'text-accent' : 'text-text-muted group-hover:text-text-secondary',
      )}>
        {props.icon}
      </span>
      <span className="font-medium tracking-tight flex-1">{props.label}</span>
      {props.badge && (
        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-accent/20 text-accent font-semibold">
          {props.badge}
        </span>
      )}
    </Link>
  )
}

export default function ShellLayout({ children }: PropsWithChildren) {
  const { t } = useTranslation()
  const { user, logout } = useAuth()
  const nav = useNavigate()
  const loc = useLocation()
  const [cdk, setCdk] = useState('')
  const [cdkMsg, setCdkMsg] = useState<string | null>(null)
  const [cdkLoading, setCdkLoading] = useState(false)
  const [cdkModalOpen, setCdkModalOpen] = useState(false)
  const [shouldBlink, setShouldBlink] = useState(false)
  const [proFeaturesExpanded, setProFeaturesExpanded] = useState(false)
  const [changePwModalOpen, setChangePwModalOpen] = useState(false)
  const [changePwOld, setChangePwOld] = useState('')
  const [changePwNew, setChangePwNew] = useState('')
  const [changePwConfirm, setChangePwConfirm] = useState('')
  const [changePwMsg, setChangePwMsg] = useState<string | null>(null)
  const [changePwLoading, setChangePwLoading] = useState(false)

  useEffect(() => {
    if (user) {
      const hasClickedConfig = localStorage.getItem(`config_clicked_${user.username}`)
      if (!hasClickedConfig) setShouldBlink(true)
    } else {
      setShouldBlink(false)
    }
  }, [user])

  useEffect(() => {
    if (user && loc.pathname === '/config' && shouldBlink) {
      localStorage.setItem(`config_clicked_${user.username}`, 'true')
      setShouldBlink(false)
    }
  }, [loc.pathname, user, shouldBlink])

  const handleConfigClick = () => {
    if (user && shouldBlink) {
      localStorage.setItem(`config_clicked_${user.username}`, 'true')
      setShouldBlink(false)
    }
  }

  const handleChangePasswordSubmit = async () => {
    if (changePwNew !== changePwConfirm) {
      setChangePwMsg(t('account.passwordsDoNotMatch'))
      return
    }
    setChangePwMsg(null)
    setChangePwLoading(true)
    try {
      await changePassword(changePwOld, changePwNew)
      setChangePwMsg(t('account.passwordChanged'))
      setTimeout(() => {
        setChangePwModalOpen(false)
        setChangePwMsg(null)
        setChangePwOld('')
        setChangePwNew('')
        setChangePwConfirm('')
      }, 1200)
    } catch (e: any) {
      const detail = e?.response?.data?.detail
      if (detail === 'incorrect_old_password') setChangePwMsg(t('account.incorrectOldPassword'))
      else setChangePwMsg(detail || t('common.error'))
    } finally {
      setChangePwLoading(false)
    }
  }

  const navSection = (label: string, children: React.ReactNode) => (
    <div>
      {label && (
        <div className="px-2 pt-1 pb-2 text-[10px] font-bold uppercase tracking-widest text-text-tertiary">
          {label}
        </div>
      )}
      <nav className="flex flex-col gap-0.5">{children}</nav>
    </div>
  )

  return (
    <div className="min-h-screen">
      <div className="mx-auto max-w-7xl px-4 py-6 md:px-6">
        {/* ── Header ── */}
        <header className="mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between animate-fade-slide-up">
          <div className="flex items-start gap-3.5">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-accent/15 text-accent border border-accent/25 shadow-[0_0_0_1px_rgba(10,132,255,0.15),0_4px_16px_rgba(10,132,255,0.1)]">
              <FlaskConical size={22} />
            </div>
            <div className="min-w-0">
              <div className="text-xl font-bold tracking-tight text-text-primary leading-tight">
                {t('app.title')}
              </div>
              <div className="text-sm text-text-secondary mt-0.5">{t('app.subtitle')}</div>
            </div>
          </div>

          <div className="flex items-center gap-2.5 flex-wrap">
            {/* Quick actions */}
            <div className="hidden lg:flex items-center gap-1.5 glass rounded-xl px-2 py-1 border border-border text-[11px] text-text-muted">
              <span className="font-mono text-text-secondary">API</span>
              <span className="opacity-50">:</span>
              <span className="font-mono text-text-secondary">/api</span>
            </div>

            {user ? (
              <div className="flex items-center gap-2">
                <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-white/[0.04] border border-border text-xs text-text-secondary">
                  <span className="font-medium">{user.username}</span>
                  <span className="text-text-tertiary opacity-60">·</span>
                  <span className="text-text-muted">{user.role}</span>
                  <span className="text-text-tertiary opacity-60">·</span>
                  <span className={user.tier === 'pro' ? 'text-accent font-semibold' : 'text-text-muted'}>
                    {user.tier}
                  </span>
                </div>
              </div>
            ) : null}

            <Link to="/config" onClick={handleConfigClick} className="hidden md:block">
              <Button
                variant="secondary"
                size="sm"
                icon={<Settings size={13} className={shouldBlink ? 'animate-spin' : ''} />}
                className={clsx(
                  shouldBlink && 'animate-blink-glow ring-2 ring-accent/50',
                )}
              >
                {t('nav.config')}
              </Button>
            </Link>

            {!user && (
              <Link to="/login">
                <Button variant="primary" size="sm">{t('auth.login')}</Button>
              </Link>
            )}
            {user && (
              <Button
                size="sm"
                variant="ghost"
                icon={<LogOut size={13} />}
                onClick={async () => { await logout(); nav('/login', { replace: true }) }}
                className="text-text-muted hover:text-text-secondary"
              >
                <span className="hidden sm:inline">{t('auth.logout')}</span>
              </Button>
            )}

            <div className="hidden md:flex items-center gap-1.5">
              <LanguageSwitch />
              <ThemeSwitch />
            </div>
          </div>
        </header>

        {/* ── Mobile language / theme ── */}
        <div className="flex md:hidden items-center gap-2 mb-4 -mt-1">
          <LanguageSwitch />
          <ThemeSwitch />
        </div>

        {/* ── Main content grid ── */}
        <div className="grid grid-cols-1 gap-5 md:grid-cols-[240px_1fr] xl:grid-cols-[260px_1fr]">
          {/* ── Sidebar ── */}
          <aside className="glass rounded-2xl p-3.5 shadow-glass animate-fade-slide-left stagger-1">
            <nav className="flex flex-col gap-0.5">
              {navSection(t('nav.section'), <>
                <NavItem to="/" label={t('nav.home')} icon={<Home size={16} />} />
                <NavItem to="/uploads" label={t('nav.uploads')} icon={<Upload size={16} />} />
                <NavItem to="/jobs/new?type=cooling" label={t('modules.cooling.title')} icon={<Snowflake size={16} />} />
                <NavItem to="/jobs/new?type=heating" label={t('modules.heating.title')} icon={<Flame size={16} />} />
                <NavItem to="/tools" label={t('nav.tools')} icon={<Wrench size={16} />} />
              </>)}

              {/* Pro features collapsible */}
              <NavItem
                to="#"
                label={t('nav.proFeatures')}
                icon={<ChevronRight size={15} className={clsx(
                  'text-text-muted transition-transform duration-200',
                  proFeaturesExpanded && 'rotate-90'
                )} />}
                onClick={() => setProFeaturesExpanded(!proFeaturesExpanded)}
              />
              {proFeaturesExpanded && (
                <div className="ml-3 flex flex-col gap-0.5 border-l border-border/50 pl-3 animate-fade-slide-up">
                  <NavItem to="/jobs/new?type=in_situ_simulation" label={t('nav.inSituSimulation')} icon={<Snowflake size={15} />} />
                  <NavItem to="/map" label={t('nav.mapDrawing')} icon={<Map size={15} />} />
                  <NavItem to="/glass-map" label={t('nav.glassComparison')} icon={<Map size={15} />} />
                </div>
              )}

              {navSection('', <>
                <NavItem to="/qa" label={t('nav.qa')} icon={<MessageCircle size={15} />} />
                <NavItem to="/ai-chat" label={t('nav.aiChat')} icon={<BotMessageSquare size={15} />} />
                <a
                  href="https://qun.qq.com/universal-share/share"
                  target="_blank"
                  rel="noreferrer"
                  className="group flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm transition-all duration-200 text-text-secondary hover:bg-white/[0.04] hover:text-text-primary border border-transparent"
                >
                  <span className="text-text-muted group-hover:text-text-secondary transition-all duration-200">
                    <Info size={15} />
                  </span>
                  <span className="font-medium tracking-tight">{t('nav.consultDetails')}</span>
                </a>
                <NavItem to="/config" label={t('nav.config')} icon={<Settings size={15} />} />
                <NavItem to="/jobs" label={t('nav.jobs')} icon={<ListChecks size={15} />} />
                {user?.role === 'admin' && (
                  <NavItem to="/admin" label={t('nav.admin')} icon={<Settings size={15} />} badge="PRO" />
                )}
              </>)}
            </nav>

            {/* Tip card */}
            <div className="mt-3 p-3 rounded-xl bg-accent/8 border border-accent/20">
              <div className="text-xs font-semibold text-text-primary mb-1">{t('nav.tipTitle')}</div>
              <div className="text-[11px] leading-relaxed text-text-secondary">{t('nav.tipBody')}</div>
            </div>

            {/* Account card */}
            {user ? (
              <div className="mt-3 p-3 rounded-xl bg-white/[0.04] border border-border/60 space-y-2">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="text-xs font-semibold text-text-primary">{t('account.center')}</div>
                    <div className="mt-0.5 text-[11px] text-text-secondary font-mono">{user.username}</div>
                  </div>
                  {user.tier === 'normal' && (
                    <Button
                      size="xs"
                      variant="ghost"
                      className="text-[10px] text-accent hover:bg-accent/10"
                      onClick={() => { setCdk(''); setCdkMsg(null); setCdkModalOpen(true) }}
                    >
                      {t('account.upgrade')}
                    </Button>
                  )}
                </div>
                {user.tier === 'pro' && user.pro_expires_at && (
                  <div className="text-[10px] text-accent/80">
                    PRO · {new Date(user.pro_expires_at).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' })}
                  </div>
                )}
                {user.tier === 'normal' && (
                  <div className="text-[10px] text-text-muted">{t('account.upgradeDesc')}</div>
                )}
                <button
                  onClick={() => { setChangePwOld(''); setChangePwNew(''); setChangePwConfirm(''); setChangePwMsg(null); setChangePwModalOpen(true) }}
                  className="w-full text-center text-[10px] text-text-muted hover:text-text-secondary transition-colors py-0.5"
                >
                  {t('account.changePassword')}
                </button>
              </div>
            ) : null}
          </aside>

          {/* ── Main ── */}
          <main className="glass rounded-2xl p-5 md:p-6 shadow-glass animate-fade-slide-up stagger-2">
            {children}
          </main>
        </div>

        {/* ── Footer ── */}
        <footer className="mt-6 text-center text-[11px] text-text-tertiary">
          Radiation Cooling &amp; Heating Calculation · Web Platform
        </footer>
      </div>

      {/* ── CDK Modal ── */}
      {user && user.tier === 'normal' && cdkModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="absolute inset-0 modal-backdrop-in"
            style={{ backgroundColor: 'var(--modal-overlay)', backdropFilter: 'blur(6px)' }}
            onClick={() => { setCdkModalOpen(false); setCdkMsg(null) }}
          />
          <div className="relative glass rounded-2xl border border-border shadow-glass-lg w-full max-w-sm p-5 modal-animate-in">
            <div className="flex items-center justify-between mb-1">
              <div className="text-sm font-bold text-text-primary">{t('cdk.title')}</div>
              <button
                onClick={() => { setCdkModalOpen(false); setCdkMsg(null) }}
                className="text-text-muted hover:text-text-primary transition-colors p-1 rounded-lg hover:bg-white/5"
              >
                <span className="text-base leading-none">×</span>
              </button>
            </div>
            <div className="text-xs text-text-secondary mb-4 leading-relaxed">{t('cdk.desc')}</div>

            <input
              value={cdk}
              onChange={(e) => setCdk(e.target.value)}
              className="w-full rounded-field border border-border glass-light px-3.5 py-2.5 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 mb-3"
              placeholder={t('cdk.placeholder')}
              onKeyDown={(e) => e.key === 'Enter' && !cdkLoading && cdk.trim() && (async () => {
                setCdkMsg(null); setCdkLoading(true)
                try {
                  await redeemCdk(cdk.trim())
                  setCdkMsg(t('cdk.success'))
                } catch (e: any) {
                  const detail = e?.response?.data?.detail
                  if (detail === 'invalid_cdk') setCdkMsg(t('cdk.invalid'))
                  else if (detail === 'cdk_already_used') setCdkMsg(t('cdk.alreadyUsed'))
                  else if (detail === 'user_not_found') setCdkMsg(t('cdk.userNotFound'))
                  else setCdkMsg(detail || e?.message || t('common.error'))
                } finally { setCdkLoading(false) }
              })()}
            />

            {cdkMsg && (
              <div className="mb-4 text-[11px] text-text-secondary px-2 py-1.5 rounded-lg bg-white/[0.03] border border-border/50">
                {cdkMsg}
              </div>
            )}

            <div className="flex items-center justify-end gap-2">
              <Button
                size="sm"
                variant="ghost"
                onClick={() => { setCdkModalOpen(false); setCdkMsg(null) }}
              >
                {t('common.cancel')}
              </Button>
              <a href="https://ifdian.net/item/9b3d2992fae211f089e452540025c377" target="_blank" rel="noreferrer">
                <Button size="sm" variant="secondary">{t('cdk.getKey')}</Button>
              </a>
              <Button
                size="sm"
                variant="primary"
                loading={cdkLoading}
                disabled={!cdk.trim()}
                onClick={async () => {
                  setCdkMsg(null); setCdkLoading(true)
                  try {
                    await redeemCdk(cdk.trim())
                    setCdkMsg(t('cdk.success'))
                  } catch (e: any) {
                    const detail = e?.response?.data?.detail
                    if (detail === 'invalid_cdk') setCdkMsg(t('cdk.invalid'))
                    else if (detail === 'cdk_already_used') setCdkMsg(t('cdk.alreadyUsed'))
                    else if (detail === 'user_not_found') setCdkMsg(t('cdk.userNotFound'))
                    else setCdkMsg(detail || e?.message || t('common.error'))
                  } finally { setCdkLoading(false) }
                }}
              >
                {t('cdk.confirmActivate')}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ── Change Password Modal ── */}
      {changePwModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="absolute inset-0"
            style={{ backgroundColor: 'var(--modal-overlay)', backdropFilter: 'blur(6px)' }}
            onClick={() => { setChangePwModalOpen(false); setChangePwMsg(null) }}
          />
          <div className="relative glass rounded-2xl border border-border shadow-glass-lg w-full max-w-sm p-5">
            <div className="flex items-center justify-between mb-1">
              <div className="text-sm font-bold text-text-primary">{t('account.changePassword')}</div>
              <button
                onClick={() => { setChangePwModalOpen(false); setChangePwMsg(null) }}
                className="text-text-muted hover:text-text-primary transition-colors p-1 rounded-lg hover:bg-white/5"
              >
                <span className="text-base leading-none">×</span>
              </button>
            </div>
            <div className="text-[11px] text-text-secondary mb-4 leading-relaxed">{t('account.changePasswordDesc')}</div>

            <div className="space-y-3">
              <div>
                <label className="block text-[11px] text-text-secondary mb-1">{t('account.oldPassword')}</label>
                <input
                  type="password"
                  value={changePwOld}
                  onChange={(e) => setChangePwOld(e.target.value)}
                  className="w-full rounded-field border border-border glass-light px-3.5 py-2.5 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
                  placeholder={t('account.enterOldPassword')}
                  onKeyDown={(e) => e.key === 'Enter' && handleChangePasswordSubmit()}
                />
              </div>
              <div>
                <label className="block text-[11px] text-text-secondary mb-1">{t('account.newPassword')}</label>
                <input
                  type="password"
                  value={changePwNew}
                  onChange={(e) => setChangePwNew(e.target.value)}
                  className="w-full rounded-field border border-border glass-light px-3.5 py-2.5 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
                  placeholder={t('account.enterNewPassword')}
                  onKeyDown={(e) => e.key === 'Enter' && handleChangePasswordSubmit()}
                />
              </div>
              <div>
                <label className="block text-[11px] text-text-secondary mb-1">{t('account.confirmNewPassword')}</label>
                <input
                  type="password"
                  value={changePwConfirm}
                  onChange={(e) => setChangePwConfirm(e.target.value)}
                  className="w-full rounded-field border border-border glass-light px-3.5 py-2.5 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
                  placeholder={t('account.enterConfirmPassword')}
                  onKeyDown={(e) => e.key === 'Enter' && handleChangePasswordSubmit()}
                />
              </div>
            </div>

            {changePwMsg && (
              <div className="mt-3 text-[11px] text-text-secondary px-2 py-1.5 rounded-lg bg-white/[0.03] border border-border/50">
                {changePwMsg}
              </div>
            )}

            <div className="flex items-center justify-end gap-2 mt-4">
              <Button
                size="sm"
                variant="ghost"
                onClick={() => { setChangePwModalOpen(false); setChangePwMsg(null) }}
              >
                {t('common.cancel')}
              </Button>
              <Button
                size="sm"
                variant="primary"
                loading={changePwLoading}
                disabled={!changePwOld.trim() || !changePwNew.trim() || !changePwConfirm.trim()}
                onClick={handleChangePasswordSubmit}
              >
                {t('common.confirm')}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
