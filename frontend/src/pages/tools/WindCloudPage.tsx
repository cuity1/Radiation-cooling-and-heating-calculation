import { useMemo, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import Plot from 'react-plotly.js'
import { getPlotlyLayout } from '../../lib/plotlyConfig'
import * as XLSX from 'xlsx'

import Button from '../../components/ui/Button'
import { Card, CardDesc, CardHeader, CardTitle } from '../../components/ui/Card'
import HelpButton from '../../components/Help/HelpButton'
import { computeWindCloud, type WindCloudResponse } from '../../services/tools'

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
        'hover:border-border-light hover:bg-bg-elevated'      }
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
  // rows: emissivity (Y), columns: wind (X)
  const header = ['emissivity\\wind', ...axisX.map((v) => v.toFixed(6))].join(',')
  const rows = axisY.map((y, i) => {
    const vals = (matrix[i] ?? []).map((v) => (Number.isFinite(v) ? String(v) : ''))
    return [y.toFixed(6), ...vals].join(',')
  })
  return [header, ...rows].join('\n')
}

function exportWindCloudExcel(res: WindCloudResponse) {
  const wsDelta = XLSX.utils.aoa_to_sheet([
    ['emissivity\\wind', ...res.wind],
    ...res.emissivity.map((e, i) => [e, ...(res.delta_t[i] ?? [])]),
  ])
  const wsHc = XLSX.utils.aoa_to_sheet([
    ['emissivity\\wind', ...res.wind],
    ...res.emissivity.map((e, i) => [e, ...(res.h_conv[i] ?? [])]),
  ])

  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, wsDelta, 'Temperature_Difference')
  XLSX.utils.book_append_sheet(wb, wsHc, 'Convection_Coefficient')

  XLSX.writeFile(wb, 'wind-cloud.xlsx')
}

