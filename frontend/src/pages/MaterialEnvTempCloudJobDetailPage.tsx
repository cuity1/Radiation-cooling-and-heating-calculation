import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import Plot from 'react-plotly.js'

import Button from '../components/ui/Button'
import { Card, CardDesc, CardHeader, CardTitle } from '../components/ui/Card'
import { getJob, getJobResult } from '../services/jobs'
import { getPlotlyLayout } from '../lib/plotlyConfig'
import { formatLocalTime } from '../lib/time'
import type { JobDetail, JobResult } from '../types/jobs'
import Badge from '../components/ui/Badge'

function statusTone(status: JobDetail['status']): 'info' | 'success' | 'warning' | 'danger' | 'neutral' {
  if (status === 'queued') return 'info'
  if (status === 'started') return 'warning'
  if (status === 'succeeded') return 'success'
  if (status === 'failed') return 'danger'
  return 'neutral'
}

function downloadTextFile(filename: string, content: string, mime = 'text/plain;charset=utf-8') {
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

function toCsvFromCloud(cloud: any): string {
  const tEnv: number[] = cloud?.t_env_c ?? []
  const tFilm: number[] = cloud?.t_film_c ?? []
  const zRaw: number[][] = cloud?.cooling_power ?? []

  // 后端 cooling_power 形状为 (T_env 行 × T_film 列)，这里转置为 (T_film 行 × T_env 列)
  const z: (number | null)[][] = tFilm.map((_, j) =>
    tEnv.map((_, i) => (zRaw[i] && Number.isFinite(zRaw[i][j]) ? zRaw[i][j] : null)),
  )

  const header = ['T_film (°C) \\ T_env (°C)', ...tEnv.map((v) => v.toFixed(6))].join(',')
  const rows = tFilm.map((tf, i) => {
    const row = z[i] ?? []
    const vals = row.map((v) => (Number.isFinite(v) ? String(v) : ''))
    return [tf.toFixed(6), ...vals].join(',')
  })

  return [header, ...rows].join('\n')
}

export default function MaterialEnvTempCloudJobDetailPage() {
  const { t } = useTranslation()
  const { jobId } = useParams()

  const jobQ = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => getJob(jobId!),
    enabled: !!jobId,
    refetchInterval: 2000,
  })

  const resultQ = useQuery({
    queryKey: ['job', jobId, 'result'],
    queryFn: () => getJobResult(jobId!),
    enabled: !!jobId && jobQ.data?.status === 'succeeded',
  })

  const job = jobQ.data
  const result: JobResult | undefined = resultQ.data

  const cloud = useMemo(() => {
    const summary = result?.summary ?? {}
    // 后端在 summary.cloud 里返回完整云图数据
    return (summary as any).cloud ?? null
  }, [result])

  const statusDesc = useMemo(() => {
    if (job?.status === 'succeeded') return t('pages.jobDetail.statusReady')
    if (job?.status === 'failed') return t('pages.jobDetail.statusFailed')
    return t('pages.jobDetail.statusWaiting')
  }, [job?.status, t])

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-lg font-semibold text-text-primary">{t('tools.materialEnvTempCloud.title')}</div>
          <div className="text-sm text-text-secondary">
            {t('tools.materialEnvTempCloud.desc')}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Link to="/jobs">
            <Button variant="secondary">{t('nav.jobs')}</Button>
          </Link>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t('job.id')}</CardTitle>
          <CardDesc>{jobId}</CardDesc>
        </CardHeader>

        {jobQ.isLoading ? (
          <div className="text-sm text-text-secondary">{t('common.loading')}</div>
        ) : jobQ.isError ? (
          <div className="rounded-xl border border-danger-soft bg-danger-soft p-3 text-sm text-text-secondary">
            {t('pages.jobDetail.loadFailed')}
          </div>
        ) : job ? (
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-field border border-border glass-light p-3">
              <div className="text-xs font-semibold text-text-muted">{t('job.type')}</div>
              <div className="mt-1 text-sm text-text-primary">{t('jobTypes.material_env_temp_cloud')}</div>
            </div>
            <div className="rounded-field border border-border glass-light p-3">
              <div className="text-xs font-semibold text-text-muted">{t('job.status')}</div>
              <div className="mt-1 flex items-center gap-2">
                <Badge tone={statusTone(job.status)}>{t(`job.${job.status}`)}</Badge>
                <span className="text-xs text-text-muted">{t('common.autoRefresh')}</span>
              </div>
            </div>
            <div className="rounded-field border border-border glass-light p-3">
              <div className="text-xs font-semibold text-text-muted">{t('job.createdAt')}</div>
              <div className="mt-1 text-sm text-text-secondary">{formatLocalTime(job.created_at)}</div>
            </div>
            <div className="rounded-field border border-border glass-light p-3">
              <div className="text-xs font-semibold text-text-muted">{t('job.updatedAt')}</div>
              <div className="mt-1 text-sm text-text-secondary">{formatLocalTime(job.updated_at)}</div>
            </div>
            <div className="rounded-field border border-border glass-light p-3">
              <div className="text-xs font-semibold text-text-muted">{t('job.remark')}</div>
              <div className="mt-1 text-sm text-text-secondary">{job.remark || '-'}</div>
            </div>
          </div>
        ) : null}
      </Card>

      <Card className="glass-light">
        <CardHeader>
          <CardTitle>{t('pages.jobDetail.paramsTitle')}</CardTitle>
          <CardDesc>{t('pages.jobDetail.paramsDesc')}</CardDesc>
        </CardHeader>

        {job ? (
          <div className="grid gap-3 md:grid-cols-4">
            <div className="rounded-field border border-border glass-light p-3">
              <div className="text-xs font-semibold text-text-muted">T_env,min (°C)</div>
              <div className="mt-1 text-sm text-text-secondary">{String(job.params?.t_env_min_c ?? '-')}</div>
            </div>
            <div className="rounded-field border border-border glass-light p-3">
              <div className="text-xs font-semibold text-text-muted">T_env,max (°C)</div>
              <div className="mt-1 text-sm text-text-secondary">{String(job.params?.t_env_max_c ?? '-')}</div>
            </div>
            <div className="rounded-field border border-border glass-light p-3">
              <div className="text-xs font-semibold text-text-muted">h_c (W/m²·K)</div>
              <div className="mt-1 text-sm text-text-secondary">{String(job.params?.h_c_wm2k ?? '-')}</div>
            </div>
            <div className="rounded-field border border-border glass-light p-3">
              <div className="text-xs font-semibold text-text-muted">{t('pages.newJob.natConvLabel')}</div>
              <div className="mt-1 text-sm text-text-secondary">
                {job.params?.enable_natural_convection ? t('common.on') : t('common.off')}
              </div>
            </div>
            <div className="rounded-field border border-border glass-light p-3">
              <div className="text-xs font-semibold text-text-muted">{t('pages.newJob.latentHeatTitle')}</div>
              <div className="mt-1 text-sm text-text-secondary">
                {job.params?.enable_latent_heat
                  ? `${t('common.on')} RH=${job.params?.relative_humidity ?? 'N/A'}`
                  : t('common.off')}
              </div>
            </div>
            <div className="rounded-field border border-border glass-light p-3">
              <div className="text-xs font-semibold text-text-muted">{t('pages.newJob.wetFraction')}</div>
              <div className="mt-1 text-sm text-text-secondary">{String(job.params?.wet_fraction ?? '-')}</div>
            </div>
            <div className="rounded-field border border-border glass-light p-3">
              <div className="text-xs font-semibold text-text-muted">{t('pages.newJob.phaseTitle')}</div>
              <div className="mt-1 text-sm text-text-secondary">
                {job.params?.phase_temp_c == null
                  ? t('common.off')
                  : `${t('common.on')} T=${job.params.phase_temp_c}°C, P=${job.params.phase_power_wm2} W/m²`}
              </div>
            </div>
          </div>
        ) : null}
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div>
              <CardTitle>{t('tools.materialEnvTempCloud.plot.title')}</CardTitle>
              <CardDesc>{statusDesc}</CardDesc>
            </div>

            {job?.status === 'succeeded' && cloud ? (
              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  onClick={() => {
                    const csv = toCsvFromCloud(cloud)
                    downloadTextFile(`material_env_temp_cloud_${jobId}.csv`, csv, 'text/csv;charset=utf-8')
                  }}
                >
                  {t('common.exportCsv')}
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => {
                    const el = document.querySelector(
                      '#material_env_temp_cloud_plot .modebar-btn[data-title="Download plot as a png"]',
                    ) as HTMLElement | null
                    el?.click()
                  }}
                >
                  {t('common.exportPng')}
                </Button>
              </div>
            ) : null}
          </div>
        </CardHeader>

        {job?.status === 'failed' ? (
          <div className="rounded-2xl border border-danger-soft bg-danger-soft p-4">
            <div className="text-sm font-semibold text-text-primary">{t('pages.jobDetail.errorTitle')}</div>
            <pre className="mt-2 overflow-auto text-xs text-text-secondary">{job.error_message || '-'}</pre>
          </div>
        ) : null}

        {job?.status === 'succeeded' ? (
          !cloud ? (
            <div className="text-sm text-text-secondary">{t('pages.jobDetail.resultLoadFailed')}</div>
          ) : (
            <div className="rounded-2xl border border-border glass-light p-3">
              <div className="h-[520px]" id="material_env_temp_cloud_plot">
                {(() => {
                  const tEnv: number[] = cloud?.t_env_c ?? []
                  const tFilm: number[] = cloud?.t_film_c ?? []
                  const zRaw: number[][] = cloud?.cooling_power ?? []
                  // 转置 cooling_power: (T_env 行 × T_film 列) -> (T_film 行 × T_env 列)
                  const z: (number | null)[][] = tFilm.map((_, j) =>
                    tEnv.map((_, i) => (zRaw[i] && Number.isFinite(zRaw[i][j]) ? zRaw[i][j] : null)),
                  )

                  return (
                    <Plot
                      data={[
                        {
                          type: 'heatmap',
                          x: tEnv,
                          y: tFilm,
                          z,
                          colorscale: 'RdBu',
                          reversescale: true,
                          colorbar: { title: t('cooling.yAxis') },
                        } as any,
                      ]}
                      layout={getPlotlyLayout({
                        autosize: true,
                        margin: { l: 70, r: 20, t: 10, b: 60 },
                        xaxis: { title: t('tools.materialEnvTempCloud.plot.xaxis') },
                        yaxis: { title: t('tools.materialEnvTempCloud.plot.yaxis') },
                      })}
                      style={{ width: '100%', height: '100%' }}
                      useResizeHandler
                      config={{ displayModeBar: true, responsive: true }}
                    />
                  )
                })()}
              </div>
            </div>
          )
        ) : (
          <div className="text-sm text-text-secondary">{t('pages.jobDetail.processing')}</div>
        )}
      </Card>

      {/* 推荐引用参考文献 */}
      <Card className="glass-light">
        <CardHeader>
          <CardTitle>{t('pages.jobDetail.recommendedReferences')}</CardTitle>
          <CardDesc>推荐引用以下参考文献</CardDesc>
        </CardHeader>
        <div className="glass-light mt-2 rounded-field border border-border p-3 text-xs text-text-secondary whitespace-pre-line leading-relaxed">
          {t('pages.jobDetail.referencesContent')}
        </div>
      </Card>
    </div>
  )
}

