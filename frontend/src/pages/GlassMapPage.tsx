import { useState, useEffect, useMemo } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import Button from '../components/ui/Button'
import { Card, CardDesc, CardHeader, CardTitle } from '../components/ui/Card'
import Segmented from '../components/ui/Segmented'
import ColormapSelector, { DEFAULT_COLORMAP_PARAMS } from '../components/ColormapSelector'
import { createGlassComparisonJob, type GlassScenario, type GlobalParams, type GlassProperties } from '../services/glass_materials'
import { useAuth } from '../context/AuthContext'
import HelpButton from '../components/Help/HelpButton'
import { hasCache, loadParamsFromCache, debouncedSave, getCacheTimestamp, formatCacheTime, exportParams, importParamsFromFile, clearCache, getDefaultScenarios, getDefaultColormapParams, DEFAULT_GLOBAL_PARAMS } from '../services/glassCache'


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

function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={
        'w-full rounded-field border border-border glass-light px-3.5 py-2.5 text-sm text-text-primary ' +
        'placeholder:text-text-muted transition-all duration-150 ' +
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 focus-visible:border-accent/50 ' +
        'hover:border-border-light hover:bg-bg-elevated'
      }
    />
  )
}

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

function NumberInput({
  value,
  onChange,
  min,
  max,
  step,
  placeholder,
  disabled,
}: {
  value: number | null
  onChange: (value: number | null) => void
  min?: number
  max?: number
  step?: number
  placeholder?: string
  disabled?: boolean
}) {
  return (
    <Input
      type="number"
      value={value ?? ''}
      onChange={(e) => {
        const val = e.target.value
        if (val === '') {
          onChange(null)
        } else {
          const num = parseFloat(val)
          if (!isNaN(num)) {
            onChange(num)
          }
        }
      }}
      min={min}
      max={max}
      step={step}
      placeholder={placeholder}
      disabled={disabled}
    />
  )
}

// 默认玻璃参数 - 对应 IDF 文件中的 WindowMaterial:Glazing 对象
// 基准玻璃 (glass_duibi) -> duibi.idf 中的 duibi 对象
// 实验玻璃1 (glass_shiyan1) -> glass.idf 中的 shiyanhigh 对象
// 实验玻璃2 (glass_shiyan2) -> glass.idf 中的 shiyanlow 对象
const DEFAULT_GLASS_PARAMS: Record<string, GlassProperties> = {
  glass_duibi: {
    // duibi.idf 中的基准玻璃对象参数
    Name: 'duibi',
    OpticalDataType: 'SpectralAverage',
    Thickness: 0.003,
    SolarTransmittance: 0.777,
    SolarReflectanceFront: 0.071,
    SolarReflectanceBack: 0.071,
    VisibleTransmittance: 0.881,
    VisibleReflectanceFront: 0.08,
    VisibleReflectanceBack: 0.08,
    InfraredTransmittance: 0,
    Emissivity: 0.84,  // Front Side Infrared Hemispherical Emissivity
    EmissivityBack: 0.84,  // Back Side Infrared Hemispherical Emissivity
    Conductivity: 0.187,
    DirtCorrectionFactor: 1,
    SolarDiffusing: false,
  },
  glass_shiyan1: {
    // glass.idf 中的 shiyanhigh 对象参数（高温态玻璃）
    Name: 'shiyanhigh',
    OpticalDataType: 'SpectralAverage',
    Thickness: 0.003,
    SolarTransmittance: 0.344,
    SolarReflectanceFront: 0.1,
    SolarReflectanceBack: 0,
    VisibleTransmittance: 0.278,
    VisibleReflectanceFront: 0.1,
    VisibleReflectanceBack: 0,
    InfraredTransmittance: 0,
    Emissivity: 0.86,  // Front Side Infrared Hemispherical Emissivity
    EmissivityBack: 0.86,  // Back Side Infrared Hemispherical Emissivity
    Conductivity: 0.187,
    DirtCorrectionFactor: 1,
    SolarDiffusing: false,
  },
  glass_shiyan2: {
    // glass.idf 中的 shiyanlow 对象参数（低温态玻璃）
    Name: 'shiyanlow',
    OpticalDataType: 'SpectralAverage',
    Thickness: 0.003,
    SolarTransmittance: 0.65,
    SolarReflectanceFront: 0.1,
    SolarReflectanceBack: 0,
    VisibleTransmittance: 0.639,
    VisibleReflectanceFront: 0.1,
    VisibleReflectanceBack: 0,
    InfraredTransmittance: 0,
    Emissivity: 0.9,  // Front Side Infrared Hemispherical Emissivity
    EmissivityBack: 0.9,  // Back Side Infrared Hemispherical Emissivity
    Conductivity: 0.187,
    DirtCorrectionFactor: 1,
    SolarDiffusing: false,
  },
}

