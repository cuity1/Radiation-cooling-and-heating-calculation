import { useMemo, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import Plot from 'react-plotly.js'
import { getPlotlyLayout } from '../../lib/plotlyConfig'
import * as XLSX from 'xlsx'

import Button from '../../components/ui/Button'
import { Card, CardDesc, CardHeader, CardTitle } from '../../components/ui/Card'
import HelpButton from '../../components/Help/HelpButton'
import {
  computeEmissivitySolarCloud,
  type EmissivitySolarCloudResponse,
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

function clampInt(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, Math.floor(value)))
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

function toCsvMatrix(axisX: number[], axisY: number[], matrix: number[][]) {
  const header = ['S_solar\\emissivity', ...axisX.map((v) => v.toFixed(6))].join(',')
  const rows = axisY.map((y, i) => {
    const vals = (matrix[i] ?? []).map((v) => (Number.isFinite(v) ? String(v) : ''))
    return [y.toFixed(6), ...vals].join(',')
  })
  return [header, ...rows].join('\n')
}

function exportEmissivitySolarExcel(res: EmissivitySolarCloudResponse) {
  const wsMatrix = XLSX.utils.aoa_to_sheet([
    ['Solar_Irradiance_W/m2', ...res.atm_emissivity],
    ...res.solar_irradiance.map((s, i) => [s, ...(res.cooling_power[i] ?? [])]),
  ])

  const wsParams = XLSX.utils.json_to_sheet([
    { Parameter: 'Material Emissivity', Value: res.meta.avg_emissivity },
    { Parameter: 'Solar Absorptance', Value: res.meta.alpha_s },
    { Parameter: 'Ambient Temperature (°C)', Value: res.meta.t_a1 },
    { Parameter: 'Film Temperature (°C)', Value: res.meta.t_a1 },
    { Parameter: 'Delta T (°C)', Value: res.meta.delta_t },
    { Parameter: 'Grid: emissivity points', Value: res.meta.n_emissivity },
    { Parameter: 'Grid: solar points', Value: res.meta.n_solar },
    { Parameter: 'Solar max (W/m²)', Value: res.meta.solar_max },
  ])

  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, wsMatrix, 'Cooling_Power')
  XLSX.utils.book_append_sheet(wb, wsParams, 'Parameters')

  XLSX.writeFile(wb, 'emissivity-solar-cloud.xlsx')
}

export default function EmissivitySolarCloudPage() {
  const { t } = useTranslation()

  const [nEmissivity, setNEmissivity] = useState('100')
  const [nSolar, setNSolar] = useState('100')
  const [solarMax, setSolarMax] = useState('1000')

  const m = useMutation({
    mutationFn: computeEmissivitySolarCloud,
  })

  const parsed = useMemo(() => {
    const ne = clampInt(Number(nEmissivity), 2, 200)
    const ns = clampInt(Number(nSolar), 2, 200)
    const sm = Number(solarMax)

    const ok = Number.isFinite(sm) && sm > 0

    return {
      req: {
        n_emissivity: ne,
        n_solar: ns,
        solar_max: sm,
      },
      ok,
    }
  }, [nEmissivity, nSolar, solarMax])

  const res = m.data

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div>
              <CardTitle>{t('tools.emissivitySolarCloud.title')}</CardTitle>
              <CardDesc>{t('tools.emissivitySolarCloud.desc')}</CardDesc>
            </div>
            <HelpButton doc="emissivity_solar_cloud" />
          </div>
        </CardHeader>

        <div className="grid gap-4 md:grid-cols-2">
          <Field label={t('tools.emissivitySolarCloud.fields.nEmissivity')} hint={t('tools.emissivitySolarCloud.fields.samplingHint')}>
            <Input value={nEmissivity} onChange={(e) => setNEmissivity(e.target.value)} />
          </Field>
          <Field label={t('tools.emissivitySolarCloud.fields.nSolar')} hint={t('tools.emissivitySolarCloud.fields.samplingHint')}>
            <Input value={nSolar} onChange={(e) => setNSolar(e.target.value)} />
          </Field>
          <div className="md:col-span-2">
            <Field label={t('tools.emissivitySolarCloud.fields.solarMax')} hint={t('tools.emissivitySolarCloud.fields.solarMaxHint')}>
              <Input value={solarMax} onChange={(e) => setSolarMax(e.target.value)} />
            </Field>
          </div>

          <div className="md:col-span-2 flex items-center justify-end gap-2">
            <Button variant="secondary" onClick={() => m.reset()} disabled={!m.isSuccess && !m.isError}>
              {t('common.refresh')}
            </Button>
            <Button variant="secondary" disabled={!parsed.ok || m.isPending} onClick={() => m.mutate(parsed.req)}>
              {m.isPending ? t('common.loading') : t('common.create')}
            </Button>
          </div>

          {m.isError ? (
            <div className="md:col-span-2 rounded-xl border border-danger-soft bg-danger-soft p-3 text-sm text-text-secondary">
              {t('tools.emissivitySolarCloud.error')}
            </div>
          ) : null}

          {res ? (
            <div className="md:col-span-2 glass-light rounded-field border border-border p-3 text-sm text-text-secondary">
              <div className="grid gap-2 md:grid-cols-4">
                <div>
                  <div className="text-xs text-text-muted">avg_emissivity</div>
                  <div className="text-sm text-text-primary">{res.meta.avg_emissivity.toFixed(6)}</div>
                </div>
                <div>
                  <div className="text-xs text-text-muted">alpha_s</div>
                  <div className="text-sm text-text-primary">{res.meta.alpha_s.toFixed(6)}</div>
                </div>
                <div>
                  <div className="text-xs text-text-muted">T_a1 (°C)</div>
                  <div className="text-sm text-text-primary">{res.meta.t_a1.toFixed(2)}</div>
                </div>
                <div className="flex items-end justify-end gap-2">
                  <Button
                    variant="secondary"
                    onClick={() =>
                      downloadText(
                        'emissivity-solar-cloud.csv',
                        toCsvMatrix(res.atm_emissivity, res.solar_irradiance, res.cooling_power),
                        'text/csv;charset=utf-8',
                      )
                    }
                  >
                    {t('common.exportCsv')}
                  </Button>
                  <Button variant="secondary" onClick={() => exportEmissivitySolarExcel(res)}>Excel</Button>
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
              <CardTitle>{t('tools.emissivitySolarCloud.plot.title')}</CardTitle>
              <CardDesc>{t('tools.emissivitySolarCloud.plot.desc')}</CardDesc>
            </CardHeader>
            <div className="h-[520px]">
              <Plot
                data={[
                  {
                    type: 'heatmap',
                    x: res.atm_emissivity,
                    y: res.solar_irradiance,
                    z: res.cooling_power,
                    colorscale: 'RdBu',
                    reversescale: true,
                  } as any,
                ]}
                layout={getPlotlyLayout({
                  autosize: true,
                  margin: { l: 70, r: 20, t: 10, b: 60 },
                  xaxis: { title: t('tools.emissivitySolarCloud.plot.xaxis') },
                  yaxis: { title: t('tools.emissivitySolarCloud.plot.yaxis') },
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
