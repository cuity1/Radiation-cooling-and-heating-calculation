import { useState, useMemo } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import Button from '../components/ui/Button'
import { Card, CardDesc, CardHeader, CardTitle } from '../components/ui/Card'
import MaterialPhaseEditor, { type MaterialPhaseEditorProps } from '../components/MaterialPhaseEditor'
import { createRadiationCoolingClothingJob, type MaterialPhase, type RadiationCoolingClothingParams } from '../services/radiationCoolingClothing'
import HelpButton from '../components/Help/HelpButton'

function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className={
        'w-full rounded-field border border-border glass-light px-3.5 py-2.5 text-sm text-text-primary ' +
        'transition-all duration-150 cursor-pointer ' +
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 focus-visible:border-accent/50 ' +
        'hover:border-border-light hover:bg-bg-elevated'
      }
    />
  )
}

function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={
        'w-full rounded-field border border-border glass-light px-3.5 py-2.5 text-sm text-text-primary ' +
        'transition-all duration-150 ' +
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 focus-visible:border-accent/50 ' +
        'hover:border-border-light hover:bg-bg-elevated ' +
        (props.className || '')
      }
    />
  )
}

function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <div className="space-y-1">
      <div className="text-xs font-semibold text-text-secondary">{label}</div>
      {children}
      {hint ? <div className="text-xs text-text-muted">{hint}</div> : null}
    </div>
  )
}

