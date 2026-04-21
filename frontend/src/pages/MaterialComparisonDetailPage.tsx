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

export default function MaterialComparisonDetailPage() {
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
    if (dataCsvFile && dataCsvFile.url) {
      setCsvLoading(true)
      // 确保URL是完整的
      const fullUrl = dataCsvFile.url.startsWith('http') 
        ? dataCsvFile.url 
        : `${window.location.origin}${dataCsvFile.url}`
      
      fetch(fullUrl)
        .then((res) => res.text())
        .then((text) => {
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
          
          setCsvData(data)
        })
        .catch((err) => {
          console.error('加载CSV失败:', err)
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
    if (job?.status === 'succeeded') return '分析完成'
    if (job?.status === 'failed') return '分析失败'
    return '分析进行中...'
  }

  // 判断是哪种地图类型
  const isWorldMap = job?.params?.weather_group === 'world' || job?.params?.weather_group === 'world_weather2025'
  const isChinaMap = job?.params?.weather_group === 'china'

  // 安全获取 artifacts 数组
  const artifacts = result?.artifacts || []
  
  // 查找data.csv文件
  const dataCsvFile = artifacts.find((a: any) => a.name === 'data.csv')
  
  // 查找Excel对比表（只显示 material_radiative_cooling_comparison_all.xlsx）
  const excelFiles = artifacts.filter((a: any) => 
    a.name?.endsWith('.xlsx') && a.name === 'material_radiative_cooling_comparison_all.xlsx'
  )
  
  // 查找所有PNG文件
  const pngFiles = artifacts.filter((a: any) => a.name?.endsWith('.png'))
  
  // 查找所有ZIP压缩包文件（output_*.zip）
  const zipFiles = artifacts.filter((a: any) => 
    a.name?.endsWith('.zip') && a.name?.toLowerCase().startsWith('output_')
  )
  
  // 中国地图：查找所有china_*.png文件（应该是6张：china_cooling_energy, china_heating_energy, china_total_energy, china_cooling_co2, china_heating_co2, china_total_co2）
  // 不包含合集图片 chinamap_energy_and_co2_grid.png
  const chinaMapPngs = useMemo(() => {
    if (!isChinaMap) return []
    
    const filtered = pngFiles.filter((a: any) => {
      const name = a.name?.toLowerCase() || ''
      return name.startsWith('china_') && !name.includes('grid') && name.endsWith('.png')
    })
    
    // 去重：按文件名去重，保留第一个
    const seen = new Set<string>()
    const unique = filtered.filter((a: any) => {
      const name = a.name?.toLowerCase() || ''
      if (seen.has(name)) {
        console.warn(`[DEBUG] 发现重复的中国地图文件：${name}`)
        return false
      }
      seen.add(name)
      return true
    })
    
    // 调试信息
    if (unique.length !== 6) {
      console.warn(`[DEBUG] 中国地图文件数量异常：期望6张，实际${unique.length}张`)
      console.warn(`[DEBUG] 找到的文件：`, unique.map((a: any) => a.name))
      console.warn(`[DEBUG] 所有PNG文件：`, pngFiles.map((a: any) => a.name))
    }
    
    // 按预期顺序排序
    const expectedOrder = [
      'china_cooling_energy.png',
      'china_heating_energy.png',
      'china_total_energy.png',
      'china_cooling_co2.png',
      'china_heating_co2.png',
      'china_total_co2.png'
    ]
    
    return unique.sort((a: any, b: any) => {
      const aIndex = expectedOrder.indexOf(a.name?.toLowerCase() || '')
      const bIndex = expectedOrder.indexOf(b.name?.toLowerCase() || '')
      if (aIndex === -1 && bIndex === -1) return 0
      if (aIndex === -1) return 1
      if (bIndex === -1) return -1
      return aIndex - bIndex
    })
  }, [isChinaMap, pngFiles])
  
  // 世界地图：查找所有world_*.png文件（包括world_*_robinson.png）
  const worldMapPngs = isWorldMap ? pngFiles.filter((a: any) => {
    const name = a.name?.toLowerCase() || ''
    return name.startsWith('world_') && name.endsWith('.png')
  }) : []

  // 准备柱状图数据 - 适配中国地图和世界地图的不同数据结构
  const barChartData = useMemo(() => {
    if (!csvData || csvData.length === 0) return null

    // 自动识别标签列（优先级：NAME > FQ > EPW > QID）
    // 中国模式：使用NAME（省份名）
    // 世界模式：使用FQ（气候区标识，如Af, Am, Aw等）或QID（网格ID）
    const getLabelColumn = (row: any): string => {
      if (row.NAME && String(row.NAME).trim() !== '') return String(row.NAME).trim()
      if (row.FQ && String(row.FQ).trim() !== '') return String(row.FQ).trim()
      if (row.EPW && String(row.EPW).trim() !== '') return String(row.EPW).trim()
      if (row.QID !== undefined && row.QID !== null && String(row.QID).trim() !== '') return String(row.QID).trim()
      return ''
    }

    // 辅助函数：不区分大小写和空格地获取列值
    const getColumnValue = (row: any, columnName: string): any => {
      // 先尝试精确匹配
      if (row[columnName] !== undefined) return row[columnName]
      // 规范化列名（去除空格，转小写）
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

    // 提取数据，过滤掉无效行
    // 注意：列名可能是 "Cooling saving", "Heating saving", "Total saving" 或 "Cooling", "Heating", "Total"
    const validData = csvData
      .map(row => ({
        label: getLabelColumn(row),
        cooling: safeParseFloat(getColumnValue(row, 'Cooling saving')) || safeParseFloat(getColumnValue(row, 'Cooling')),
        heating: safeParseFloat(getColumnValue(row, 'Heating saving')) || safeParseFloat(getColumnValue(row, 'Heating')),
        total: safeParseFloat(getColumnValue(row, 'Total saving')) || safeParseFloat(getColumnValue(row, 'Total')),
        coolingPercent: safeParseFloat(getColumnValue(row, 'Cooling%')),
        heatingPercent: safeParseFloat(getColumnValue(row, 'Heating%')),
        totalPercent: safeParseFloat(getColumnValue(row, 'Total%')),
      }))
      .filter(item => item.label !== '')

    if (validData.length === 0) {
      // 调试：输出可用的列名
      if (csvData.length > 0) {
        console.warn('CSV数据解析失败：未找到有效数据行。可用列名：', Object.keys(csvData[0]))
      }
      return null
    }

    // 调试：检查数据是否全为0
    const hasNonZeroData = validData.some(item => 
      item.cooling !== 0 || item.heating !== 0 || item.total !== 0
    )
    if (!hasNonZeroData && validData.length > 0) {
      console.warn('警告：所有绝对值数据都为0，但百分比数据可能正常。')
    }

    // 根据标签类型选择排序方式
    const isNumeric = validData.every(item => !isNaN(parseFloat(item.label)))
    const sortedData = [...validData].sort((a, b) => {
      if (isNumeric) {
        return parseFloat(a.label) - parseFloat(b.label)
      } else {
        // 中文或英文名称排序
        return a.label.localeCompare(b.label, 'zh-CN')
      }
    })

    const labels = sortedData.map(item => item.label)
    const cooling = sortedData.map(item => item.cooling)
    const heating = sortedData.map(item => item.heating)
    const total = sortedData.map(item => item.total)
    const coolingPercent = sortedData.map(item => item.coolingPercent)
    const heatingPercent = sortedData.map(item => item.heatingPercent)
    const totalPercent = sortedData.map(item => item.totalPercent)

    // 根据地图类型确定X轴标题
    const xAxisTitle = isChinaMap ? '省份' : isWorldMap ? '地区/网格' : '地区'

    return {
      labels,
      cooling,
      heating,
      total,
      coolingPercent,
      heatingPercent,
      totalPercent,
      xAxisTitle,
      dataCount: validData.length,
    }
  }, [csvData, isChinaMap, isWorldMap])

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-lg font-semibold text-text-primary">节能地图分析详情</div>
          <div className="text-sm text-text-secondary">查看材料辐射节能效果对比分析结果</div>
        </div>
        <div className="flex items-center gap-2">
          <HelpButton doc="material_comparison" />
          <Link to="/jobs">
            <Button variant="secondary">任务列表</Button>
          </Link>
          <Link to="/map">
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
              <div className="mt-1 text-sm text-text-primary">节能地图</div>
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

        <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-field border border-border glass-light p-3">
              <div className="text-xs font-semibold text-text-muted">天气组</div>
              <div className="mt-1 text-sm text-text-secondary">
                {job?.params?.weather_group === 'world' ? '世界' : 
                 job?.params?.weather_group === 'world_weather2025' ? '世界2025' : '中国'}
              </div>
            </div>
          <div className="rounded-field border border-border glass-light p-3">
            <div className="text-xs font-semibold text-text-muted">场景数量</div>
            <div className="mt-1 text-sm text-text-secondary">
              {result?.summary?.scenarios_count ?? job?.params?.scenarios?.length ?? '-'}
            </div>
          </div>
          <div className="rounded-field border border-border glass-light p-3">
            <div className="text-xs font-semibold text-text-muted">计算引擎</div>
            <div className="mt-1 text-sm text-text-secondary">
              EnergyPlus
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
              <CardTitle>分析结果</CardTitle>
              <CardDesc>{statusDesc()}</CardDesc>
            </div>

            {job?.status === 'succeeded' && result ? (
              <div className="flex items-center gap-2">
                {dataCsvFile && (
                  <a href={dataCsvFile.url} download={dataCsvFile.name}>
                    <Button variant="secondary">下载 data.csv</Button>
                  </a>
                )}
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
              {/* 地图可视化 - 只显示PNG */}
              {isChinaMap && chinaMapPngs && chinaMapPngs.length > 0 ? (
                <Card className="w-full">
                  <CardHeader>
                    <CardTitle>中国地图可视化</CardTitle>
                    <CardDesc>节能效果地理分布图（共 {chinaMapPngs.length} 张地图）</CardDesc>
                  </CardHeader>
                  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {chinaMapPngs.map((pngFile: any, idx: number) => (
                      <div key={pngFile.name || pngFile.url || idx} className="space-y-2">
                        <div className="rounded-field border border-border overflow-hidden glass-light">
                          <img
                            src={pngFile.url}
                            alt={pngFile.name}
                            className="w-full h-auto cursor-pointer hover:opacity-90 transition-opacity"
                            onClick={() => {
                              window.open(pngFile.url, '_blank')
                            }}
                          />
                        </div>
                        <div className="flex items-center justify-between">
                          <div className="text-xs text-text-muted truncate flex-1 mr-2">
                            {pngFile.name}
                          </div>
                          <a href={pngFile.url} download={pngFile.name}>
                            <Button variant="secondary" size="sm">下载</Button>
                          </a>
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="mt-4 text-xs text-text-muted">
                    提示：可下载data.csv在工具箱中使用工具重绘地图
                  </div>
                </Card>
              ) : isWorldMap && worldMapPngs && worldMapPngs.length > 0 ? (
                <Card className="w-full">
                  <CardHeader>
                    <CardTitle>世界地图可视化</CardTitle>
                    <CardDesc>节能效果地理分布图（共 {worldMapPngs.length} 张地图）</CardDesc>
                  </CardHeader>
                  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {worldMapPngs.map((pngFile: any, idx: number) => (
                      <div key={idx} className="space-y-2">
                        <div className="rounded-field border border-border overflow-hidden glass-light">
                          <img
                            src={pngFile.url}
                            alt={pngFile.name}
                            className="w-full h-auto cursor-pointer hover:opacity-90 transition-opacity"
                            onClick={() => {
                              window.open(pngFile.url, '_blank')
                            }}
                          />
                        </div>
                        <div className="flex items-center justify-between">
                          <div className="text-xs text-text-muted truncate flex-1 mr-2">
                            {pngFile.name}
                          </div>
                          <a href={pngFile.url} download={pngFile.name}>
                            <Button variant="secondary" size="sm">下载</Button>
                          </a>
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="mt-4 text-xs text-text-muted">
                    提示：可下载data.csv在工具箱中使用工具重绘地图
                  </div>
                </Card>
              ) : null}

              {/* 柱状图可视化 - 基于 data.csv */}
              {dataCsvFile ? (
                csvLoading ? (
                  <Card className="w-full">
                    <CardHeader>
                      <CardTitle>节能效果统计（绝对值）</CardTitle>
                      <CardDesc>正在加载 data.csv 数据...</CardDesc>
                    </CardHeader>
                    <div className="text-sm text-text-secondary p-4">正在加载数据...</div>
                  </Card>
                ) : barChartData ? (
                <>
                  {/* 第一张图：绝对值（Cooling, Heating, Total） */}
                  <Card className="w-full">
                    <CardHeader>
                      <CardTitle>节能效果统计（绝对值）</CardTitle>
                      <CardDesc>
                        基于 data.csv 的节能效果统计
                        {isChinaMap ? '（按省份）' : isWorldMap ? '（按地区/网格）' : '（按地区）'}
                        （共 {barChartData.dataCount} 条数据）
                      </CardDesc>
                    </CardHeader>
                    <div className="rounded-2xl border border-border glass-light p-3">
                      <div className="h-[500px]">
                        <Plot
                          data={[
                            {
                              x: barChartData.labels,
                              y: barChartData.cooling,
                              name: '制冷节能 (MJ/m²/year)',
                              type: 'bar',
                              marker: { color: '#045FB4' },
                            },
                            {
                              x: barChartData.labels,
                              y: barChartData.heating,
                              name: '制热节能 (MJ/m²/year)',
                              type: 'bar',
                              marker: { color: '#B40404' },
                            },
                            {
                              x: barChartData.labels,
                              y: barChartData.total,
                              name: '总节能 (MJ/m²/year)',
                              type: 'bar',
                              marker: { color: '#0B6121' },
                            },
                          ]}
                            layout={getPlotlyLayout({
                              autosize: true,
                              margin: { l: 80, r: 20, t: 20, b: barChartData.dataCount > 20 ? 120 : 100 },
                              xaxis: { 
                                title: barChartData.xAxisTitle,
                                tickangle: barChartData.dataCount > 20 ? -45 : -30,
                                automargin: true,
                              },
                              yaxis: { 
                                title: '节能效果 (MJ/m²/year)',
                                rangemode: 'tozero',  // 确保从0开始显示
                              },
                              legend: { 
                                orientation: 'h',
                                y: -0.2,
                                x: 0.5,
                                xanchor: 'center',
                              },
                              barmode: 'group',
                            })}
                            config={{ 
                              displayModeBar: true, 
                              responsive: true,
                              modeBarButtonsToRemove: ['pan2d', 'lasso2d'],
                            }}
                            style={{ width: '100%', height: '100%' }}
                          />
                        </div>
                      </div>
                  </Card>

                  {/* 第二张图：百分比（Cooling%, Heating%, Total%） */}
                  <Card className="w-full">
                    <CardHeader>
                      <CardTitle>节能效率统计（百分比）</CardTitle>
                      <CardDesc>
                        基于 data.csv 的节能效率百分比统计
                        {isChinaMap ? '（按省份）' : isWorldMap ? '（按地区/网格）' : '（按地区）'}
                        （共 {barChartData.dataCount} 条数据）
                      </CardDesc>
                    </CardHeader>
                    <div className="rounded-2xl border border-border glass-light p-3">
                        <div className="h-[500px]">
                          <Plot
                            data={[
                              {
                                x: barChartData.labels,
                                y: barChartData.coolingPercent,
                                name: '制冷节能效率 (%)',
                                type: 'bar',
                                marker: { color: '#045FB4' },
                              },
                              {
                                x: barChartData.labels,
                                y: barChartData.heatingPercent,
                                name: '制热节能效率 (%)',
                                type: 'bar',
                                marker: { color: '#B40404' },
                              },
                              {
                                x: barChartData.labels,
                                y: barChartData.totalPercent,
                                name: '总节能效率 (%)',
                                type: 'bar',
                                marker: { color: '#0B6121' },
                              },
                            ]}
                            layout={getPlotlyLayout({
                              autosize: true,
                              margin: { l: 80, r: 20, t: 20, b: barChartData.dataCount > 20 ? 120 : 100 },
                              xaxis: { 
                                title: barChartData.xAxisTitle,
                                tickangle: barChartData.dataCount > 20 ? -45 : -30,
                                automargin: true,
                              },
                              yaxis: { 
                                title: '节能效率 (%)',
                                rangemode: 'tozero',  // 确保从0开始显示
                              },
                              legend: { 
                                orientation: 'h',
                                y: -0.2,
                                x: 0.5,
                                xanchor: 'center',
                              },
                              barmode: 'group',
                            })}
                            config={{ 
                              displayModeBar: true, 
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
                      <CardTitle>节能效果统计（绝对值）</CardTitle>
                      <CardDesc>
                        基于 data.csv 的节能效果统计
                        {isChinaMap ? '（按省份）' : isWorldMap ? '（按地区/网格）' : '（按地区）'}
                      </CardDesc>
                    </CardHeader>
                    <div className="text-sm text-text-secondary p-4 space-y-2">
                      <div>无法解析 data.csv 数据或数据为空。</div>
                      <div className="text-xs text-text-muted">
                        CSV文件已找到，但数据解析失败。可能的原因：
                        <ul className="list-disc list-inside mt-1 space-y-1">
                          <li>CSV文件格式不正确</li>
                          <li>缺少必要的列（Cooling saving/Heating saving/Total saving 或 Cooling/Heating/Total，以及 NAME/FQ/QID）</li>
                          <li>所有数据行都被过滤掉</li>
                        </ul>
                      </div>
                      {csvData.length > 0 && (
                        <div className="text-xs text-text-muted mt-2">
                          已加载 {csvData.length} 行原始数据，但无法生成图表。
                        </div>
                      )}
                    </div>
                  </Card>
                )
              ) : null}

              {/* 地图可视化 - 未找到文件时的提示 */}
              {!isChinaMap && !isWorldMap && (
                <Card className="w-full">
                  <CardHeader>
                    <CardTitle>地图可视化</CardTitle>
                    <CardDesc>地图文件生成中或未找到...</CardDesc>
                  </CardHeader>
                  <div className="text-sm text-text-secondary p-4 space-y-2">
                    {job?.status === 'succeeded' ? (
                      <>
                        <div>未找到地图文件，可能地图生成失败或尚未完成。</div>
                        {artifacts.length > 0 ? (
                          <div className="mt-2">
                            <div className="text-xs font-semibold text-text-muted mb-1">已生成的文件列表（共 {artifacts.length} 个）：</div>
                            <div className="text-xs text-text-muted space-y-1 max-h-32 overflow-y-auto">
                              {artifacts.map((a: any, idx: number) => (
                                <div key={idx}>• {a.name} ({a.kind || 'file'})</div>
                              ))}
                            </div>
                            <div className="mt-2 text-xs text-text-muted">
                              提示：中国地图应包含多个 chinamap_*.png 文件，世界地图应包含多个 world_*.png 文件
                            </div>
                          </div>
                        ) : (
                          <div className="mt-2 text-xs text-text-muted">
                            未找到任何生成的文件。请检查任务是否成功完成。
                          </div>
                        )}
                      </>
                    ) : (
                      <div>任务完成后将显示地图可视化结果。</div>
                    )}
                  </div>
                </Card>
              )}

              {/* 数据文件列表 */}
              <Card>
                <CardHeader>
                  <CardTitle>生成的文件</CardTitle>
                  <CardDesc>共 {result.artifacts?.length ?? 0} 个文件</CardDesc>
                </CardHeader>
                <div className="grid gap-2">
                  {dataCsvFile && (
                    <div className="flex items-center justify-between rounded-field border border-border glass-light p-3">
                      <div>
                        <div className="text-sm font-semibold text-text-primary">{dataCsvFile.name}</div>
                        <div className="text-xs text-text-muted">地图数据CSV文件，使用该文件在工具箱中绘制地图</div>
                      </div>
                      <a href={dataCsvFile.url} download={dataCsvFile.name}>
                        <Button variant="secondary" size="sm">下载</Button>
                      </a>
                    </div>
                  )}

                  {zipFiles && zipFiles.length > 0 && (
                    <div className="space-y-2">
                      <div className="text-xs font-semibold text-text-muted">输出文件压缩包</div>
                      {zipFiles.map((file: any, idx: number) => (
                        <div key={idx} className="flex items-center justify-between rounded-field border border-border glass-light p-3 bg-[rgba(69,95,180,0.10)] border-[rgba(69,95,180,0.35)]">
                          <div>
                            <div className="text-sm font-semibold text-text-primary">{file.name}</div>
                            <div className="text-xs text-text-muted">包含所有EnergyPlus输出文件的压缩包（output目录）</div>
                          </div>
                          <a href={file.url} download={file.name}>
                            <Button variant="primary" size="sm">下载压缩包</Button>
                          </a>
                        </div>
                      ))}
                    </div>
                  )}

                  {excelFiles && excelFiles.length > 0 && (
                    <div className="space-y-2">
                      <div className="text-xs font-semibold text-text-muted">Excel对比表</div>
                      {excelFiles.map((file: any, idx: number) => (
                        <div key={idx} className="flex items-center justify-between rounded-field border border-border glass-light p-3">
                          <div>
                            <div className="text-sm font-semibold text-text-primary">{file.name}</div>
                            <div className="text-xs text-text-muted">节能地图结果表</div>
                          </div>
                          <a href={file.url} download={file.name}>
                            <Button variant="secondary" size="sm">下载</Button>
                          </a>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* 其他PNG文件（不包括已在地图可视化中显示的） */}
                  {pngFiles && pngFiles.length > 0 && (
                    <div className="space-y-2">
                      <div className="text-xs font-semibold text-text-muted">绘图使用数据文件</div>
                      <div className="grid gap-2 md:grid-cols-2">
                        {pngFiles
                          .filter((file: any) => {
                            // 排除已在地图可视化中显示的图片
                            if (isWorldMap && worldMapPngs?.some((p: any) => p.name === file.name)) {
                              return false
                            }
                            if (isChinaMap && chinaMapPngs?.some((p: any) => p.name === file.name)) {
                              return false
                            }
                            return true
                          })
                          .map((file: any, idx: number) => (
                            <div key={idx} className="flex items-center justify-between rounded-field border border-border glass-light p-3">
                              <div>
                                <div className="text-sm font-semibold text-text-primary">{file.name}</div>
                              </div>
                              <a href={file.url} download={file.name}>
                                <Button variant="secondary" size="sm">下载</Button>
                              </a>
                            </div>
                          ))}
                      </div>
                    </div>
                  )}

                  {/* 其他文件 */}
                  {result.artifacts
                    ?.filter((a: any) => 
                      a.name !== 'data.csv' && 
                      !a.name?.endsWith('.html') && 
                      !a.name?.endsWith('.xlsx') && 
                      !a.name?.endsWith('.png') &&
                      !(a.name?.endsWith('.zip') && a.name?.toLowerCase().startsWith('output_'))
                    )
                    .map((file: any, idx: number) => (
                      <div key={idx} className="flex items-center justify-between rounded-field border border-border glass-light p-3">
                        <div>
                          <div className="text-sm font-semibold text-text-primary">{file.name}</div>
                        </div>
                        <a href={file.url} download={file.name}>
                          <Button variant="secondary" size="sm">下载</Button>
                        </a>
                      </div>
                    ))}
                </div>
              </Card>

              {/* 结果摘要 */}
              <Card className="glass-light">
                <CardHeader>
                  <CardTitle>结果摘要</CardTitle>
                  <CardDesc>分析统计信息</CardDesc>
                </CardHeader>
                <div className="grid gap-3 md:grid-cols-3">
                    <div className="rounded-field border border-border glass-light p-3">
                      <div className="text-xs font-semibold text-text-muted">天气组</div>
                      <div className="mt-1 text-sm text-text-primary">
                        {result.summary?.weather_group === 'world' ? '世界' : 
                         result.summary?.weather_group === 'world_weather2025' ? '世界2025' : '中国'}
                      </div>
                    </div>
                  <div className="rounded-field border border-border glass-light p-3">
                    <div className="text-xs font-semibold text-text-muted">场景数量</div>
                    <div className="mt-1 text-sm text-text-primary">{result.summary?.scenarios_count ?? '-'}</div>
                  </div>
                  <div className="rounded-field border border-border glass-light p-3">
                    <div className="text-xs font-semibold text-text-muted">生成文件数</div>
                    <div className="mt-1 text-sm text-text-primary">{result.summary?.output_files_count ?? result.artifacts?.length ?? 0}</div>
                  </div>
                </div>
              </Card>

              {/* CO2减排计算说明 */}
              <Card className="glass-light">
                <CardHeader>
                  <CardTitle>CO₂ 减排量计算说明</CardTitle>
                  <CardDesc>了解节能地图中 CO₂ 减排量的计算方式</CardDesc>
                </CardHeader>
                <div className="glass-light mt-2 rounded-field border border-border p-4 text-sm text-text-secondary space-y-3">
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900/50 text-blue-600 dark:text-blue-300 flex items-center justify-center font-semibold text-sm">1</div>
                    <div>
                      <div className="font-medium text-text-primary mb-1">计算公式</div>
                      <div className="font-mono bg-slate-50 dark:bg-slate-700 text-slate-800 dark:text-slate-100 rounded px-3 py-2 text-xs border border-slate-200 dark:border-slate-600">
                        CO₂ 减排量 = 能耗节约量 × 0.138
                      </div>
                      <div className="text-xs text-text-muted mt-1">
                        即：CO₂ 减排量 (kg/m²/year) = 能耗节约量 (MJ/m²/year) × 0.138
                      </div>
                    </div>
                  </div>
                  
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900/50 text-blue-600 dark:text-blue-300 flex items-center justify-center font-semibold text-sm">2</div>
                    <div>
                      <div className="font-medium text-text-primary mb-1">能耗节约量计算</div>
                      <div className="font-mono bg-slate-50 dark:bg-slate-700 text-slate-800 dark:text-slate-100 rounded px-3 py-2 text-xs border border-slate-200 dark:border-slate-600">
                        能耗节约量 = 基准材料能耗 − 辐射冷却材料能耗
                      </div>
                      <div className="text-xs text-text-muted mt-1">
                        单位：MJ/m²/year（兆焦耳/平方米/年）
                      </div>
                    </div>
                  </div>
                  
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900/50 text-blue-600 dark:text-blue-300 flex items-center justify-center font-semibold text-sm">3</div>
                    <div>
                      <div className="font-medium text-text-primary mb-1">碳排放因子说明</div>
                      <div className="text-xs">
                        系数 <span className="font-mono bg-slate-50 dark:bg-slate-700 text-slate-800 dark:text-slate-100 rounded px-1 border border-slate-200 dark:border-slate-600">0.138</span> 是基于电网碳排放因子（≈ 0.5 kgCO₂/kWh）计算的转换系数：
                        <div className="mt-1 font-mono bg-slate-50 dark:bg-slate-700 text-slate-800 dark:text-slate-100 rounded px-3 py-2 text-xs border border-slate-200 dark:border-slate-600">
                          0.138 ≈ 0.5 kgCO₂/kWh × 0.2778 kWh/MJ
                        </div>
                      </div>
                    </div>
                  </div>
                  
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900/50 text-blue-600 dark:text-blue-300 flex items-center justify-center font-semibold text-sm">4</div>
                    <div>
                      <div className="font-medium text-text-primary mb-1">地图说明</div>
                      <div className="text-xs text-text-muted">
                        地图中 <span className="text-green-600 dark:text-green-400 font-medium">*_energy.png</span> 显示能耗节约量，
                        <span className="text-green-600 dark:text-green-400 font-medium"> *_co2.png</span> 显示对应的 CO₂ 减排量。
                      </div>
                    </div>
                  </div>
                </div>
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
          ) : null
        ) : (
          <div className="text-sm text-text-secondary">分析进行中，请稍候...</div>
        )}
      </Card>
    </div>
  )
}
