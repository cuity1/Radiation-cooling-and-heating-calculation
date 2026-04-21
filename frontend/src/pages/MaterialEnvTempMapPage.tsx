import { useState, useMemo } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import Button from '../components/ui/Button'
import { Card, CardDesc, CardHeader, CardTitle } from '../components/ui/Card'
import MaterialPhaseEditor from '../components/MaterialPhaseEditor'
import { createMaterialEnvTempMapJob, type MaterialPhase, type MaterialEnvTempMapParams } from '../services/materialEnvTempMap'
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

export default function MaterialEnvTempMapPage() {
  const { t } = useTranslation()
  const nav = useNavigate()

  const [weatherGroup, setWeatherGroup] = useState<'china' | 'world' | 'world_weather2025'>('china')
  const [phases, setPhases] = useState<MaterialPhase[]>([
    {
      temperature: 20,
      emissivity: 0.9,
      absorptivity: 0.1,
    },
  ])
  const [transitionMode, setTransitionMode] = useState<'gradient' | 'step'>('gradient')
  const [hCoefficient, setHCoefficient] = useState<string>('20')
  const [coolingEfficiencyFactor, setCoolingEfficiencyFactor] = useState<string>('0.75')
  const [remark, setRemark] = useState('')

  const m = useMutation({
    mutationFn: createMaterialEnvTempMapJob,
    onSuccess: (res) => nav(`/material-env-temp-map/${res.job_id}`),
  })

  const canSubmit = useMemo(() => {
    const eff = parseFloat(coolingEfficiencyFactor)
    return phases.length >= 1 && !isNaN(eff) && eff >= 0.5 && eff <= 1.0
  }, [phases, coolingEfficiencyFactor])

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div>
              <CardTitle>材料温度地图</CardTitle>
              <CardDesc>
                根据辐射制冷物理模型，计算在EPW天气点条件下，材料制冷功率为0时的温度。
                与环境温度相减得到温差（ΔT = T_eq - T_a），生成全年最大温差和平均温差两张地图。
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

          <Field label="对流换热系数" hint="额外对流散热量（W/(m²·K)），系统内置基准 25 W/(m²·K)，默认输入 20，总对流散热 = 25 + 输入值 = 45 W/(m²·K)">
            <Input
              type="number"
              min="0"
              step="1"
              value={hCoefficient}
              onChange={(e) => setHCoefficient(e.target.value)}
              placeholder="例如：20"
            />
          </Field>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <Field
            label="辐射制冷效率修正系数"
            hint="用于补偿简化模型对辐射制冷效果的高估（0.5~1.0）。1.0 = 不修正；默认 0.75 = 将制冷贡献打75折。建议范围 0.70~0.85。"
          >
            <Input
              type="number"
              min="0.5"
              max="1.0"
              step="0.05"
              value={coolingEfficiencyFactor}
              onChange={(e) => setCoolingEfficiencyFactor(e.target.value)}
              placeholder="例如：0.75"
            />
          </Field>
        </div>

        <div className="mt-6">
          <MaterialPhaseEditor
            phases={phases}
            onChange={setPhases}
            transitionMode={transitionMode}
            onTransitionModeChange={setTransitionMode}
          />
        </div>

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
                const hVal = parseFloat(hCoefficient)
                if (isNaN(hVal) || hVal < 0) {
                  alert('对流换热系数必须为非负数')
                  return
                }
                const effVal = parseFloat(coolingEfficiencyFactor)
                if (isNaN(effVal) || effVal < 0.5 || effVal > 1.0) {
                  alert('辐射制冷效率修正系数必须在 0.5~1.0 之间')
                  return
                }

                const params: MaterialEnvTempMapParams = {
                  weather_group: weatherGroup,
                  phases: phases,
                  transition_mode: transitionMode,
                  h_coefficient: hVal,
                  cooling_efficiency_factor: effVal,
                }
                m.mutate({ params, remark: remark.trim() || undefined })
              }}
            >
              {m.isPending ? t('common.loading') : '开始计算'}
            </Button>
          </div>

          {m.isError ? (
            <div className="mt-4 rounded-xl border border-danger/30 bg-danger/10 backdrop-blur-sm p-3 text-sm text-text-secondary">
              创建任务失败：{m.error instanceof Error ? m.error.message : '未知错误'}
            </div>
          ) : null}
        </div>
      </Card>

      <Card className="glass-light">
        <CardHeader>
          <CardTitle>使用说明</CardTitle>
          <CardDesc>材料温度地图功能说明</CardDesc>
        </CardHeader>
        <div className="text-sm text-text-secondary leading-relaxed space-y-2">
          <p>
            <strong>功能说明：</strong>本工具基于辐射制冷物理模型，根据材料相态配置和环境辐射数据，
            求解制冷功率为0时的材料温度 T_eq，并计算与实际环境温度的差值 ΔT = T_eq - T_a。
          </p>
          <div>
            <strong>核心算法：</strong>
            <ul className="list-disc list-inside ml-4 mt-1">
              <li>热辐射+对流平衡方程：k·[εσ(T_eq⁴ - T_a⁴) + ε·IR_sky - α·G_solar] + h·(T_eq - T_a) = 0，其中 k 为辐射制冷效率修正系数（默认 0.75），h 为总对流换热系数（默认 25 + 用户输入）</li>
              <li>使用牛顿迭代法求解 T_eq</li>
              <li>ΔT = T_eq - T_a（越负越好）：ΔT 越负，材料相对环境降温越多，制冷效果越好</li>
              <li>效率修正：k &lt; 1 用于补偿简化宽带模型对辐射制冷效果的高估（天空有效温度、视角因子、非窗口波段等未精确建模）</li>
            </ul>
          </div>
          <div>
            <strong>输出结果：</strong>
            <ul className="list-disc list-inside ml-4 mt-1">
              <li>全年最大制冷温差地图（Max ΔT）：取全年每个时刻 ΔT = T_eq - T_a 的最小值（最深亚环境降温），ΔT 越负，制冷效果越好</li>
              <li>全年平均温差地图（Avg ΔT）：取全年 ΔT 的平均值，代表整体制冷效果</li>
              <li>柱状图：各城市/地区的最大制冷温差和平均温差对比</li>
              <li>数据下载：可下载完整计算结果 CSV 文件</li>
            </ul>
          </div>
          <div>
            <strong>材料相态配置：</strong>
            <ul className="list-disc list-inside ml-4 mt-1">
              <li>可以配置多个温度点及其对应的发射率和吸收率</li>
              <li>渐变模式：在相邻温度点之间进行高斯插值，平滑过渡</li>
              <li>突变模式：使用距离当前温度最近的相态点的值</li>
            </ul>
          </div>
        </div>
      </Card>
    </div>
  )
}
