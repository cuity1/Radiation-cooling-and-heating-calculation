import { useEffect, useMemo, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import Plot from 'react-plotly.js'
import { getPlotlyLayout } from '../../lib/plotlyConfig'
import Button from '../../components/ui/Button'
import { Card, CardDesc, CardHeader, CardTitle } from '../../components/ui/Card'
import {
  ModtranRunRequest,
  runModtranTransmittance,
} from '../../services/tools'

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
        'focus:outline-none focus:ring-2 focus-visible:ring-2 focus-visible:ring-accent/50 focus-visible:border-accent/50 ' +
        'hover:border-border-light hover:bg-bg-elevated'
      }
    />
  )
}

function numberOrDefault(x: string, fallback = 0) {
  const v = Number(x)
  return Number.isFinite(v) ? v : fallback
}

const DEFAULT_TEMPLATE = 'Anew1.ltn'

const MODEL_TYPE_ITEMS: Array<{ code: 'T' | 'R'; label: string }> = [
  { code: 'T', label: 'T - 透射率 (Transmittance)' },
  { code: 'R', label: 'R - 辐射率 (Radiance)' },
]

const ATMOSPHERE_ITEMS: Array<{ code: number; label: string }> = [
  { code: 1, label: '1 - 热带 (Tropical)' },
  { code: 2, label: '2 - 中纬度夏季 (Mid-Latitude Summer)' },
  { code: 3, label: '3 - 中纬度冬季 (Mid-Latitude Winter)' },
  { code: 4, label: '4 - 副极地夏季 (Sub-Arctic Summer)' },
  { code: 5, label: '5 - 副极地冬季 (Sub-Arctic Winter)' },
  { code: 6, label: '6 - 1976美国标准大气 (US Std 1976)' },
]

const AEROSOL_ITEMS: Array<{ code: number; label: string }> = [
  { code: 0, label: '0 - 无气溶胶 (None)' },
  { code: 1, label: '1 - 乡村气溶胶 (Rural)' },
  { code: 2, label: '2 - 城市气溶胶 (Urban)' },
  { code: 3, label: '3 - 海洋气溶胶 (Maritime)' },
  { code: 4, label: '4 - 对流层气溶胶 (Tropospheric)' },
  { code: 5, label: '5 - 沙漠气溶胶 (Desert)' },
]

