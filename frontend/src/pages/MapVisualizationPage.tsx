import { useState, useMemo, useEffect, useCallback } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import Button from '../components/ui/Button'
import { Card, CardDesc, CardHeader, CardTitle } from '../components/ui/Card'
import Segmented from '../components/ui/Segmented'
import ColormapSelector, { DEFAULT_COLORMAP_PARAMS } from '../components/ColormapSelector'
import { createMaterialComparisonJob, type MaterialScenario, type GlobalParams, type MaterialProperties } from '../services/materials'
import { loadParamsFromCache, hasCache, saveParamsToCache, debouncedSave } from '../services/materialCache'
import type { MaterialComparisonParams } from '../services/materials'
import { useAuth } from '../context/AuthContext'
import HelpButton from '../components/Help/HelpButton'


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

function Checkbox({
  checked,
  onChange,
  label,
}: {
  checked: boolean
  onChange: (checked: boolean) => void
  label: string
}) {
  return (
    <label className="flex items-center gap-2.5 rounded-field border border-border glass-light px-3.5 py-2.5 text-sm text-text-secondary cursor-pointer transition-all duration-150 hover:bg-bg-elevated hover:border-border-light">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="cursor-pointer w-4 h-4 rounded accent-accent-DEFAULT"
      />
      <span>{label}</span>
    </label>
  )
}

const MATERIAL_FIELDS_BASE = [
  { key: 'Roughness', labelKey: 'roughness', type: 'select', options: ['Smooth', 'MediumRough', 'Rough', 'VeryRough'], unit: '' },
  { key: 'Thickness', labelKey: 'thickness', type: 'number', min: 0, max: 10, step: 0.001 },
  { key: 'Conductivity', labelKey: 'conductivity', type: 'number', min: 0.01, max: 10, step: 0.01 },
  { key: 'Density', labelKey: 'density', type: 'number', min: 1, max: 10000, step: 1 },
  { key: 'SpecificHeat', labelKey: 'specificHeat', type: 'number', min: 100, max: 10000, step: 10 },
  { key: 'ThermalAbsorptance', labelKey: 'thermalAbsorptance', type: 'number', min: 0, max: 1, step: 0.01 },
  { key: 'SolarAbsorptance', labelKey: 'solarAbsorptance', type: 'number', min: 0, max: 1, step: 0.01 },
  { key: 'VisibleAbsorptance', labelKey: 'visibleAbsorptance', type: 'number', min: 0, max: 1, step: 0.01 },
] as const

function getMaterialFields(t: (key: string) => string) {
  return MATERIAL_FIELDS_BASE.map(field => ({
    ...field,
    label: t(`mapVisualization.${field.labelKey}`),
    hint: t(`mapVisualization.${field.labelKey}Hint`),
  }))
}