// 玻璃场景编辑器组件
function GlassScenarioEditor({
  scenario,
  onChange,
  disabled,
}: {
  scenario: GlassScenario
  onChange: (scenario: GlassScenario) => void
  disabled?: boolean
}) {
  const glass = scenario.glass

  const updateGlass = (updates: Partial<GlassProperties>) => {
    onChange({
      ...scenario,
      glass: { ...glass, ...updates },
    })
  }

  return (
    <div className="rounded-field border border-border glass-light p-4 space-y-3">
      <div className="font-semibold text-sm text-text-primary">{scenario.name}</div>
      <div className="text-xs text-text-muted">{scenario.desc}</div>

      {/* 基本参数 */}
      <div className="pt-2 border-t border-border-light">
        <div className="text-xs font-semibold text-text-secondary mb-2">基本参数</div>
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
          <Field label="厚度 (Thickness)" hint="单位：m">
            <NumberInput
              value={glass.Thickness ?? null}
              onChange={(v) => updateGlass({ Thickness: v })}
              min={0} max={1} step={0.001}
              placeholder="0.003"
              disabled={disabled}
            />
          </Field>

          <Field label="导热系数 (Conductivity)" hint="单位：W/(m·K)">
            <NumberInput
              value={glass.Conductivity ?? null}
              onChange={(v) => updateGlass({ Conductivity: v })}
              min={0} step={0.01}
              placeholder="0.187"
              disabled={disabled}
            />
          </Field>

          <Field label="污垢修正因子" hint="0-1之间，默认1">
            <NumberInput
              value={glass.DirtCorrectionFactor ?? null}
              onChange={(v) => updateGlass({ DirtCorrectionFactor: v })}
              min={0} max={1} step={0.01}
              placeholder="1"
              disabled={disabled}
            />
          </Field>

          <Field label="太阳散射" hint="Yes/No">
            <select
              value={glass.SolarDiffusing ? 'true' : 'false'}
              onChange={(e) => updateGlass({ SolarDiffusing: e.target.value === 'true' })}
              className={
                'w-full rounded-field border border-border glass-light px-3.5 py-2.5 text-sm text-text-primary ' +
                'transition-all duration-150 cursor-pointer ' +
                'focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 focus-visible:border-accent/50 ' +
                'hover:border-border-light hover:bg-bg-elevated'
              }
              disabled={disabled}
            >
              <option value="false">否 (No)</option>
              <option value="true">是 (Yes)</option>
            </select>
          </Field>
        </div>
      </div>

      {/* 太阳光谱参数 */}
      <div className="pt-2 border-t border-border-light">
        <div className="text-xs font-semibold text-text-secondary mb-2">太阳光谱参数</div>
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
          <Field label="太阳透射率" hint="0-1之间">
            <NumberInput
              value={glass.SolarTransmittance ?? null}
              onChange={(v) => updateGlass({ SolarTransmittance: v })}
              min={0} max={1} step={0.01}
              placeholder="0-1"
              disabled={disabled}
            />
          </Field>

          <Field label="太阳反射率-正面" hint="0-1之间">
            <NumberInput
              value={glass.SolarReflectanceFront ?? null}
              onChange={(v) => updateGlass({ SolarReflectanceFront: v })}
              min={0} max={1} step={0.01}
              placeholder="0-1"
              disabled={disabled}
            />
          </Field>

          <Field label="太阳反射率-背面" hint="0-1之间">
            <NumberInput
              value={glass.SolarReflectanceBack ?? null}
              onChange={(v) => updateGlass({ SolarReflectanceBack: v })}
              min={0} max={1} step={0.01}
              placeholder="0-1"
              disabled={disabled}
            />
          </Field>
        </div>
      </div>

      {/* 可见光谱参数 */}
      <div className="pt-2 border-t border-border-light">
        <div className="text-xs font-semibold text-text-secondary mb-2">可见光谱参数</div>
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
          <Field label="可见光透射率" hint="0-1之间">
            <NumberInput
              value={glass.VisibleTransmittance ?? null}
              onChange={(v) => updateGlass({ VisibleTransmittance: v })}
              min={0} max={1} step={0.01}
              placeholder="0-1"
              disabled={disabled}
            />
          </Field>

          <Field label="可见光反射率-正面" hint="0-1之间">
            <NumberInput
              value={glass.VisibleReflectanceFront ?? null}
              onChange={(v) => updateGlass({ VisibleReflectanceFront: v })}
              min={0} max={1} step={0.01}
              placeholder="0-1"
              disabled={disabled}
            />
          </Field>

          <Field label="可见光反射率-背面" hint="0-1之间">
            <NumberInput
              value={glass.VisibleReflectanceBack ?? null}
              onChange={(v) => updateGlass({ VisibleReflectanceBack: v })}
              min={0} max={1} step={0.01}
              placeholder="0-1"
              disabled={disabled}
            />
          </Field>
        </div>
      </div>

      {/* 红外光谱参数 */}
      <div className="pt-2 border-t border-border-light">
        <div className="text-xs font-semibold text-text-secondary mb-2">红外光谱参数</div>
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
          <Field label="红外透射率" hint="0-1之间">
            <NumberInput
              value={glass.InfraredTransmittance ?? null}
              onChange={(v) => updateGlass({ InfraredTransmittance: v })}
              min={0} max={1} step={0.01}
              placeholder="0-1"
              disabled={disabled}
            />
          </Field>

          <Field label="红外发射率-正面" hint="0-1之间">
            <NumberInput
              value={glass.Emissivity ?? null}
              onChange={(v) => updateGlass({ Emissivity: v })}
              min={0} max={1} step={0.01}
              placeholder="0-1"
              disabled={disabled}
            />
          </Field>

          <Field label="红外发射率-背面" hint="0-1之间">
            <NumberInput
              value={glass.EmissivityBack ?? null}
              onChange={(v) => updateGlass({ EmissivityBack: v })}
              min={0} max={1} step={0.01}
              placeholder="0-1"
              disabled={disabled}
            />
          </Field>
        </div>
      </div>
    </div>
  )
}