export default function ModtranTransmittancePage() {
  const { t } = useTranslation()

  // 写死默认模型：不再暴露模板选择（用户要求）
  const template = DEFAULT_TEMPLATE

  // 参数用“中文可读”的下拉项；值仍提交 code
  const [modelType, setModelType] = useState<'T' | 'R'>('T')
  const [atm, setAtm] = useState('6')
  const [aerosol, setAerosol] = useState('2')
  const [obsZen, setObsZen] = useState('0')
  const [obsAzi, setObsAzi] = useState('30')
  const [solZen, setSolZen] = useState('45')
  const [solAzi, setSolAzi] = useState('0')
  const [gndAlt, setGndAlt] = useState('1.5')
  // 默认范围：500–10000 cm⁻¹（用户要求）
  const [startCm, setStartCm] = useState('500')
  const [endCm, setEndCm] = useState('10000')
  const [resCm, setResCm] = useState('5')
  const [outResCm, setOutResCm] = useState('5')

  const startUm = useMemo(() => (numberOrDefault(startCm) > 0 ? 10000 / numberOrDefault(startCm) : 0), [startCm])
  const endUm = useMemo(() => (numberOrDefault(endCm) > 0 ? 10000 / numberOrDefault(endCm) : 0), [endCm])

  const runM = useMutation({
    mutationFn: (req: ModtranRunRequest) => runModtranTransmittance(req),
  })

  const parsed = useMemo(() => {
    const req: ModtranRunRequest = {
      template,
      model_type: modelType,
      atmosphere_model: numberOrDefault(atm, 6),
      aerosol_model: numberOrDefault(aerosol, 2),
      observer_zenith_deg: numberOrDefault(obsZen),
      observer_azimuth_deg: numberOrDefault(obsAzi),
      solar_zenith_deg: numberOrDefault(solZen),
      solar_azimuth_deg: numberOrDefault(solAzi),
      ground_alt_km: numberOrDefault(gndAlt),
      start_cm1: numberOrDefault(startCm),
      end_cm1: numberOrDefault(endCm),
      res_cm1: numberOrDefault(resCm),
      out_res_cm1: numberOrDefault(outResCm),
      export_excel: true,
    }
    const ok =
      req.template &&
      req.start_cm1 > 0 &&
      req.end_cm1 > 0 &&
      req.start_cm1 < req.end_cm1 &&
      req.res_cm1 > 0 &&
      req.out_res_cm1 > 0 &&
      (req.model_type === 'T' || req.model_type === 'R')
    return { req, ok }
  }, [template, modelType, atm, aerosol, obsZen, obsAzi, solZen, solAzi, gndAlt, startCm, endCm, resCm, outResCm])

  const res = runM.data

  const [wlX, setWlX] = useState<number[] | null>(null)
  const [wlY, setWlY] = useState<number[] | null>(null)
  const [plotError, setPlotError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function loadWavelengthCsv() {
      setPlotError(null)
      setWlX(null)
      setWlY(null)
      if (!res?.downloads?.wavelength_csv) return
      try {
        const r = await fetch(res.downloads.wavelength_csv)
        if (!r.ok) throw new Error(`download_failed: ${r.status}`)
        const text = await r.text()
        const lines = text.split(/\r?\n/).filter(Boolean)
        if (lines.length < 2) throw new Error('empty_csv')
        const header = lines[0].split(',')
        const idxWl = header.indexOf('Wavelength_um')
        const idxT = header.indexOf('Transmittance')
        if (idxWl < 0 || idxT < 0) throw new Error('missing_columns')
        const x: number[] = []
        const y: number[] = []
        for (const ln of lines.slice(1)) {
          const parts = ln.split(',')
          const a = Number(parts[idxWl])
          const b = Number(parts[idxT])
          if (!Number.isFinite(a) || !Number.isFinite(b)) continue
          x.push(a)
          y.push(b)
        }
        if (cancelled) return
        setWlX(x)
        setWlY(y)
      } catch (e: any) {
        if (cancelled) return
        setPlotError(String(e?.message ?? e))
      }
    }
    loadWavelengthCsv()
    return () => {
      cancelled = true
    }
  }, [res?.downloads?.wavelength_csv])

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div>
              <CardTitle>{t('tools.modtran.title')}</CardTitle>
              <CardDesc>{t('tools.modtran.desc')}</CardDesc>
            </div>
          </div>
        </CardHeader>

        <div className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2">
            <Field label={t('tools.modtran.fields.modelType')}>
              <select
                value={modelType}
                onChange={(e) => setModelType((e.target.value as any) ?? 'T')}
                className="w-full rounded-field border border-border bg-bg-elevated px-3.5 py-2 text-sm text-text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
              >
                {MODEL_TYPE_ITEMS.map((it) => (
                  <option key={it.code} value={it.code}>
                    {it.label}
                  </option>
                ))}
              </select>
            </Field>

            <Field label={t('tools.modtran.fields.atm')}>
              <select
                value={atm}
                onChange={(e) => setAtm(e.target.value)}
                className="w-full rounded-field border border-border bg-bg-elevated px-3.5 py-2 text-sm text-text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
              >
                {ATMOSPHERE_ITEMS.map((it) => (
                  <option key={it.code} value={String(it.code)}>
                    {it.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={t('tools.modtran.fields.aerosol')}>
              <select
                value={aerosol}
                onChange={(e) => setAerosol(e.target.value)}
                className="w-full rounded-field border border-border bg-bg-elevated px-3.5 py-2 text-sm text-text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
              >
                {AEROSOL_ITEMS.map((it) => (
                  <option key={it.code} value={String(it.code)}>
                    {it.label}
                  </option>
                ))}
              </select>
            </Field>

            <Field label={t('tools.modtran.fields.obsZen')}>
              <Input value={obsZen} onChange={(e) => setObsZen(e.target.value)} />
            </Field>
            <Field label={t('tools.modtran.fields.obsAzi')}>
              <Input value={obsAzi} onChange={(e) => setObsAzi(e.target.value)} />
            </Field>

            <Field label={t('tools.modtran.fields.solZen')}>
              <Input value={solZen} onChange={(e) => setSolZen(e.target.value)} />
            </Field>
            <Field label={t('tools.modtran.fields.solAzi')}>
              <Input value={solAzi} onChange={(e) => setSolAzi(e.target.value)} />
            </Field>

            <Field label={t('tools.modtran.fields.gndAlt')}>
              <Input value={gndAlt} onChange={(e) => setGndAlt(e.target.value)} />
            </Field>

            <Field label={t('tools.modtran.fields.startCm')}>
              <Input value={startCm} onChange={(e) => setStartCm(e.target.value)} />
            </Field>
            <Field label={t('tools.modtran.fields.endCm')}>
              <Input value={endCm} onChange={(e) => setEndCm(e.target.value)} />
            </Field>
            <Field label={t('tools.modtran.fields.startUm')}>
              <Input value={startUm.toFixed(5)} readOnly />
            </Field>
            <Field label={t('tools.modtran.fields.endUm')}>
              <Input value={endUm.toFixed(5)} readOnly />
            </Field>

            <Field label={t('tools.modtran.fields.resCm')}>
              <Input value={resCm} onChange={(e) => setResCm(e.target.value)} />
            </Field>
            <Field label={t('tools.modtran.fields.outResCm')}>
              <Input value={outResCm} onChange={(e) => setOutResCm(e.target.value)} />
            </Field>
          </div>

          <div className="flex items-center justify-end gap-2">
            <Button variant="secondary" disabled={!parsed.ok || runM.isPending} onClick={() => runM.mutate(parsed.req)}>
              {runM.isPending ? t('common.loading') : t('common.create')}
            </Button>
          </div>

          {runM.isError ? (
            <div className="rounded-xl border border-danger-soft bg-danger-soft p-3 text-sm text-text-secondary">
              {t('tools.modtran.error')}
            </div>
          ) : null}
        </div>
      </Card>

      {res ? (
        <div className="space-y-4">
          <Card className="glass-light">
            <CardHeader>
              <CardTitle>{t('tools.modtran.outputs.title')}</CardTitle>
              <CardDesc>{t('tools.modtran.outputs.desc')}</CardDesc>
            </CardHeader>
            <div className="space-y-3 text-sm text-text-secondary">
              <div className="grid gap-2 md:grid-cols-3">
                <div>
                  <div className="text-xs text-text-muted">{t('tools.modtran.outputs.duration')}</div>
                  <div className="text-sm text-text-primary">{res.meta.duration_sec.toFixed(2)} s</div>
                </div>
                <div>
                  <div className="text-xs text-text-muted">{t('tools.modtran.outputs.rows')}</div>
                  <div className="text-sm text-text-primary">{res.meta.rows}</div>
                </div>
                <div>
                  <div className="text-xs text-text-muted">{t('tools.modtran.outputs.source')}</div>
                  <div className="text-sm text-text-primary">{res.meta.spectrum_source}</div>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                {Object.entries(res.downloads).map(([k, url]) => (
                  <Button key={k} variant="secondary" onClick={() => window.open(url, '_blank')}>
                    {k}
                  </Button>
                ))}
              </div>
            </div>
          </Card>

          <Card className="glass-light">
            <CardHeader>
              <CardTitle>透过率-波长曲线</CardTitle>
              <CardDesc>来自后端导出的 wavelength.csv（Plotly 绘制）</CardDesc>
            </CardHeader>
            <div className="h-[520px]">
              {plotError ? (
                <div className="rounded-xl border border-danger-soft bg-danger-soft p-3 text-sm text-text-secondary">
                  plot_load_failed: {plotError}
                </div>
              ) : wlX && wlY ? (
                <Plot
                  data={[
                    {
                      type: 'scatter',
                      mode: 'lines',
                      x: wlX,
                      y: wlY,
                      line: { width: 2 },
                      name: 'Transmittance',
                    } as any,
                  ]}
                  layout={getPlotlyLayout({
                    autosize: true,
                    margin: { l: 60, r: 20, t: 10, b: 60 },
                    xaxis: { title: 'Wavelength (μm)', range: [0.2, 25], fixedrange: true },
                    yaxis: { title: 'Transmittance', range: [0, 1] },
                  })}
                  style={{ width: '100%', height: '100%' }}
                  useResizeHandler
                  config={{ displayModeBar: true, responsive: true }}
                />
              ) : (
                <div className="text-sm text-text-secondary">加载绘图数据中…</div>
              )}
            </div>
          </Card>
        </div>
      ) : null}
    </div>
  )
}
