import { useState, useMemo, useCallback, useRef, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Card, CardDesc, CardHeader, CardTitle } from '../components/ui/Card'
import Button from '../components/ui/Button'
import { COLORMAP_LIST } from '../components/ColormapSelector'
import {
  type KoppenData,
  KOPPEN_CODES,
  parseKoppenCSV,
  getDataRange,
} from '../services/mapRedraw'
import { koppenMapApi, type KoppenPreviewResult } from '../services/koppenMapApi'

// ─── Reverse lookup: Köppen zone → list of ISO 3166-1 numeric country codes ───
// Countries mapped to Köppen zones (simplified world Köppen classification)
// ISO 3166-1 numeric codes as keys
const KOPPEN_TO_ISO: Record<string, number[]> = {
  // Tropical (A)
  Af: [12, 24, 180, 86, 76, 218, 340, 320, 328, 670, 706, 748, 800, 858, 862, 516, 646],
  Am: [404, 356, 50, 662],
  As: [462, 776],
  Aw: [24, 566, 288, 686, 508, 716, 800, 818, 706, 504, 108, 834, 232, 710, 729, 768, 854, 204, 854],
  // Dry (B)
  BSh: [120, 144, 231, 320, 340, 466, 562, 566, 598, 646, 694, 706, 716, 768, 788, 800, 818, 12, 356, 364, 368, 376, 400, 414, 422, 887, 792],
  BSk: [4, 8, 68, 156, 192, 203, 208, 214, 218, 231, 246, 250, 266, 300, 324, 332, 352, 428, 440, 442, 496, 528, 578, 620, 752, 756, 764, 792, 804, 826, 840, 860, 894],
  BWh: [12, 48, 64, 78, 262, 288, 304, 368, 372, 376, 414, 422, 430, 434, 454, 478, 504, 512, 516, 554, 562, 566, 586, 634, 682, 706, 710, 729, 732, 748, 764, 784, 788, 818, 887],
  BWk: [4, 8, 50, 68, 104, 116, 120, 144, 156, 162, 170, 196, 204, 218, 231, 262, 288, 356, 364, 368, 376, 380, 388, 392, 400, 414, 422, 434, 478, 484, 496, 504, 512, 516, 554, 558, 562, 566, 586, 591, 598, 604, 620, 634, 642, 682, 686, 694, 706, 710, 729, 732, 748, 752, 756, 764, 784, 788, 792, 800, 804, 818, 826, 840, 860, 862, 887, 894],
  // Temperate (C)
  Cfa: [36, 76, 124, 152, 156, 170, 188, 203, 208, 246, 250, 276, 300, 340, 348, 356, 380, 392, 528, 554, 566, 578, 591, 604, 616, 620, 626, 634, 642, 643, 682, 702, 703, 710, 724, 752, 756, 764, 788, 792, 804, 826, 840, 858, 860, 862, 704],
  Cfb: [32, 68, 76, 152, 170, 188, 203, 208, 214, 246, 250, 276, 300, 320, 328, 340, 348, 356, 372, 380, 392, 528, 554, 558, 578, 591, 600, 604, 620, 626, 634, 642, 643, 702, 703, 710, 724, 752, 756, 764, 788, 792, 800, 804, 826, 840, 858, 860, 862],
  Cfc: [74, 239, 352, 578, 744, 752, 796],
  Csa: [12, 36, 56, 191, 196, 203, 208, 246, 300, 348, 368, 376, 380, 400, 414, 422, 434, 438, 470, 478, 484, 504, 620, 634, 642, 682, 688, 694, 706, 710, 729, 752, 756, 764, 788, 792, 800, 804, 826, 858, 862, 887],
  Csb: [68, 152, 170, 188, 192, 203, 208, 214, 246, 300, 320, 328, 340, 348, 356, 368, 372, 380, 392, 528, 554, 558, 578, 591, 604, 616, 620, 626, 634, 642, 643, 682, 688, 694, 702, 703, 710, 724, 752, 756, 764, 788, 792, 800, 804, 826, 840, 858, 862],
  Csc: [152, 170, 188, 203, 208, 214, 340, 352, 578, 752],
  Cwa: [12, 24, 50, 120, 144, 152, 156, 178, 180, 204, 231, 232, 288, 320, 324, 340, 356, 360, 404, 450, 454, 466, 484, 508, 516, 562, 566, 578, 586, 598, 604, 608, 616, 620, 634, 642, 643, 646, 662, 682, 694, 706, 710, 716, 728, 729, 748, 764, 800, 804, 818, 826, 834, 854, 858, 862, 894],
  Cwb: [24, 50, 68, 120, 144, 152, 156, 180, 204, 231, 320, 340, 356, 360, 404, 450, 508, 516, 566, 586, 598, 604, 608, 616, 620, 634, 642, 643, 646, 682, 694, 706, 710, 716, 728, 729, 748, 764, 800, 804, 818, 834, 854, 858, 862, 894],
  Cwc: [68, 340, 604, 616, 620, 634, 642, 716, 728, 748, 764, 800, 804, 858],
  // Continental (D)
  Dfa: [156, 203, 246, 276, 300, 348, 356, 398, 428, 440, 442, 496, 528, 578, 616, 620, 634, 642, 643, 682, 702, 710, 752, 756, 764, 792, 804, 826, 840, 860, 862, 804],
  Dfb: [40, 56, 100, 112, 203, 246, 250, 276, 300, 348, 352, 356, 372, 380, 398, 428, 440, 442, 496, 528, 578, 616, 620, 626, 634, 642, 643, 682, 688, 694, 702, 703, 710, 752, 756, 764, 788, 792, 804, 826, 840, 860, 862],
  Dfc: [8, 74, 112, 116, 124, 208, 246, 250, 268, 296, 300, 352, 356, 398, 428, 440, 496, 578, 598, 604, 608, 616, 620, 626, 634, 642, 643, 682, 694, 702, 703, 710, 744, 752, 756, 764, 788, 792, 795, 804, 826, 840, 860, 862],
  Dfd: [643],
  Dsa: [31, 51, 100, 268, 296, 356, 364, 368, 376, 400, 414, 422, 434, 496, 586, 634, 682, 688, 694, 706, 710, 729, 760, 762, 764, 792, 795, 804, 818, 860, 887],
  Dsb: [31, 51, 100, 112, 191, 268, 300, 348, 356, 364, 368, 372, 376, 400, 414, 422, 434, 496, 558, 586, 604, 616, 620, 634, 642, 643, 682, 688, 694, 702, 703, 710, 724, 729, 752, 756, 760, 762, 764, 788, 792, 795, 804, 818, 826, 840, 860, 862, 887],
  Dsc: [398, 428, 496, 578, 598, 604, 608, 616, 620, 634, 642, 643, 682, 694, 702, 703, 710, 744, 752, 756, 764, 788, 792, 795, 804, 826, 840, 860, 862],
  Dsd: [643, 796],
  Dwa: [156, 408, 496, 584, 598, 608, 616, 620, 634, 643, 702, 710, 756, 764, 826, 840, 860],
  Dwb: [44, 50, 64, 104, 116, 156, 343, 356, 408, 496, 584, 598, 608, 616, 620, 634, 642, 643, 682, 694, 702, 703, 710, 752, 756, 764, 788, 792, 795, 804, 826, 840, 860, 862],
  Dwc: [50, 64, 104, 116, 156, 343, 356, 408, 496, 584, 598, 604, 608, 616, 620, 634, 642, 643, 682, 694, 702, 703, 710, 752, 756, 764, 788, 792, 795, 804, 826, 840, 860, 862],
  Dwd: [643, 796],
  // Polar (E)
  EF: [8, 74, 239, 296, 304, 352, 744, 796],
  ET: [10, 74, 239, 266, 304, 352, 428, 578, 744, 752, 796],
  // Extended
  'EF+ET': [8, 10, 74, 239, 266, 296, 304, 352, 428, 578, 744, 752, 796],
}