export default function RadiationCoolingClothingPage() {
  const { t } = useTranslation()
  const nav = useNavigate()

  const [weatherGroup, setWeatherGroup] = useState<'china' | 'world' | 'world_weather2025'>('china')
  const [phases, setPhases] = useState<MaterialPhase[]>([
    {
      temperature: 20,
      emissivity: 0.9,
      absorptivity: 0.6,
    },
  ])
  const [transitionMode, setTransitionMode] = useState<'gradient' | 'step'>('gradient')
  const [enableLatentHeat, setEnableLatentHeat] = useState(false)
  const [wetFraction, setWetFraction] = useState<string>('1')
  const [clothingAreaPerPerson, setClothingAreaPerPerson] = useState<string>('')
  const [remark, setRemark] = useState('')

  const m = useMutation({
    mutationFn: createRadiationCoolingClothingJob,
    onSuccess: (res) => nav(`/radiation-cooling-clothing/${res.job_id}`),
  })

  const canSubmit = useMemo(() => {
    // 需要至少1个相态点
    if (phases.length < 1) return false
    // 需要衣物面积/人大于0
    const area = parseFloat(clothingAreaPerPerson)
    if (isNaN(area) || area <= 0) return false
    return true
  }, [phases, clothingAreaPerPerson])

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div>
              <CardTitle>辐射制冷服饰</CardTitle>
              <CardDesc>
                使用EPW天气文件数据，计算辐射制冷服饰的制冷功量。
                系统会根据各省级行政区的人口数据，计算总制冷功量（年平均功率 × 衣物面积/人 × 人口数）。
                对于中国天气组（china），系统会自动根据 data.csv 中的 AveragePower 列和各省级行政区人口数据绘制中国省级制冷功量地图。
              </CardDesc>
            </div>
            <HelpButton doc="material_comparison" />
          </div>
        </CardHeader>

        <div className="grid gap-4 md:grid-cols-2">
          <Field label="天气组选择" hint="请选择中国天气文件组">
            <Select
              value={weatherGroup}
              onChange={(e) => setWeatherGroup(e.target.value as 'china' | 'world' | 'world_weather2025')}
            >
              <option value="china">中国（china_weather）</option>
              <option value="world">世界（world_weather）</option>
              <option value="world_weather2025">世界2025（world_weather2025）</option>
            </Select>
          </Field>

          <Field label="衣物面积/人" hint="请输入每人的衣物面积（单位：m²）">
            <Input
              type="number"
              step="0.01"
              min="0"
              value={clothingAreaPerPerson}
              onChange={(e) => setClothingAreaPerPerson(e.target.value)}
              placeholder="例如：1.5"
            />
          </Field>
        </div>

        <div className="mt-4 space-y-3">
          <label className="inline-flex items-center gap-2 text-xs cursor-pointer select-none text-text-secondary">
            <input
              type="checkbox"
              checked={enableLatentHeat}
              onChange={(e) => setEnableLatentHeat(e.target.checked)}
              className="h-4 w-4 rounded border-border text-accent focus-visible:ring-2 focus-visible:ring-accent/50 focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
            />
            <span className="font-semibold text-text-secondary">启用蒸发冷却</span>
            <span className="text-[11px] text-text-muted">
              使用天气文件中的相对湿度，叠加蒸发潜热制冷功率
            </span>
          </label>
          
          {enableLatentHeat && (
            <div className="ml-6">
              <Field label="蒸发冷却强度" hint="材料表面润湿面积比例（0-1），1表示完全湿润，0表示完全干燥">
                <Input
                  type="number"
                  min="0"
                  max="1"
                  step="0.01"
                  value={wetFraction}
                  onChange={(e) => setWetFraction(e.target.value)}
                  placeholder="例如：1.0"
                />
              </Field>
            </div>
          )}
        </div>

        <div className="mt-6">
          <MaterialPhaseEditor
            phases={phases}
            onChange={setPhases}
            transitionMode={transitionMode}
            onTransitionModeChange={setTransitionMode}
          />
        </div>

        {/* 按钮和错误提示区域 */}
        <div className="mt-6 pt-4 border-t border-border">
          <div className="mb-4 rounded-xl border border-border glass-light px-3 py-3">
            <div className="text-xs font-semibold text-text-muted mb-1">{t('job.remark')}</div>
            <div className="text-xs text-text-muted mb-2">{remark.length} / 50</div>
            <input
              type="text"
              value={remark}
              onChange={(e) => { if (e.target.value.length <= 50) setRemark(e.target.value) }}
              maxLength={50}
              placeholder={t('job.remark')}
              className={
                'w-full rounded-field border border-border glass-light px-3.5 py-2.5 text-sm text-text-primary ' +
                'placeholder:text-text-muted transition-all duration-150 ' +
                'focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 focus-visible:border-accent/50 ' +
                'hover:border-border-light hover:bg-bg-elevated'
              }
            />
          </div>
          <div className="flex items-center justify-end gap-2">
            <Button variant="secondary" onClick={() => nav('/jobs')}>
              {t('common.cancel')}
            </Button>
            <Button
              variant="secondary"
              disabled={!canSubmit || m.isPending}
              onClick={() => {
                // 验证衣物面积
                const areaValue = parseFloat(clothingAreaPerPerson)
                if (isNaN(areaValue) || areaValue <= 0) {
                  alert('请输入有效的衣物面积/人（必须大于0）')
                  return
                }
                
                // 验证 wet_fraction 值
                let wetFractionValue: number | undefined = undefined
                if (enableLatentHeat) {
                  if (wetFraction.trim() === '') {
                    wetFractionValue = 1.0  // 默认值
                  } else {
                    const parsed = parseFloat(wetFraction)
                    if (isNaN(parsed) || parsed < 0 || parsed > 1) {
                      alert('蒸发冷却强度必须在0-1之间')
                      return
                    }
                    wetFractionValue = parsed
                  }
                }
                
                // 构建参数对象，只包含有效的值
                const params: RadiationCoolingClothingParams = {
                  weather_group: weatherGroup,
                  phases: phases,
                  transition_mode: transitionMode,
                  clothing_area_per_person: areaValue,
                }

                // 只在启用蒸发冷却时添加相关参数
                if (enableLatentHeat) {
                  params.enable_latent_heat = true
                  if (wetFractionValue !== undefined) {
                    params.wet_fraction = wetFractionValue
                  }
                }

                m.mutate({ params, remark: remark.trim() || undefined })
              }}
            >
              {m.isPending ? t('common.loading') : '开始计算'}
            </Button>
          </div>

          {m.isError ? (
            <div className="mt-4 rounded-xl border border-danger/30 bg-danger/10 backdrop-blur-sm p-3 text-sm text-text-secondary">
              <div className="font-semibold text-text-primary mb-1">创建任务失败</div>
              <div>
                {m.error instanceof Error ? (
                  <>
                    {m.error.message}
                    {'detail' in m.error && typeof (m.error as any).detail === 'string' && (
                      <div className="mt-2 text-xs text-text-muted">
                        详细信息: {(m.error as any).detail}
                      </div>
                    )}
                    {'response' in m.error && (m.error as any).response?.data && (
                      <div className="mt-2 text-xs text-text-muted">
                        错误详情: {JSON.stringify((m.error as any).response.data, null, 2)}
                      </div>
                    )}
                  </>
                ) : (
                  '未知错误'
                )}
              </div>
            </div>
          ) : null}
        </div>
      </Card>

      <Card className="glass-light">
        <CardHeader>
          <CardTitle>使用说明</CardTitle>
          <CardDesc>辐射制冷服饰功能说明</CardDesc>
        </CardHeader>
        <div className="text-sm text-text-secondary leading-relaxed space-y-2">
          <p>
            <strong>功能说明：</strong>本工具使用EPW天气文件数据，根据材料相态配置计算制冷功量，并考虑人口数据计算总制冷功量。
          </p>
          <p>
            <strong>计算方案：</strong>
            <ul className="list-disc list-inside ml-4 mt-1">
              <li><strong>制冷：</strong>计算每小时总热辐射能量减去红外天空辐射，乘以发射率，得到净热辐射（小于0则设为0），对所有小时求和得到制冷功量（Wh）</li>
              <li><strong>总制冷功量：</strong>年平均功率（W/m²）× 衣物面积/人（m²）× 人口数（人）= 总制冷功量（W）</li>
            </ul>
          </p>
          <p>
            <strong>材料相态配置：</strong>
            <ul className="list-disc list-inside ml-4 mt-1">
              <li>可以配置多个温度点及其对应的发射率和吸收率</li>
              <li>渐变模式：在相邻温度点之间进行线性插值，每1°C插值1个点</li>
              <li>突变模式：使用距离当前温度最近的相态点的值</li>
            </ul>
          </p>
          <p>
            <strong>人口数据：</strong>系统会自动从 data.csv 文件中读取各省级行政区的人口数据，用于计算总制冷功量。
          </p>
        </div>
      </Card>
    </div>
  )
}
