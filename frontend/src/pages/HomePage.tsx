import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Card, CardDesc, CardHeader, CardTitle } from '../components/ui/Card'
import Button from '../components/ui/Button'
import { Snowflake, Flame, Workflow, Wrench, ExternalLink, Code2, PlayCircle, BookOpen, TrendingUp, Zap, Users } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { getJobStats } from '../services/jobs'

function FeatureCard(props: {
  index: number
  icon: React.ReactNode
  title: string
  desc: React.ReactNode
  to?: string
  href?: string
  cta: string
  accentColor?: string
}) {
  const content = (
    <Card className="group glass-light hover:glass-strong h-full card-lift">
      <CardHeader className="mb-3">
        <div className="flex items-start gap-3.5">
          <div
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl transition-all duration-300 group-hover:scale-105"
            style={{
              background: props.accentColor ? `${props.accentColor}18` : 'var(--accent-soft)',
              color: props.accentColor || 'var(--accent)',
              boxShadow: props.accentColor ? `0 0 0 1px ${props.accentColor}30, 0 4px 12px ${props.accentColor}20` : 'var(--shadow-glow)',
            }}
          >
            <div className="flex items-center justify-center">{props.icon}</div>
          </div>
          <div className="min-w-0 flex-1">
            <CardTitle>{props.title}</CardTitle>
            <CardDesc>{props.desc}</CardDesc>
          </div>
        </div>
      </CardHeader>
      <Button variant="secondary" className="w-full text-xs" icon={<Zap size={11} />}>
        {props.cta}
      </Button>
    </Card>
  )

  const animClass = `animate-fade-slide-up stagger-${Math.min(props.index, 10)}`

  if (props.href) {
    return <a href={props.href} target="_blank" rel="noopener noreferrer" className={`block ${animClass}`}>{content}</a>
  }
  return <Link to={props.to ?? ''} className={`block ${animClass}`}>{content}</Link>
}

function StatCard(props: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="flex flex-col items-center py-2 px-4">
      <div className="text-2xl font-bold text-gradient-accent tabular-nums">{props.value}</div>
      <div className="text-xs text-text-secondary mt-1 font-medium">{props.label}</div>
      {props.sub && <div className="text-[10px] text-text-muted mt-0.5">{props.sub}</div>}
    </div>
  )
}