// All valid Köppen codes (union of keys)
const ALL_KOPPEN_CODES = Object.keys(KOPPEN_TO_ISO)

// ─── Plotly color scale (matched to ColormapSelector choices) ───
// Each entry is [normalized_position, hex_color]
type ColorStop = [number, string]
type PlotlyColorScale = ColorStop[]

const PLOTLY_COLORSCALES: Record<string, PlotlyColorScale> = {
  viridis: [
    [0, '#440154'], [0.125, '#482878'], [0.25, '#3E4A89'],
    [0.375, '#31688E'], [0.5, '#26838F'], [0.625, '#1F9E89'],
    [0.75, '#6CCE59'], [0.875, '#B6DE2B'], [1, '#FEE825'],
  ],
  cividis: [
    [0, '#00224E'], [0.125, '#123570'], [0.25, '#575D6D'],
    [0.375, '#707173'], [0.5, '#8A8678'], [0.625, '#A59C74'],
    [0.75, '#C3B569'], [0.875, '#E3CD53'], [1, '#F0F921'],
  ],
  magma: [
    [0, '#000004'], [0.143, '#1C1041'], [0.286, '#4F1273'],
    [0.429, '#8F0F5D'], [0.571, '#CE3753'], [0.714, '#F27B50'],
    [0.857, '#FCA50A'], [1, '#F0F921'],
  ],
  plasma: [
    [0, '#0D0887'], [0.111, '#46039F'], [0.222, '#7201A8'],
    [0.333, '#9C179E'], [0.444, '#BD3786'], [0.556, '#D8576B'],
    [0.667, '#ED7953'], [0.778, '#FB9F3A'], [0.889, '#FDCA26'],
    [1, '#F0F921'],
  ],
  inferno: [
    [0, '#000004'], [0.143, '#1B0C41'], [0.286, '#4A0C6B'],
    [0.429, '#781C6D'], [0.571, '#B52F5D'], [0.714, '#F48849'],
    [0.857, '#FBD526'], [1, '#FCFFA4'],
  ],
  turbo: [
    [0, '#23171B'], [0.071, '#2C0D6B'], [0.143, '#3B0F70'],
    [0.214, '#57106E'], [0.286, '#6F1E68'], [0.357, '#8B2C5E'],
    [0.429, '#A43A52'], [0.5, '#BB4A43'], [0.571, '#CC5D32'],
    [0.643, '#DA7725'], [0.714, '#E69420'], [0.786, '#F3B026'],
    [0.857, '#FFCC4D'], [0.929, '#F8E638'], [1, '#F0F921'],
  ],
  Greys: [
    [0, '#FFFFFF'], [0.143, '#F0F0F0'], [0.286, '#D9D9D9'],
    [0.429, '#BDBDBD'], [0.571, '#969696'], [0.714, '#737373'],
    [0.857, '#525252'], [1, '#252525'],
  ],
  Blues: [
    [0, '#EFF3FF'], [0.25, '#BDD7E7'], [0.5, '#6BAED6'],
    [0.75, '#2171B5'], [1, '#084594'],
  ],
  Reds: [
    [0, '#FCBBA1'], [0.167, '#FC9272'], [0.333, '#FB6A4A'],
    [0.5, '#EF3B2C'], [0.667, '#CB181D'], [1, '#99000D'],
  ],
  Greens: [
    [0, '#F7FCB9'], [0.2, '#ADDD8E'], [0.4, '#78C679'],
    [0.6, '#41AB5D'], [0.8, '#238B45'], [1, '#006837'],
  ],
  coolwarm: [
    [0, '#3B4CC0'], [0.125, '#6787D9'], [0.25, '#9ABBF0'],
    [0.375, '#C0D4F0'], [0.5, '#E0D5E8'], [0.625, '#F0B8C0'],
    [0.75, '#D97A8C'], [1, '#B40E4C'],
  ],
  coolwarm_r: [
    [0, '#B40E4C'], [0.25, '#D97A8C'], [0.375, '#F0B8C0'],
    [0.5, '#E0D5E8'], [0.625, '#C0D4F0'], [0.75, '#9ABBF0'],
    [0.875, '#6787D9'], [1, '#3B4CC0'],
  ],
  RdBu: [
    [0, '#B2182B'], [0.143, '#D6604D'], [0.286, '#F4A582'],
    [0.429, '#FDDBC7'], [0.5, '#D1E5F0'], [0.571, '#92C5DE'],
    [0.714, '#4393C3'], [1, '#2166AC'],
  ],
  RdGy: [
    [0, '#B2182B'], [0.167, '#EF8A62'], [0.333, '#FDDBC7'],
    [0.5, '#FFFFFF'], [0.667, '#D1D1D1'], [0.833, '#999999'],
    [1, '#4D4D4D'],
  ],
  spectral: [
    [0, '#9E0142'], [0.111, '#D53E4F'], [0.222, '#F46D43'],
    [0.333, '#FDAE61'], [0.444, '#FEE08B'], [0.556, '#E6F598'],
    [0.667, '#ABDDA4'], [0.778, '#66C2A5'], [0.889, '#3288BD'],
    [1, '#5E4FA2'],
  ],
  YlGnBu: [
    [0, '#FFFFD9'], [0.143, '#EDF8B1'], [0.286, '#C7E9B4'],
    [0.429, '#7FCDBB'], [0.571, '#41B6C4'], [0.714, '#1D91C0'],
    [0.857, '#225EA8'], [1, '#0C2C84'],
  ],
  PuBuGn: [
    [0, '#FFF7FB'], [0.143, '#ECE7F2'], [0.286, '#D2D4E8'],
    [0.429, '#A6BDDB'], [0.571, '#74A9CF'], [0.714, '#3690C0'],
    [0.857, '#0570B0'], [1, '#034E7B'],
  ],
  tab10: [
    [0, '#4C72B0'], [0.111, '#DD8452'], [0.222, '#55A868'],
    [0.333, '#C44E52'], [0.444, '#8172B2'], [0.556, '#937860'],
    [0.667, '#DA8BC3'], [0.778, '#8C8C8C'], [0.889, '#CCB974'],
    [1, '#64B5CD'],
  ],
}

