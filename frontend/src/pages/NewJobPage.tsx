import { useMemo, useState, useEffect } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import Button from '../components/ui/Button'
import { Card, CardDesc, CardHeader, CardTitle } from '../components/ui/Card'
import Segmented from '../components/ui/Segmented'
import AtmPresetPicker from '../components/AtmPresetPicker'
import CheckboxPill from '../components/ui/CheckboxPill'
import { Search } from 'lucide-react'
import HelpButton from '../components/Help/HelpButton'
import Modal from '../components/ui/Modal'
import { createJob } from '../services/jobs'
import { getUploadsActive, uploadAtmPreset } from '../services/uploads'
import { listAtmPresets } from '../services/presets'
import type { JobType } from '../types/jobs'
import { useAuth } from '../context/AuthContext'

function SectionLabel(props: { children: React.ReactNode }) {
  return (
    <div className="text-[11px] font-bold uppercase tracking-widest text-text-tertiary mb-3 mt-2 px-1">
      {props.children}
    </div>
  )
}

function Field({
  label,
  hint,
  children,
}: {
  label: React.ReactNode
  hint?: string
  children: React.ReactNode
}) {
  return (
    <div className="space-y-1.5">
      <div className="text-xs font-semibold text-text-secondary px-1">{label}</div>
      {children}
      {hint ? <div className="text-xs text-text-muted px-1">{hint}</div> : null}
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

type Precision = 'low' | 'medium' | 'high'

function precisionToAngleSteps(p: Precision): number {
  if (p === 'low') return 1000
  if (p === 'high') return 5000
  return 2000
}

const FIGURE_FILES = [
  '1_1_cooling_power_timeline.png',
  '1_2_power_components.png',
  '1_3_temperature_cloud.png',
  '1_4_wind_humidity.png',
  '1_5_solar_components.png',
  '2_1_hourly_variation.png',
  '2_2_power_composition.png',
  '2_3_day_night_boxplot.png',
  '2_4_cooling_vs_temperature.png',
  '2_5_cooling_vs_wind.png',
  '2_6_humidity_vs_solar.png',
  '3_1_distribution.png',
  '3_2_cumulative.png',
  '3_3_material_vs_ideal.png',
  '3_4_heatmap_cloud_temp.png',
  '3_5_radar.png',
  '3_6_transmittance_effect.png',
  '4_1_solar_reflectance_opt.png',
  '4_2_emissivity_opt.png',
  '4_3_best_conditions.png',
  '4_4_correlation_matrix.png',
  '4_5_humidity_effect.png',
  '4_6_recommendations.png',
  '5_0_kpi_cards.png',
  '5_1_time_series.png',
  '5_2_hourly_avg.png',
  '5_3_distribution.png',
  '5_4_cloud_temp_power.png',
  '5_5_day_night_box.png',
  '5_6_efficiency.png',
  '5_7_transmittance.png',
  '5_8_summary_table.png',
]

function groupKey(filename: string): '1' | '2' | '3' | '4' | '5' {
  const m = filename.match(/^(\d)_/)
  return (m?.[1] as any) || '1'
}

export default function NewJobPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const nav = useNavigate()
  const [searchParams] = useSearchParams()

  const typeFromUrl = (searchParams.get('type') as JobType | null) ?? null
  const initialType = (typeFromUrl ?? 'cooling') as JobType

  const [type, setType] = useState<JobType>(initialType)

  const DEFAULT_LON = '117.26956'
  const DEFAULT_LAT = '31.8369'

  useEffect(() => {
    if (typeFromUrl && typeFromUrl !== type) {
      setType(typeFromUrl)
      setAtmPreset(typeFromUrl === 'in_situ_simulation' ? 'Fullytransparent.dll' : 'clear_sky.dll')
    }
  }, [typeFromUrl, type])
  const [precision, setPrecision] = useState<Precision>('medium')
  const [atmPreset, setAtmPreset] = useState(
    initialType === 'in_situ_simulation' ? 'Fullytransparent.dll' : 'clear_sky.dll',
  )
  const [customAtmItems, setCustomAtmItems] = useState<string[]>([])
  const [enableNatConv, setEnableNatConv] = useState(false)

  const [enablePhaseChange, setEnablePhaseChange] = useState(false)
  const [phaseTemp, setPhaseTemp] = useState('')
  const [phasePower, setPhasePower] = useState('0')
  const [phaseWidth, setPhaseWidth] = useState('0')

  const [enableLatentHeat, setEnableLatentHeat] = useState(false)
  const [relativeHumidity, setRelativeHumidity] = useState('50')
  const [wetFraction, setWetFraction] = useState('1')
  const [wetFractionHelpOpen, setWetFractionHelpOpen] = useState(false)
  const [remark, setRemark] = useState('')

  const [startDate, setStartDate] = useState('2024-01-01')
  const [endDate, setEndDate] = useState('2024-01-01')
  const [lon, setLon] = useState(DEFAULT_LON)
  const [lat, setLat] = useState(DEFAULT_LAT)
  const [tzOffset, setTzOffset] = useState('8')
  const [skyView, setSkyView] = useState('1.0')
  const [atmMode, setAtmMode] = useState(0)
  const [userEditedLonLat, setUserEditedLonLat] = useState(false)
  const [geoAttempted, setGeoAttempted] = useState(false)
  const [geoStatus, setGeoStatus] = useState<
    'idle' | 'requesting' | 'success' | 'denied' | 'unavailable' | 'timeout' | 'error' | 'unsupported' | 'ipLocating' | 'ipSuccess' | 'ipFailed'
  >('idle')
  const [geoMessage, setGeoMessage] = useState<string>('')

  async function requestIPLocation() {
    const amapKey = '7f804584cb35f022a2f1bd2d0888e491'

    try {
      setGeoStatus('ipLocating')
      setGeoMessage(t('geolocation.ipLocating'))

      const resp = await fetch(`https://restapi.amap.com/v3/ip?key=${amapKey}`)
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)

      const data: any = await resp.json()
      if (data.status !== '1') throw new Error(data.info || 'ip location failed')

      let lonNum: number | null = null
      let latNum: number | null = null

      if (typeof data.location === 'string' && data.location.includes(',')) {
        const [lonStr, latStr] = data.location.split(',')
        lonNum = Number(lonStr)
        latNum = Number(latStr)
      } else if (typeof data.rectangle === 'string' && data.rectangle.includes(';')) {
        const [p1, p2] = data.rectangle.split(';')
        const [lon1Str, lat1Str] = p1.split(',')
        const [lon2Str, lat2Str] = p2.split(',')
        const lon1 = Number(lon1Str)
        const lat1 = Number(lat1Str)
        const lon2 = Number(lon2Str)
        const lat2 = Number(lat2Str)
        if (Number.isFinite(lon1) && Number.isFinite(lat1) && Number.isFinite(lon2) && Number.isFinite(lat2)) {
          lonNum = (lon1 + lon2) / 2
          latNum = (lat1 + lat2) / 2
        }
      }

      if (lonNum === null || latNum === null || !Number.isFinite(lonNum) || !Number.isFinite(latNum)) {
        throw new Error('invalid ip location coords')
      }

      const nextLon = lonNum.toFixed(4)
      const nextLat = latNum.toFixed(4)

      setLon(nextLon)
      setLat(nextLat)
      setGeoStatus('ipSuccess')
      setGeoMessage(t('geolocation.ipSuccess'))
      setGeoAttempted(true)
    } catch (err) {
      if (import.meta.env.DEV) console.error('IP 定位失败', err)
      setGeoStatus('ipFailed')
      setGeoMessage(t('geolocation.ipFailed'))
      setGeoAttempted(true)
    }
  }

  function requestGeolocation() {
    if (!('geolocation' in navigator)) {
      requestIPLocation()
      return
    }

    setGeoStatus('requesting')
    setGeoMessage(t('geolocation.requesting'))

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const nextLon = pos.coords.longitude
        const nextLat = pos.coords.latitude
        if (Number.isFinite(nextLon) && Number.isFinite(nextLat)) {
          setLon(nextLon.toFixed(6))
          setLat(nextLat.toFixed(6))
          setGeoStatus('success')
          setGeoMessage(t('geolocation.success'))
        } else {
          setGeoStatus('error')
          setGeoMessage(t('geolocation.invalid'))
        }
        setGeoAttempted(true)
      },
      (err) => {
        if (err.code === err.PERMISSION_DENIED) {
          setGeoStatus('denied')
          setGeoMessage(t('geolocation.denied'))
          requestIPLocation()
        } else if (err.code === err.POSITION_UNAVAILABLE) {
          setGeoStatus('unavailable')
          setGeoMessage(t('geolocation.unavailable'))
          requestIPLocation()
        } else if (err.code === err.TIMEOUT) {
          setGeoStatus('timeout')
          setGeoMessage(t('geolocation.timeout'))
          requestIPLocation()
        } else {
          setGeoStatus('error')
          setGeoMessage(t('geolocation.error'))
          requestIPLocation()
        }
      },
      { enableHighAccuracy: true, maximumAge: 0 }
    )
  }

  useEffect(() => {
    if (type !== 'in_situ_simulation') return
    if (geoAttempted) return
    if (userEditedLonLat) return
    if (lon !== DEFAULT_LON || lat !== DEFAULT_LAT) return
    requestGeolocation()
  }, [type, geoAttempted, userEditedLonLat, lon, lat, DEFAULT_LON, DEFAULT_LAT])

  const [figureFlags, setFigureFlags] = useState<boolean[]>(() => {
    const flags = Array(FIGURE_FILES.length).fill(false)
    for (let i = 0; i < 5; i++) flags[i] = true
    for (let i = 5; i < 11; i++) flags[i] = true
    const idx44 = FIGURE_FILES.indexOf('4_4_correlation_matrix.png')
    if (idx44 >= 0) flags[idx44] = true
    const idx31 = FIGURE_FILES.indexOf('3_1_distribution.png')
    if (idx31 >= 0) flags[idx31] = true
    const idx32 = FIGURE_FILES.indexOf('3_2_cumulative.png')
    if (idx32 >= 0) flags[idx32] = true
    const idx33 = FIGURE_FILES.indexOf('3_3_material_vs_ideal.png')
    if (idx33 >= 0) flags[idx33] = true
    return flags
  })

  const groups = useMemo(() => {
    const g: Record<string, string[]> = { '1': [], '2': [], '3': [], '4': [], '5': [] }
    for (const f of FIGURE_FILES) g[groupKey(f)].push(f)
    return g
  }, [])

  function setAllGroup(group: '1' | '2' | '3' | '4' | '5', value: boolean) {
    const newFlags = [...figureFlags]
    for (const fname of groups[group]) {
      const idx = FIGURE_FILES.indexOf(fname)
      if (idx >= 0) newFlags[idx] = value
    }
    setFigureFlags(newFlags)
  }

  const dateConstraintError = useMemo(() => {
    if (type !== 'in_situ_simulation') return null
    const sd = new Date(startDate + 'T00:00:00')
    const ed = new Date(endDate + 'T00:00:00')
    if (Number.isNaN(sd.getTime()) || Number.isNaN(ed.getTime())) return t('dateValidation.invalidFormat')
    if (ed < sd) return t('dateValidation.endBeforeStart')
    if (sd.getFullYear() !== ed.getFullYear()) return t('dateValidation.crossYear')
    const ym0 = sd.getFullYear() * 12 + sd.getMonth()
    const ym1 = ed.getFullYear() * 12 + ed.getMonth()
    if (ym1 - ym0 > 1) return t('dateValidation.maxOneMonth')
    return null
  }, [startDate, endDate, type, t])

  const atmQ = useQuery({ queryKey: ['presets', 'atm'], queryFn: listAtmPresets })
  const uploadsQ = useQuery({ queryKey: ['uploads', 'active'], queryFn: getUploadsActive })

  const uploadAtmMutation = useMutation({
    mutationFn: uploadAtmPreset,
    onSuccess: (res) => {
      setCustomAtmItems((prev) => prev.includes(res.stored_name) ? prev : [...prev, res.stored_name])
    },
  })

  const mergedAtmItems = useMemo(
    () => Array.from(new Set([...(atmQ.data ?? []), ...customAtmItems])),
    [atmQ.data, customAtmItems],
  )

  const angleSteps = useMemo(() => precisionToAngleSteps(precision), [precision])

  const canSubmit = useMemo(() => {
    if (user?.tier === 'normal' && type === 'in_situ_simulation') return false
    if (type === 'in_situ_simulation') return dateConstraintError === null
    return type === 'cooling' || type === 'heating' || type === 'mock'
  }, [type, dateConstraintError, user?.tier])

  const uploadsReady = uploadsQ.data?.ready ?? false
  const requiresMaterial = type === 'cooling' || type === 'heating' || type === 'in_situ_simulation'
  const canSubmitWithMaterial = !requiresMaterial || uploadsReady

  const m = useMutation({
    mutationFn: createJob,
    onSuccess: (res) => nav(`/jobs/${res.job_id}`),
  })

  return (
    <div className="space-y-5">
      <Card className="animate-fade-slide-up">
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div>
              <CardTitle>{t('pages.newJob.title')}</CardTitle>
              <CardDesc>{t('pages.newJob.desc')}</CardDesc>
            </div>
            {type === 'cooling' ? (
              <HelpButton doc="cooling" />
            ) : type === 'heating' ? (
              <HelpButton doc="heating" />
            ) : type === 'in_situ_simulation' ? (
              <HelpButton doc="in_situ_era5" />
            ) : null}
          </div>
        </CardHeader>

        <div className="grid gap-5 md:grid-cols-2">
          <Field label={t('job.type')} hint={t('pages.newJob.typeHint')}>
            <Select
              value={type}
              onChange={(e) => {
                const next = e.target.value as JobType
                setType(next)
                setAtmPreset(next === 'in_situ_simulation' ? 'Fullytransparent.dll' : 'clear_sky.dll')
              }}
              disabled={typeFromUrl !== null}
            >
              <option value="cooling">{t('jobTypes.cooling')}</option>
              <option value="heating">{t('jobTypes.heating')}</option>
              <option value="in_situ_simulation">{t('jobTypes.in_situ_simulation')}</option>
              <option value="mock">{t('jobTypes.mock')}</option>
            </Select>
          </Field>

          <Field label={t('pages.newJob.presetLabel')} hint={t('pages.newJob.presetHint')}>
            <div className="glass-light rounded-field border border-border px-3.5 py-2.5 text-sm text-text-secondary">
              default/
            </div>
          </Field>

          {type !== 'in_situ_simulation' ? (
            <>
              <div className="md:col-span-2">
                <SectionLabel>{t('pages.newJob.precision')}</SectionLabel>
                <Segmented<Precision>
                  value={precision}
                  onChange={setPrecision}
                  options={[
                    { value: 'low', label: t('precision.low'), description: t('pages.newJob.precisionSteps', { steps: 1000 }) },
                    { value: 'medium', label: t('precision.medium'), description: t('pages.newJob.precisionSteps', { steps: 2000 }) },
                    { value: 'high', label: t('precision.high'), description: t('pages.newJob.precisionSteps', { steps: 5000 }) },
                  ]}
                />
              </div>

              <div className="md:col-span-2">
                <Field label={t('pages.newJob.atmPresetLabel')} hint={t('pages.newJob.atmPresetHint')}>
                  <div className="space-y-3">
                    <AtmPresetPicker items={mergedAtmItems.length ? mergedAtmItems : ['Fullytransparent.dll']} value={atmPreset} onChange={setAtmPreset} />
                    <div className="flex flex-wrap items-center gap-2 text-xs text-text-muted">
                      <span>{t('uploadAtm.hint')}</span>
                      <label className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-dashed border-border px-3 py-1.5 text-xs text-text-secondary hover:border-accent/40 hover:text-text-primary transition-colors duration-150">
                        <input
                          type="file"
                          accept=".dll"
                          className="hidden"
                          onChange={(e) => {
                            const file = e.target.files?.[0]
                            if (!file) return
                            uploadAtmMutation.mutate(file)
                            e.target.value = ''
                          }}
                        />
                        <span className="font-semibold">
                          {uploadAtmMutation.isPending ? t('common.loading') : t('uploadAtm.uploadFile')}
                        </span>
                      </label>
                    </div>
                    {uploadAtmMutation.isSuccess ? (
                      <div className="text-xs text-accent font-medium">
                        {t('uploadAtm.successHint')}
                        {(uploadAtmMutation.data?.stored_name ?? '').replace('.dll', '')}
                      </div>
                    ) : null}
                    {uploadAtmMutation.isError ? (
                      <div className="text-xs text-danger font-medium">{t('uploadAtm.failed')}</div>
                    ) : null}
                  </div>
                </Field>
              </div>

              <Field label={t('pages.newJob.natConvLabel')} hint={t('pages.newJob.natConvHint')}>
                <label className="glass-light flex items-center gap-2 rounded-field border border-border px-3.5 py-2.5 text-sm text-text-secondary transition-all duration-150 hover:bg-bg-elevated hover:border-border-light cursor-pointer">
                  <input type="checkbox" checked={enableNatConv} onChange={(e) => setEnableNatConv(e.target.checked)} className="cursor-pointer w-4 h-4 rounded accent-accent" />
                  <span>{enableNatConv ? t('common.enabled') : t('common.disabled')}</span>
                </label>
              </Field>

              <div className="md:col-span-2">
                <SectionLabel>{t('pages.newJob.phaseTitle')}</SectionLabel>
              </div>

              <Field label={t('pages.newJob.phaseEnable')} hint={t('pages.newJob.phaseEnableDesc')}>
                <label className="glass-light flex items-center gap-2 rounded-field border border-border px-3.5 py-2.5 text-sm text-text-secondary transition-all duration-150 hover:bg-bg-elevated hover:border-border-light cursor-pointer">
                  <input type="checkbox" checked={enablePhaseChange} onChange={(e) => setEnablePhaseChange(e.target.checked)} className="cursor-pointer w-4 h-4 rounded accent-accent" />
                  <span>{enablePhaseChange ? t('common.enabled') : t('common.disabled')}</span>
                </label>
              </Field>

              {enablePhaseChange && (
                <>
                  <Field label={t('pages.newJob.phaseTemp')} hint={t('pages.newJob.phaseTempHint')}>
                    <Input value={phaseTemp} onChange={(e) => setPhaseTemp(e.target.value)} placeholder={t('pages.newJob.placeholderExample', { value: 25 })} />
                  </Field>
                  <Field label={t('pages.newJob.phasePower')} hint={t('pages.newJob.phasePowerHint')}>
                    <Input value={phasePower} onChange={(e) => setPhasePower(e.target.value)} placeholder={t('pages.newJob.placeholderExample', { value: 0 })} />
                  </Field>
                  <Field label={t('pages.newJob.phaseWidth')} hint={t('pages.newJob.phaseWidthHint')}>
                    <Input value={phaseWidth} onChange={(e) => setPhaseWidth(e.target.value)} placeholder={t('pages.newJob.placeholderExample', { value: 0 })} />
                  </Field>
                </>
              )}

              <div className="md:col-span-2">
                <SectionLabel>{t('pages.newJob.latentHeatTitle')}</SectionLabel>
              </div>

              <Field label={t('pages.newJob.latentHeatEnable')} hint={t('pages.newJob.latentHeatDesc')}>
                <label className="glass-light flex items-center gap-2 rounded-field border border-border px-3.5 py-2.5 text-sm text-text-secondary transition-all duration-150 hover:bg-bg-elevated hover:border-border-light cursor-pointer">
                  <input type="checkbox" checked={enableLatentHeat} onChange={(e) => setEnableLatentHeat(e.target.checked)} className="cursor-pointer w-4 h-4 rounded accent-accent" />
                  <span>{enableLatentHeat ? t('common.enabled') : t('common.disabled')}</span>
                </label>
              </Field>

              {enableLatentHeat && (
                <>
                  <Field label={t('pages.newJob.relativeHumidity')} hint={t('pages.newJob.relativeHumidityHint')}>
                    <Input type="number" min="0" max="100" value={relativeHumidity} onChange={(e) => setRelativeHumidity(e.target.value)} placeholder={t('pages.newJob.placeholderExample', { value: 50 })} />
                  </Field>
                  <Field label={t('pages.newJob.wetFraction')} hint={t('pages.newJob.wetFractionHint')}>
                    <Input type="number" min="0" max="1" step="0.01" value={wetFraction} onChange={(e) => setWetFraction(e.target.value)} placeholder={t('pages.newJob.placeholderExample', { value: 1 })} />
                  </Field>
                  <Modal open={wetFractionHelpOpen} onClose={() => setWetFractionHelpOpen(false)} title={t('pages.newJob.wetFractionHelpTitle')} widthClassName="max-w-2xl">
                    <div className="text-sm text-text-secondary leading-relaxed whitespace-pre-line">{t('pages.newJob.wetFractionHelpBody')}</div>
                  </Modal>
                </>
              )}
            </>
          ) : (
            <div className="md:col-span-2">
              <Field label={t('pages.newJob.atmPresetLabel')} hint={t('pages.newJob.atmPresetHint')}>
                <div className="space-y-2">
                  <div className="glass-light flex items-center gap-2 rounded-field border border-border px-3.5 py-2.5 transition-all duration-150 hover:border-border-light">
                    <Search size={14} className="text-text-muted shrink-0" />
                    <input
                      type="text"
                      value={atmPreset}
                      onChange={(e) => setAtmPreset(e.target.value)}
                      placeholder={t('uploadAtm.placeholder')}
                      className="flex-1 bg-transparent border-none outline-none text-sm text-text-primary placeholder:text-text-muted"
                      list="atm-preset-suggestions"
                    />
                    <datalist id="atm-preset-suggestions">
                      {mergedAtmItems.map((name) => (
                        <option key={name} value={name} />
                      ))}
                    </datalist>
                  </div>
                  <div className="text-xs text-text-muted px-1">{t('uploadAtm.default')}</div>
                </div>
              </Field>
            </div>
          )}

          {type === 'in_situ_simulation' ? (
            <>
              <div className="md:col-span-2">
                <SectionLabel>{t('inSituSimulation.paramsTitle')}</SectionLabel>
              </div>

              <Field label={t('inSituSimulation.startDate')} hint={t('inSituSimulation.startDateHint')}>
                <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
              </Field>
              <Field label={t('inSituSimulation.endDate')} hint={t('inSituSimulation.endDateHint')}>
                <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
              </Field>
              <Field label={t('inSituSimulation.longitude')}>
                <Input value={lon} onChange={(e) => { setUserEditedLonLat(true); setLon(e.target.value) }} />
              </Field>
              <Field label={t('inSituSimulation.latitude')}>
                <Input value={lat} onChange={(e) => { setUserEditedLonLat(true); setLat(e.target.value) }} />
              </Field>

              <div className="md:col-span-2">
                <div className="flex items-center justify-between gap-3 rounded-field border border-border glass-light px-3.5 py-2.5">
                  <div className="text-xs text-text-muted">
                    {geoStatus === 'idle' ? <>{t('geolocation.hint')}</> : <>{geoMessage}</>}
                  </div>
                  <Button type="button" size="sm" variant="secondary" disabled={geoStatus === 'requesting' || geoStatus === 'ipLocating'} onClick={() => { setGeoAttempted(false); requestGeolocation() }}>
                    {t('geolocation.autoLocate')}
                  </Button>
                </div>
              </div>

              <div className="md:col-span-2">
                <div className="mt-2">
                  <div className="flex items-center justify-between gap-3 mb-2">
                    <div className="text-xs font-semibold text-text-secondary">
                      {t('geolocation.positionPreview')} (Lon: {lon}, Lat: {lat})
                    </div>
                    <a href="https://jingweidu.bmcx.com/" target="_blank" rel="noreferrer" className="text-xs rounded-lg border border-border px-2 py-1 text-text-secondary transition-all duration-150 hover:bg-bg-elevated hover:border-border-light">
                      {t('geolocation.lonLatQuery')}
                    </a>
                  </div>
                  {(() => {
                    const lonNum = Number(lon)
                    const latNum = Number(lat)
                    const isValidLon = !isNaN(lonNum) && lonNum >= -180 && lonNum <= 180
                    const isValidLat = !isNaN(latNum) && latNum >= -90 && latNum <= 90
                    const amapKey = '7f804584cb35f022a2f1bd2d0888e491'

                    if (!isValidLon || !isValidLat) {
                      return (
                        <div className="glass-light w-full rounded-field border border-border p-4 text-center text-sm text-text-muted">
                          {t('geolocation.enterValidCoords')}
                        </div>
                      )
                    }
                    return (
                      <>
                        <div className="w-full rounded-field border border-border overflow-hidden">
                          <iframe
                            key={`${lon}-${lat}`}
                            width="100%"
                            height="340"
                            style={{ border: 'none' }}
                            loading="lazy"
                            referrerPolicy="no-referrer-when-downgrade"
                            src={`https://restapi.amap.com/v3/staticmap?location=${lon},${lat}&zoom=12&size=375*167&scale=2&markers=mid,,A:${lon},${lat}&key=${amapKey}`}
                            title={t('geolocation.mapTitle')}
                          />
                        </div>
                        <div className="mt-1 text-xs text-text-muted">{t('geolocation.mapProvidedBy')}</div>
                      </>
                    )
                  })()}
                </div>
              </div>

              <Field label={t('inSituSimulation.timezoneOffset')}>
                <Input value={tzOffset} onChange={(e) => setTzOffset(e.target.value)} />
              </Field>
              <Field label={t('inSituSimulation.skyView')}>
                <Input value={skyView} onChange={(e) => setSkyView(e.target.value)} />
              </Field>
              <div className="md:col-span-2">
                <Field label={t('inSituSimulation.atmMode')} hint={t('inSituSimulation.atmModeHint')}>
                  <div className="flex flex-col gap-2">
                    {[
                      { val: 0, label: t('inSituSimulation.realAtmData') },
                      { val: 1, label: t('inSituSimulation.correctedMixedMode') },
                      { val: 2, label: t('inSituSimulation.theoreticalMode') },
                    ].map(({ val, label }) => (
                      <label key={val} className="glass-light flex items-center gap-2 rounded-field border border-border px-3.5 py-2.5 text-sm text-text-secondary transition-all duration-150 hover:bg-bg-elevated hover:border-border-light cursor-pointer">
                        <input type="radio" name="atm_mode" checked={atmMode === val} onChange={() => setAtmMode(val)} className="cursor-pointer w-4 h-4 accent-accent" />
                        <span>{label}</span>
                      </label>
                    ))}
                  </div>
                </Field>
              </div>

              <div className="md:col-span-2">
                <SectionLabel>{t('pages.newJob.latentHeatTitle')}</SectionLabel>
              </div>

              <Field label={t('pages.newJob.latentHeatEnable')} hint={t('pages.newJob.latentHeatInSituDesc')}>
                <label className="glass-light flex items-center gap-2 rounded-field border border-border px-3.5 py-2.5 text-sm text-text-secondary transition-all duration-150 hover:bg-bg-elevated hover:border-border-light cursor-pointer">
                  <input type="checkbox" checked={enableLatentHeat} onChange={(e) => setEnableLatentHeat(e.target.checked)} className="cursor-pointer w-4 h-4 rounded accent-accent" />
                  <span>{enableLatentHeat ? t('common.enabled') : t('common.disabled')}</span>
                </label>
              </Field>

              {enableLatentHeat && (
                <Field label={t('pages.newJob.wetFraction')} hint={t('pages.newJob.wetFractionHint')}>
                  <Input type="number" min="0" max="1" step="0.1" value={wetFraction} onChange={(e) => setWetFraction(e.target.value)} placeholder={t('pages.newJob.placeholderExample', { value: 1 })} />
                </Field>
              )}

              <div className="md:col-span-2">
                <SectionLabel>{t('inSituSimulation.figureSelection')}</SectionLabel>
                {(['1', '2', '3', '4', '5'] as const).map((k) => (
                  <div key={k} className="mb-3 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <div className="font-medium text-sm text-text-secondary">{t('inSituSimulation.group')} {k}</div>
                      <div className="flex gap-2">
                        <Button variant="secondary" size="sm" onClick={() => setAllGroup(k, true)}>{t('inSituSimulation.selectAll')}</Button>
                        <Button variant="secondary" size="sm" onClick={() => setAllGroup(k, false)}>{t('inSituSimulation.selectNone')}</Button>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {groups[k].map((fname) => {
                        const idx = FIGURE_FILES.indexOf(fname)
                        const checked = figureFlags[idx]
                        return (
                          <CheckboxPill
                            key={fname}
                            checked={checked}
                            onChange={(v) => {
                              const next = [...figureFlags]
                              next[idx] = v
                              setFigureFlags(next)
                            }}
                            label={fname.replace('.png', '')}
                          />
                        )
                      })}
                    </div>
                  </div>
                ))}
              </div>

              {dateConstraintError ? (
                <div className="md:col-span-2 rounded-field border border-danger/30 bg-danger/10 p-3 text-sm text-text-secondary">
                  {dateConstraintError}
                </div>
              ) : null}
            </>
          ) : null}

          {!canSubmitWithMaterial && requiresMaterial ? (
            <div className="md:col-span-2 rounded-field border border-warning/30 bg-warning/10 p-3 text-sm">
              <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                <div>
                  <div className="font-semibold text-text-primary">{t('pages.newJob.materialNotReadyTitle')}</div>
                  <div className="text-xs text-text-secondary">{t('pages.newJob.materialNotReadyDesc')}</div>
                </div>
                <Link to="/uploads">
                  <Button variant="secondary" size="sm">{t('pages.newJob.goToUploads')}</Button>
                </Link>
              </div>
            </div>
          ) : null}

          {user?.tier === 'normal' && type === 'in_situ_simulation' ? (
            <div className="md:col-span-2 rounded-field border border-warning/30 bg-warning/10 p-3 text-xs text-text-secondary">
              {t('account.normalTierRestriction')}
            </div>
          ) : null}

          {/* Remark */}
          <div className="md:col-span-2 rounded-field border border-border glass-light p-3.5">
            <div className="flex items-center justify-between mb-1.5">
              <div className="text-[11px] font-bold uppercase tracking-wider text-text-muted">{t('job.remark')}</div>
              <div className="text-[11px] text-text-tertiary">{remark.length} / 50</div>
            </div>
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

          {/* Actions */}
          <div className="md:col-span-2 flex items-center justify-end gap-2 pt-2">
            <Button size="lg" variant="secondary" onClick={() => nav('/jobs')}>
              {t('common.cancel')}
            </Button>
            <Button
              size="lg"
              variant="primary"
              loading={m.isPending}
              disabled={!canSubmit || !canSubmitWithMaterial}
              onClick={() => {
                if (type === 'in_situ_simulation') {
                  m.mutate({
                    type,
                    remark: remark.trim() || undefined,
                    params: {
                      start_date: startDate,
                      end_date: endDate,
                      lon: Number(lon),
                      lat: Number(lat),
                      tz_offset_hours: Number(tzOffset),
                      sky_view: Number(skyView),
                      use_empirical_atm: atmMode,
                      enable_latent_heat: enableLatentHeat,
                      wet_fraction: enableLatentHeat ? Number(wetFraction) : undefined,
                      figure_flags: figureFlags,
                    },
                  })
                } else {
                  m.mutate({
                    type,
                    remark: remark.trim() || undefined,
                    params: {
                      angle_steps: angleSteps,
                      atm_preset: atmPreset,
                      enable_natural_convection: enableNatConv,
                      phase_temp_c: enablePhaseChange && phaseTemp.trim() !== '' ? Number(phaseTemp) : null,
                      phase_power_wm2: enablePhaseChange ? Number(phasePower) : 0,
                      phase_half_width_c: enablePhaseChange ? Number(phaseWidth) : 0,
                      enable_latent_heat: enableLatentHeat,
                      relative_humidity: enableLatentHeat ? Number(relativeHumidity) : undefined,
                      wet_fraction: enableLatentHeat ? Number(wetFraction) : undefined,
                    },
                  })
                }
              }}
            >
              {m.isPending ? t('common.loading') : t('common.create')}
            </Button>
          </div>

          {m.isError ? (
            <div className="md:col-span-2 rounded-field border border-danger/30 bg-danger/10 p-3 text-sm text-text-secondary">
              {t('pages.newJob.createFailed')}
            </div>
          ) : null}
        </div>
      </Card>

      <Card className="glass-light animate-fade-slide-up stagger-3">
        <CardHeader>
          <CardTitle>{t('pages.newJob.notesTitle')}</CardTitle>
          <CardDesc>{t('pages.newJob.notesDesc')}</CardDesc>
        </CardHeader>
        <div className="text-sm text-text-secondary leading-relaxed">{t('pages.newJob.notesBody')}</div>
      </Card>
    </div>
  )
}
