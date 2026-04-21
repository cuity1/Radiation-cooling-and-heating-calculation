import { useMemo, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import Plot from 'react-plotly.js'
import * as XLSX from 'xlsx'

import Button from '../../components/ui/Button'
import { Card, CardDesc, CardHeader, CardTitle } from '../../components/ui/Card'
import HelpButton from '../../components/Help/HelpButton'
import { getPlotlyLayout } from '../../lib/plotlyConfig'
import {
  computeMaterialEnvTempCloud,
  type MaterialEnvTempCloudResponse,
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
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 focus-visible:border-accent/50 ' +
        'hover:border-border-light hover:bg-bg-elevated'
      }
    />
  )
}

function downloadText(filename: string, content: string, mime = 'text/plain;charset=utf-8') {
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

function toCsvHeatmap(x: number[], y: number[], z: number[][], xLabel: string, yLabel: string) {
  const header = [xLabel + '\\' + yLabel, ...y.map((v) => v.toFixed(6))].join(',')
  const rows = x.map((xv, i) => {
    const row = z[i] ?? []
    const vals = row.map((v) => (Number.isFinite(v) ? String(v) : ''))
    return [xv.toFixed(6), ...vals].join(',')
  })
  return [header, ...rows].join('\n')
}

function exportMaterialEnvTempExcel(res: MaterialEnvTempCloudResponse) {
  const wsMatrix = XLSX.utils.aoa_to_sheet([
    ['T_film (°C) \\ T_env (°C)', ...res.t_env_c],
    ...res.t_film_c.map((tFilm, i) => [tFilm, ...(res.cooling_power[i] ?? [])]),
  ])

  const wsParams = XLSX.utils.json_to_sheet([
    { Parameter: 'h_c (W/m²·K)', Value: res.meta.h_c_wm2k },
    { Parameter: 'ΔT_env step (°C)', Value: res.meta.temp_step_c },
    { Parameter: 'avg_emissivity', Value: res.meta.avg_emissivity },
    { Parameter: 'alpha_sol', Value: res.meta.alpha_sol },
    { Parameter: 'alpha_sol_visible', Value: res.meta.alpha_sol_visible },
    { Parameter: 'S_solar (W/m²)', Value: res.meta.S_solar },
    { Parameter: 'T_a1_ref (°C)', Value: res.meta.T_a1_ref_c },
    { Parameter: 'T_env points', Value: res.t_env_c.length },
    { Parameter: 'T_film points', Value: res.t_film_c.length },
  ])

  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, wsMatrix, 'Cooling_Power')
  XLSX.utils.book_append_sheet(wb, wsParams, 'Parameters')

  XLSX.writeFile(wb, 'material-env-temp-cloud.xlsx')
}