export default function HomePage() {
  const { t } = useTranslation()

  const { data: stats, isError } = useQuery({
    queryKey: ['jobStats'],
    queryFn: getJobStats,
    refetchInterval: 30000,
    retry: 1,
  })

  const featureCards = [
    {
      index: 1,
      icon: <Snowflake size={20} strokeWidth={1.75} />,
      title: t('modules.cooling.title'),
      desc: t('modules.cooling.desc'),
      to: '/jobs/new?type=cooling',
      cta: t('modules.cooling.cta'),
      accentColor: '#5AC8FA',
    },
    {
      index: 2,
      icon: <Flame size={20} strokeWidth={1.75} />,
      title: t('modules.heating.title'),
      desc: t('modules.heating.desc'),
      to: '/jobs/new?type=heating',
      cta: t('modules.heating.cta'),
      accentColor: '#FF9F0A',
    },
    {
      index: 3,
      icon: <Workflow size={18} strokeWidth={1.75} />,
      title: t('modules.queue.title'),
      desc: t('modules.queue.desc'),
      to: '/jobs',
      cta: t('modules.queue.cta'),
      accentColor: '#30D158',
    },
    {
      index: 4,
      icon: <Wrench size={18} strokeWidth={1.75} />,
      title: t('modules.tools.title'),
      desc: <span style={{ color: '#FF6B6B' }}>{t('modules.tools.desc')}</span>,
      to: '/tools',
      cta: t('modules.tools.cta'),
      accentColor: '#FF6B6B',
    },
    {
      index: 5,
      icon: <BookOpen size={18} strokeWidth={1.75} />,
      title: t('modules.manual.title'),
      desc: t('modules.manual.desc'),
      href: '/user-manual',
      cta: t('modules.manual.cta'),
      accentColor: '#BF5AF2',
    },
  ]

  return (
    <div className="space-y-6">
      {/* ── Hero Card ── */}
      <div className="glass rounded-2xl p-6 md:p-8 shadow-glass animate-fade-slide-up relative overflow-hidden">
        {/* Subtle gradient orb decoration */}
        <div className="absolute top-0 right-0 w-64 h-64 rounded-full opacity-[0.04] pointer-events-none" style={{ background: 'radial-gradient(circle, var(--accent) 0%, transparent 70%)' }} />
        <div className="absolute bottom-0 left-0 w-48 h-48 rounded-full opacity-[0.03] pointer-events-none" style={{ background: 'radial-gradient(circle, #BF5AF2 0%, transparent 70%)' }} />

        <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 relative">
          <div className="flex-1 min-w-0">
            <h1 className="text-xl font-bold text-text-primary tracking-tight leading-tight">
              {t('pages.home.title')}
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed font-semibold" style={{ color: '#FF6B6B' }}>
              {t('pages.home.desc')}
            </p>
            <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-text-secondary">
              {t('pages.home.desc2')}
            </p>
          </div>

          <div className="flex flex-col gap-2 shrink-0 animate-fade-slide-right">
            <a
              href="https://gitee.com/cuity1999/Radiation-cooling-and-heating-calculation"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 rounded-field border border-border glass-light px-3.5 py-2.5 text-xs text-text-secondary hover:text-text-primary hover:border-accent/30 hover:bg-bg-elevated transition-all duration-200 whitespace-nowrap group"
            >
              <Code2 size={14} className="text-text-muted group-hover:text-accent transition-colors" />
              <span className="font-medium">{t('pages.home.repoLink')}</span>
              <ExternalLink size={12} className="opacity-50" />
            </a>
            <a
              href="https://www.bilibili.com/video/av116072900593444"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 rounded-field border border-border glass-light px-3.5 py-2.5 text-xs text-text-secondary hover:text-text-primary hover:border-accent/30 hover:bg-bg-elevated transition-all duration-200 whitespace-nowrap group"
            >
              <PlayCircle size={14} className="text-text-muted group-hover:text-accent transition-colors" />
              <span className="font-medium">{t('pages.home.tutorialLink')}</span>
              <ExternalLink size={12} className="opacity-50" />
            </a>
          </div>
        </div>
      </div>

      {/* ── Feature Cards ── */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {featureCards.map((card) => (
          <FeatureCard key={card.index} {...card} />
        ))}
      </div>

      {/* ── Stats ── */}
      <Card className="glass-light animate-fade-slide-up stagger-6">
        <CardHeader>
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/15 text-accent">
              <TrendingUp size={16} />
            </div>
            <CardTitle>{t('pages.home.statsTitle')}</CardTitle>
          </div>
        </CardHeader>
        {isError ? (
          <div className="text-center text-sm text-text-muted py-4">{t('common.error')}</div>
        ) : (
          <div className="flex items-center justify-center gap-0">
            <StatCard label={t('pages.home.statsToday')} value={stats?.today_jobs ?? '—'} />
            <div className="h-10 w-px bg-border mx-2" />
            <StatCard label={t('pages.home.statsTotal')} value={stats?.total_jobs ?? '—'} />
          </div>
        )}
        <div className="mt-3 text-center text-xs text-text-secondary">
          {t('pages.home.statsTasks')}
        </div>
      </Card>

      {/* ── Note ── */}
      <Card className="glass-light animate-fade-slide-up stagger-7">
        <CardHeader>
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-warning/15 text-warning">
              <Zap size={16} />
            </div>
            <CardTitle>{t('pages.home.noteTitle')}</CardTitle>
          </div>
          <CardDesc>{t('pages.home.noteDesc')}</CardDesc>
        </CardHeader>
        <div className="text-sm text-text-secondary leading-relaxed pl-10">
          {t('pages.home.noteBody')}
        </div>
      </Card>
    </div>
  )
}
