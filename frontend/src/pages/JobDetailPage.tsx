import { useMemo, useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link, useParams, Navigate } from 'react-router-dom'
import Plot from 'react-plotly.js'
import { getPlotlyLayout, mergePlotlyLayout } from '../lib/plotlyConfig'

import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import CheckboxPill from '../components/ui/CheckboxPill'
import { Card, CardDesc, CardHeader, CardTitle } from '../components/ui/Card'
import { getJob, getJobResult } from '../services/jobs'
import { apiGet } from '../services/api'
import { formatLocalTime } from '../lib/time'
import { convertToRelativePaths } from '../lib/pathUtils'
import type { JobResult } from '../types/jobs'
import type { JobStatus, JobType } from '../types/jobs'

type Era5PlotItem = {
  plot_id: string
  title: string
  kind: string
  spec_url: string
  data_url: string
}

type PlotlySpec = {
  data: any[]
  layout: any
}

function statusTone(status: JobStatus): 'info' | 'success' | 'warning' | 'danger' | 'neutral' {
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

function toCsv(result: JobResult) {
  const plots = result.plots || []
  const linePlot = plots.find((p: any) => p?.kind === 'line')
  const xVals: number[] = linePlot?.x?.values || []
  const series: Array<{ name: string; values: number[] }> = linePlot?.series || []

  const header = ['T_film (°C)', ...series.map((s) => s.name)].join(',')
  const rows = xVals.map((x, i) => {
    const y = series.map((s) => {
      const v = s.values?.[i]
      if (v === null || v === undefined || Number.isNaN(v)) return ''
      return String(v)
    })
    return [String(x), ...y].join(',')
  })

  return [header, ...rows].join('\n')
}

function angleStepsToPrecisionLabel(angleSteps: number | undefined): string {
  if (angleSteps === 1000) return 'Low'
  if (angleSteps === 2000) return 'Medium'
  if (angleSteps === 5000) return 'High'
  if (!angleSteps || Number.isNaN(angleSteps)) return '-'
  return String(angleSteps)
}

function getModuleMeta(t: any, jobType: JobType | undefined) {
  if (jobType === 'heating') {
    return {
      title: t('jobTypes.heating'),
      plotTitle: t('heating.plotTitle'),
      yAxis: t('heating.yAxis'),
      exportPrefix: 'heating',
      power0Hint: t('heating.power0Hint'),
    }
  }
  if (jobType === 'in_situ_simulation') {
    return {
      title: t('jobTypes.in_situ_simulation'),
      plotTitle: '',
      yAxis: '',
      exportPrefix: 'in_situ_simulation',
      power0Hint: '',
    }
  }
  return {
    title: t('jobTypes.cooling'),
    plotTitle: t('cooling.plotTitle'),
    yAxis: t('cooling.yAxis'),
    exportPrefix: 'cooling',
    power0Hint: t('cooling.power0Hint'),
  }
}

export default function JobDetailPage() {
  const { t, i18n } = useTranslation()
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
  const result = resultQ.data

  // For in_situ_simulation, fetch era5 plots
  const era5PlotsQ = useQuery({
    queryKey: ['job', jobId, 'era5', 'plots'],
    queryFn: () => apiGet<Era5PlotItem[]>(`/era5/${jobId}/plots`),
    enabled: !!jobId && job?.type === 'in_situ_simulation' && job?.status === 'succeeded',
  })

  const era5Plots = era5PlotsQ.data ?? []
  const [era5PlotSpecs, setEra5PlotSpecs] = useState<Record<string, PlotlySpec>>({})

  // Load plot specs when plots are available
  useEffect(() => {
    if (era5Plots.length > 0) {
      era5Plots.forEach((p) => {
        if (!era5PlotSpecs[p.plot_id]) {
          apiGet<PlotlySpec>(p.spec_url.replace('/api', ''))
            .then((spec) => {
              setEra5PlotSpecs((prev) => ({ ...prev, [p.plot_id]: spec }))
            })
            .catch(() => {
              // ignore
            })
        }
      })
    }
  }, [era5Plots, era5PlotSpecs])

  const meta = useMemo(() => getModuleMeta(t, job?.type), [t, job?.type])

  const linePlot = useMemo(() => {
    const r = result
    if (!r) return null
    return (r.plots || []).find((p: any) => p?.kind === 'line')
  }, [result])

  const seriesNames: string[] = useMemo(() => {
    const s = linePlot?.series || []
    return s.map((x: any) => x?.name).filter(Boolean)
  }, [linePlot])

  const [visibleMap, setVisibleMap] = useState<Record<string, boolean>>({})

  const normalizedVisibleMap = useMemo(() => {
    const m: Record<string, boolean> = {}
    for (const name of seriesNames) {
      m[name] = visibleMap[name] ?? true
    }
    return m
  }, [seriesNames, visibleMap])

  const plotData = useMemo(() => {
    if (!linePlot) return null

    const x: number[] = linePlot?.x?.values || []
    const series: Array<{ name: string; values: number[] }> = linePlot?.series || []

    const data = series
      .filter((s) => normalizedVisibleMap[s.name] !== false)
      .map((s) => ({
        x,
        y: s.values || [],
        type: 'scatter',
        mode: 'lines',
        name: s.name,
        line: { width: 2 },
      }))

    return {
      title: linePlot?.title || meta.plotTitle,
      data,
    }
  }, [linePlot, normalizedVisibleMap, meta.plotTitle])

  const precisionLabel = useMemo(() => {
    const angleSteps = Number(job?.params?.angle_steps)
    return angleStepsToPrecisionLabel(angleSteps)
  }, [job])

  const statusDesc = useMemo(() => {
    if (job?.status === 'succeeded') return t('pages.jobDetail.statusReady')
    if (job?.status === 'failed') return t('pages.jobDetail.statusFailed')
    return t('pages.jobDetail.statusWaiting')
  }, [job?.status, t])

  const rSolDesc = useMemo(() => {
    const zh = String(result?.summary?.R_sol_desc_zh ?? '太阳光吸收率')
    const en = String(result?.summary?.R_sol_desc_en ?? 'Solar spectral absorptance')
    return i18n.language === 'zh' ? zh : en
  }, [result?.summary, i18n.language])

  const rSol1Desc = useMemo(() => {
    const zh = String(result?.summary?.R_sol1_desc_zh ?? '可见光吸收率')
    const en = String(result?.summary?.R_sol1_desc_en ?? 'Visible spectral absorptance')
    return i18n.language === 'zh' ? zh : en
  }, [result?.summary, i18n.language])

  const avgEmiDesc = useMemo(() => {
    const zh = String(result?.summary?.avg_emissivity_desc_zh ?? '加权发射率')
    const en = String(result?.summary?.avg_emissivity_desc_en ?? 'Weighted emissivity')
    return i18n.language === 'zh' ? zh : en
  }, [result?.summary, i18n.language])

  // 针对特殊任务类型，统一在所有 hooks 之后做重定向，避免 Hooks 顺序变化
  if (job?.type === 'compare_materials') {
    return <Navigate to={`/materials/${jobId}`} replace />
  }
  if (job?.type === 'energy_map') {
    return <Navigate to={`/power-map/${jobId}`} replace />
  }
  if (job?.type === 'material_env_temp_map') {
    return <Navigate to={`/material-env-temp-map/${jobId}`} replace />
  }
  if (job?.type === 'radiation_cooling_clothing') {
    return <Navigate to={`/radiation-cooling-clothing/${jobId}`} replace />
  }
  if (job?.type === 'material_env_temp_cloud') {
    return <Navigate to={`/tools/material-env-temp-cloud/${jobId}`} replace />
  }
  if (job?.type === 'compare_glass') {
    return <Navigate to={`/glass-comparison/${jobId}`} replace />
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-lg font-semibold text-text-primary">{t('pages.jobDetail.title')}</div>
          <div className="text-sm text-text-secondary">{t('pages.jobDetail.desc')}</div>
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
              <div className="mt-1 text-sm text-text-primary">{t(`jobTypes.${job.type}`)}</div>
            </div>
            <div className="rounded-field border border-border glass-light p-3">
              <div className="text-xs font-semibold text-text-muted">{t('job.status')}</div>
              <div className="mt-1 flex items-center gap-2">
                <Badge tone={statusTone(job.status)}>{t(`job.${job.status}`)}</Badge>
                <span className="text-xs text-text-muted">{t('common.autoRefresh')}</span>
              </div>
            </div>
            <div className="rounded-field border border-border glass-light p-3">
              <div className="text-xs font-semibold text-text-muted">用户ID</div>
              <div className="mt-1 text-sm text-text-secondary">{job.user_id ?? '-'}</div>
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

        {job?.type === 'in_situ_simulation' ? (
          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-field border border-border glass-light p-3">
              <div className="text-xs font-semibold text-text-muted">开始日期</div>
              <div className="mt-1 text-sm text-text-secondary">{String(job?.params?.start_date ?? '-')}</div>
            </div>
            <div className="rounded-field border border-border glass-light p-3">
              <div className="text-xs font-semibold text-text-muted">结束日期</div>
              <div className="mt-1 text-sm text-text-secondary">{String(job?.params?.end_date ?? '-')}</div>
            </div>
            <div className="rounded-field border border-border glass-light p-3">
              <div className="text-xs font-semibold text-text-muted">位置</div>
              <div className="mt-1 text-sm text-text-secondary">
                {job?.params?.lon != null && job?.params?.lat != null
                  ? `Lon: ${job.params.lon}, Lat: ${job.params.lat}`
                  : '-'}
              </div>
            </div>
            <div className="rounded-field border border-border glass-light p-3">
              <div className="text-xs font-semibold text-text-muted">天空视角系数</div>
              <div className="mt-1 text-sm text-text-secondary">{String(job?.params?.sky_view ?? '-')}</div>
            </div>
            <div className="rounded-field border border-border glass-light p-3">
              <div className="text-xs font-semibold text-text-muted">辐照强度</div>
              <div className="mt-1 text-sm text-text-secondary">
                {result?.summary?.solar_irradiance_mean_wm2 != null || result?.summary?.solar_irradiance_max_wm2 != null
                  ? `mean=${Number(result?.summary?.solar_irradiance_mean_wm2 ?? 0).toFixed(2)} W/m², max=${Number(
                      result?.summary?.solar_irradiance_max_wm2 ?? 0,
                    ).toFixed(2)} W/m²`
                  : '-'}
              </div>
            </div>
            <div className="rounded-field border border-border glass-light p-3">
              <div className="text-xs font-semibold text-text-muted">大气辐射模式</div>
              <div className="mt-1 text-sm text-text-secondary">
                {job?.params?.use_empirical_atm === 2
                  ? '理论模式 (0.8×经验+0.2×strd)'
                  : job?.params?.use_empirical_atm === 1
                  ? '修正混合模式 (0.3×经验+0.7×strd)'
                  : '使用真实大气数据 (strd)'}
              </div>
            </div>
            <div className="rounded-field border border-border glass-light p-3">
              <div className="text-xs font-semibold text-text-muted">时区偏移</div>
              <div className="mt-1 text-sm text-text-secondary">
                {job?.params?.tz_offset_hours != null ? `${job.params.tz_offset_hours} 小时` : '-'}
              </div>
            </div>
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-4">
            <div className="rounded-field border border-border glass-light p-3">
              <div className="text-xs font-semibold text-text-muted">{t('pages.jobDetail.atmosphere')}</div>
              <div className="mt-1 text-sm text-text-secondary">{String(job?.params?.atm_preset ?? '-')}</div>
            </div>
            <div className="rounded-field border border-border glass-light p-3">
              <div className="text-xs font-semibold text-text-muted">辐照强度 (S_solar)</div>
              <div className="mt-1 text-sm text-text-secondary">
                {result?.summary?.S_solar_wm2 != null ? `${Number(result.summary.S_solar_wm2).toFixed(2)} W/m²` : '-'}
              </div>
            </div>
            <div className="rounded-field border border-border glass-light p-3">
              <div className="text-xs font-semibold text-text-muted">环境温度 (T_a1)</div>
              <div className="mt-1 text-sm text-text-secondary">
                {result?.summary?.T_a1_c != null ? `${Number(result.summary.T_a1_c).toFixed(2)} °C` : '-'}
              </div>
            </div>
            <div className="rounded-field border border-border glass-light p-3">
              <div className="text-xs font-semibold text-text-muted">{t('pages.jobDetail.phase')}</div>
              <div className="mt-1 text-sm text-text-secondary">
                {job?.params?.phase_temp_c == null ? t('common.off') : `${t('common.on')} T=${job.params.phase_temp_c}°C`}
              </div>
            </div>
            <div className="rounded-field border border-border glass-light p-3">
              <div className="text-xs font-semibold text-text-muted">{t('pages.newJob.latentHeatTitle')}</div>
              <div className="mt-1 text-sm text-text-secondary">
                {job?.params?.enable_latent_heat
                  ? `${t('common.on')} RH=${job?.params?.relative_humidity ?? 'N/A'}%`
                  : t('common.off')}
              </div>
            </div>
          </div>
        )}

        <div className="mt-3">
          <div className="text-xs font-semibold text-text-muted">{t('pages.jobDetail.raw')}</div>
          <pre className="glass-light mt-2 overflow-auto rounded-field border border-border p-3 text-xs text-text-secondary">
            {job ? JSON.stringify(convertToRelativePaths(job.params), null, 2) : '{}'}
          </pre>
        </div>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div>
              <CardTitle>{meta.title}</CardTitle>
              <CardDesc>{statusDesc}</CardDesc>
            </div>

            {job?.status === 'succeeded' && result ? (
              <div className="flex items-center gap-2">
                {job?.type === 'in_situ_simulation' ? (
                  <a 
                    href={`/api/era5/${jobId}/results-csv`} 
                    download="radiative_cooling_results_from_weather.csv"
                    style={{ textDecoration: 'none' }}
                  >
                    <Button variant="secondary" type="button">
                      {t('common.exportCsv')}
                    </Button>
                  </a>
                ) : (
                  <Button
                    variant="secondary"
                    onClick={() => {
                      // For other job types, use the existing CSV export logic
                      const csv = toCsv(result)
                      downloadTextFile(`${meta.exportPrefix}_${jobId}.csv`, csv, 'text/csv;charset=utf-8')
                    }}
                  >
                    {t('common.exportCsv')}
                  </Button>
                )}
                {job?.params?._file_paths && (
                  <Button
                    variant="secondary"
                    onClick={() => {
                      const filePaths = job.params._file_paths as Record<string, string>
                      // 遍历所有文件并下载
                      Object.entries(filePaths).forEach(([key, _relativePath]) => {
                        const url = `/api/jobs/${jobId}/input-files/${key}`
                        const link = document.createElement('a')
                        link.href = url
                        link.download = `${key}_${job?.id || 'data'}`
                        document.body.appendChild(link)
                        link.click()
                        document.body.removeChild(link)
                      })
                    }}
                  >
                    下载计算使用的数据
                  </Button>
                )}
                <Button
                  variant="secondary"
                  onClick={() => {
                    const el = document.querySelector('#result_plot .modebar-btn[data-title="Download plot as a png"]') as HTMLElement | null
                    el?.click()
                  }}
                >
                  {t('common.exportPng')}
                </Button>
                <Button variant="ghost" onClick={() => resultQ.refetch()}>
                  {t('common.refresh')}
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
          job?.type === 'in_situ_simulation' ? (
            era5Plots.length > 0 ? (
              <div className="flex flex-col gap-4">
                <div className="text-sm font-semibold text-text-primary">图表预览</div>
                {era5Plots.map((p) => {
                  const spec = era5PlotSpecs[p.plot_id]
                  return (
                    <Card key={p.plot_id} className="w-full block">
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <div>
                          <div className="font-medium text-text-primary">{p.title}</div>
                          <div className="text-xs text-text-muted">{p.plot_id}</div>
                        </div>
                        <a href={p.data_url} target="_blank" rel="noreferrer">
                          <Button variant="secondary" size="sm">导出数据(CSV)</Button>
                        </a>
                      </div>

                      <div className="w-full min-w-0" style={{ position: 'relative', clear: 'both' }}>
                        {spec ? (
                          <div className="w-full" style={{ minWidth: 0, height: '500px', position: 'relative' }}>
                            <Plot
                              data={spec.data}
                              layout={mergePlotlyLayout({
                                ...spec.layout, 
                                autosize: true, 
                                width: undefined,
                                height: 500
                              })}
                              style={{ width: '100%', height: '100%', minWidth: 0, position: 'relative' }}
                              useResizeHandler
                              config={{ displayModeBar: true, responsive: true }}
                            />
                          </div>
                        ) : (
                          <div className="text-sm text-text-secondary">图表数据加载中...</div>
                        )}
                      </div>
                    </Card>
                  )
                })}

                {resultQ.data ? (
                  <div className="rounded-field border border-border glass-light p-3">
                    <div className="text-xs font-semibold text-text-muted">{t('pages.jobDetail.recommendedReferences')}</div>
                    <div className="mt-2 text-xs text-text-secondary whitespace-pre-line leading-relaxed">
                      {t('pages.jobDetail.referencesContent')}
                    </div>
                  </div>
                ) : resultQ.isLoading ? (
                  <div className="text-sm text-text-secondary">加载原始结果中...</div>
                ) : null}
              </div>
            ) : (
              <div className="text-sm text-text-secondary">图表加载中...</div>
            )
          ) : resultQ.isLoading ? (
            <div className="text-sm text-text-secondary">{t('common.loading')}</div>
          ) : resultQ.isError ? (
            <div className="rounded-xl border border-danger-soft bg-danger-soft p-3 text-sm text-text-secondary">
              {t('pages.jobDetail.resultLoadFailed')}
            </div>
          ) : result ? (
            <div className="grid gap-3">
              <div className="grid gap-3 md:grid-cols-4">
                <div className="rounded-field border border-border glass-light p-3">
                  <div className="text-xs font-semibold text-text-muted">Power_0 (W/m²)</div>
                  <div className="mt-1 text-2xl font-semibold text-text-primary">
                    {Number(result.summary?.Power_0 ?? NaN).toFixed(4)}
                  </div>
                  <div className="mt-1 text-xs text-text-muted">{meta.power0Hint}</div>
                </div>

                <div className="rounded-field border border-border glass-light p-3">
                  <div className="text-xs font-semibold text-text-muted">α_sol</div>
                  <div className="mt-1 text-2xl font-semibold text-text-primary">
                    {Number(result.summary?.R_sol ?? NaN).toFixed(4)}
                  </div>
                  <div className="mt-1 text-xs text-text-muted">{rSolDesc}</div>
                </div>

                <div className="rounded-field border border-border glass-light p-3">
                  <div className="text-xs font-semibold text-text-muted">α_sol1</div>
                  <div className="mt-1 text-2xl font-semibold text-text-primary">
                    {result.summary?.R_sol1 != null ? Number(result.summary.R_sol1).toFixed(4) : '-'}
                  </div>
                  <div className="mt-1 text-xs text-text-muted">{rSol1Desc}</div>
                </div>

                <div className="rounded-field border border-border glass-light p-3">
                  <div className="text-xs font-semibold text-text-muted">avg_emissivity</div>
                  <div className="mt-1 text-2xl font-semibold text-text-primary">
                    {Number(result.summary?.avg_emissivity ?? NaN).toFixed(4)}
                  </div>
                  <div className="mt-1 text-xs text-text-muted">{avgEmiDesc}</div>
                </div>
              </div>

              {(result.summary?.R_sol_reflectance_only != null || result.summary?.T_sol != null) && (
                <div className="grid gap-3 md:grid-cols-4 mt-3">
                  <div className="rounded-field border border-border glass-light p-3">
                    <div className="text-xs font-semibold text-text-muted">R_sol (反射率)</div>
                    <div className="mt-1 text-2xl font-semibold text-text-primary">
                      {result.summary?.R_sol_reflectance_only != null
                        ? Number(result.summary.R_sol_reflectance_only).toFixed(4)
                        : '-'}
                    </div>
                    <div className="mt-1 text-xs text-text-muted">
                      {i18n.language === 'zh'
                        ? result.summary?.R_sol_reflectance_only_desc_zh ?? '太阳光谱反射率'
                        : result.summary?.R_sol_reflectance_only_desc_en ?? 'Solar spectral reflectance'}
                    </div>
                  </div>

                  <div className="rounded-field border border-border glass-light p-3">
                    <div className="text-xs font-semibold text-text-muted">R_sol1 (反射率)</div>
                    <div className="mt-1 text-2xl font-semibold text-text-primary">
                      {result.summary?.R_sol1_reflectance_only != null
                        ? Number(result.summary.R_sol1_reflectance_only).toFixed(4)
                        : '-'}
                    </div>
                    <div className="mt-1 text-xs text-text-muted">
                      {i18n.language === 'zh'
                        ? result.summary?.R_sol1_reflectance_only_desc_zh ?? '可见光谱反射率'
                        : result.summary?.R_sol1_reflectance_only_desc_en ?? 'Visible spectral reflectance'}
                    </div>
                  </div>

                  <div className="rounded-field border border-border glass-light p-3">
                    <div className="text-xs font-semibold text-text-muted">T_sol</div>
                    <div className="mt-1 text-2xl font-semibold text-text-primary">
                      {result.summary?.T_sol != null ? Number(result.summary.T_sol).toFixed(4) : '-'}
                    </div>
                    <div className="mt-1 text-xs text-text-muted">
                      {i18n.language === 'zh'
                        ? result.summary?.T_sol_desc_zh ?? '太阳光谱透过率'
                        : result.summary?.T_sol_desc_en ?? 'Solar spectral transmittance'}
                    </div>
                  </div>

                  <div className="rounded-field border border-border glass-light p-3">
                    <div className="text-xs font-semibold text-text-muted">T_sol1</div>
                    <div className="mt-1 text-2xl font-semibold text-text-primary">
                      {result.summary?.T_sol1 != null ? Number(result.summary.T_sol1).toFixed(4) : '-'}
                    </div>
                    <div className="mt-1 text-xs text-text-muted">
                      {i18n.language === 'zh'
                        ? result.summary?.T_sol1_desc_zh ?? '可见光谱透过率'
                        : result.summary?.T_sol1_desc_en ?? 'Visible spectral transmittance'}
                    </div>
                  </div>
                </div>
              )}

              {plotData ? (
                <div className="rounded-2xl border border-border glass-light p-3">
                  <div className="mb-2 text-sm font-semibold text-text-primary">{plotData.title}</div>

                  {seriesNames.length ? (
                    <div className="mb-3 flex flex-wrap gap-2">
                      {seriesNames.map((name) => (
                        <CheckboxPill
                          key={name}
                          checked={normalizedVisibleMap[name] !== false}
                          onChange={(v) => setVisibleMap((prev) => ({ ...prev, [name]: v }))}
                          label={name}
                        />
                      ))}
                    </div>
                  ) : null}

                  <div className="h-[420px]" id="result_plot">
                    <Plot
                      data={plotData.data as any}
                      layout={getPlotlyLayout({
                        autosize: true,
                        margin: { l: 60, r: 20, t: 20, b: 50 },
                        xaxis: { title: 'T_film (°C)' },
                        yaxis: { title: meta.yAxis },
                        legend: { orientation: 'h', y: -0.2 },
                      })}
                      config={{ displayModeBar: true, responsive: true }}
                      style={{ width: '100%', height: '100%' }}
                    />
                  </div>
                </div>
              ) : (
                <div className="rounded-field border border-border glass-light p-3 text-sm text-text-secondary">
                  {t('pages.jobDetail.plotMissing')}
                </div>
              )}

              <div className="rounded-field border border-border glass-light p-3">
                <div className="text-xs font-semibold text-text-muted">{t('pages.jobDetail.recommendedReferences')}</div>
                <div className="mt-2 text-xs text-text-secondary whitespace-pre-line leading-relaxed">
                  {t('pages.jobDetail.referencesContent')}
                </div>
              </div>
            </div>
          ) : null
        ) : (
          <div className="text-sm text-text-secondary">{t('pages.jobDetail.processing')}</div>
        )}
      </Card>
    </div>
  )
}
