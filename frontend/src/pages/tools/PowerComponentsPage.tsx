import { useMemo, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import Plot from 'react-plotly.js'
import { getPlotlyLayout } from '../../lib/plotlyConfig'
import * as XLSX from 'xlsx'

import Button from '../../components/ui/Button'
import { Card, CardDesc, CardHeader, CardTitle } from '../../components/ui/Card'
import HelpButton from '../../components/Help/HelpButton'
import { computePowerComponents, type PowerComponentsResponse } from '../../services/tools'

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

function exportPowerComponentsExcel(res: PowerComponentsResponse) {
  const keys = Object.keys(res.components)
  const ws = XLSX.utils.aoa_to_sheet([
    ['T_film', ...keys],
    ...res.t_film.map((t, i) => [t, ...keys.map((k) => res.components[k]?.[i] ?? null)]),
  ])

  const wsMeta = XLSX.utils.json_to_sheet([
    { Parameter: 'angle_steps', Value: res.meta.angle_steps },
    { Parameter: 'h_cond_wm2k', Value: res.meta.h_cond_wm2k },
    { Parameter: 'enable_natural_convection', Value: res.meta.enable_natural_convection },
    { Parameter: 'phase_temp_c', Value: res.meta.phase_temp_c },
    { Parameter: 'phase_power_wm2', Value: res.meta.phase_power_wm2 },
    { Parameter: 'phase_half_width_c', Value: res.meta.phase_half_width_c },
    { Parameter: 'T_a1', Value: res.t_a1 },
  ])

  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, 'Power_Components')
  XLSX.utils.book_append_sheet(wb, wsMeta, 'Parameters')
  XLSX.writeFile(wb, 'power-components.xlsx')
}

function toCsv(res: PowerComponentsResponse) {
  const keys = Object.keys(res.components)
  const header = ['T_film', ...keys].join(',')
  const rows = res.t_film.map((t, i) => [t, ...keys.map((k) => res.components[k]?.[i] ?? '')].join(','))
  return [header, ...rows].join('\n')
}