export default function MaterialEnvTempCloudPage() {
  const { t } = useTranslation()
  const nav = useNavigate()

  const [tEnvMin, setTEnvMin] = useState('-20')
  const [tEnvMax, setTEnvMax] = useState('60')
  const [hC, setHC] = useState('5')
  const [enableNatConv, setEnableNatConv] = useState(false)
  const [enableLatentHeat, setEnableLatentHeat] = useState(false)
  const [relativeHumidity, setRelativeHumidity] = useState('')
  const [wetFraction, setWetFraction] = useState('1')
  const [enablePhase, setEnablePhase] = useState(false)
  const [phaseTemp, setPhaseTemp] = useState('')
  const [phasePower, setPhasePower] = useState('')
  const [phaseHalfWidth, setPhaseHalfWidth] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [remark, setRemark] = useState('')

  const m = useMutation({
    mutationFn: computeMaterialEnvTempCloud,
  })

  const parsed = useMemo(() => {
    const tMin = Number(tEnvMin)
    const tMax = Number(tEnvMax)
    const h = Number(hC)
    const rh = relativeHumidity.trim() === '' ? null : Number(relativeHumidity)
    const wf = wetFraction.trim() === '' ? 1 : Number(wetFraction)
    const phaseTempNum = phaseTemp.trim() === '' ? null : Number(phaseTemp)
    const phasePowerNum = phasePower.trim() === '' ? 0 : Number(phasePower)
    const phaseHalfWidthNum = phaseHalfWidth.trim() === '' ? 0 : Number(phaseHalfWidth)

    const ok =
      Number.isFinite(tMin) &&
      Number.isFinite(tMax) &&
      tMax > tMin &&
      Number.isFinite(h) &&
      h > 0 &&
      h <= 5000 &&
      (rh === null || (Number.isFinite(rh) && rh >= 0 && rh <= 1000)) &&
      Number.isFinite(wf) &&
      wf >= 0 &&
      wf <= 1 &&
      (!enablePhase ||
        ((phaseTempNum === null || Number.isFinite(phaseTempNum)) &&
          Number.isFinite(phasePowerNum) &&
          Number.isFinite(phaseHalfWidthNum) &&
          phasePowerNum >= 0 &&
          phaseHalfWidthNum >= 0))

    const reqPhaseTemp = enablePhase ? phaseTempNum : null
    const reqPhasePower = enablePhase ? phasePowerNum : 0
    const reqPhaseHalfWidth = enablePhase ? phaseHalfWidthNum : 0

    return {
      req: {
        t_env_min_c: tMin,
        t_env_max_c: tMax,
        h_c_wm2k: h,
        enable_natural_convection: enableNatConv,
        enable_latent_heat: enableLatentHeat,
        relative_humidity: rh,
        wet_fraction: wf,
        phase_temp_c: reqPhaseTemp,
        phase_power_wm2: reqPhasePower,
        phase_half_width_c: reqPhaseHalfWidth,
      },
      ok,
    }
  }, [
    tEnvMin,
    tEnvMax,
    hC,
    enableNatConv,
    enableLatentHeat,
    relativeHumidity,
    wetFraction,
    enablePhase,
    phaseTemp,
    phasePower,
    phaseHalfWidth,
  ])

  const res = m.data

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div>
              <CardTitle>{t('tools.materialEnvTempCloud.title')}</CardTitle>
              <CardDesc>{t('tools.materialEnvTempCloud.desc')}</CardDesc>
            </div>
            <HelpButton doc="cooling" />
          </div>
        </CardHeader>

        <div className="grid gap-4 md:grid-cols-2">
          <Field label={t('tools.materialEnvTempCloud.fields.tEnvMin')}>
            <Input
              type="number"
              value={tEnvMin}
              onChange={(e) => setTEnvMin(e.target.value)}
            />
          </Field>
          <Field label={t('tools.materialEnvTempCloud.fields.tEnvMax')}>
            <Input
              type="number"
              value={tEnvMax}
              onChange={(e) => setTEnvMax(e.target.value)}
            />
          </Field>
          <div className="md:col-span-2">
            <Field
              label={t('tools.materialEnvTempCloud.fields.hC')}
              hint={t('tools.materialEnvTempCloud.fields.hCHint')}
            >
              <Input
                type="number"
                value={hC}
                onChange={(e) => setHC(e.target.value)}
              />
            </Field>
          </div>

          <div className="md:col-span-2">
            <label className="inline-flex items-center gap-2 text-xs cursor-pointer select-none text-text-secondary">
              <input
                type="checkbox"
                checked={enableNatConv}
                onChange={(e) => setEnableNatConv(e.target.checked)}
                className="h-4 w-4 rounded border-border text-accent focus-visible:ring-2 focus-visible:ring-accent/50 focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
              />
              <span className="font-semibold text-text-secondary">
                {t('pages.newJob.natConvLabel')}
              </span>
              <span className="text-[11px] text-text-muted">{t('pages.newJob.natConvHint')}</span>
            </label>
          </div>

          <div className="md:col-span-2 space-y-2 rounded-xl border border-border/60 bg-bg-elevated/40 px-3 py-2.5">
            <label className="inline-flex items-center gap-2 text-xs cursor-pointer select-none text-text-secondary">
              <input
                type="checkbox"
                checked={enableLatentHeat}
                onChange={(e) => setEnableLatentHeat(e.target.checked)}
                className="h-4 w-4 rounded border-border text-accent focus-visible:ring-2 focus-visible:ring-accent/50 focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
              />
              <span className="font-semibold text-text-secondary">
                {t('pages.newJob.latentHeatTitle')}
              </span>
              <span className="text-[11px] text-text-muted">
                {t('pages.newJob.latentHeatDesc')}
              </span>
            </label>

            {enableLatentHeat && (
              <div className="grid gap-3 md:grid-cols-2 pl-5">
                <Field
                  label={t('pages.newJob.relativeHumidity')}
                  hint={t('pages.newJob.relativeHumidityHint')}
                >
                  <Input
                    type="number"
                    value={relativeHumidity}
                    onChange={(e) => setRelativeHumidity(e.target.value)}
                    placeholder="例如 50（可留空）"
                  />
                </Field>
                <Field
                  label={t('pages.newJob.wetFraction')}
                  hint={t('pages.newJob.wetFractionHint')}
                >
                  <Input
                    type="number"
                    value={wetFraction}
                    onChange={(e) => setWetFraction(e.target.value)}
                    placeholder="0-1，例如 1"
                    step="0.01"
                  />
                </Field>
              </div>
            )}
          </div>

          <div className="md:col-span-2 space-y-2 rounded-xl border border-border/60 bg-bg-elevated/40 px-3 py-2.5">
            <label className="inline-flex items-center gap-2 text-xs cursor-pointer select-none text-text-secondary">
              <input
                type="checkbox"
                checked={enablePhase}
                onChange={(e) => setEnablePhase(e.target.checked)}
                className="h-4 w-4 rounded border-border text-accent focus-visible:ring-2 focus-visible:ring-accent/50 focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
              />
              <span className="font-semibold text-text-secondary">
                {t('pages.newJob.phaseTitle')}
              </span>
            </label>

            {enablePhase && (
              <div className="grid gap-3 md:grid-cols-3 pl-5">
                <Field label={t('pages.newJob.phaseTemp')} hint={t('pages.newJob.phaseTempHint')}>
                  <Input
                    type="number"
                    value={phaseTemp}
                    onChange={(e) => setPhaseTemp(e.target.value)}
                    placeholder="例如 25"
                  />
                </Field>
                <Field label={t('pages.newJob.phasePower')} hint={t('pages.newJob.phasePowerHint')}>
                  <Input
                    type="number"
                    value={phasePower}
                    onChange={(e) => setPhasePower(e.target.value)}
                    placeholder="例如 50"
                  />
                </Field>
                <Field label={t('pages.newJob.phaseWidth')} hint={t('pages.newJob.phaseWidthHint')}>
                  <Input
                    type="number"
                    value={phaseHalfWidth}
                    onChange={(e) => setPhaseHalfWidth(e.target.value)}
                    placeholder="例如 5"
                  />
                </Field>
              </div>
            )}
          </div>

          <div className="md:col-span-2 mb-4 rounded-xl border border-border glass-light px-3 py-3">
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

          <div className="md:col-span-2 flex items-center justify-end gap-2">
            <Button variant="secondary" onClick={() => m.reset()} disabled={!m.isSuccess && !m.isError}>
              {t('common.refresh')}
            </Button>
            <Button
              variant="secondary"
              disabled={!parsed.ok || m.isPending || submitting}
              onClick={() => {
                if (!parsed.ok || submitting) return
                setSubmitting(true)
                const params = parsed.req

                fetch('/api/jobs', {
                  method: 'POST',
                  headers: {
                    'Content-Type': 'application/json',
                  },
                  body: JSON.stringify({
                    type: 'material_env_temp_cloud',
                    remark: remark.trim() || undefined,
                    params,
                  }),
                })
                  .then(async (resp) => {
                    if (!resp.ok) throw new Error(await resp.text())
                    return resp.json() as Promise<{ job_id: string }>
                  })
                  .then((data) => {
                    nav(`/tools/material-env-temp-cloud/${data.job_id}`)
                  })
                  .catch(() => {
                    // 若异步任务创建失败，允许回退到同步调用，并重新允许点击
                    setSubmitting(false)
                    m.mutate(parsed.req)
                  })
              }}
            >
              {submitting || m.isPending ? t('common.loading') : '提交任务'}
            </Button>
          </div>

          {m.isError ? (
            <div className="md:col-span-2 rounded-xl border border-danger-soft bg-danger-soft p-3 text-sm text-text-secondary">
              {t('tools.materialEnvTempCloud.error')}
            </div>
          ) : null}

          {res ? (
            <div className="md:col-span-2 glass-light rounded-xl border border-border p-3 text-sm text-text-secondary">
              <div className="grid gap-2 md:grid-cols-4">
                <div>
                  <div className="text-xs text-text-muted">h_c (W/m²·K)</div>
                  <div className="text-sm text-text-primary">{res.meta.h_c_wm2k.toFixed(3)}</div>
                </div>
                <div>
                  <div className="text-xs text-text-muted">avg_emissivity</div>
                  <div className="text-sm text-text-primary">{res.meta.avg_emissivity.toFixed(4)}</div>
                </div>
                <div>
                  <div className="text-xs text-text-muted">alpha_sol</div>
                  <div className="text-sm text-text-primary">{res.meta.alpha_sol.toFixed(4)}</div>
                </div>
                <div className="flex items-end justify-end gap-2">
                  <Button
                    variant="secondary"
                    onClick={() =>
                      downloadText(
                        'material-env-temp-cloud.csv',
                        toCsvHeatmap(
                          res.t_film_c,
                          res.t_env_c,
                          res.cooling_power,
                          'T_film (°C)',
                          'T_env (°C)',
                        ),
                        'text/csv;charset=utf-8',
                      )
                    }
                  >
                    {t('common.exportCsv')}
                  </Button>
                  <Button variant="secondary" onClick={() => exportMaterialEnvTempExcel(res)}>Excel</Button>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      </Card>

      {res ? (
        <div className="grid gap-4 md:grid-cols-1">
          <Card className="glass-light">
            <CardHeader>
              <CardTitle>{t('tools.materialEnvTempCloud.plot.title')}</CardTitle>
              <CardDesc>{t('tools.materialEnvTempCloud.plot.desc')}</CardDesc>
            </CardHeader>
            <div className="h-[520px]">
              <Plot
                data={[
                  {
                    type: 'heatmap',
                    x: res.t_env_c,
                    y: res.t_film_c,
                    z: res.cooling_power,
                    colorscale: 'RdBu',
                    reversescale: true,
                    colorbar: { title: t('cooling.yAxis') },
                  } as any,
                ]}
                layout={getPlotlyLayout({
                  autosize: true,
                  margin: { l: 70, r: 20, t: 10, b: 60 },
                  xaxis: { title: t('tools.materialEnvTempCloud.plot.xaxis') },
                  yaxis: { title: t('tools.materialEnvTempCloud.plot.yaxis') },
                })}
                style={{ width: '100%', height: '100%' }}
                useResizeHandler
                config={{ displayModeBar: true, responsive: true }}
              />
            </div>
          </Card>
        </div>
      ) : null}
    </div>
  )
}