// Default color scale
const DEFAULT_CMAP = 'Blues'

// Fallback for unmapped color scales: use a simple white-to-color gradient
function buildFallbackScale(baseColor = '#2171B5'): PlotlyColorScale {
  return [
    [0, '#FFFFFF'],
    [0.25, baseColor + 'AA'],
    [0.5, baseColor],
    [0.75, baseColor + 'CC'],
    [1, '#08306B'],
  ]
}

function getColorScale(key: string): PlotlyColorScale {
  return PLOTLY_COLORSCALES[key] ?? buildFallbackScale('#2171B5')
}

/** Interpolate between a list of hex colors at position t (0-1) */
function interpolateColor(colors: string[], t: number): string {
  const idx = Math.max(0, Math.min(colors.length - 2, Math.floor(t * (colors.length - 1))))
  const localT = t * (colors.length - 1) - idx
  const c1 = hexToRgb(colors[idx])
  const c2 = hexToRgb(colors[idx + 1] ?? colors[idx])
  const r = Math.round(c1.r + (c2.r - c1.r) * localT)
  const g = Math.round(c1.g + (c2.g - c1.g) * localT)
  const b = Math.round(c1.b + (c2.b - c1.b) * localT)
  return `rgb(${r},${g},${b})`
}

function hexToRgb(hex: string): { r: number; g: number; b: number } {
  const clean = hex.replace('#', '')
  const n = parseInt(clean, 16)
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 }
}

// ─── Small UI components ───────────────────────────────────────────────────────

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

function NumberInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
                className={
                  'w-full rounded-field border border-border glass-light px-3.5 py-2.5 text-sm text-text-primary ' +
                  'transition-all duration-150 ' +
                  'focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 focus-visible:border-accent/50 ' +
                  'hover:border-border-light hover:bg-bg-elevated ' +
                  (props.className || '')
      }
    />
  )
}