export default function PowerComponentsPage() {
  const { t } = useTranslation()

  const [angleSteps, setAngleSteps] = useState('2000')
  const [hCond, setHCond] = useState('5.0')
  const [enableNatConv, setEnableNatConv] = useState(false)

  const [phaseTemp, setPhaseTemp] = useState('')
  const [phasePower, setPhasePower] = useState('0')
  const [phaseWidth, setPhaseWidth] = useState('0')

  const m = useMutation({
    mutationFn: computePowerComponents,
  })

  const parsed = useMemo(() => {
    const angle_steps = Math.floor(Number(angleSteps))
    const h_cond_wm2k = Number(hCond)
    const phase_temp_c = phaseTemp.trim() === '' ? null : Number(phaseTemp)
    const phase_power_wm2 = Number(phasePower)
    const phase_half_width_c = Number(phaseWidth)

    const ok =
      Number.isFinite(angle_steps) &&
      angle_steps >= 100 &&
      angle_steps <= 20000 &&
      Number.isFinite(h_cond_wm2k) &&
      h_cond_wm2k > 0 &&
      Number.isFinite(phase_temp_c ?? 0) &&
      Number.isFinite(phase_power_wm2) &&
      Number.isFinite(phase_half_width_c)

    return {
      ok,
      req: {
        angle_steps,
        h_cond_wm2k,
        enable_natural_convection: enableNatConv,
        phase_temp_c,
        phase_power_wm2,
        phase_half_width_c,
      },
    }
  }, [angleSteps, hCond, enableNatConv, phaseTemp, phasePower, phaseWidth])

  const res = m.data
  const comps = res?.components

  const series = useMemo(() => {
    if (!res) return []
    const order = ['p_r', 'p_a', 'Q_solar', 'P_phase', 'Q_nat', 'Q_cond', 'Q_conv', 'p_net']
    const keys = [...order.filter((k) => k in res.components), ...Object.keys(res.components).filter((k) => !order.includes(k))]

    return keys.map((k) => ({
      name: k,
      y: res.components[k] ?? [],
    }))
  }, [res])

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div>
              <CardTitle>{t('tools.powerComponents.title')}</CardTitle>
              <CardDesc>{t('tools.powerComponents.desc')}</CardDesc>
            </div>
            <HelpButton doc="power_components" />
          </div>
        </CardHeader>

        <div className="grid gap-4 md:grid-cols-2">
          <Field label="angle_steps" hint="100–20000">
            <Input value={angleSteps} onChange={(e) => setAngleSteps(e.target.value)} />
          </Field>

          <Field label="h_cond_wm2k" hint="Equivalent conduction coefficient (W/m²·K)">
            <Input value={hCond} onChange={(e) => setHCond(e.target.value)} />
          </Field>

          <Field label="Natural convection">
            <label className="flex items-center gap-2 rounded-field border border-border bg-bg-subtle px-3 py-2 text-sm text-text-secondary">
              <input type="checkbox" checked={enableNatConv} onChange={(e) => setEnableNatConv(e.target.checked)} />
              <span>{enableNatConv ? t('common.enabled') : t('common.disabled')}</span>
            </label>
          </Field>

          <div className="md:col-span-2">
            <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-text-muted">Phase-change (optional)</div>
          </div>

          <Field label="phase_temp_c (°C)" hint="Empty to disable">
            <Input value={phaseTemp} onChange={(e) => setPhaseTemp(e.target.value)} placeholder="e.g. 25" />
          </Field>
          <Field label="phase_power_wm2 (W/m²)">
            <Input value={phasePower} onChange={(e) => setPhasePower(e.target.value)} />
          </Field>
          <Field label="phase_half_width_c (°C)">
            <Input value={phaseWidth} onChange={(e) => setPhaseWidth(e.target.value)} />
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
              Power components failed.
            </div>
          ) : null}

          {res ? (
            <div className="md:col-span-2 flex flex-wrap items-center justify-end gap-2">
              <Button variant="secondary" onClick={() => downloadText('power-components.csv', toCsv(res), 'text/csv;charset=utf-8')}>
                {t('common.exportCsv')}
              </Button>
              <Button variant="secondary" onClick={() => exportPowerComponentsExcel(res)}>Excel</Button>
            </div>
          ) : null}

          {res ? (
            <div className="md:col-span-2 glass-light rounded-field border border-border p-3 text-sm text-text-secondary">
              <div className="grid gap-2 md:grid-cols-3">
                <div>
                  <div className="text-xs text-text-muted">T_a1 (°C)</div>
                  <div className="text-sm text-text-primary">{res.t_a1.toFixed(2)}</div>
                </div>
                <div>
                  <div className="text-xs text-text-muted">Series</div>
                  <div className="text-sm text-text-primary">{Object.keys(comps ?? {}).length}</div>
                </div>
                <div>
                  <div className="text-xs text-text-muted">Points</div>
                  <div className="text-sm text-text-primary">{res.t_film.length}</div>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      </Card>

      {res ? (
        <Card className="glass-light">
          <CardHeader>
            <CardTitle>Power components vs film temperature</CardTitle>
            <CardDesc>Desktop-aligned decomposition (sign convention matches original)</CardDesc>
          </CardHeader>
          <div className="h-[560px]">
            <Plot
              data={series.map((s) => ({
                type: 'scatter',
                mode: 'lines',
                name: s.name,
                x: res.t_film,
                y: s.y,
              })) as any}
              layout={getPlotlyLayout({
                autosize: true,
                margin: { l: 70, r: 20, t: 10, b: 60 },
                xaxis: { title: 'T_film (°C)' },
                yaxis: { title: 'Power (W/m²)' },
                legend: { orientation: 'h' },
              })}
              style={{ width: '100%', height: '100%' }}
              useResizeHandler
              config={{ displayModeBar: true, responsive: true }}
            />
          </div>
        </Card>
      ) : null}
    </div>
  )
}