// 全局参数编辑器
function GlobalParamsEditor({
  value,
  onChange,
  disabled,
}: {
  value: GlobalParams
  onChange: (value: GlobalParams) => void
  disabled?: boolean
}) {
  return (
    <div className="rounded-field border border-border glass-light p-4">
      <div className="text-sm font-semibold text-text-primary mb-3">全局参数（可选）</div>
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        <Field label="换气次数 (ACH)" hint="换气次数 (1/hr)">
          <NumberInput
            value={value.global_ach ?? null}
            onChange={(v) => onChange({ ...value, global_ach: v })}
            min={0} step={0.1}
            placeholder="默认 0.3"
            disabled={disabled}
          />
        </Field>

        <Field label="照明功率密度 (W/m2)" hint="照明功率密度">
          <NumberInput
            value={value.global_lighting_w_per_m2 ?? null}
            onChange={(v) => onChange({ ...value, global_lighting_w_per_m2: v })}
            min={0} step={1}
            placeholder="默认 10.76"
            disabled={disabled}
          />
        </Field>

        <Field label="冬季供暖设定温度 (C)" hint="供暖设定温度">
          <NumberInput
            value={value.global_thermostat_heat_c ?? null}
            onChange={(v) => onChange({ ...value, global_thermostat_heat_c: v })}
            step={1}
            placeholder="默认 21"
            disabled={disabled}
          />
        </Field>

        <Field label="夏季制冷设定温度 (C)" hint="制冷设定温度">
          <NumberInput
            value={value.global_thermostat_cool_c ?? null}
            onChange={(v) => onChange({ ...value, global_thermostat_cool_c: v })}
            step={1}
            placeholder="默认 24"
            disabled={disabled}
          />
        </Field>

        <Field label="人员密度 (person/m2)" hint="每人占用的地板面积">
          <NumberInput
            value={value.global_people_per_m2 ?? null}
            onChange={(v) => onChange({ ...value, global_people_per_m2: v })}
            min={0} step={0.01}
            placeholder="默认 0.05"
            disabled={disabled}
          />
        </Field>

        <Field label="相变温度 (C)" hint="光致变色玻璃的相变温度点，如果高温和低温态是相同态，那么这里不用管 ">
          <NumberInput
            value={value.phase_change_temp ?? null}
            onChange={(v) => onChange({ ...value, phase_change_temp: v })}
            min={-50} max={100} step={1}
            placeholder="默认 26"
            disabled={disabled}
          />
        </Field>
      </div>
    </div>
  )
}

