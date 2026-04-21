import { useMemo, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import Plot from 'react-plotly.js'
import { getPlotlyLayout } from '../../lib/plotlyConfig'
import * as XLSX from 'xlsx'

import Button from '../../components/ui/Button'
import { Card, CardDesc, CardHeader, CardTitle } from '../../components/ui/Card'
import HelpButton from '../../components/Help/HelpButton'
import { computeAngularPower, type AngularPowerResponse } from '../../services/tools'

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

function exportAngularExcel(res: AngularPowerResponse) {
  const ws = XLSX.utils.aoa_to_sheet([
    ['theta_deg', 'power_density_per_sr'],
    ...res.theta_deg.map((th, i) => [th, res.power_density_per_sr[i] ?? null]),
  ])

  const wsMeta = XLSX.utils.json_to_sheet([
    { Parameter: 'temp_diff_c', Value: res.meta.temp_diff_c },
    { Parameter: 'angle_steps', Value: res.meta.angle_steps },
    { Parameter: 'T_a_K', Value: res.meta.T_a_K ?? '' },
    { Parameter: 'T_s_K', Value: res.meta.T_s_K ?? '' },
    { Parameter: 'wavelength_range_um', Value: res.meta.wavelength_range_um ? res.meta.wavelength_range_um.join(' - ') : '' },
    { Parameter: 'dlam_nm', Value: res.meta.dlam_nm ?? '' },
    { Parameter: 'power_density_total', Value: res.power_density_total ?? '' },
    { Parameter: 'hemispherical_solid_angle', Value: res.hemispherical_solid_angle ?? '' },
    { Parameter: 'half_power_angle_deg', Value: res.half_power_angle_deg ?? '' },
  ])

  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, 'Angular_Power')
  XLSX.utils.book_append_sheet(wb, wsMeta, 'Parameters')
  XLSX.writeFile(wb, 'angular-power.xlsx')
}