function TickControl({
  label,
  hint,
  value,
  onChange,
}: {
  label: string
  hint?: string
  value: number
  onChange: (v: number) => void
}) {
  return (
    <Field label={label} hint={hint}>
      <NumberInput
        type="number"
        value={value}
        step={0.1}
        onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
      />
    </Field>
  )
}

// ─── Colormap preview strip ────────────────────────────────────────────────────
function ColormapPreview({ colors }: { colors: string[] }) {
  const gradient = colors.map((c, i) =>
    `${c} ${Math.round((i / (colors.length - 1)) * 100)}%`
  ).join(', ')
  return (
    <div
      className="h-3 flex-1 rounded"
      style={{ background: `linear-gradient(to right, ${gradient})` }}
    />
  )
}

// ─── Main Page ────────────────────────────────────────────────────────────────
export default function MapRedrawPage() {
  const { t, i18n } = useTranslation()
  const isZh = i18n.language.startsWith('zh')

  // ── File & data state ──
  const [fileName, setFileName] = useState<string>('')
  const [parsedData, setParsedData] = useState<KoppenData>([])
  const [parseError, setParseError] = useState<string>('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  // ── Map control state ──
  const [colormap, setColormap] = useState(DEFAULT_CMAP)
  const [showTitle, setShowTitle] = useState(true)
  const [mapTitle, setMapTitle] = useState('Köppen Zone Energy Map')
  const [cbarLabel, setCbarLabel] = useState('Cooling Energy Saving (MJ/m²)')
  const [zAutoRange, setZAutoRange] = useState(true)
  const [zMin, setZMin] = useState(0)
  const [zMax, setZMax] = useState(100)
  const [tickCount, setTickCount] = useState(6)
  const [showTraceValues, setShowTraceValues] = useState(false)
  const [addGrid, setAddGrid] = useState(false)

  // ── GEE map preview state ──
  const [previewData, setPreviewData] = useState<KoppenPreviewResult | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState<string>('')
  const previewCacheRef = useRef<Map<string, KoppenPreviewResult>>(new Map())

  // ── Parse CSV file ──
  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setFileName(file.name)
    setParseError('')

    const reader = new FileReader()
    reader.onload = (ev) => {
      try {
        const text = ev.target?.result as string
        const data = parseKoppenCSV(text)
        if (data.length === 0) {
          setParseError('CSV 解析失败或数据为空，请检查文件格式,注意一定要包含 "FQ"和"results" 列。')
          setParsedData([])
          return
        }
        setParsedData(data)
        // Auto-set z range
        const [mn, mx] = getDataRange(data)
        setZMin(mn)
        setZMax(mx)
      } catch {
        setParseError('CSV 解析失败，请确认文件为标准 CSV 格式。')
        setParsedData([])
      }
    }
    reader.onerror = () => {
      setParseError('文件读取失败。')
      setParsedData([])
    }
    reader.readAsText(file)
  }, [])

  // ── Build CSV string for GEE API ──
  const csvString = useMemo(() => {
    if (parsedData.length === 0) return ''
    const header = 'ID,QID,FQ,results'
    const rows = parsedData.map((e, i) => `${i + 1},${i + 1},${e.FQ},${e.value}`)
    return [header, ...rows].join('\n')
  }, [parsedData])

  // ── Trigger GEE preview when params change ──
  useEffect(() => {
    if (!csvString) {
      setPreviewData(null)
      setPreviewError('')
      return
    }

    const cacheKey = JSON.stringify({ csv: csvString, colormap, title: mapTitle, label: cbarLabel, zmin: zAutoRange ? null : zMin, zmax: zAutoRange ? null : zMax, grid: addGrid })

    // Serve from in-memory cache
    const cached = previewCacheRef.current.get(cacheKey)
    if (cached) {
      setPreviewData(cached)
      setPreviewError('')
      return
    }

    setPreviewLoading(true)
    setPreviewError('')

    koppenMapApi.getPreview({
      csv_content: csvString,
      colormap,
      title: mapTitle,
      colorbar_label: cbarLabel,
      z_min: zAutoRange ? null : zMin,
      z_max: zAutoRange ? null : zMax,
      add_grid: addGrid,
    }).then((result) => {
      previewCacheRef.current.set(cacheKey, result)
      setPreviewData(result)
      setPreviewError('')
    }).catch((err) => {
      const msg = err?.response?.data?.detail ?? err?.message ?? 'Unknown error'
      setPreviewError(String(msg))
      setPreviewData(null)
    }).finally(() => {
      setPreviewLoading(false)
    })
  }, [csvString, colormap, mapTitle, cbarLabel, zAutoRange, zMin, zMax, addGrid])

  // ── Data table rows ──
  const tableData = useMemo(() => {
    if (parsedData.length === 0) return []
    const [mn, mx] = getDataRange(parsedData)
    return parsedData.map((entry) => ({
      FQ: entry.FQ,
      value: entry.value,
      pct: mn === mx ? 50 : Math.round(((entry.value - mn) / (mx - mn)) * 100),
    }))
  }, [parsedData])

  // ── Color scale preview ──
  const currentCmapColors = useMemo(() => {
    const cmap = COLORMAP_LIST.find((c) => c.key === colormap)
    return cmap?.colors ?? ['#FFFFFF', '#2171B5', '#084594']
  }, [colormap])

  return (
    <div className="space-y-5">

      {/* ── Upload Card ── */}
      <Card>
        <CardHeader>
          <CardTitle>{isZh ? '世界地图绘制工具' : 'World Map Redraw Tool'}</CardTitle>
          <CardDesc>
            {isZh
              ? '上传 data.csv 文件（包含 FQ 和 results 列），系统将根据 Köppen 气候区自动匹配各国并绘制交互式地图。(需要自己打开data.csv修改绘图使用列名为results)'
              : 'Upload data.csv (with FQ and results columns). The tool will match Köppen zones to countries and draw an interactive map.'}
          </CardDesc>
        </CardHeader>

        {/* File input */}
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[200px]">
            <Field label={isZh ? 'CSV 文件' : 'CSV File'}>
              <div className="flex gap-2">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv,text/csv"
                  onChange={handleFileChange}
                  className="hidden"
                />
                <Button
                  variant="secondary"
                  onClick={() => fileInputRef.current?.click()}
                  className="flex-shrink-0"
                >
                  {isZh ? '选择文件…' : 'Choose File…'}
                </Button>
                {fileName ? (
                  <span className="flex items-center text-xs text-text-secondary truncate">
                    {fileName}
                  </span>
                ) : (
                  <span className="flex items-center text-xs text-text-muted truncate">
                    {isZh ? '未选择文件' : 'No file selected'}
                  </span>
                )}
              </div>
            </Field>
          </div>

          {parsedData.length > 0 && (
            <div className="text-xs text-text-secondary space-y-1">
              <div>
                <span className="font-semibold">{parsedData.length}</span>
                {isZh ? ' 条数据已加载' : ' rows loaded'}
              </div>
              <div>
                FQ 代码：
                {parsedData.map((d) => d.FQ).join(', ')}
              </div>
            </div>
          )}
        </div>

        {parseError && (
          <div className="mt-3 rounded-xl border border-danger/30 bg-danger/10 p-3 text-xs text-danger">
            {parseError}
          </div>
        )}

        {/* Data preview table */}
        {tableData.length > 0 && (
          <div className="mt-4">
            <div className="mb-2 text-xs font-semibold text-text-secondary uppercase tracking-wider">
              {isZh ? '数据预览' : 'Data Preview'}
            </div>
            <div className="rounded-field border border-border overflow-hidden">
              <div className="max-h-40 overflow-auto">
                <table className="min-w-full text-xs">
                  <thead className="bg-bg-elevated sticky top-0">
                    <tr>
                      <th className="px-3 py-2 text-left font-semibold text-text-secondary border-b border-border">
                        FQ
                      </th>
                      <th className="px-3 py-2 text-right font-semibold text-text-secondary border-b border-border">
                        Value
                      </th>
                      <th className="px-3 py-2 text-right font-semibold text-text-secondary border-b border-border">
                        %
                      </th>
                      <th className="px-3 py-2 text-left font-semibold text-text-secondary border-b border-border">
                        {isZh ? '颜色预览' : 'Color Preview'}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {tableData.map((row) => (
                      <tr key={row.FQ} className="border-b border-border-light last:border-0">
                        <td className="px-3 py-1.5 font-mono font-semibold text-text-primary">{row.FQ}</td>
                        <td className="px-3 py-1.5 text-right text-text-secondary">{row.value.toFixed(2)}</td>
                        <td className="px-3 py-1.5 text-right text-text-secondary">{row.pct}%</td>
                        <td className="px-3 py-1.5">
                          <div
                            className="h-3 rounded"
                            style={{
                              background: interpolateColor(
                                currentCmapColors,
                                row.pct / 100
                              ),
                            }}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </Card>

      {/* ── Map Controls ── */}
      <Card className="glass-light">
        <CardHeader>
          <CardTitle>{isZh ? '地图设置' : 'Map Settings'}</CardTitle>
        </CardHeader>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {/* Colormap */}
          <Field
            label={isZh ? '颜色方案' : 'Colormap'}
            hint={isZh ? '选择地图着色色系' : 'Color scale for the map'}
          >
            <div className="space-y-2">
              <select
                value={colormap}
                onChange={(e) => setColormap(e.target.value)}
                className="w-full rounded-field border border-border glass-light px-3.5 py-2.5 text-sm text-text-primary cursor-pointer transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 focus-visible:border-accent/50 hover:border-border-light hover:bg-bg-elevated"
              >
                {COLORMAP_LIST.map((cmap) => (
                  <option key={cmap.key} value={cmap.key}>
                    {isZh ? cmap.desc_zh : cmap.desc_en}
                  </option>
                ))}
              </select>
              <ColormapPreview colors={currentCmapColors} />
            </div>
          </Field>

          {/* Lat/Lon Grid toggle */}
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="addgrid"
              checked={addGrid}
              onChange={(e) => setAddGrid(e.target.checked)}
              className="h-4 w-4 rounded border-border text-accent focus-visible:ring-2 focus-visible:ring-accent/50 focus-visible:ring-offset-2 focus-visible:ring-offset-bg cursor-pointer"
            />
            <label htmlFor="addgrid" className="text-sm cursor-pointer text-text-secondary">
              {isZh ? '显示经纬度网格' : 'Show Lat/Lon Grid'}
            </label>
          </div>

          {/* Tick count */}
          <Field
            label={isZh ? '刻度数量' : 'Tick Count'}
            hint={isZh ? '颜色条刻度数量' : 'Number of colorbar ticks'}
          >
            <NumberInput
              type="number"
              min={2}
              max={20}
              value={tickCount}
              onChange={(e) => setTickCount(parseInt(e.target.value) || 6)}
            />
          </Field>

          {/* Z auto range toggle */}
          <div className="flex items-center gap-2 md:col-span-2 lg:col-span-3">
            <input
              type="checkbox"
              id="zauto"
              checked={zAutoRange}
              onChange={(e) => setZAutoRange(e.target.checked)}
              className="h-4 w-4 rounded border-border text-accent focus-visible:ring-2 focus-visible:ring-accent/50 focus-visible:ring-offset-2 focus-visible:ring-offset-bg cursor-pointer"
            />
            <label htmlFor="zauto" className="text-sm cursor-pointer text-text-secondary">
              {isZh ? '自动范围（根据数据自动计算）' : 'Auto range (calculate from data)'}
            </label>
          </div>

          {/* Z min / max */}
          {!zAutoRange && (
            <>
              <TickControl
                label={isZh ? '最小值 (zmin)' : 'Min Value (zmin)'}
                value={zMin}
                onChange={setZMin}
              />
              <TickControl
                label={isZh ? '最大值 (zmax)' : 'Max Value (zmax)'}
                value={zMax}
                onChange={setZMax}
              />
            </>
          )}

          {/* Title toggle */}
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="showtitle"
              checked={showTitle}
              onChange={(e) => setShowTitle(e.target.checked)}
              className="h-4 w-4 rounded border-border text-accent focus-visible:ring-2 focus-visible:ring-accent/50 focus-visible:ring-offset-2 focus-visible:ring-offset-bg cursor-pointer"
            />
            <label htmlFor="showtitle" className="text-sm cursor-pointer text-text-secondary">
              {isZh ? '显示标题' : 'Show Title'}
            </label>
          </div>

          {/* Title text */}
          {showTitle && (
            <Field label={isZh ? '标题文字' : 'Title Text'}>
              <input
                type="text"
                value={mapTitle}
                onChange={(e) => setMapTitle(e.target.value)}
                className="w-full rounded-field border border-border glass-light px-3.5 py-2.5 text-sm text-text-primary transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 focus-visible:border-accent/50 hover:border-border-light hover:bg-bg-elevated"
              />
            </Field>
          )}

          {/* Colorbar label */}
          <Field label={isZh ? '颜色条标签' : 'Colorbar Label'}>
            <input
              type="text"
              value={cbarLabel}
              onChange={(e) => setCbarLabel(e.target.value)}
              className="w-full rounded-field border border-border glass-light px-3.5 py-2.5 text-sm text-text-primary transition-all duration-150 focus:outline-none focus:ring-2 focus-visible:ring-2 focus-visible:ring-accent/50 focus-visible:border-accent/50 hover:border-border-light hover:bg-bg-elevated"
            />
          </Field>

          {/* Show trace values */}
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="tracevals"
              checked={showTraceValues}
              onChange={(e) => setShowTraceValues(e.target.checked)}
              className="h-4 w-4 rounded border-border text-accent focus-visible:ring-2 focus-visible:ring-accent/50 focus-visible:ring-offset-2 focus-visible:ring-offset-bg cursor-pointer"
            />
            <label htmlFor="tracevals" className="text-sm cursor-pointer text-text-secondary">
              {isZh ? '显示数据标签' : 'Show Data Labels'}
            </label>
          </div>
        </div>

        {/* Quick presets */}
        <div className="mt-4 pt-4 border-t border-border">
          <div className="text-xs font-semibold text-text-secondary mb-2">
            {isZh ? '快速预设' : 'Quick Presets'}
          </div>
          <div className="flex flex-wrap gap-2">
            {[
              { key: 'Blues', label: isZh ? '蓝（制冷）' : 'Blue (Cooling)' },
              { key: 'Reds', label: isZh ? '红（制热）' : 'Red (Heating)' },
              { key: 'coolwarm', label: isZh ? '蓝红发散' : 'Coolwarm' },
              { key: 'RdBu', label: isZh ? '红蓝发散' : 'RdBu' },
              { key: 'Greens', label: isZh ? '绿色' : 'Green' },
              { key: 'viridis', label: 'Viridis' },
              { key: 'magma', label: 'Magma' },
              { key: 'spectral', label: 'Spectral' },
            ].map((preset) => (
              <button
                key={preset.key}
                onClick={() => setColormap(preset.key)}
                className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-all duration-150 ${
                  colormap === preset.key
                    ? 'border-accent bg-accent/10 text-accent'
                    : 'border-border bg-bg-elevated text-text-secondary hover:border-border-light hover:text-text-primary'
                }`}
              >
                {preset.label}
              </button>
            ))}
          </div>
        </div>
      </Card>

      {/* ── GEE Map Preview ── */}
      {parsedData.length === 0 && (
        <Card className="glass-light">
          <div className="flex flex-col items-center justify-center h-64 gap-4">
            <svg
              width="64"
              height="64"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              className="text-text-muted"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 6.75V15m6-6v8.25m.503 3.498l4.875-2.437c.381-.19.622-.58.622-1.006V4.82c0-.836-.88-1.38-1.628-1.006l-3.869 1.934c-.317.159-.69.159-1.006 0L9.503 3.252a1.125 1.125 0 00-1.006 0L3.622 5.689C3.24 5.88 3 6.27 3 6.695V19.18c0 .836.88 1.38 1.628 1.006l3.869-1.934c.317-.159.69-.159 1.006 0l4.994 2.497c.317.158.69.158 1.006 0z" />
            </svg>
            <div className="text-center">
              <div className="text-sm font-semibold text-text-secondary">
                {isZh ? '请上传 CSV 文件以开始绘图' : 'Upload a CSV file to start drawing'}
              </div>
              <div className="mt-1 text-xs text-text-muted">
                {isZh
                  ? '支持 FQ, results 列格式'
                  : 'Supports FQ, results column format'}
              </div>
            </div>
          </div>
        </Card>
      )}

      {parsedData.length > 0 && (
        <Card className="p-0 overflow-hidden">
          <div className="p-5 pb-0">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-base font-semibold text-text-primary tracking-tight">
                  {mapTitle || (isZh ? 'Köppen 气候区地图预览' : 'Köppen Climate Zone Map Preview')}
                </div>
                <div className="mt-1 text-sm text-text-secondary">
                  {isZh
                    ? '基于 GEE 全球 Köppen 栅格地图渲染（像素级上色）· 更改参数后自动刷新'
                    : 'Rendered via GEE global Köppen raster (pixel-level coloring) · Auto-refreshes on param change'}
                </div>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                {previewData && (
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => {
                      const a = document.createElement('a')
                      a.href = koppenMapApi.getExportUrl(previewData.cache_key)
                      a.download = `koppen_map_${previewData.cache_key}.png`
                      a.target = '_blank'
                      a.rel = 'noopener'
                      a.click()
                    }}
                  >
                    {isZh ? '下载高清 PNG' : 'Export HD PNG'}
                  </Button>
                )}
              </div>
            </div>
          </div>

          <div className="p-4">
            {previewLoading && (
              <div className="flex flex-col items-center justify-center h-80 gap-4">
                <div className="w-8 h-8 border-2 border-t-accent border-border rounded-full animate-spin" />
                <div className="text-sm text-text-muted">
                  {isZh
                    ? '正在从 GEE 获取地图（首次需联网，可能需要 30 秒）...'
                    : 'Fetching map from GEE (first call may take ~30s)...'}
                </div>
              </div>
            )}

            {previewError && !previewLoading && (
              <div className="flex flex-col items-center justify-center h-80 gap-3 p-6">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-red-400">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
                </svg>
                <div className="text-sm text-red-400 text-center max-w-md">{previewError}</div>
              </div>
            )}

            {previewData && !previewLoading && !previewError && (
              <img
                src={previewData.data_url}
                alt={isZh ? 'Köppen 气候区地图预览' : 'Köppen Climate Zone Map Preview'}
                className="w-full h-auto rounded-lg"
                style={{ display: 'block', maxHeight: 600 }}
              />
            )}
          </div>

          {/* Cache note */}
          <div className="px-5 pb-4">
            <div className="glass-light rounded-field border border-border p-3 text-xs text-text-muted">
              <strong className="text-text-secondary">{isZh ? '缓存说明：' : 'Cache Note:'}</strong>{' '}
              {isZh
                ? '相同参数（CSV、色图、标题、颜色范围）的请求会从本地缓存（内存 + 服务器磁盘）返回，无需重复联网。首次请求需联网获取 GEE 栅格。'
                : 'Identical parameter sets (CSV, colormap, title, color range) are served from local cache (memory + server disk) with no repeated GEE calls. First request requires internet.'}
            </div>
          </div>
        </Card>
      )}

      {/* ── Help / Usage Card ── */}
      <Card className="glass-light">
        <CardHeader>
          <CardTitle>{isZh ? '功能说明' : 'Feature Guide'}</CardTitle>
        </CardHeader>
        <div className="text-sm text-text-secondary leading-relaxed space-y-2">
          <p>
            <strong>{isZh ? '数据格式：' : 'Data Format:'}</strong>{' '}
            {isZh
              ? 'CSV 文件只需包含 FQ 和 results 两列。FQ 为 Köppen 气候区代码（如 Af, Cfa, BSk 等），results 为绘图数值（如节能、CO₂ 减排量等）。'
              : 'CSV needs only FQ (Köppen climate zone code, e.g., Af, Cfa) and results (value to plot, e.g., energy saving, CO₂ reduction).'}
          </p>
          <p>
            <strong>{isZh ? 'Köppen 气候区代码参考：' : 'Köppen Zone Code Reference:'}</strong>
          </p>
          <div className="grid grid-cols-3 md:grid-cols-5 gap-1 text-xs font-mono">
            {KOPPEN_CODES.map((code) => (
              <span key={code} className="rounded bg-bg-elevated px-2 py-1 text-text-secondary">
                {code}
              </span>
            ))}
          </div>
          <p className="pt-2">
            <strong>{isZh ? '颜色方案：' : 'Colormap:'}</strong>{' '}
            {isZh
              ? '支持 37 种科学可视化色系，支持蓝-红发散（coolwarm）用于表示正负变化，或单色渐变（Blues/Reds）用于单向数据。'
              : '37 scientific colormaps supported. Use coolwarm/RdBu for diverging data, Blues/Reds for sequential data.'}
          </p>
          <p>
            <strong>{isZh ? '地图导出：' : 'Export:'}</strong>{' '}
            {isZh
              ? '点击 Plotly 工具栏中的下载图标（相机图标）可导出 PNG 高清图片（2× 缩放）。'
              : 'Click the camera icon in Plotly toolbar to export PNG (2× scale).'}
          </p>
          <p>
            <strong>CSV {isZh ? '示例数据格式：' : 'Sample Format:'}</strong>
          </p>
          <pre className="rounded-lg bg-bg-elevated p-3 text-xs font-mono text-text-secondary overflow-x-auto">
{`FQ,results
Af,131.76
Am,101.66
Aw,128.87
BSh,104.42
BSk,56.97
Cfa,47.34
Cfb,25.60
Dfa,34.81
...`}
          </pre>
        </div>
      </Card>

      {/* ── Recommended References ── */}
      <Card className="glass-light">
        <CardHeader>
          <CardTitle>{t('pages.jobDetail.recommendedReferences')}</CardTitle>
          <CardDesc>{isZh ? '推荐引用以下参考文献' : 'Recommended references to cite'}</CardDesc>
        </CardHeader>
        <div className="glass-light mt-2 rounded-field border border-border p-3 text-xs text-text-secondary whitespace-pre-line leading-relaxed">
          {t('pages.jobDetail.referencesContent')}
        </div>
      </Card>
    </div>
  )
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Country name lookup by ISO 3166-1 numeric code */
const ISO_TO_NAME: Record<number, string> = {
  4: 'Afghanistan', 8: 'Albania', 12: 'Algeria', 24: 'Angola',
  32: 'Argentina', 36: 'Australia', 40: 'Austria', 50: 'Bangladesh',
  56: 'Belgium', 68: 'Bolivia', 76: 'Brazil', 100: 'Bulgaria',
  104: 'Myanmar', 116: 'Cambodia', 120: 'Cameroon', 124: 'Canada',
  144: 'Sri Lanka', 152: 'Chile', 156: 'China', 170: 'Colombia',
  178: 'Congo', 180: 'DR Congo', 191: 'Croatia', 192: 'Cuba',
  196: 'Cyprus', 203: 'Czech Republic', 204: 'Benin', 208: 'Denmark',
  214: 'Dominican Republic', 218: 'Ecuador', 231: 'Ethiopia', 232: 'Eritrea',
  246: 'Finland', 250: 'France', 262: 'Djibouti', 266: 'Gabon',
  268: 'Georgia', 276: 'Germany', 288: 'Ghana', 296: 'Kiribati',
  300: 'Greece', 304: 'Greenland', 320: 'Guatemala', 324: 'Guinea',
  328: 'Guyana', 332: 'Haiti', 340: 'Honduras', 343: 'Slovakia',
  348: 'Hungary', 352: 'Iceland', 356: 'India', 360: 'Indonesia',
  364: 'Iran', 368: 'Iraq', 372: 'Ireland', 376: 'Israel',
  380: 'Italy', 388: 'Jamaica', 392: 'Japan', 398: 'Kazakhstan',
  400: 'Jordan', 404: 'Kenya', 408: 'North Korea', 414: 'Kuwait',
  418: 'Laos', 422: 'Lebanon', 428: 'Latvia', 430: 'Liberia',
  434: 'Libya', 440: 'Lithuania', 442: 'Luxembourg', 450: 'Madagascar',
  454: 'Malawi', 462: 'Maldives', 466: 'Mali', 470: 'Malta',
  478: 'Mauritania', 484: 'Mexico', 496: 'Mongolia', 504: 'Morocco',
  508: 'Mozambique', 516: 'Namibia', 528: 'Netherlands', 554: 'New Zealand',
  558: 'Nicaragua', 562: 'Niger', 566: 'Nigeria', 578: 'Norway',
  586: 'Pakistan', 591: 'Panama', 598: 'Papua New Guinea', 604: 'Peru',
  608: 'Philippines', 616: 'Poland', 620: 'Portugal', 626: 'Timor-Leste',
  634: 'Qatar', 642: 'Romania', 643: 'Russia', 646: 'Rwanda',
  662: 'Saint Lucia', 670: 'Saint Vincent', 678: 'São Tomé', 682: 'Saudi Arabia',
  686: 'Senegal', 688: 'Serbia', 694: 'Sierra Leone', 696: 'Comoros',
  706: 'Somalia', 710: 'South Africa', 716: 'Zimbabwe', 724: 'Spain',
  728: 'South Sudan', 729: 'Sudan', 732: 'Western Sahara', 744: 'Svalbard',
  748: 'Eswatini', 752: 'Sweden', 756: 'Switzerland', 760: 'Syria',
  762: 'Tajikistan', 764: 'Thailand', 768: 'Togo', 776: 'Tonga',
  784: 'UAE', 788: 'Tunisia', 792: 'Turkey', 795: 'Turkmenistan',
  796: 'French Southern', 800: 'Uganda', 804: 'Ukraine',
  826: 'United Kingdom', 834: 'Tanzania', 840: 'United States',
  854: 'Burkina Faso', 858: 'Uruguay', 860: 'Uzbekistan', 862: 'Venezuela',
  887: 'Yemen', 894: 'Zambia',
}
