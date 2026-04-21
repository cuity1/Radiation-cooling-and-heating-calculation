import { useMutation, useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import { Card, CardHeader, CardTitle } from '../components/ui/Card'
import { cleanupQueuedJobs } from '../services/admin'
import { listJobs } from '../services/jobs'
import type { JobStatus, JobSummary } from '../types/jobs'
import { formatLocalTime } from '../lib/time'
import { ListChecks, RefreshCw, Plus, Trash2, Clock, CheckCircle2, AlertCircle, Loader2, XCircle } from 'lucide-react'

const STATUS_CONFIG: Record<JobStatus, { tone: 'info' | 'success' | 'warning' | 'danger' | 'neutral'; label: string; Icon: typeof Clock }> = {
  queued:    { tone: 'info',    label: 'queued',    Icon: Loader2 },
  started:   { tone: 'warning', label: 'started',   Icon: Loader2 },
  succeeded: { tone: 'success', label: 'succeeded', Icon: CheckCircle2 },
  failed:    { tone: 'danger',  label: 'failed',    Icon: XCircle },
  cancelled: { tone: 'neutral', label: 'cancelled', Icon: AlertCircle },
}

function statusTone(status: JobStatus) {
  return STATUS_CONFIG[status]?.tone ?? 'neutral'
}

function JobCard(props: { job: JobSummary; index: number }) {
  const { t } = useTranslation()
  const { job } = props
  const cfg = STATUS_CONFIG[job.status] ?? STATUS_CONFIG.cancelled
  const statusLabel = t(`job.${job.status}`)

  let detailPath = `/jobs/${job.id}`
  if (job.type === 'compare_materials') detailPath = `/materials/${job.id}`
  else if (job.type === 'energy_map') detailPath = `/power-map/${job.id}`
  else if (job.type === 'material_env_temp_map') detailPath = `/material-env-temp-map/${job.id}`
  else if (job.type === 'radiation_cooling_clothing') detailPath = `/radiation-cooling-clothing/${job.id}`

  const animClass = `animate-fade-slide-up stagger-${Math.min(props.index + 1, 10)}`

  return (
    <Link to={detailPath} className={`block ${animClass}`}>
      <div className="glass-light rounded-2xl px-4 py-3.5 border border-border transition-all duration-200 hover:glass-strong hover:border-border-light card-lift group">
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          {/* Left: type + badge */}
          <div className="flex items-center gap-3 min-w-0">
            <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-xl transition-colors ${
              job.status === 'succeeded' ? 'bg-success/15 text-success' :
              job.status === 'failed'    ? 'bg-danger/15  text-danger'  :
              job.status === 'started'   ? 'bg-warning/15 text-warning' :
              'bg-accent/15 text-accent'
            }`}>
              <cfg.Icon size={15} className={job.status === 'started' || job.status === 'queued' ? 'animate-spin' : ''} />
            </div>
            <div className="min-w-0">
              <div className="text-sm font-semibold text-text-primary truncate">{t(`jobTypes.${job.type}`)}</div>
              <div className="text-[11px] text-text-muted font-mono truncate">{job.remark || job.id}</div>
            </div>
          </div>

          {/* Status badge */}
          <div className="flex items-center gap-2 shrink-0">
            <Badge tone={cfg.tone} showDot>{statusLabel}</Badge>
          </div>

          {/* Right: timestamps */}
          <div className="text-[11px] text-text-secondary space-y-0.5 md:text-right shrink-0 md:min-w-[160px]">
            <div>
              <span className="text-text-muted">{t('job.createdAt')}: </span>
              <span className="font-mono">{formatLocalTime(job.created_at)}</span>
            </div>
            <div>
              <span className="text-text-muted">{t('job.updatedAt')}: </span>
              <span className="font-mono">{formatLocalTime(job.updated_at)}</span>
            </div>
          </div>
        </div>
      </div>
    </Link>
  )
}

export default function JobsListPage() {
  const { t } = useTranslation()

  const q = useQuery({
    queryKey: ['jobs'],
    queryFn: listJobs,
    refetchInterval: 2500,
  })

  const cleanupM = useMutation({
    mutationFn: cleanupQueuedJobs,
    onSuccess: async () => { await q.refetch() },
  })

  return (
    <div className="space-y-5">
      {/* Header */}
      <Card className="animate-fade-slide-up">
        <CardHeader>
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-2.5">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent/15 text-accent">
                <ListChecks size={18} />
              </div>
              <div>
                <CardTitle>{t('pages.jobs.title')}</CardTitle>
                <p className="text-xs text-text-muted mt-0.5">{t('pages.jobs.desc')}</p>
              </div>
            </div>

            {/* Controls */}
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-text-muted px-2 py-1 rounded-lg bg-white/[0.04] border border-border">
                {q.isLoading ? t('common.loading') : `${q.data?.length ?? 0} ${t('pages.jobs.count', { count: q.data?.length ?? 0 }).split(' ').pop() ?? 'items'}`}
              </span>
              <Button
                variant="secondary"
                size="sm"
                icon={<RefreshCw size={12} className={q.isFetching ? 'animate-spin' : ''} />}
                onClick={() => q.refetch()}
              >
                {t('common.refresh')}
              </Button>
              <Button
                variant="danger"
                size="sm"
                icon={<Trash2 size={12} />}
                loading={cleanupM.isPending}
                onClick={() => cleanupM.mutate()}
              >
                {t('pages.jobs.cleanupQueued')}
              </Button>
              <Link to="/jobs/new">
                <Button variant="primary" size="sm" icon={<Plus size={13} />}>
                  {t('nav.newJob')}
                </Button>
              </Link>
            </div>
          </div>
        </CardHeader>

        {/* Feedback messages */}
        {cleanupM.isError && (
          <div className="mt-3 rounded-field border border-danger/30 bg-danger/10 p-2.5 text-xs text-text-secondary animate-scale-fade-in">
            {t('pages.jobs.cleanupFailed')}
          </div>
        )}
        {cleanupM.isSuccess && (
          <div className="mt-3 rounded-field border border-success/30 bg-success/10 p-2.5 text-xs text-text-secondary animate-scale-fade-in">
            {t('pages.jobs.cleanupSuccess', { count: cleanupM.data?.cancelled ?? 0 })}
          </div>
        )}
      </Card>

      {/* Job list */}
      <div className="grid gap-2">
        {(q.data ?? []).map((job, i) => (
          <JobCard key={job.id} job={job} index={i} />
        ))}

        {!q.isLoading && (q.data?.length ?? 0) === 0 && (
          <div className="glass-light rounded-2xl p-10 text-center animate-scale-fade-in">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white/[0.04] text-text-muted mx-auto mb-3">
              <ListChecks size={24} />
            </div>
            <p className="text-sm font-semibold text-text-secondary">{t('pages.jobs.empty')}</p>
            <Link to="/jobs/new" className="mt-3 inline-block">
              <Button variant="primary" size="sm" icon={<Plus size={12} />}>{t('nav.newJob')}</Button>
            </Link>
          </div>
        )}

        {q.isLoading && (
          <div className="glass-light rounded-2xl p-8 space-y-2">
            {[1, 2, 3].map(i => (
              <div key={i} className="flex items-center gap-3 p-2">
                <div className="skeleton-shimmer h-8 w-8 rounded-xl" />
                <div className="flex-1 space-y-1.5">
                  <div className="skeleton-shimmer h-3.5 w-32 rounded" />
                  <div className="skeleton-shimmer h-2.5 w-20 rounded" />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
