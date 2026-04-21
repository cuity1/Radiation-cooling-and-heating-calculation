import { useState, useEffect, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import Plot from 'react-plotly.js'
import { getPlotlyLayout } from '../lib/plotlyConfig'

import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import { Card, CardDesc, CardHeader, CardTitle } from '../components/ui/Card'
import HelpButton from '../components/Help/HelpButton'
import { getJob, getJobResult } from '../services/jobs'
import { formatLocalTime } from '../lib/time'
import { convertToRelativePaths } from '../lib/pathUtils'
import type { JobStatus } from '../types/jobs'

function statusTone(status: JobStatus): 'info' | 'success' | 'warning' | 'danger' | 'neutral' {
  if (status === 'queued') return 'info'
  if (status === 'started') return 'warning'
  if (status === 'succeeded') return 'success'
  if (status === 'failed') return 'danger'
  return 'neutral'
}

export default function MaterialEnvTempMapDetailPage() {
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
  const result = resultQ.data

  const [csvData, setCsvData] = useState<any[]>([])
  const [csvLoading, setCsvLoading] = useState(false)

  useEffect(() => {
    const dataCsvFile = result?.artifacts?.find((a: any) => a.name === 'data.csv')

    if (dataCsvFile && dataCsvFile.url) {
      setCsvLoading(true)
      const fullUrl = dataCsvFile.url.startsWith('http')
        ? dataCsvFile.url
        : `${window.location.origin}${dataCsvFile.url}`

      fetch(fullUrl)
        .then((res) => {
          if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`)
          return res.text()
        })
        .then((text) => {
          const lines = text.split('\n').filter(line => line.trim())
          if (lines.length < 2) {
            setCsvData([])
            return
          }

          const parseCSVLine = (line: string): string[] => {
            const result: string[] = []
            let current = ''
            let inQuotes = false
            for (let i = 0; i < line.length; i++) {
              const char = line[i]
              if (char === '"') {
                inQuotes = !inQuotes
              } else if (char === ',' && !inQuotes) {
                result.push(current.trim())
                current = ''
              } else {
                current += char
              }
            }
            result.push(current.trim())
            return result
          }

          const headers = parseCSVLine(lines[0]).map(h => h.replace(/^"|"$/g, ''))
          const data = lines.slice(1).map(line => {
            const values = parseCSVLine(line).map(v => v.replace(/^"|"$/g, ''))
            const row: any = {}
            headers.forEach((header, idx) => {
              const value = values[idx] || ''
              const numValue = parseFloat(value)
              row[header] = isNaN(numValue) || value === '' ? value : numValue
            })
            return row
          }).filter(row => {
            if (row.NAME && String(row.NAME).trim() !== '') return true
            if (row.QID !== undefined && row.QID !== null && String(row.QID).trim() !== '') return true
            if (row.FQ && String(row.FQ).trim() !== '') return true
            return false
          })

          setCsvData(data)
        })
        .catch((err) => {
          console.error('[MaterialEnvTempMapDetailPage] 加载CSV失败:', err)
          setCsvData([])
        })
        .finally(() => {
          setCsvLoading(false)
        })
    } else {
      setCsvData([])
    }
  }, [result])

  const statusDesc = () => {
    if (job?.status === 'succeeded') return '计算完成'
    if (job?.status === 'failed') return '计算失败'
    return '计算进行中...'
  }

  const isWorldMap = job?.params?.weather_group === 'world' || job?.params?.weather_group === 'world_weather2025'
  const isChinaMap = job?.params?.weather_group === 'china'
  const artifacts = result?.artifacts || []
  const dataCsvFile = artifacts.find((a: any) => a.name === 'data.csv')

  // 查找两张地图图片
  const maxDeltaTMapImage = artifacts.find(
    (a: any) =>
      a.kind === 'image' &&
      typeof a.name === 'string' &&
      a.name.toLowerCase().includes('max_deltat'),
  )
  const avgDeltaTMapImage = artifacts.find(
    (a: any) =>
      a.kind === 'image' &&
      typeof a.name === 'string' &&
      a.name.toLowerCase().includes('avg_deltat'),
  )

  // 准备柱状图数据
  const barChartData = useMemo(() => {
    if (!csvData || csvData.length === 0) return null

    const getLabelColumn = (row: any): string => {
      if (row.NAME && String(row.NAME).trim() !== '') return String(row.NAME).trim()
      if (row.FQ && String(row.FQ).trim() !== '') return String(row.FQ).trim()
      if (row.EPW && String(row.EPW).trim() !== '') return String(row.EPW).trim()
      if (row.QID !== undefined && row.QID !== null && String(row.QID).trim() !== '') return String(row.QID).trim()
      return ''
    }

    const getColumnValue = (row: any, columnName: string): any => {
      if (row[columnName] !== undefined) return row[columnName]
      const normalizedColumnName = columnName.trim().toLowerCase()
      for (const key in row) {
        const normalizedKey = key.trim().toLowerCase()
        if (normalizedKey === normalizedColumnName) return row[key]
      }
      return undefined
    }

    const safeParseFloat = (value: any): number => {
      if (typeof value === 'number') return isNaN(value) ? 0 : value
      if (value === null || value === undefined || value === '') return 0
      const parsed = parseFloat(String(value))
      return isNaN(parsed) ? 0 : parsed
    }

    // 注意：MaxDeltaT = 全年最深的亚环境降温（最负的ΔT，制冷最强）；MinDeltaT = 全年最差情况（最正的ΔT，材料比环境还热）
    const validData = csvData
      .map(row => ({
        label: getLabelColumn(row),
        maxDeltaT: safeParseFloat(getColumnValue(row, 'MaxDeltaT')),  // 最深降温（制冷最强，ΔT最负）
        avgDeltaT: safeParseFloat(getColumnValue(row, 'AvgDeltaT')),
        minDeltaT: safeParseFloat(getColumnValue(row, 'MinDeltaT')),  // 最差情况（材料最热，ΔT最正）
      }))
      .filter(item => item.label !== '')

    if (validData.length === 0) return null

    const isNumeric = validData.every(item => !isNaN(parseFloat(item.label)))
    const sortedData = [...validData].sort((a, b) => {
      if (isNumeric) return parseFloat(a.label) - parseFloat(b.label)
      return a.label.localeCompare(b.label, 'zh-CN')
    })

    const labels = sortedData.map(item => item.label)
    const maxDeltaT = sortedData.map(item => item.maxDeltaT)
    const avgDeltaT = sortedData.map(item => item.avgDeltaT)
    const minDeltaT = sortedData.map(item => item.minDeltaT)

    const xAxisTitle = isChinaMap ? '省份' : isWorldMap ? '地区/网格' : '地区'

    return {
      labels,
      maxDeltaT,
      avgDeltaT,
      minDeltaT,
      xAxisTitle,
      dataCount: validData.length,
    }
  }, [csvData, isChinaMap, isWorldMap])

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-lg font-semibold text-text-primary">材料温度地图分析详情</div>
          <div className="text-sm text-text-secondary">查看材料与环境温差计算结果</div>
        </div>
        <div className="flex items-center gap-2">
          <HelpButton doc="material_comparison" />
          <Link to="/jobs">
            <Button variant="secondary">任务列表</Button>
          </Link>
          <Link to="/material-env-temp-map">
            <Button variant="secondary">新建分析</Button>
          </Link>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>任务信息</CardTitle>
          <CardDesc>任务ID: {jobId}</CardDesc>
        </CardHeader>

        {jobQ.isLoading ? (
          <div className="text-sm text-text-secondary">{t('common.loading')}</div>
        ) : jobQ.isError ? (
          <div className="rounded-xl border border-danger-soft bg-danger-soft p-3 text-sm text-text-secondary">
            加载失败
          </div>
        ) : job ? (
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-field border border-border glass-light p-3">
              <div className="text-xs font-semibold text-text-muted">任务类型</div>
              <div className="mt-1 text-sm text-text-primary">材料温度地图</div>
            </div>
            <div className="rounded-field border border-border glass-light p-3">
              <div className="text-xs font-semibold text-text-muted">任务状态</div>
              <div className="mt-1 flex items-center gap-2">
                <Badge tone={statusTone(job.status)}>{t(`job.${job.status}`)}</Badge>
                <span className="text-xs text-text-muted">自动刷新中</span>
              </div>
            </div>
            <div className="rounded-field border border-border glass-light p-3">
              <div className="text-xs font-semibold text-text-muted">创建时间</div>
              <div className="mt-1 text-sm text-text-secondary">{formatLocalTime(job.created_at)}</div>
            </div>
            <div className="rounded-field border border-border glass-light p-3">
              <div className="text-xs font-semibold text-text-muted">更新时间</div>
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
          <CardTitle>分析参数</CardTitle>
          <CardDesc>本次分析使用的配置参数</CardDesc>
        </CardHeader>

        <div className="grid gap-3 md:grid-cols-2">
          <div className="rounded-field border border-border glass-light p-3">
            <div className="text-xs font-semibold text-text-muted">天气组</div>
            <div className="mt-1 text-sm text-text-secondary">
              {job?.params?.weather_group === 'world' ? '世界' :
               job?.params?.weather_group === 'world_weather2025' ? '世界2025' : '中国'}
            </div>
          </div>
          <div className="rounded-field border border-border glass-light p-3">
            <div className="text-xs font-semibold text-text-muted">相态变化模式</div>
            <div className="mt-1 text-sm text-text-secondary">
              {job?.params?.transition_mode === 'gradient' ? '渐变' : '突变'}
            </div>
          </div>
          <div className="rounded-field border border-border glass-light p-3">
            <div className="text-xs font-semibold text-text-muted">对流换热系数 (W/(m²·K))</div>
            <div className="mt-1 text-sm text-text-secondary">
              额外 {job?.params?.h_coefficient ?? '-'} + 基准10 = 实际 {job?.result?.summary?.total_h ?? '-'}
            </div>
          </div>
          <div className="rounded-field border border-border glass-light p-3">
            <div className="text-xs font-semibold text-text-muted">相态点数量</div>
            <div className="mt-1 text-sm text-text-secondary">
              {job?.params?.phases?.length ?? '-'}
            </div>
          </div>
          <div className="rounded-field border border-border glass-light p-3">
            <div className="text-xs font-semibold text-text-muted">处理的EPW文件数</div>
            <div className="mt-1 text-sm text-text-secondary">
              {job?.result?.summary?.total_epw_processed ?? '-'}
            </div>
          </div>
        </div>

        <div className="mt-3">
          <div className="text-xs font-semibold text-text-muted">完整参数</div>
          <pre className="glass-light mt-2 overflow-auto rounded-field border border-border p-3 text-xs text-text-secondary">
            {job ? JSON.stringify(convertToRelativePaths(job.params), null, 2) : '{}'}
          </pre>
        </div>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div>
              <CardTitle>计算结果</CardTitle>
              <CardDesc>{statusDesc()}</CardDesc>
            </div>
            {job?.status === 'succeeded' && result ? (
              <div className="flex items-center gap-2">
                <Button variant="ghost" onClick={() => resultQ.refetch()}>
                  {t('common.refresh')}
                </Button>
              </div>
            ) : null}
          </div>
        </CardHeader>

        {job?.status === 'failed' ? (
          <div className="rounded-2xl border border-danger-soft bg-danger-soft p-4">
            <div className="text-sm font-semibold text-text-primary">错误信息</div>
            <pre className="mt-2 overflow-auto text-xs text-text-secondary">{job.error_message || '-'}</pre>
          </div>
        ) : null}

        {job?.status === 'succeeded' ? (
          resultQ.isLoading ? (
            <div className="text-sm text-text-secondary">{t('common.loading')}</div>
          ) : resultQ.isError ? (
            <div className="rounded-xl border border-danger-soft bg-danger-soft p-3 text-sm text-text-secondary">
              结果加载失败
            </div>
          ) : result ? (
            <div className="grid gap-4">
              {/* 柱状图 */}
              {dataCsvFile ? (
                csvLoading ? (
                  <Card className="w-full">
                    <CardHeader>
                      <CardTitle>温差柱状图</CardTitle>
                      <CardDesc>正在加载数据...</CardDesc>
                    </CardHeader>
                    <div className="text-sm text-text-secondary p-4">加载中...</div>
                  </Card>
                ) : barChartData ? (
                  <>
                    {/* 最大制冷温差柱状图（最深亚环境降温） */}
                    <Card className="w-full">
                      <CardHeader>
                        <CardTitle>最大制冷温差柱状图</CardTitle>
                        <CardDesc>
                          各城市全年最深亚环境降温 ΔT = T_eq - T_a（ΔT 越负，制冷效果越强）（共 {barChartData.dataCount} 个城市）
                        </CardDesc>
                      </CardHeader>
                      <div className="rounded-field border border-border glass-light p-4">
                        <div className="h-[500px]">
                          <Plot
                            data={[
                              {
                                x: barChartData.labels,
                                y: barChartData.maxDeltaT,
                                type: 'bar',
                                name: '最大制冷温差 ΔT_max (°C)',
                                marker: { color: 'rgba(54, 162, 235, 0.8)' },
                              },
                            ]}
                            layout={getPlotlyLayout({
                              title: {
                                text: '全年最大制冷温差城市对比（ΔT = T_eq - T_a，越负越强）',
                                font: { size: 16 },
                              },
                              xaxis: {
                                title: { text: barChartData.xAxisTitle },
                                tickangle: barChartData.dataCount > 20 ? -45 : -30,
                                automargin: true,
                              },
                              yaxis: {
                                title: { text: '最大制冷温差 ΔT (°C)' },
                                rangemode: 'normal',
                              },
                              margin: { b: barChartData.dataCount > 20 ? 120 : 100, t: 50, l: 80, r: 30 },
                              height: 500,
                            })}
                            config={{
                              displayModeBar: true,
                              displaylogo: false,
                              responsive: true,
                              modeBarButtonsToRemove: ['pan2d', 'lasso2d'],
                            }}
                            style={{ width: '100%', height: '100%' }}
                          />
                        </div>
                      </div>
                    </Card>

                    {/* 平均温差柱状图 */}
                    <Card className="w-full">
                      <CardHeader>
                        <CardTitle>全年平均温差柱状图</CardTitle>
                        <CardDesc>
                          各城市全年平均温差 ΔT = T_eq - T_a 对比（共 {barChartData.dataCount} 个城市）
                        </CardDesc>
                      </CardHeader>
                      <div className="rounded-field border border-border glass-light p-4">
                        <div className="h-[500px]">
                          <Plot
                            data={[
                              {
                                x: barChartData.labels,
                                y: barChartData.avgDeltaT,
                                type: 'bar',
                                name: '全年平均温差 ΔT_avg (°C)',
                                marker: { color: 'rgba(54, 162, 235, 0.8)' },
                              },
                            ]}
                            layout={getPlotlyLayout({
                              title: {
                                text: '全年平均温差城市对比（ΔT = T_eq - T_a）',
                                font: { size: 16 },
                              },
                              xaxis: {
                                title: { text: barChartData.xAxisTitle },
                                tickangle: barChartData.dataCount > 20 ? -45 : -30,
                                automargin: true,
                              },
                              yaxis: {
                                title: { text: '平均温差 ΔT (°C)' },
                                rangemode: 'normal',
                              },
                              margin: { b: barChartData.dataCount > 20 ? 120 : 100, t: 50, l: 80, r: 30 },
                              height: 500,
                            })}
                            config={{
                              displayModeBar: true,
                              displaylogo: false,
                              responsive: true,
                              modeBarButtonsToRemove: ['pan2d', 'lasso2d'],
                            }}
                            style={{ width: '100%', height: '100%' }}
                          />
                        </div>
                      </div>
                    </Card>
                  </>
                ) : (
                  <Card className="w-full">
                    <CardHeader>
                      <CardTitle>温差柱状图</CardTitle>
                      <CardDesc>数据加载失败或数据为空</CardDesc>
                    </CardHeader>
                    <div className="text-sm text-text-secondary p-4">无法加载柱状图数据</div>
                  </Card>
                )
              ) : null}

              {/* 全年最大制冷温差地图（最深亚环境降温） */}
              {isChinaMap && maxDeltaTMapImage && (
                <Card className="w-full">
                  <CardHeader>
                    <CardTitle>中国全年最大制冷温差地图（Max ΔT）</CardTitle>
                    <CardDesc>
                      根据 data.csv 中的 MaxDeltaT 列绘制的中国省级最大制冷温差分布图，
                      代表各地全年制冷效果最强的时刻（ΔT 越负，降温效果越好）。鼠标右键-将图片另存为可下载。
                    </CardDesc>
                  </CardHeader>
                  <div className="rounded-field border border-border glass-light p-4">
                    <div className="w-full max-h-[640px] overflow-hidden rounded-field border border-border bg-bg-elevated">
                      <img
                        src={maxDeltaTMapImage.url.startsWith('http') ? maxDeltaTMapImage.url : `${window.location.origin}${maxDeltaTMapImage.url}`}
                        alt="中国全年最大制冷温差地图"
                        className="w-full h-auto object-contain"
                      />
                    </div>
                    <div className="mt-2 text-xs text-text-muted">
                      说明：地图使用 data.csv 中的省份名称（NAME）与阿里云中国省级边界数据进行匹配，按 MaxDeltaT 着色。
                      ΔT 越负，表示材料能实现越深的亚环境降温，制冷效果越好。
                    </div>
                  </div>
                </Card>
              )}

              {/* 全年平均温差地图 */}
              {isChinaMap && avgDeltaTMapImage && (
                <Card className="w-full">
                  <CardHeader>
                    <CardTitle>中国全年平均温差地图（Avg ΔT）</CardTitle>
                    <CardDesc>
                      根据 data.csv 中的 AvgDeltaT 列绘制的中国省级平均温差分布图，
                      代表各地全年整体制冷效果。鼠标右键-将图片另存为可下载。
                    </CardDesc>
                  </CardHeader>
                  <div className="rounded-field border border-border glass-light p-4">
                    <div className="w-full max-h-[640px] overflow-hidden rounded-field border border-border bg-bg-elevated">
                      <img
                        src={avgDeltaTMapImage.url.startsWith('http') ? avgDeltaTMapImage.url : `${window.location.origin}${avgDeltaTMapImage.url}`}
                        alt="中国全年平均温差地图"
                        className="w-full h-auto object-contain"
                      />
                    </div>
                    <div className="mt-2 text-xs text-text-muted">
                      说明：地图使用 data.csv 中的省份名称（NAME）与阿里云中国省级边界数据进行匹配，按 AvgDeltaT 着色。
                      ΔT 越负，表示材料整体制冷效果越好；ΔT 为正，表示材料整体制冷失效。
                    </div>
                  </div>
                </Card>
              )}

              {/* 数据下载 */}
              {dataCsvFile && (
                <Card className="w-full">
                  <CardHeader>
                    <CardTitle>计算结果数据</CardTitle>
                    <CardDesc>下载计算结果CSV文件</CardDesc>
                  </CardHeader>
                  <div className="flex items-center justify-between rounded-field border border-border glass-light p-4">
                    <div>
                      <div className="text-sm font-semibold text-text-primary">{dataCsvFile.name}</div>
                      <div className="text-xs text-text-muted mt-1">
                        包含所有城市的 MaxDeltaT（最深亚环境降温，ΔT越负制冷越强）、AvgDeltaT（平均温差）、MinDeltaT（最差情况，材料比环境还热）
                      </div>
                    </div>
                    <a
                      href={dataCsvFile.url.startsWith('http') ? dataCsvFile.url : `${window.location.origin}${dataCsvFile.url}`}
                      download={dataCsvFile.name}
                    >
                      <Button variant="secondary">下载 data.csv</Button>
                    </a>
                  </div>
                </Card>
              )}
            </div>
          ) : null
        ) : (
          <div className="text-sm text-text-secondary">计算进行中，请稍候...</div>
        )}
      </Card>
    </div>
  )
}