function ScenarioEditor({
  scenario,
  onChange,
  index,
}: {
  scenario: MaterialScenario
  onChange: (scenario: MaterialScenario) => void
  index: number
}) {
  const { t } = useTranslation()
  const scenarioNames = [
    t('mapVisualization.baseline'),
    t('mapVisualization.coolingComparison'),
    t('mapVisualization.heatingComparison')
  ]
  const scenarioDescriptions = [
    t('mapVisualization.scenarioDesc.baseline'),
    t('mapVisualization.scenarioDesc.cooling'),
    t('mapVisualization.scenarioDesc.heating'),
  ]
  const materialFields = getMaterialFields(t)

  const updateField = (field: keyof MaterialScenario, value: any) => {
    onChange({ ...scenario, [field]: value })
  }

  const updateMaterialField = (field: keyof MaterialProperties, value: string | number | null) => {
    const updatedMaterial = {
      ...scenario.material,
      [field]: value,
    }
    onChange({
      ...scenario,
      material: updatedMaterial,
    })
  }

  return (
    <Card className="glass-light">
      <CardHeader>
        <CardTitle>{t('mapVisualization.scenario')} {index + 1}: {scenarioNames[index]}</CardTitle>
        <CardDesc>{scenario.desc || scenarioDescriptions[index]}</CardDesc>
      </CardHeader>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="md:col-span-2">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-text-muted">
            {t('mapVisualization.materialParams')}
          </div>
        </div>

        {materialFields.map((field) => (
          <Field key={field.key} label={field.label} hint={field.hint}>
            {field.type === 'select' ? (
              <Select
                value={(scenario.material[field.key as keyof MaterialProperties] as string) || ''}
                onChange={(e) => updateMaterialField(field.key as keyof MaterialProperties, e.target.value || null)}
              >
                <option value="">{t('mapVisualization.useDefault')}</option>
                {field.options?.map((opt) => (
                  <option key={opt} value={opt}>
                    {field.key === 'Roughness' ? t(`mapVisualization.${opt.toLowerCase()}`) : opt}
                  </option>
                ))}
              </Select>
            ) : (
              <NumberInput
                value={(scenario.material[field.key as keyof MaterialProperties] as number | null | undefined) ?? null}
                onChange={(v) => updateMaterialField(field.key as keyof MaterialProperties, v)}
                min={field.min}
                max={field.max}
                step={field.step}
                placeholder={t('mapVisualization.useDefault')}
              />
            )}
          </Field>
        ))}

        <div className="md:col-span-2">
          <div className="glass-light rounded-field border border-border p-3 text-xs text-text-secondary">
            <strong className="text-text-primary">{t('mapVisualization.tip')}</strong>{t('mapVisualization.tipContent')}
          </div>
        </div>
      </div>
    </Card>
  )
}

function GlobalParamsEditor({
  globalParams,
  onChange,
}: {
  globalParams: GlobalParams
  onChange: (params: GlobalParams) => void
}) {
  const { t } = useTranslation()
  const updateParam = (key: keyof GlobalParams, value: number | null) => {
    onChange({ ...globalParams, [key]: value })
  }

  return (
    <Card className="glass-light">
      <CardHeader>
        <CardTitle>{t('mapVisualization.globalParams')}</CardTitle>
        <CardDesc>{t('mapVisualization.globalParamsHint')}</CardDesc>
      </CardHeader>
      <div className="grid gap-4 md:grid-cols-2">
        <Field
          label={t('mapVisualization.ach')}
          hint={t('mapVisualization.achHint')}
        >
          <NumberInput
            value={globalParams.global_ach ?? null}
            onChange={(v) => updateParam('global_ach', v)}
            min={0}
            max={10}
            step={0.1}
            placeholder="0.5"
          />
        </Field>
        <Field
          label={t('mapVisualization.lighting')}
          hint={t('mapVisualization.lightingHint')}
        >
          <NumberInput
            value={globalParams.global_lighting_w_per_m2 ?? null}
            onChange={(v) => updateParam('global_lighting_w_per_m2', v)}
            min={0}
            max={50}
            step={0.5}
            placeholder="10.8"
          />
        </Field>
        <Field
          label={t('mapVisualization.heatSetpoint')}
          hint={t('mapVisualization.heatSetpointHint')}
        >
          <NumberInput
            value={globalParams.global_thermostat_heat_c ?? null}
            onChange={(v) => updateParam('global_thermostat_heat_c', v)}
            min={10}
            max={30}
            step={0.5}
            placeholder="20"
          />
        </Field>
        <Field
          label={t('mapVisualization.coolSetpoint')}
          hint={t('mapVisualization.coolSetpointHint')}
        >
          <NumberInput
            value={globalParams.global_thermostat_cool_c ?? null}
            onChange={(v) => updateParam('global_thermostat_cool_c', v)}
            min={20}
            max={35}
            step={0.5}
            placeholder="26"
          />
        </Field>
        <Field
          label={t('mapVisualization.occupancy')}
          hint={t('mapVisualization.occupancyHint')}
        >
          <NumberInput
            value={globalParams.global_people_per_m2 ?? null}
            onChange={(v) => updateParam('global_people_per_m2', v)}
            min={0}
            max={10}
            step={0.01}
            placeholder="0.05"
          />
        </Field>

        <div className="md:col-span-2">
          <div className="glass-light rounded-field border border-border p-3 text-xs text-text-secondary">
            <strong className="text-text-primary">{t('mapVisualization.tip')}</strong>{t('mapVisualization.tipContent')}
          </div>
        </div>
      </div>
    </Card>
  )
}