export default function GlassMapPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { user } = useAuth()

  // 缓存状态
  const [cacheStatus, setCacheStatus] = useState<'idle' | 'saved' | 'saving'>('idle')

  // 状态
  const [weatherGroup, setWeatherGroup] = useState<'china' | 'world' | 'world_weather2025'>('china')
  const [idfTemplateDir, setIdfTemplateDir] = useState('model/model1')
  const [remark, setRemark] = useState('')
  const [enableLatentHeat, setEnableLatentHeat] = useState(false)
  const [wetFraction, setWetFraction] = useState<number | null>(1.0)
  const [colormapParams, setColormapParams] = useState<Record<string, string>>({})

  // 场景状态
  const [scenarios, setScenarios] = useState<GlassScenario[]>(getDefaultScenarios())

  // 全局参数状态
  const [globalParams, setGlobalParams] = useState<GlobalParams>(DEFAULT_GLOBAL_PARAMS)

  // 页面加载时：从缓存恢复参数
  useEffect(() => {
    if (hasCache()) {
      const cached = loadParamsFromCache()
      if (cached) {
        setWeatherGroup(cached.weather_group)
        setIdfTemplateDir(cached.idf_template_dir || 'model/model1')
        setEnableLatentHeat(cached.enable_latent_heat)
        setWetFraction(cached.wet_fraction)
        setScenarios(cached.scenarios)
        setGlobalParams(cached.global_params)
        setColormapParams(cached.colormap_params)
      }
    }
  }, [])

  // 模型预览相关状态
  const [modelInfHeaders, setModelInfHeaders] = useState<string[] | null>(null)
  const [modelInfRows, setModelInfRows] = useState<string[][]>([])
  const [modelInfLoading, setModelInfLoading] = useState(false)
  const [modelInfError, setModelInfError] = useState<string | null>(null)

  // 从 idfTemplateDir 提取模型键（如 "model/model1" -> "model1"）
  const activePreviewModel = useMemo(() => {
    const match = idfTemplateDir.match(/model(\d+)$/)
    return match ? `model${match[1]}` : null
  }, [idfTemplateDir])

  // 加载 inf.csv 数据
  useEffect(() => {
    if (!activePreviewModel) {
      setModelInfHeaders(null)
      setModelInfRows([])
      setModelInfLoading(false)
      setModelInfError(null)
      return
    }

    const controller = new AbortController()
    const load = async () => {
      try {
        setModelInfLoading(true)
        setModelInfError(null)
        setModelInfHeaders(null)
        setModelInfRows([])

        const resp = await fetch(`/api/glass/model-preview/${activePreviewModel}/inf`, {
          signal: controller.signal,
        })
        if (!resp.ok) {
          throw new Error(`Failed to load inf.csv (${resp.status})`)
        }
        const text = await resp.text()
        const trimmed = text.trim()
        if (!trimmed) {
          setModelInfHeaders([])
          setModelInfRows([])
          return
        }
        const lines = trimmed.split(/\r?\n/)
        const [headerLine, ...rest] = lines
        const headers = headerLine.split(',').map((h) => h.trim())
        const rows = rest
          .map((line) => line.split(',').map((v) => v.trim()))
          .filter((r) => r.length && r.some((cell) => cell !== ''))
        setModelInfHeaders(headers)
        setModelInfRows(rows)
      } catch (err) {
        if ((err as any)?.name === 'AbortError') return
        setModelInfError(err instanceof Error ? err.message : 'Unknown error')
      } finally {
        setModelInfLoading(false)
      }
    }

    void load()
    return () => controller.abort()
  }, [activePreviewModel])

  // 参数变化时：自动保存到缓存
  useEffect(() => {
    debouncedSave({
      weather_group: weatherGroup,
      idf_template_dir: idfTemplateDir,
      enable_latent_heat: enableLatentHeat,
      wet_fraction: wetFraction ?? 1.0,
      scenarios,
      global_params: globalParams,
      colormap_params: colormapParams,
    })
    setCacheStatus('saving')
    const timer = setTimeout(() => setCacheStatus('saved'), 1100)
    return () => clearTimeout(timer)
  }, [weatherGroup, idfTemplateDir, enableLatentHeat, wetFraction, scenarios, globalParams, colormapParams])

  // 导入参数处理
  const handleImport = async (file: File) => {
    const params = await importParamsFromFile(file)
    if (params) {
      setWeatherGroup(params.weather_group)
      setIdfTemplateDir(params.idf_template_dir || 'model/model1')
      setEnableLatentHeat(params.enable_latent_heat)
      setWetFraction(params.wet_fraction)
      setScenarios(params.scenarios)
      setGlobalParams(params.global_params)
      setColormapParams(params.colormap_params)
      alert('参数导入成功')
    } else {
      alert('参数导入失败，请检查文件格式')
    }
  }

  // 导出参数处理
  const handleExport = () => {
    exportParams({
      weather_group: weatherGroup,
      idf_template_dir: idfTemplateDir,
      enable_latent_heat: enableLatentHeat,
      wet_fraction: wetFraction ?? 1.0,
      scenarios,
      global_params: globalParams,
      colormap_params: colormapParams,
    })
  }

  // 清除缓存处理
  const handleClearCache = () => {
    if (confirm('确定要清除本地缓存吗？')) {
      clearCache()
      setWeatherGroup('china')
      setIdfTemplateDir('model/model1')
      setEnableLatentHeat(false)
      setWetFraction(1.0)
      setScenarios(getDefaultScenarios())
      setGlobalParams(DEFAULT_GLOBAL_PARAMS)
      setColormapParams(getDefaultColormapParams('china'))
      alert('缓存已清除')
    }
  }

  // 创建任务 mutation
  const createJob = useMutation({
    mutationFn: createGlassComparisonJob,
    onSuccess: (data) => {
      console.log('[GlassMapPage] Job created successfully:', data)
      navigate(`/glass-comparison/${data.job_id}`)
    },
    onError: (error: any) => {
      // 详细记录错误信息用于调试
      console.error('[GlassMapPage] Job creation failed:', error)
      if (error?.response) {
        console.error('[GlassMapPage] Response status:', error.response.status)
        console.error('[GlassMapPage] Response data:', error.response.data)
      }
      alert(`提交失败: ${error?.message || error?.response?.data?.detail || '未知错误'}`)
    },
  })

  const handleSubmit = () => {
    if (!user) return

    // 调试：打印将要提交的参数
    const submitParams = {
      weather_group: weatherGroup,
      scenarios: scenarios,
      idf_template_dir: idfTemplateDir || undefined,
      global_params: Object.keys(globalParams).length > 0 ? globalParams : undefined,
      enable_latent_heat: enableLatentHeat,
      wet_fraction: wetFraction ?? 1.0,
      colormap_params: Object.keys(colormapParams).length > 0 ? colormapParams : undefined,
    }
    console.log('[GlassMapPage] Submitting job with params:', JSON.stringify(submitParams, null, 2))

    createJob.mutate({
      params: submitParams,
      remark: remark || undefined,
    })
  }

  const updateScenario = (index: number, scenario: GlassScenario) => {
    const newScenarios = [...scenarios]
    newScenarios[index] = scenario
    setScenarios(newScenarios)
  }

  return (
    <div className="space-y-5">
      {/* 页面头部 */}
      <div className="flex items-center justify-between">
        <div>
          <div className="text-lg font-semibold text-text-primary">玻璃辐射节能效果对比</div>
          <div className="text-sm text-text-secondary">分析不同玻璃材料的节能效果</div>
        </div>
        <div className="flex items-center gap-3">
          {/* 缓存状态 */}
          <div className="text-xs text-text-muted">
            {cacheStatus === 'saving' && '保存中...'}
            {cacheStatus === 'saved' && `已保存 ${formatCacheTime(getCacheTimestamp() || Date.now())}`}
          </div>
          {/* 参数导入/导出/清除 */}
          <div className="flex gap-2">
            <label className="cursor-pointer px-3 py-1.5 text-xs rounded-lg border border-border hover:bg-bg-elevated transition-all duration-150">
              导入
              <input
                type="file"
                accept=".json"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0]
                  if (file) handleImport(file)
                  e.target.value = ''
                }}
              />
            </label>
            <button
              onClick={handleExport}
              className="px-3 py-1.5 text-xs rounded-lg border border-border hover:bg-bg-elevated transition-all duration-150"
            >
              导出
            </button>
            <button
              onClick={handleClearCache}
              className="px-3 py-1.5 text-xs rounded-lg border border-border hover:bg-bg-elevated transition-all duration-150 text-text-muted"
            >
              清除缓存
            </button>
          </div>
          <HelpButton doc="cooling" />
        </div>
      </div>

      {/* 提示卡片 */}
      <Card className="glass-light">
        <CardHeader>
          <CardTitle>功能说明</CardTitle>
        </CardHeader>
        <div className="text-sm text-text-secondary space-y-2">
          <p>
            玻璃辐射节能效果对比工具用于分析不同玻璃材料对建筑能耗的影响。
            通过对比基准玻璃和实验玻璃的光学参数（太阳透射率、发射率等），
            可以评估不同玻璃的节能效果。
          </p>
          <p className="text-xs text-text-muted">
            提示：该工具基于 EnergyPlus 模拟计算，需要配置正确的 IDF 模板文件。
            请确保 IDF 模板目录中包含玻璃材料定义。
          </p>
        </div>
      </Card>

      {/* 基本参数 */}
      <Card>
        <CardHeader>
          <CardTitle>基本参数</CardTitle>
        </CardHeader>

        <div className="grid gap-4 md:grid-cols-2">
          <Field label="天气区域组" hint="选择分析的中国省份或世界气候区">
            <Segmented
              value={weatherGroup}
              onChange={(v) => setWeatherGroup(v as any)}
              options={[
                { label: '中国', value: 'china' },
                { label: '世界', value: 'world' },
                { label: '世界2025', value: 'world_weather2025' },
              ]}
            />
          </Field>

          <Field label="IDF模板目录" hint="留空使用默认目录">
            <Input
              value={idfTemplateDir}
              onChange={(e) => setIdfTemplateDir(e.target.value)}
              placeholder="如: model/model1"
            />
          </Field>

          <Field label="任务备注（可选）" hint="方便识别任务">
            <Input
              value={remark}
              onChange={(e) => setRemark(e.target.value)}
              placeholder="输入任务备注"
            />
          </Field>
        </div>

        {/* 模型预览区域 */}
        {activePreviewModel && (
          <div className="mt-4 glass-light rounded-field border border-border p-4">
            <div className="mb-3 text-xs font-semibold text-text-secondary">
              当前模型预览 - {activePreviewModel}
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              {/* 左侧图片 */}
              <div className="flex items-center justify-center bg-bg-elevated/60 rounded-field border border-border-light overflow-hidden min-h-[200px]">
                <img
                  src={`/api/glass/model-preview/${activePreviewModel}/figure`}
                  alt="模型预览图"
                  className="max-h-[320px] w-full object-contain"
                />
              </div>
              {/* 右侧表格 */}
              <div className="rounded-field border border-border-light bg-bg-elevated/60 overflow-hidden">
                <div className="border-b border-border-light px-3 py-2 text-xs font-semibold text-text-secondary">
                  模型说明表（inf.csv）
                </div>
                <div className="max-h-[320px] overflow-auto">
                  {modelInfLoading ? (
                    <div className="px-3 py-2 text-xs text-text-muted">加载中...</div>
                  ) : modelInfError ? (
                    <div className="px-3 py-2 text-xs text-danger">
                      加载失败: {modelInfError}
                    </div>
                  ) : !modelInfHeaders || modelInfHeaders.length === 0 ? (
                    <div className="px-3 py-2 text-xs text-text-muted">暂无数据</div>
                  ) : (
                    <table className="min-w-full text-xs text-left table-fixed">
                      <colgroup>
                        {modelInfHeaders.map((_, idx) => (
                          <col key={idx} className="w-[120px]" />
                        ))}
                      </colgroup>
                      <thead className="bg-bg-elevated">
                        <tr>
                          {modelInfHeaders.map((h, idx) => (
                            <th
                              key={idx}
                              className="px-2 py-1.5 font-semibold text-text-secondary border-b border-border-light whitespace-nowrap overflow-hidden text-ellipsis"
                            >
                              {h || `列${idx + 1}`}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {modelInfRows.map((row, rowIdx) => (
                          <tr key={rowIdx} className={rowIdx % 2 === 0 ? '' : 'bg-bg-elevated/40'}>
                            {row.map((cell, cellIdx) => (
                              <td
                                key={cellIdx}
                                className="px-2 py-1 border-b border-border-light text-text-primary whitespace-nowrap overflow-hidden text-ellipsis"
                              >
                                {cell}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </Card>

      {/* 场景参数 */}
      <Card>
        <CardHeader>
          <CardTitle>玻璃场景配置</CardTitle>
          <CardDesc>设置对比的玻璃材料参数</CardDesc>
        </CardHeader>

        <div className="space-y-4">
          {scenarios.map((scenario, index) => (
            <GlassScenarioEditor
              key={index}
              scenario={scenario}
              onChange={(s) => updateScenario(index, s)}
            />
          ))}
        </div>
      </Card>

      {/* 全局参数 */}
      <Card>
        <CardHeader>
          <CardTitle>全局参数（可选）</CardTitle>
          <CardDesc>设置影响所有场景的建筑参数</CardDesc>
        </CardHeader>
        <GlobalParamsEditor value={globalParams} onChange={setGlobalParams} />
      </Card>

      {/* 高级参数 */}
      <Card>
        <CardHeader>
          <CardTitle>高级参数</CardTitle>
        </CardHeader>

        <div className="grid gap-4 md:grid-cols-3">
          <Field label="启用蒸发潜热" hint="考虑蒸发潜热的影响">
            <Segmented
              value={enableLatentHeat ? 'true' : 'false'}
              onChange={(v) => setEnableLatentHeat(v === 'true')}
              options={[
                { label: '是', value: 'true' },
                { label: '否', value: 'false' },
              ]}
            />
          </Field>

          <Field label="润湿面积比例" hint="0-1之间，默认1.0">
            <NumberInput
              value={wetFraction}
              onChange={(v) => setWetFraction(v)}
              min={0} max={1} step={0.1}
              placeholder="1.0"
            />
          </Field>
        </div>
      </Card>

      {/* 色系参数 */}
      <Card>
        <CardHeader>
          <CardTitle>色系配置</CardTitle>
          <CardDesc>自定义地图颜色方案</CardDesc>
        </CardHeader>
        <ColormapSelector
          value={colormapParams}
          onChange={setColormapParams}
          weatherGroup={weatherGroup}
        />
      </Card>

      {/* 提交按钮 */}
      <div className="flex items-center justify-end gap-3">
        <Button size="lg" variant="secondary" onClick={() => navigate('/jobs')}>
          取消
        </Button>
        <Button
          size="lg"
          variant="primary"
          onClick={handleSubmit}
          disabled={createJob.isPending}
        >
          {createJob.isPending ? '提交中...' : '开始分析'}
        </Button>
      </div>

      {/* 错误提示 */}
      {createJob.isError && (
        <div className="rounded-xl border border-danger-soft bg-danger-soft p-4 text-sm text-text-secondary">
          提交失败: {createJob.error?.message || '未知错误'}
        </div>
      )}
    </div>
  )
}