export default function AngularPowerPage() {
  const { t } = useTranslation()

  const [tempDiff, setTempDiff] = useState('0')
  const [angleSteps, setAngleSteps] = useState('91')

  const m = useMutation({ mutationFn: computeAngularPower })

  const parsed = useMemo(() => {
    const temp_diff_c = Number(tempDiff)
    const angle_steps = clampInt(Number(angleSteps), 2, 720)
    const ok = Number.isFinite(temp_diff_c) && temp_diff_c >= -300 && temp_diff_c <= 300 && Number.isFinite(angle_steps)

    return {
      ok,
      req: { temp_diff_c, angle_steps },
    }
  }, [tempDiff, angleSteps])

  const res = m.data

  const csv = useMemo(() => {
    if (!res) return ''
    const header = 'theta_deg,power_density_per_sr'
    const rows = res.theta_deg.map((th, i) => `${th},${res.power_density_per_sr[i] ?? ''}`)
    return [header, ...rows].join('\n')
  }, [res])

  const polar = useMemo(() => {
    if (!res) return { thetaRad: [], r: [] }
    return {
      thetaRad: res.theta_deg.map((d) => (d * Math.PI) / 180),
      r: res.power_density_per_sr,
    }
  }, [res])

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div>
              <CardTitle>{t('tools.angularPower.title')}</CardTitle>
              <CardDesc>{t('tools.angularPower.desc')}</CardDesc>
            </div>
            <HelpButton doc="angular_power" />
          </div>
        </CardHeader>

        <div className="grid gap-4 md:grid-cols-2">
          <Field label="temp_diff_c (°C)" hint="-300 to 300">
            <Input value={tempDiff} onChange={(e) => setTempDiff(e.target.value)} />
          </Field>
          <Field label="angle_steps" hint="2–720">
            <Input value={angleSteps} onChange={(e) => setAngleSteps(e.target.value)} />
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
              Angular power failed.
            </div>
          ) : null}

          {res ? (
            <div className="md:col-span-2 flex flex-wrap items-center justify-end gap-2">
              <Button variant="secondary" onClick={() => downloadText('angular-power.csv', csv, 'text/csv;charset=utf-8')}>
                {t('common.exportCsv')}
              </Button>
              <Button variant="secondary" onClick={() => exportAngularExcel(res)}>Excel</Button>
            </div>
          ) : null}
        </div>
      </Card>

      {res ? (
        <div className="space-y-4">
          <Card className="glass-light">
            <CardHeader>
              <CardTitle>Summary statistics</CardTitle>
            </CardHeader>
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              {res.power_density_total != null && (
                <div className="rounded-lg bg-bg-elevated p-3 text-center">
                  <div className="text-xs text-text-muted">Hemispherical power</div>
                  <div className="mt-1 font-mono text-lg font-semibold text-accent">
                    {res.power_density_total.toFixed(3)}&nbsp;W/m²
                  </div>
                </div>
              )}
              {res.hemispherical_solid_angle != null && (
                <div className="rounded-lg bg-bg-elevated p-3 text-center">
                  <div className="text-xs text-text-muted">Hemisphere solid angle</div>
                  <div className="mt-1 font-mono text-lg font-semibold text-accent">
                    {res.hemispherical_solid_angle.toFixed(4)}&nbsp;sr
                  </div>
                </div>
              )}
              {res.half_power_angle_deg != null && !isNaN(res.half_power_angle_deg) && (
                <div className="rounded-lg bg-bg-elevated p-3 text-center">
                  <div className="text-xs text-text-muted">Half-power angle</div>
                  <div className="mt-1 font-mono text-lg font-semibold text-accent">
                    {res.half_power_angle_deg.toFixed(2)}&nbsp;°
                  </div>
                </div>
              )}
              {res.meta.T_a_K && (
                <div className="rounded-lg bg-bg-elevated p-3 text-center">
                  <div className="text-xs text-text-muted">T<sub>a</sub> / T<sub>s</sub></div>
                  <div className="mt-1 font-mono text-lg font-semibold text-accent">
                    {res.meta.T_a_K.toFixed(1)}&nbsp;K&nbsp;/&nbsp;{res.meta.T_s_K?.toFixed(1)}&nbsp;K
                  </div>
                </div>
              )}
            </div>
            {res.meta.wavelength_range_um && (
              <div className="mt-3 text-xs text-text-muted">
                Wavelength range: {res.meta.wavelength_range_um[0]}–{res.meta.wavelength_range_um[1]} μm &nbsp;|&nbsp;
                Step: {res.meta.dlam_nm?.toFixed(3)} nm &nbsp;|&nbsp;
                {res.meta.angle_steps} angle samples
              </div>
            )}
          </Card>

          <Card className="glass-light">
            <CardHeader>
              <CardTitle>Angular profile (Cartesian)</CardTitle>
              <CardDesc>Power density per sr vs zenith angle</CardDesc>
            </CardHeader>
            <div className="h-[420px]">
              <Plot
                data={[
                  {
                    type: 'scatter',
                    mode: 'lines',
                    x: res.theta_deg,
                    y: res.power_density_per_sr,
                    name: 'power_density_per_sr',
                  } as any,
                  ...(res.half_power_angle_deg != null && !isNaN(res.half_power_angle_deg) ? [{
                    type: 'scatter',
                    mode: 'lines',
                    x: [res.half_power_angle_deg, res.half_power_angle_deg],
                    y: [0, Math.max(...res.power_density_per_sr) * 1.05],
                    name: `half-power @ ${res.half_power_angle_deg.toFixed(1)}°`,
                    line: { color: 'rgba(239,68,68,0.6)', width: 1.5, dash: 'dot' as const },
                  }] : []),
                ]}
                layout={{
                  autosize: true,
                  margin: { l: 70, r: 20, t: 10, b: 60 },
                  xaxis: { title: 'Zenith angle (deg)', range: [0, 90] },
                  yaxis: { title: 'Radiative power density (W/m²/sr)' },
                }}
                style={{ width: '100%', height: '100%' }}
                useResizeHandler
                config={{ displayModeBar: true, responsive: true }}
              />
            </div>
          </Card>

          <Card className="glass-light">
            <CardHeader>
              <CardTitle>Angular profile (Polar)</CardTitle>
              <CardDesc>Hemispherical distribution</CardDesc>
            </CardHeader>
            <div className="h-[420px]">
              <Plot
                data={[
                  {
                    type: 'scatterpolar',
                    mode: 'lines',
                    theta: res.theta_deg,
                    r: polar.r,
                    name: 'power_density_per_sr',
                  } as any,
                ]}
                layout={getPlotlyLayout({
                  autosize: true,
                  margin: { l: 40, r: 40, t: 10, b: 40 },
                  polar: {
                    angularaxis: { direction: 'clockwise', rotation: 90, range: [0, 90] },
                    radialaxis: { title: 'W/m²/sr' },
                  },
                  showlegend: false,
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
