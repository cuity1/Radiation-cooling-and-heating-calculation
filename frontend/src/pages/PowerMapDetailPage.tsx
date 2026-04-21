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

export default function PowerMapDetailPage() {
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

  // 加载和解析 CSV 数据用于柱状图
  const [csvData, setCsvData] = useState<any[]>([])
  const [csvLoading, setCsvLoading] = useState(false)
  
  useEffect(() => {
    const dataCsvFile = result?.artifacts?.find((a: any) => a.name === 'data.csv')
    console.log('[PowerMapDetailPage] Looking for data.csv:', { 
      hasResult: !!result, 
      artifacts: result?.artifacts, 
      dataCsvFile 
    })
    
    if (dataCsvFile && dataCsvFile.url) {
      setCsvLoading(true)
      // 确保URL是完整的
      const fullUrl = dataCsvFile.url.startsWith('http') 
        ? dataCsvFile.url 
        : `${window.location.origin}${dataCsvFile.url}`
      
      console.log('[PowerMapDetailPage] Fetching CSV from:', fullUrl)
      
      fetch(fullUrl)
        .then((res) => {
          console.log('[PowerMapDetailPage] CSV fetch response:', res.status, res.statusText)
          if (!res.ok) {
            throw new Error(`HTTP ${res.status}: ${res.statusText}`)
          }
          return res.text()
        })
        .then((text) => {
          console.log('[PowerMapDetailPage] CSV content length:', text.length)
          console.log('[PowerMapDetailPage] CSV first 500 chars:', text.substring(0, 500))
          // 改进的CSV解析（处理引号、逗号等）
          const lines = text.split('\n').filter(line => line.trim())
          if (lines.length < 2) {
            setCsvData([])
            return
          }
          
          // 解析CSV行（处理引号内的逗号）
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
              // 尝试转换为数字
              const numValue = parseFloat(value)
              row[header] = isNaN(numValue) || value === '' ? value : numValue
            })
            return row
          }).filter(row => {
            // 中国模式：必须有NAME列
            // 世界模式：必须有QID或FQ列
            if (row.NAME && row.NAME.trim() !== '') return true
            if (row.QID !== undefined && row.QID !== null && String(row.QID).trim() !== '') return true
            if (row.FQ && String(row.FQ).trim() !== '') return true
            return false
          })
          
          console.log('[PowerMapDetailPage] Parsed CSV data:', data.length, 'rows')
          setCsvData(data)
        })
        .catch((err) => {
          console.error('[PowerMapDetailPage] 加载CSV失败:', err)
          setCsvData([])
        })
        .finally(() => {
          setCsvLoading(false)
        })
    } else {
      console.log('[PowerMapDetailPage] No data.csv file found in artifacts')
      setCsvData([])
    }
  }, [result])

  const statusDesc = () => {
    if (job?.status === 'succeeded') return '计算完成'
    if (job?.status === 'failed') return '计算失败'
    return '计算进行中...'
  }

  // 判断是哪种地图类型
  const isWorldMap = job?.params?.weather_group === 'world' || job?.params?.weather_group === 'world_weather2025'
  const isChinaMap = job?.params?.weather_group === 'china'
  const calculationMode = job?.params?.calculation_mode || 'cooling'
  const isCombinedMode = calculationMode === 'cooling+heating'

  // 安全获取 artifacts 数组
  const artifacts = result?.artifacts || []
  
  // 查找 data.csv 文件
  const dataCsvFile = artifacts.find((a: any) => a.name === 'data.csv')

  // 查找中国功量地图图片（基于 AveragePower）
  const chinaMapImage = artifacts.find(
    (a: any) =>
      a.kind === 'image' &&
      typeof a.name === 'string' &&
      a.name.toLowerCase().includes('china_power_map_average_power'),
  ) || artifacts.find(
    (a: any) =>
      a.kind === 'image' &&
      typeof a.name === 'string' &&
      a.name.toLowerCase().includes('china') &&
      a.name.toLowerCase().includes('power') &&
      a.name.toLowerCase().includes('map'),
  )

  // 准备柱状图数据
  const barChartData = useMemo(() => {
    if (!csvData || csvData.length === 0) return null

    // 自动识别标签列（优先级：NAME > FQ > EPW > QID）
    const getLabelColumn = (row: any): string => {
      if (row.NAME && String(row.NAME).trim() !== '') return String(row.NAME).trim()
      if (row.FQ && String(row.FQ).trim() !== '') return String(row.FQ).trim()
      if (row.EPW && String(row.EPW).trim() !== '') return String(row.EPW).trim()
      if (row.QID !== undefined && row.QID !== null && String(row.QID).trim() !== '') return String(row.QID).trim()
      return ''
    }

    // 辅助函数：不区分大小写和空格地获取列值
    const getColumnValue = (row: any, columnName: string): any => {
      if (row[columnName] !== undefined) return row[columnName]
      const normalizedColumnName = columnName.trim().toLowerCase()
      for (const key in row) {
        const normalizedKey = key.trim().toLowerCase()
        if (normalizedKey === normalizedColumnName) {
          return row[key]
        }
      }
      return undefined
    }

    // 辅助函数：安全地解析数字
    const safeParseFloat = (value: any): number => {
      if (typeof value === 'number') return isNaN(value) ? 0 : value
      if (value === null || value === undefined || value === '') return 0
      const parsed = parseFloat(String(value))
      return isNaN(parsed) ? 0 : parsed
    }

    // 提取数据
    const validData = csvData
      .map(row => ({
        label: getLabelColumn(row),
        cooling: safeParseFloat(getColumnValue(row, 'Cooling')),
        heating: safeParseFloat(getColumnValue(row, 'Heating')),
        total: safeParseFloat(getColumnValue(row, 'Total')),
        averagePower: safeParseFloat(getColumnValue(row, 'AveragePower')),
      }))
      .filter(item => item.label !== '')

    if (validData.length === 0) {
      return null
    }

    // 根据标签类型选择排序方式
    const isNumeric = validData.every(item => !isNaN(parseFloat(item.label)))
    const sortedData = [...validData].sort((a, b) => {
      if (isNumeric) {
        return parseFloat(a.label) - parseFloat(b.label)
      } else {
        return a.label.localeCompare(b.label, 'zh-CN')
      }
    })

    const labels = sortedData.map(item => item.label)
    const cooling = sortedData.map(item => item.cooling)
    const heating = sortedData.map(item => item.heating)
    const total = sortedData.map(item => item.total)
    const averagePower = sortedData.map(item => item.averagePower)

    // 根据地图类型确定X轴标题
    const xAxisTitle = isChinaMap ? '省份' : isWorldMap ? '地区/网格' : '地区'

    return {
      labels,
      cooling,
      heating,
      total,
      averagePower,
      xAxisTitle,
      dataCount: validData.length,
    }
  }, [csvData, isChinaMap, isWorldMap])

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-lg font-semibold text-text-primary">功量地图分析详情</div>
          <div className="text-sm text-text-secondary">查看功量地图计算结果</div>
        </div>
        <div className="flex items-center gap-2">
          <HelpButton doc="material_comparison" />
          <Link to="/jobs">
            <Button variant="secondary">任务列表</Button>
          </Link>
          <Link to="/power-map">
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
              <div className="mt-1 text-sm text-text-primary">功量地图</div>
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
            <div className="text-xs font-semibold text-text-muted">计算方案</div>
            <div className="mt-1 text-sm text-text-secondary">
              {job?.params?.calculation_mode === 'cooling' ? '制冷' : 
               job?.params?.calculation_mode === 'heating' ? '制热' : 
               job?.params?.calculation_mode === 'cooling+heating' ? '制冷+制热' : '-'}
            </div>
          </div>
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
            <div className="text-xs font-semibold text-text-muted">相态点数量</div>
            <div className="mt-1 text-sm text-text-secondary">
              {job?.params?.phases?.length ?? '-'}
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
              {/* 全年功量柱状图 + 平均功率柱状图 */}
              {dataCsvFile ? (
                csvLoading ? (
                  <Card className="w-full">
                    <CardHeader>
                      <CardTitle>全年功量柱状图</CardTitle>
                      <CardDesc>正在加载数据...</CardDesc>
                    </CardHeader>
                    <div className="text-sm text-text-secondary p-4">加载中...</div>
                  </Card>
                ) : barChartData ? (
                  <>
                    {/* 全年功量柱状图（Wh/m²） */}
                    <Card className="w-full">
                      <CardHeader>
                        <CardTitle>全年功量柱状图</CardTitle>
                        <CardDesc>
                          {isCombinedMode 
                            ? '制冷+制热全年功量城市对比' 
                            : calculationMode === 'cooling' 
                              ? '制冷全年功量城市对比' 
                              : '制热全年功量城市对比'}（共 {barChartData.dataCount} 个城市）
                        </CardDesc>
                      </CardHeader>
                      <div className="rounded-field border border-border glass-light p-4">
                        <div className="h-[500px]">
                          <Plot
                            data={isCombinedMode ? [
                              {
                                x: barChartData.labels,
                                y: barChartData.cooling,
                                type: 'bar',
                                name: '全年制冷功量 (W/(m²·year))',
                                marker: { color: 'rgba(54, 162, 235, 0.8)' },
                              },
                              {
                                x: barChartData.labels,
                                y: barChartData.heating,
                                type: 'bar',
                                name: '全年制热功量 (W/(m²·year))',
                                marker: { color: 'rgba(255, 99, 132, 0.8)' },
                              },
                              {
                                x: barChartData.labels,
                                y: barChartData.total,
                                type: 'bar',
                                name: '全年总功量 (W/(m²·year))',
                                marker: { color: 'rgba(75, 192, 192, 0.8)' },
                              },
                            ] : [
                              {
                                x: barChartData.labels,
                                y: calculationMode === 'cooling' ? barChartData.cooling : barChartData.heating,
                                type: 'bar',
                                marker: {
                                  color: calculationMode === 'cooling' 
                                    ? 'rgba(54, 162, 235, 0.8)' 
                                    : 'rgba(255, 99, 132, 0.8)',
                                },
                                name: calculationMode === 'cooling' ? '全年制冷功量 (W/(m²·year))' : '全年制热功量 (W/(m²·year))',
                              },
                            ]}
                            layout={getPlotlyLayout({
                              title: {
                                text: isCombinedMode 
                                  ? '制冷+制热全年功量城市对比' 
                                  : calculationMode === 'cooling' 
                                    ? '制冷全年功量城市对比' 
                                    : '制热全年功量城市对比',
                                font: { size: 16 },
                              },
                              xaxis: {
                                title: { text: barChartData.xAxisTitle },
                                tickangle: barChartData.dataCount > 20 ? -45 : -30,
                                automargin: true,
                              },
                              yaxis: {
                                title: { text: '全年功量 (W/(m²·year))' },
                                rangemode: 'tozero',
                              },
                              margin: { b: barChartData.dataCount > 20 ? 120 : 100, t: 50, l: 80, r: 30 },
                              height: 500,
                              barmode: isCombinedMode ? 'group' : 'group',
                              legend: isCombinedMode ? {
                                orientation: 'h',
                                y: -0.2,
                                x: 0.5,
                                xanchor: 'center',
                              } : undefined,
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

                    {/* 平均功率柱状图（W/m²，基于 AveragePower 列） */}
                    <Card className="w-full">
                      <CardHeader>
                        <CardTitle>平均功率柱状图</CardTitle>
                        <CardDesc>
                          年平均功率城市对比（Total/8760，单位 W/m²）
                        </CardDesc>
                      </CardHeader>
                      <div className="rounded-field border border-border glass-light p-4">
                        <div className="h-[500px]">
                          <Plot
                            data={[
                              {
                                x: barChartData.labels,
                                y: barChartData.averagePower,
                                type: 'bar',
                                name: '年平均功率 (W/m²)',
                                marker: { color: 'rgba(255, 206, 86, 0.9)' },
                              },
                            ]}
                            layout={getPlotlyLayout({
                              title: {
                                text: '年平均功率城市对比',
                                font: { size: 16 },
                              },
                              xaxis: {
                                title: { text: barChartData.xAxisTitle },
                                tickangle: barChartData.dataCount > 20 ? -45 : -30,
                                automargin: true,
                              },
                              yaxis: {
                                title: { text: '年平均功率 (W/m²)' },
                                rangemode: 'tozero',
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
                      <CardTitle>全年功量柱状图</CardTitle>
                      <CardDesc>数据加载失败或数据为空</CardDesc>
                    </CardHeader>
                    <div className="text-sm text-text-secondary p-4">无法加载柱状图数据</div>
                  </Card>
                )
              ) : null}

              {/* 基于 AveragePower 的中国功量地图 */}
              {isChinaMap && chinaMapImage && (
                <Card className="w-full">
                  <CardHeader>
                    <CardTitle>中国功量地图（AveragePower）</CardTitle>
                    <CardDesc>根据 data.csv 中的 AveragePower 列绘制的中国省级功量分布图，鼠标右键-将图片另存为可下载</CardDesc>
                  </CardHeader>
                  <div className="rounded-field border border-border glass-light p-4">
                    <div className="w-full max-h-[640px] overflow-hidden rounded-field border border-border bg-bg-elevated">
                      <img
                        src={chinaMapImage.url.startsWith('http') ? chinaMapImage.url : `${window.location.origin}${chinaMapImage.url}`}
                        alt="中国功量地图（基于 AveragePower）"
                        className="w-full h-auto object-contain"
                      />
                    </div>
                    <div className="mt-2 text-xs text-text-muted">
                      说明：地图使用 data.csv 中的省份名称（NAME）与阿里云中国省级边界数据进行匹配，按 AveragePower 着色。
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
                        包含所有城市的功量计算结果
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
          ) : null
        ) : (
          <div className="text-sm text-text-secondary">计算进行中，请稍候...</div>
        )}
      </Card>
    </div>
  )
}