export default function WindCloudPage() {
  const { t } = useTranslation()

  const [windMin, setWindMin] = useState('0')
  const [windMax, setWindMax] = useState('5')
  const [windPoints, setWindPoints] = useState('100')

  const [emisMin, setEmisMin] = useState('0')
  const [emisMax, setEmisMax] = useState('1')
  const [emisPoints, setEmisPoints] = useState('100')

  const [sSolar, setSSolar] = useState('')

  const m = useMutation({
    mutationFn: computeWindCloud,
  })

  const parsed = useMemo(() => {
    const req = {
      wind_min: Number(windMin),
      wind_max: Number(windMax),
      wind_points: clampInt(Number(windPoints), 2, 200),
      emissivity_min: Number(emisMin),
      emissivity_max: Number(emisMax),
      emissivity_points: clampInt(Number(emisPoints), 2, 200),
      s_solar: sSolar.trim() === '' ? null : Number(sSolar),
    }

    const ok =
      Number.isFinite(req.wind_min) &&
      Number.isFinite(req.wind_max) &&
      req.wind_max > req.wind_min &&
      Number.isFinite(req.emissivity_min) &&
      Number.isFinite(req.emissivity_max) &&
      req.emissivity_max > req.emissivity_min &&
      Number.isFinite(req.s_solar ?? 0)

    return { req, ok }
  }, [windMin, windMax, windPoints, emisMin, emisMax, emisPoints, sSolar])

  const res = m.data

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div>
              <CardTitle>{t('tools.windCloud.title')}</CardTitle>
              <CardDesc>{t('tools.windCloud.desc')}</CardDesc>
            </div>
            <HelpButton doc="wind_cloud" />
          </div>
        </CardHeader>

        <div className="grid gap-4 md:grid-cols-2">
          <Field label={t('tools.windCloud.fields.windMin')}>
            <Input value={windMin} onChange={(e) => setWindMin(e.target.value)} />
          </Field>
          <Field label={t('tools.windCloud.fields.windMax')}>
            <Input value={windMax} onChange={(e) => setWindMax(e.target.value)} />
          </Field>
          <Field label={t('tools.windCloud.fields.windPoints')} hint={t('tools.windCloud.fields.windPointsHint')}>
            <Input value={windPoints} onChange={(e) => setWindPoints(e.target.value)} />
          </Field>

          <Field label={t('tools.windCloud.fields.emisMin')}>
            <Input value={emisMin} onChange={(e) => setEmisMin(e.target.value)} />
          </Field>
          <Field label={t('tools.windCloud.fields.emisMax')}>
            <Input value={emisMax} onChange={(e) => setEmisMax(e.target.value)} />
          </Field>
          <Field label={t('tools.windCloud.fields.emisPoints')} hint={t('tools.windCloud.fields.emisPointsHint')}>
            <Input value={emisPoints} onChange={(e) => setEmisPoints(e.target.value)} />
          </Field>

          <div className="md:col-span-2">
            <Field label={t('tools.windCloud.fields.sSolar')} hint={t('tools.windCloud.fields.sSolarHint')}>
              <Input value={sSolar} onChange={(e) => setSSolar(e.target.value)} />
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
              {t('tools.windCloud.error')}
            </div>
          ) : null}

          {res ? (
            <div className="md:col-span-2 glass-light rounded-field border border-border p-3 text-sm text-text-secondary">
              <div className="grid gap-2 md:grid-cols-4">
                <div>
                  <div className="text-xs text-text-muted">{t('tools.windCloud.meta.sSolar')}</div>
                  <div className="text-sm text-text-primary">{res.meta.s_solar.toFixed(3)}</div>
                </div>
                <div>
                  <div className="text-xs text-text-muted">{t('tools.windCloud.meta.avgEmissivity')}</div>
                  <div className="text-sm text-text-primary">{res.meta.avg_emissivity.toFixed(6)}</div>
                </div>
                <div>
                  <div className="text-xs text-text-muted">{t('tools.windCloud.meta.rSol')}</div>
                  <div className="text-sm text-text-primary">{res.meta.r_sol.toFixed(6)}</div>
                </div>
                <div>
                  <div className="text-xs text-text-muted">{t('tools.windCloud.meta.alphaS')}</div>
                  <div className="text-sm text-text-primary">{res.meta.alpha_s.toFixed(6)}</div>
                </div>
              </div>
            </div>
          ) : null}

          {res ? (
            <div className="md:col-span-2 flex flex-wrap items-center justify-end gap-2">
              <Button
                variant="secondary"
                onClick={() =>
                  downloadText(
                    'wind-cloud-deltaT.csv',
                    toCsvMatrix(res.wind, res.emissivity, res.delta_t),
                    'text/csv;charset=utf-8',
                  )
                }
              >
                {t('tools.windCloud.exportCsvDeltaT')}
              </Button>
              <Button
                variant="secondary"
                onClick={() =>
                  downloadText(
                    'wind-cloud-hconv.csv',
                    toCsvMatrix(res.wind, res.emissivity, res.h_conv),
                    'text/csv;charset=utf-8',
                  )
                }
              >
                {t('tools.windCloud.exportCsvHconv')}
              </Button>
              <Button variant="secondary" onClick={() => exportWindCloudExcel(res)}>Excel</Button>
            </div>
          ) : null}
        </div>
      </Card>

      {res ? (
        <div className="space-y-4">
          <Card className="glass-light">
            <CardHeader>
              <CardTitle>{t('tools.windCloud.plots.deltaT_title')}</CardTitle>
              <CardDesc>{t('tools.windCloud.plots.deltaT_desc')}</CardDesc>
            </CardHeader>
            <div className="h-[420px]">
              <Plot
                data={[
                  {
                    type: 'heatmap',
                    x: res.wind,
                    y: res.emissivity,
                    z: res.delta_t,
                    colorscale: 'RdBu',
                    reversescale: true,
                  } as any,
                ]}
                layout={getPlotlyLayout({
                  autosize: true,
                  margin: { l: 60, r: 20, t: 10, b: 50 },
                  xaxis: { title: 'Wind (m/s)' },
                  yaxis: { title: 'Atmospheric emissivity' },
                })}
                style={{ width: '100%', height: '100%' }}
                useResizeHandler
                config={{ displayModeBar: true, responsive: true }}
              />
            </div>
          </Card>

          <Card className="glass-light">
            <CardHeader>
              <CardTitle>{t('tools.windCloud.plots.hConv_title')}</CardTitle>
              <CardDesc>{t('tools.windCloud.plots.hConv_desc')}</CardDesc>
            </CardHeader>
            <div className="h-[420px]">
              <Plot
                data={[
                  {
                    type: 'heatmap',
                    x: res.wind,
                    y: res.emissivity,
                    z: res.h_conv,
                    colorscale: 'Viridis',
                  } as any,
                ]}
                layout={getPlotlyLayout({
                  autosize: true,
                  margin: { l: 60, r: 20, t: 10, b: 50 },
                  xaxis: { title: 'Wind (m/s)' },
                  yaxis: { title: 'Atmospheric emissivity' },
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