export default function MapVisualizationPage() {
  const { t } = useTranslation()
  const nav = useNavigate()
  const { user } = useAuth()

  const [weatherGroup, setWeatherGroup] = useState<'china' | 'world' | 'world_weather2025'>('china')
  // IDF??????????????????????????????? material_comparison_tool ????
  type IdfTemplateModelKey = 'model1' | 'model2' | 'model3' | 'custom'
  const IDF_TEMPLATE_MODELS: Array<{ key: Exclude<IdfTemplateModelKey, 'custom'>; labelKey: string; dir: string }> = [
    { key: 'model1', labelKey: 'model1', dir: 'model/model1' },
    { key: 'model2', labelKey: 'model2', dir: 'model/model2' },
    { key: 'model3', labelKey: 'model3', dir: 'model/model3' },
  ]
  const getIdfModelLabel = (key: string) => {
    if (key === 'model1') return t('mapVisualization.model1')
    if (key === 'model2') return t('mapVisualization.model2')
    if (key === 'model3') return t('mapVisualization.model3')
    return key
  }
  const [idfTemplateModel, setIdfTemplateModel] = useState<IdfTemplateModelKey>('model1')
  const [customIdfTemplateDir, setCustomIdfTemplateDir] = useState<string>('')
  const resolvedIdfTemplateDir = useMemo(() => {
    if (idfTemplateModel === 'custom') {
      const v = customIdfTemplateDir.trim()
      return v ? v : undefined
    }
    return IDF_TEMPLATE_MODELS.find((m) => m.key === idfTemplateModel)?.dir || 'model/model1'
  }, [customIdfTemplateDir, idfTemplateModel])
  const activePreviewModel = useMemo<Exclude<IdfTemplateModelKey, 'custom'> | null>(() => {
    if (idfTemplateModel === 'custom') return null
    return idfTemplateModel
  }, [idfTemplateModel])

  // Load cached params on mount
  useEffect(() => {
    if (hasCache()) {
      const cached = loadParamsFromCache()
      if (cached) {
        setWeatherGroup(cached.weather_group)
        setIdfTemplateModel(cached.idf_template_model)
        setCustomIdfTemplateDir(cached.custom_idf_template_dir || '')
        setEnableLatentHeat(cached.enable_latent_heat)
        setWetFraction(cached.wet_fraction)
        setScenarios(cached.scenarios)
        setGlobalParams(cached.global_params)
        setColormapParams(cached.colormap_params)
      }
    }
  }, [])

  // Current model's inf.csv table data
  const [modelInfHeaders, setModelInfHeaders] = useState<string[] | null>(null)
  const [modelInfRows, setModelInfRows] = useState<string[][]>([])
  const [modelInfLoading, setModelInfLoading] = useState(false)
  const [modelInfError, setModelInfError] = useState<string | null>(null)

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

        const resp = await fetch(`/api/materials/model-preview/${activePreviewModel}/inf`, {
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
  // Latent heat configuration
  const [enableLatentHeat, setEnableLatentHeat] = useState<boolean>(false)
  const [wetFraction, setWetFraction] = useState<number>(1.0)
  
  // Global parameters config (reference batch_run.py), set default values
  const [globalParams, setGlobalParams] = useState<GlobalParams>({
    global_ach: 0.5,  // 0.5 times/hour
    global_lighting_w_per_m2: 2,  // 2 W/m?
    global_thermostat_heat_c: 20,  // 20?C
    global_thermostat_cool_c: 26,  // 26?C
    global_people_per_m2: 0.05,  // 0.05 person/m?
  })

  // 色系参数状态
  const [colormapParams, setColormapParams] = useState<Record<string, string>>(() => {
    const prefix = weatherGroup === 'china' ? 'china' : 'world'
    const defaults: Record<string, string> = {}
    for (const [k, v] of Object.entries(DEFAULT_COLORMAP_PARAMS)) {
      if (k.startsWith(prefix)) {
        defaults[k] = v
      }
    }
    return defaults
  })

  // Default material parameters (typical building material values)
  const defaultMaterialValues: MaterialProperties = {
    Name: '',  // Will be set in each scenario
    Roughness: 'MediumRough',
    Thickness: 0.01,  // 0.01m
    Conductivity: 0.8,  // 0.8 W/m-K
    Density: 2000,  // 2000 kg/m?
    SpecificHeat: 900,  // 900 J/kg-K
    ThermalAbsorptance: 0.9,  // 0.9 (infrared emissivity)
    SolarAbsorptance: 0.6,  // 0.6 (solar absorptivity)
    VisibleAbsorptance: 0.6,  // 0.6 (visible light absorptivity)
  }

  // Default 3 scenarios, corresponding to FIELD_ORDER in batch_run.py
  // Note: first scenario as duibi (baseline), second as shiyan1 (cooling comparison), third as shiyan2 (heating comparison)
  const [scenarios, setScenarios] = useState<MaterialScenario[]>([
    {
      name: 'duibi',
      desc: t('mapVisualization.scenarioDesc.baseline'),
      material: {
        ...defaultMaterialValues,
        Name: 'duibi',
        SolarAbsorptance: 0.6,
        ThermalAbsorptance: 0.9,
        VisibleAbsorptance: 0.6,  // 0.6 (visible light absorptivity)
      },
    },
    {
      name: 'shiyan1',
      desc: t('mapVisualization.scenarioDesc.cooling'),
      material: {
        ...defaultMaterialValues,
        Name: 'shiyan1',
        SolarAbsorptance: 0.1,
        ThermalAbsorptance: 0.95,
        VisibleAbsorptance: 0.1,  // 0.6 (visible light absorptivity)
      },
    },
    {
      name: 'shiyan2',
      desc: t('mapVisualization.scenarioDesc.heating'),
      material: {
        ...defaultMaterialValues,
        Name: 'shiyan2',
        SolarAbsorptance: 0.9,
        ThermalAbsorptance: 0.8,
        VisibleAbsorptance: 0.9,  // 0.6 (visible light absorptivity)
      },
    },
  ])
  
  // Tab state management
  const [activeTab, setActiveTab] = useState<'config' | 'scenarios' | 'global' | 'colormap'>('config')
  const [remark, setRemark] = useState('')
  const [cacheStatus, setCacheStatus] = useState<'saved' | 'saving' | null>(null)

  // Auto-save params to localStorage with debounce
  useEffect(() => {
    debouncedSave({
      weather_group: weatherGroup,
      idf_template_model: idfTemplateModel,
      custom_idf_template_dir: customIdfTemplateDir,
      enable_latent_heat: enableLatentHeat,
      wet_fraction: wetFraction,
      scenarios,
      global_params: globalParams,
      colormap_params: colormapParams,
    })
    setCacheStatus('saving')
    const timer = setTimeout(() => setCacheStatus('saved'), 1100)
    return () => clearTimeout(timer)
  }, [weatherGroup, idfTemplateModel, customIdfTemplateDir, enableLatentHeat, wetFraction, scenarios, globalParams, colormapParams])

  const m = useMutation({
    mutationFn: createMaterialComparisonJob,
    onSuccess: (res) => nav(`/materials/${res.job_id}`),
  })

  const canSubmit = useMemo(() => {
    if (user?.tier === 'normal') return false
    // Need at least 3 scenarios
    return scenarios.length >= 3 && scenarios.every((s) => s.name.trim() !== '')
  }, [scenarios, user?.tier])

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div>
              <CardTitle>{t('mapVisualization.title')}</CardTitle>
              <CardDesc>
                {t('mapVisualization.using')}
                <a
                  href="https://energyplus.net/"
                  target="_blank"
                  rel="noreferrer"
                  className="text-sky-500 hover:text-sky-600 underline underline-offset-2 mx-0.5"
                >
                  EnergyPlus
                </a>
                {t('mapVisualization.desc')}
              </CardDesc>
            </div>
            {/* Cache status indicator */}
            {cacheStatus && (
              <div className={`flex items-center gap-1.5 text-xs px-2 py-1 rounded-full ${
                cacheStatus === 'saving'
                  ? 'bg-accent/10 text-accent'
                  : 'bg-success/10 text-success'
              }`}>
                {cacheStatus === 'saving' ? (
                  <>
                    <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                    </svg>
                    <span>{t('cacheManager.saving')}</span>
                  </>
                ) : (
                  <>
                    <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                    </svg>
                    <span>{t('cacheManager.saved')}</span>
                  </>
                )}
              </div>
            )}
          </div>
        </CardHeader>

        {/* Tab navigation */}
        <div className="border-b border-border mb-4">
          <div className="flex gap-2">
            <button
              onClick={() => setActiveTab('config')}
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === 'config'
                  ? 'border-b-2 border-accent text-accent'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              {t('mapVisualization.tabs.simulation')}
            </button>
            <button
              onClick={() => setActiveTab('scenarios')}
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === 'scenarios'
                  ? 'border-b-2 border-accent text-accent'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              {t('mapVisualization.tabs.scenarios')}
            </button>
            <button
              onClick={() => setActiveTab('global')}
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === 'global'
                  ? 'border-b-2 border-accent text-accent'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              {t('mapVisualization.tabs.global')}
            </button>
            <button
              onClick={() => setActiveTab('colormap')}
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === 'colormap'
                  ? 'border-b-2 border-accent text-accent'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              {t('mapVisualization.tabs.colormap')}
            </button>
          </div>
        </div>

        {/* Tab content */}
        {activeTab === 'config' && (
          <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <Field label={t('mapVisualization.weatherGroup')} hint={t('mapVisualization.weatherGroupHint')}>
                <Select value={weatherGroup} onChange={(e) => setWeatherGroup(e.target.value as 'china' | 'world' | 'world_weather2025')}>
                  <option value="china">{t('mapVisualization.china')}</option>
                  <option value="world">{t('mapVisualization.world')}</option>
                  <option value="world_weather2025">{t('mapVisualization.world2025')}</option>
                </Select>
              </Field>

              <Field
                label={t('mapVisualization.idfModel')}
                hint={t('mapVisualization.idfModelHint')}
              >
                <div className="space-y-2">
                  <Select
                    value={idfTemplateModel}
                    onChange={(e) => setIdfTemplateModel(e.target.value as IdfTemplateModelKey)}
                  >
                    {IDF_TEMPLATE_MODELS.map((m) => (
                      <option key={m.key} value={m.key}>
                        {getIdfModelLabel(m.key)}
                      </option>
                    ))}
                    <option value="custom">{t('mapVisualization.customPath')}</option>
                  </Select>

                  {idfTemplateModel === 'custom' ? (
                    <Input
                      value={customIdfTemplateDir}
                      onChange={(e) => setCustomIdfTemplateDir(e.target.value)}
                      placeholder={t('mapVisualization.customPathPlaceholder')}
                    />
                  ) : (
                    <div className="text-xs text-text-muted">
                      {t('mapVisualization.currentPath')}<span className="font-mono">{resolvedIdfTemplateDir}</span>
                    </div>
                  )}
                </div>
              </Field>

              <Field label={t('mapVisualization.latentHeat')} hint={t('mapVisualization.latentHeatHint')}>
                <Checkbox
                  checked={enableLatentHeat}
                  onChange={setEnableLatentHeat}
                  label={t('mapVisualization.enableLatentHeat')}
                />
              </Field>

              {enableLatentHeat && (
                <Field label={t('mapVisualization.wetFraction')} hint={t('mapVisualization.wetFractionHint')}>
                  <NumberInput
                    value={wetFraction}
                    onChange={(v) => setWetFraction(v ?? 1.0)}
                    min={0}
                    max={1}
                    step={0.1}
                    placeholder="1.0"
                  />
                </Field>
              )}
            </div>

            {/* Model preview: left image right table */}
            {activePreviewModel && (
              <div className="glass-light rounded-field border border-border p-4">
                <div className="mb-3 text-xs font-semibold text-text-secondary">
                  {t('mapVisualization.currentModel')}{activePreviewModel ? getIdfModelLabel(activePreviewModel) : ''}
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                  {/* Left image */}
                  <div className="flex items-center justify-center bg-bg-elevated/60 rounded-field border border-border-light overflow-hidden min-h-[200px]">
                    <img
                      src={`/api/materials/model-preview/${activePreviewModel}/figure`}
                      alt={t('mapVisualization.modelPreviewAlt')}
                      className="max-h-[320px] w-full object-contain"
                    />
                  </div>
                  {/* Right table */}
                  <div className="rounded-field border border-border-light bg-bg-elevated/60 overflow-hidden">
                    <div className="border-b border-border-light px-3 py-2 text-xs font-semibold text-text-secondary">
                      {t('mapVisualization.infTable')}
                    </div>
                    <div className="max-h-[320px] overflow-auto">
                      {modelInfLoading ? (
                        <div className="px-3 py-2 text-xs text-text-muted">{t('mapVisualization.loading')}</div>
                      ) : modelInfError ? (
                        <div className="px-3 py-2 text-xs text-danger">
                          {t('mapVisualization.loadFailed')}{modelInfError}
                        </div>
                      ) : !modelInfHeaders || modelInfHeaders.length === 0 ? (
                        <div className="px-3 py-2 text-xs text-text-muted">{t('mapVisualization.noData')}</div>
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
                                  {h || `${t('mapVisualization.column')}${idx + 1}`}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {modelInfRows.map((row, rIdx) => (
                              <tr key={rIdx} className={rIdx % 2 === 0 ? 'bg-bg-elevated/40' : ''}>
                                {modelInfHeaders.map((_, cIdx) => (
                                  <td
                                    key={cIdx}
                                    className="px-2 py-1.5 text-text-secondary border-b border-border-light whitespace-nowrap overflow-hidden text-ellipsis"
                                  >
                                    {row[cIdx] ?? ''}
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

            <div className="glass-light rounded-field border border-border p-3 text-xs text-text-secondary">
              <strong className="text-text-primary">{t('mapVisualization.configInstructions')}</strong>
              <ul className="list-disc list-inside ml-2 mt-1 space-y-1">
                <li>{t('mapVisualization.weatherGroupInfo')}</li>
                <li>{t('mapVisualization.climateRefText')}<a
                  href="/api/materials/climate-params"
                  download="气候参数.xlsx"
                  className="text-sky-500 hover:text-sky-600 underline underline-offset-2"
                >
                  {t('mapVisualization.downloadClimate')}
                </a>{t('mapVisualization.seeCities')}</li>

                <li>{t('mapVisualization.latentHeatInfo')}</li>
                <li>{t('mapVisualization.wetFractionInfo')}</li>
              </ul>
            </div>
          </div>
        )}

        {activeTab === 'scenarios' && (
          <div className="space-y-4">
            <div className="mb-4">
              <div className="text-sm font-semibold text-text-primary mb-1">
                {t('mapVisualization.scenarioInstructions')}
              </div>
              <div className="text-xs text-text-secondary space-y-1">
                <p>{t('mapVisualization.scenarioInfo')}</p>
                <ul className="list-disc list-inside ml-4 space-y-1">
                  <li><strong>{t('mapVisualization.scenario1')}</strong></li>
                  <li><strong>{t('mapVisualization.scenario2')}</strong></li>
                  <li><strong>{t('mapVisualization.scenario3')}</strong></li>
                </ul>
                <p className="mt-2">{t('mapVisualization.confirmParams')}</p>
              </div>
            </div>
            {scenarios.map((scenario, index) => (
              <ScenarioEditor
                key={index}
                scenario={scenario}
                onChange={(updated) => {
                  const newScenarios = [...scenarios]
                  newScenarios[index] = updated
                  setScenarios(newScenarios)
                }}
                index={index}
              />
            ))}
          </div>
        )}

        {activeTab === 'global' && (
          <GlobalParamsEditor
            globalParams={globalParams}
            onChange={setGlobalParams}
          />
        )}

        {activeTab === 'colormap' && (
          <div className="space-y-4">
            <div className="mb-4">
              <div className="text-sm font-semibold text-text-primary mb-1">
                {t('mapVisualization.colormapInstructions')}
              </div>
              <div className="text-xs text-text-secondary">
                {t('mapVisualization.colormapInstructionsDetail')}
              </div>
            </div>
            <ColormapSelector
              weatherGroup={weatherGroup}
              value={colormapParams}
              onChange={setColormapParams}
            />
          </div>
        )}

        {/* Button and error message area */}
        <div className="mt-6 pt-4 border-t border-border">
          {user?.tier === 'normal' ? (
            <div className="mb-4 rounded-xl border border-warning-soft bg-warning-soft p-3 text-xs text-text-secondary">
              {t('mapVisualization.proRestriction')}
            </div>
          ) : null}

          <div className="mb-4 rounded-field border border-border glass-light px-3 py-3">
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
                const params: MaterialComparisonParams = {
                  weather_group: weatherGroup,
                  scenarios: scenarios,
                  idf_template_dir: resolvedIdfTemplateDir,
                  global_params: Object.keys(globalParams).length > 0 ? globalParams : undefined,
                  enable_latent_heat: enableLatentHeat,
                  wet_fraction: enableLatentHeat ? wetFraction : undefined,
                  colormap_params: colormapParams,
                }
                m.mutate({ params, remark: remark.trim() || undefined })
              }}
            >
              {m.isPending ? t('common.loading') : t('mapVisualization.startAnalysis')}
            </Button>
          </div>

          {m.isError ? (
            <div className="mt-4 rounded-xl border border-danger/30 bg-danger/10 backdrop-blur-sm p-3 text-sm text-text-secondary">
              {t('mapVisualization.createFailed')}{m.error instanceof Error ? m.error.message : 'Unknown error'}
            </div>
          ) : null}
        </div>
      </Card>

      <Card className="glass-light">
        <CardHeader>
          <CardTitle>{t('mapVisualization.usage')}</CardTitle>
          <CardDesc>{t('mapVisualization.usageNote')}</CardDesc>
          <CardDesc>{t('mapVisualization.localTool')}</CardDesc>
        </CardHeader>
        <div className="text-sm text-text-secondary leading-relaxed space-y-2">
          <p>
            <strong>{t('mapVisualization.functionDesc')}</strong>
          </p>
          <p>
            <strong>{t('mapVisualization.scenarioConfig')}</strong>
            <ul className="list-disc list-inside ml-4 mt-1">
              <li>{t('mapVisualization.firstScenario')}</li>
              <li>{t('mapVisualization.secondScenario')}</li>
              <li>{t('mapVisualization.thirdScenario')}</li>
            </ul>
            {t('mapVisualization.wallRoof')}
          </p>

          <p>
            <strong>{t('mapVisualization.workflow')}</strong>
          </p>
          <ul className="list-disc list-inside ml-4 space-y-1">
            <li>{t('mapVisualization.step1')}</li>
            <li>{t('mapVisualization.step2')}</li>
            <li>{t('mapVisualization.step3')}</li>
            <li>{t('mapVisualization.step4')}</li>
            <li>{t('mapVisualization.step5')}</li>
          </ul>
          <p>
            <strong>PS:</strong>
            <a
              href="https://pan.baidu.com/s/5HSYoMlOND5rAbSu3EhKXHQ"
              target="_blank"
              rel="noopener noreferrer"
              className="font-semibold text-accent hover:text-accent/80 underline underline-offset-2 transition-colors"
            >
              {t('mapVisualization.localNote')}
            </a>
            {t('mapVisualization.localDesc')}
          </p>
        </div>
      </Card>
    </div>
  )
}
