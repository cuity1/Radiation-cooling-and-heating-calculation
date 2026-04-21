import { useMemo, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import Plot from 'react-plotly.js'
import { getPlotlyLayout } from '../../lib/plotlyConfig'
import * as XLSX from 'xlsx'

import Button from '../../components/ui/Button'
import { Card, CardDesc, CardHeader, CardTitle } from '../../components/ui/Card'
import HelpButton from '../../components/Help/HelpButton'
import { computeSolarEfficiency, type SolarEfficiencyResponse } from '../../services/tools'

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

function toCsvHeatmap(x: number[], y: number[], z: number[][]) {
  const header = ['T_a\\S_solar', ...x.map((v) => v.toFixed(6))].join(',')
  const rows = y.map((yv, i) => {
    const vals = (z[i] ?? []).map((v) => (Number.isFinite(v) ? String(v) : ''))
    return [yv.toFixed(6), ...vals].join(',')
  })
  return [header, ...rows].join('\n')
}

function exportSolarEfficiencyExcel(res: SolarEfficiencyResponse) {
  const ws = XLSX.utils.aoa_to_sheet([
    ['T_a\\S_solar', ...res.s_solar_range],
    ...res.t_a_range.map((ta, i) => [ta, ...(res.p_heat[i] ?? [])]),
  ])

  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, 'Heating_vs_Solar')
  XLSX.writeFile(wb, 'solar-efficiency.xlsx')
}

export default function SolarEfficiencyPage() {
  const { t } = useTranslation()

  const [angleSteps, setAngleSteps] = useState('2000')
  const [taPoints, setTaPoints] = useState('100')
  const [sSolarPoints, setSSolarPoints] = useState('100')

  const m = useMutation({
    mutationFn: computeSolarEfficiency,
  })

  const parsed = useMemo(() => {
    const angle = Number(angleSteps)
    const okAngle = Number.isFinite(angle) && angle >= 100 && angle <= 20000

    const ta = clampInt(Number(taPoints), 2, 200)
    const ss = clampInt(Number(sSolarPoints), 2, 200)

    const ok = okAngle

    return {
      req: {
        angle_steps: okAngle ? Math.floor(angle) : 2000,
        t_a_points: ta,
        s_solar_points: ss,
      },
      ok,
    }
  }, [angleSteps, taPoints, sSolarPoints])

  const res = m.data

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div>
              <CardTitle>{t('tools.solarEfficiency.title')}</CardTitle>
              <CardDesc>{t('tools.solarEfficiency.desc')}</CardDesc>
            </div>
            <HelpButton doc="solar_efficiency" />
          </div>
        </CardHeader>

        <div className="grid gap-4 md:grid-cols-2">
          <Field label={t('tools.solarEfficiency.fields.angleSteps')} hint={t('tools.solarEfficiency.fields.angleStepsHint')}>
            <Input value={angleSteps} onChange={(e) => setAngleSteps(e.target.value)} />
          </Field>

          <Field label={t('tools.solarEfficiency.fields.taPoints')} hint={t('tools.solarEfficiency.fields.samplingHint')}>
            <Input value={taPoints} onChange={(e) => setTaPoints(e.target.value)} />
          </Field>

          <Field label={t('tools.solarEfficiency.fields.sSolarPoints')} hint={t('tools.solarEfficiency.fields.samplingHint')}>
            <Input value={sSolarPoints} onChange={(e) => setSSolarPoints(e.target.value)} />
          </Field>

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
              {t('tools.solarEfficiency.error')}
            </div>
          ) : null}

          {res ? (
            <div className="md:col-span-2 glass-light rounded-field border border-border p-3 text-sm text-text-secondary">
              <div className="grid gap-2 md:grid-cols-3">
                <div>
                  <div className="text-xs text-text-muted">{t('tools.solarEfficiency.meta.grid')}</div>
                  <div className="text-sm text-text-primary">
                    T_a: {res.t_a_range.length} × S_solar: {res.s_solar_range.length}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-text-muted">{t('tools.solarEfficiency.meta.angleSteps')}</div>
                  <div className="text-sm text-text-primary">{res.meta.angle_steps}</div>
                </div>
                <div className="flex items-end justify-end gap-2">
                  <Button
                    variant="secondary"
                    onClick={() =>
                      downloadText(
                        'solar-efficiency.csv',
                        toCsvHeatmap(res.s_solar_range, res.t_a_range, res.p_heat),
                        'text/csv;charset=utf-8',
                      )
                    }
                  >
                    {t('common.exportCsv')}
                  </Button>
                  <Button variant="secondary" onClick={() => exportSolarEfficiencyExcel(res)}>Excel</Button>
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
              <CardTitle>{t('tools.solarEfficiency.plot.title')}</CardTitle>
              <CardDesc>{t('tools.solarEfficiency.plot.desc')}</CardDesc>
            </CardHeader>
            <div className="h-[520px]">
              <Plot
                data={[
                  {
                    type: 'heatmap',
                    x: res.s_solar_range,
                    y: res.t_a_range,
                    z: res.p_heat,
                    colorscale: 'Viridis',
                  } as any,
                ]}
                layout={getPlotlyLayout({
                  autosize: true,
                  margin: { l: 60, r: 20, t: 10, b: 50 },
                  xaxis: { title: t('tools.solarEfficiency.plot.xaxis') },
                  yaxis: { title: t('tools.solarEfficiency.plot.yaxis') },
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
