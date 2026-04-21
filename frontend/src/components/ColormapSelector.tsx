import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Card, CardHeader, CardTitle } from './ui/Card'
import Button from './ui/Button'

// ==================== Colormap Registry (must match backend) ====================
// 37 种科学可视化色系，按类别分组
export const COLORMAP_LIST = [
  // 科学色系
  { key: 'viridis',       desc_zh: '紫-绿-黄（viridis）', desc_en: 'Viridis (scientific)', colors: ['#440154', '#482878', '#3E4A89', '#31688E', '#26838F', '#1F9E89', '#6CCE59', '#B6DE2B', '#FEE825'], type: 'sequential' },
  { key: 'cividis',       desc_zh: '无障碍蓝黄（cividis）', desc_en: 'Cividis (colorblind-safe)', colors: ['#00224E', '#123570', '#3B496C', '#575D6D', '#707173', '#8A8678', '#A59C74', '#C3B569', '#E3CD53'], type: 'sequential' },
  { key: 'magma',         desc_zh: '岩浆（magma）',        desc_en: 'Magma (scientific)',  colors: ['#000004', '#1C1041', '#4F1273', '#8F0F5D', '#CE3753', '#F27B50', '#FCA50A', '#F0F921'], type: 'sequential' },
  { key: 'plasma',        desc_zh: '等离子体（plasma）',   desc_en: 'Plasma (scientific)', colors: ['#0D0887', '#46039F', '#7201A8', '#9C179E', '#BD3786', '#D8576B', '#ED7953', '#FB9F3A', '#FDCA26', '#F0F921'], type: 'sequential' },
  { key: 'inferno',       desc_zh: '火与冰（inferno）',   desc_en: 'Inferno (scientific)', colors: ['#000004', '#1B0C41', '#4A0C6B', '#781C6D', '#B52F5D', '#F48849', '#FBD526', '#FCFFA4'], type: 'sequential' },
  { key: 'turbo',         desc_zh: '彩虹高速（turbo）',     desc_en: 'Turbo rainbow',     colors: ['#23171B', '#2C0D6B', '#3B0F70', '#57106E', '#6F1E68', '#8B2C5E', '#A43A52', '#BB4A43', '#CC5D32', '#DA7725', '#E69420', '#F3B026', '#FFCC4D', '#F8E638'], type: 'sequential' },

  // 灰色系
  { key: 'Greys',         desc_zh: '灰色渐变',             desc_en: 'Grey gradient',    colors: ['#FFFFFF', '#F0F0F0', '#D9D9D9', '#BDBDBD', '#969696', '#737373', '#525252', '#252525'], type: 'sequential' },

  // 单色系
  { key: 'Blues',         desc_zh: '蓝色渐变',             desc_en: 'Blue gradient',    colors: ['#EFF3FF', '#BDD7E7', '#6BAED6', '#2171B5', '#084594'],           type: 'sequential' },
  { key: 'Blues_dark',    desc_zh: '深蓝渐变',             desc_en: 'Dark Blue gradient', colors: ['#C6DBEF', '#6BAED6', '#4292C6', '#2171B5', '#084594', '#08306B'], type: 'sequential' },
  { key: 'Greens',        desc_zh: '绿色渐变',             desc_en: 'Green gradient',   colors: ['#F7FCB9', '#ADDD8E', '#78C679', '#41AB5D', '#238B45', '#006837'], type: 'sequential' },
  { key: 'Oranges',       desc_zh: '橙色渐变',             desc_en: 'Orange gradient',  colors: ['#FFF5EB', '#FDBB84', '#FC8D59', '#EF6548', '#D94701', '#A63603', '#7F2704'], type: 'sequential' },
  { key: 'Purples',       desc_zh: '紫色渐变',             desc_en: 'Purple gradient', colors: ['#FCFBFD', '#DADAEB', '#BCBDC1', '#9E9AC8', '#756BB1', '#54278F', '#3F007D'], type: 'sequential' },

  // 黄-绿-蓝系
  { key: 'YlGnBu',        desc_zh: '黄-绿-蓝',             desc_en: 'Yellow-Green-Blue', colors: ['#FFFFD9', '#EDF8B1', '#C7E9B4', '#7FCDBB', '#41B6C4', '#1D91C0', '#225EA8', '#0C2C84'], type: 'sequential' },
  { key: 'PuBuGn',        desc_zh: '紫-蓝-绿渐变',          desc_en: 'Purple-Blue-Green gradient', colors: ['#FFF7FB', '#ECE7F2', '#D2D4E8', '#A6BDDB', '#74A9CF', '#3690C0', '#0570B0', '#034E7B', '#014636'], type: 'sequential' },
  { key: 'GnBu',          desc_zh: '绿-蓝渐变',             desc_en: 'Green-Blue gradient', colors: ['#F7FCB9', '#C7EAE5', '#B2E2E2', '#66C2A4', '#2CA25F', '#006D2C'], type: 'sequential' },
  { key: 'BuGn',          desc_zh: '蓝-绿渐变',             desc_en: 'Blue-Green gradient', colors: ['#F7FBFF', '#DEEBF7', '#C6DBEF', '#9ECAE1', '#6BAED6', '#4292C6', '#2171B5', '#084594'], type: 'sequential' },

  // 发散色系
  { key: 'RdBu',          desc_zh: '红-蓝发散',             desc_en: 'Red-Blue diverging', colors: ['#B2182B', '#D6604D', '#F4A582', '#FDDBC7', '#D1E5F0', '#92C5DE', '#4393C3', '#2166AC'], type: 'diverging' },
  { key: 'RdGy',          desc_zh: '红-灰发散',             desc_en: 'Red-Grey diverging', colors: ['#B2182B', '#EF8A62', '#FDDBC7', '#FFFFFF', '#D1D1D1', '#999999', '#4D4D4D'], type: 'diverging' },
  { key: 'PuOr',          desc_zh: '紫-橙发散',             desc_en: 'Purple-Orange diverging', colors: ['#7F3B08', '#B35806', '#E08214', '#FDB863', '#FEE0B2', '#F7F7F7', '#D8DAEB', '#B2ABD2', '#8073AC', '#542788', '#2D0042'], type: 'diverging' },
  { key: 'BrBG',          desc_zh: '棕-蓝发散',             desc_en: 'Brown-Blue diverging', colors: ['#8C510A', '#D8B365', '#F6E8C3', '#C7DBEA', '#5AB4AC', '#01665E'], type: 'diverging' },
  { key: 'BuRd',          desc_zh: '蓝红双向',              desc_en: 'Blue-Red diverging', colors: ['#B2182B', '#D6604D', '#F4A582', '#FDDBC7', '#D1E5F0', '#92C5DE', '#4393C3', '#2166AC'], type: 'diverging' },
  { key: 'BlueYellowRed', desc_zh: '蓝-黄-红',              desc_en: 'Blue-Yellow-Red',   colors: ['#2166AC', '#4393C3', '#92C5DE', '#D1E5F0', '#FDDBC7', '#F4A582', '#D6604D', '#B2182B'], type: 'diverging' },
  { key: 'PRGn',          desc_zh: '紫-绿发散',             desc_en: 'Purple-Green diverging', colors: ['#762A83', '#9970AB', '#C2A5CF', '#E7D4E8', '#F7F7F7', '#D9F0D3', '#A6DBA0', '#5AAE61', '#1B7837'], type: 'diverging' },
  { key: 'coolwarm',      desc_zh: '蓝-红发散',             desc_en: 'Blue-Red diverging', colors: ['#3B4CC0', '#6787D9', '#9ABBF0', '#C0D4F0', '#E0D5E8', '#F0B8C0', '#D97A8C', '#B40E4C'], type: 'diverging' },
  { key: 'coolwarm_r',    desc_zh: '红-蓝发散',             desc_en: 'Red-Blue diverging', colors: ['#B40E4C', '#D97A8C', '#F0B8C0', '#E0D5E8', '#C0D4F0', '#9ABBF0', '#6787D9', '#3B4CC0'], type: 'diverging' },

  // 暖色系
  { key: 'Reds',          desc_zh: '红色渐变',              desc_en: 'Red gradient',    colors: ['#FCBBA1', '#FC9272', '#FB6A4A', '#EF3B2C', '#CB181D', '#99000D'], type: 'sequential' },
  { key: 'YlGn',          desc_zh: '黄-绿渐变',              desc_en: 'Yellow-Green gradient', colors: ['#FFFFCC', '#C7E9B4', '#78C679', '#41AB5D', '#006837'], type: 'sequential' },
  { key: 'YlOrRd',        desc_zh: '黄-橙-红',               desc_en: 'Yellow-Orange-Red', colors: ['#FFFFB2', '#FED976', '#FEB24C', '#FD8D3C', '#FC4E2A', '#E31A1C', '#B10026'], type: 'sequential' },
  { key: 'RdYlGn',        desc_zh: '红-黄-绿',               desc_en: 'Red-Yellow-Green', colors: ['#D73027', '#FC8D59', '#FEE08B', '#D9EF8B', '#91CF60', '#1A9850'], type: 'diverging' },
  { key: 'Spectral',      desc_zh: '光谱色',                 desc_en: 'Spectral (scientific)', colors: ['#9E0142', '#D53E4F', '#F46D43', '#FDAE61', '#FEE08B', '#E6F598', '#ABDDA4', '#66C2A5', '#3288BD', '#5E4FA2'], type: 'diverging' },

  // 紫/粉色系
  { key: 'PuBu',          desc_zh: '紫-蓝渐变',              desc_en: 'Purple-Blue gradient', colors: ['#FFF7F3', '#ECE7F2', '#D2D4E8', '#A6BDDB', '#74A9CF', '#3690C0', '#0570B0', '#034E7B'], type: 'sequential' },
  { key: 'RdPu',          desc_zh: '红-紫渐变',              desc_en: 'Red-Purple gradient', colors: ['#FFF7F3', '#FDE0DD', '#FCC5C0', '#FA9FB5', '#F768A1', '#DD3497', '#AE017E', '#7A0177'], type: 'sequential' },
  { key: 'BuPu',          desc_zh: '蓝-紫渐变',              desc_en: 'Blue-Purple gradient', colors: ['#EDF8FB', '#B3CDE3', '#8C96C6', '#6BAED6', '#4E004F'], type: 'sequential' },

  // 柔和色系
  { key: 'Pastel1',       desc_zh: '柔和色1',                desc_en: 'Pastel 1 (categorical)', colors: ['#FBB4AE', '#B3CDE3', '#CCEBC5', '#DECBE4', '#FED9A6', '#FFFFCC', '#F2F2F2', '#CAB8D5', '#FFED6F', '#BC80BD'], type: 'categorical' },
  { key: 'Pastel2',       desc_zh: '柔和色2',                desc_en: 'Pastel 2 (categorical)', colors: ['#B3E2CD', '#FDCDAC', '#CBD5E8', '#F4CAE4', '#E6F5C9', '#FFF2AE', '#D9D9D9', '#FB8071', '#80B1D3', '#FCCDE5'], type: 'categorical' },
  { key: 'Set2',          desc_zh: '集合色2',                 desc_en: 'Set2 (categorical)', colors: ['#66C2A5', '#FC8D62', '#8DA0CB', '#E78AC3', '#A6D854', '#FFD8A8', '#E5C494', '#B3B3B3'], type: 'categorical' },
  { key: 'tab10',         desc_zh: '分类色1（tab10）',        desc_en: 'Tab10 (categorical)', colors: ['#4C72B0', '#DD8452', '#55A868', '#C44E52', '#8172B2', '#937860', '#DA8BC3', '#8C8C8C', '#CCB974', '#64B5CD'], type: 'categorical' },
]

// 全局默认色系（所有用户的默认设置）
export const DEFAULT_COLORMAP_PARAMS: Record<string, string> = {
  china_cooling_energy: 'Blues',      // 制冷节能：蓝色渐变
  china_heating_energy: 'Reds',       // 制热节能：红色渐变
  china_total_energy: 'coolwarm',     // 总节能：蓝-红发散
  china_cooling_co2: 'Greens',        // 制冷CO2减排：绿色渐变
  china_heating_co2: 'Greens',        // 制热CO2减排：绿色渐变
  china_total_co2: 'Greens',          // 总CO2减排：绿色渐变
  world_cooling_energy: 'Blues',      // 制冷节能：蓝色渐变
  world_heating_energy: 'Reds',       // 制热节能：红色渐变
  world_total_energy: 'coolwarm',     // 总节能：蓝-红发散
  world_cooling_co2: 'Greens',        // 制冷CO2减排：绿色渐变
  world_heating_co2: 'Greens',         // 制热CO2减排：绿色渐变
  world_total_co2: 'Greens',          // 总CO2减排：绿色渐变
}

// 存储用户默认色系的 localStorage 键
const STORAGE_KEY = 'material-colormap-defaults'

export function loadSavedColormaps(): Record<string, string> | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw)
  } catch {}
  return null
}

export function saveColormapsAsDefault(params: Record<string, string>): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(params))
  } catch {}
}

interface ColormapPreviewProps {
  colors: string[]
}

function ColormapPreview({ colors }: ColormapPreviewProps) {
  const gradient = colors.join(', ')
  return (
    <div
      className="h-3 flex-1 rounded"
      style={{ background: `linear-gradient(to right, ${gradient})` }}
      aria-hidden="true"
    />
  )
}

// ==================== 单个地图的色系选择器 ====================
interface SingleMapSelectorProps {
  mapKey: string
  label: string
  value: string
  onChange: (mapKey: string, cmapKey: string) => void
  isZh: boolean
}

function SingleMapSelector({ mapKey, label, value, onChange, isZh }: SingleMapSelectorProps) {
  const current = COLORMAP_LIST.find((c) => c.key === value) || COLORMAP_LIST[0]

  return (
    <div className="flex items-center gap-3 rounded-lg border border-border bg-bg-elevated p-3 transition-all duration-150 hover:border-border-light">
      <div className="w-36 flex-shrink-0 text-sm font-medium text-text-secondary">{label}</div>

      {/* 颜色预览条 */}
      <div className="flex flex-1 items-center gap-2">
        <ColormapPreview colors={current.colors} />
      </div>

      {/* 下拉选择 */}
      <select
        value={value}
        onChange={(e) => onChange(mapKey, e.target.value)}
        className="rounded-lg border border-border bg-bg-default px-3 py-1.5 text-xs text-text-primary transition-all duration-150 focus:outline-none focus:ring-2 focus-visible:ring-2 focus-visible:ring-accent/50 focus-visible:border-accent/50 hover:border-border-light"
        title={isZh ? current.desc_zh : current.desc_en}
      >
        {COLORMAP_LIST.map((cmap) => (
          <option key={cmap.key} value={cmap.key}>
            {isZh ? cmap.desc_zh : cmap.desc_en}
          </option>
        ))}
      </select>
    </div>
  )
}

// ==================== 主组件 ====================
interface ColormapSelectorProps {
  weatherGroup: 'china' | 'world' | 'world_weather2025'
  value: Record<string, string>
  onChange: (params: Record<string, string>) => void
}

export default function ColormapSelector({ weatherGroup, value, onChange }: ColormapSelectorProps) {
  const { i18n } = useTranslation()
  const isZh = (i18n.language || 'zh').startsWith('zh')

  // 用默认值初始化（或加载已保存的）
  const [localParams, setLocalParams] = useState<Record<string, string>>(() => {
    const saved = loadSavedColormaps()
    if (saved) return saved
    // 根据 weatherGroup 筛选对应默认
    const prefix = weatherGroup === 'china' ? 'china' : 'world'
    const defaults: Record<string, string> = {}
    for (const [k, v] of Object.entries(DEFAULT_COLORMAP_PARAMS)) {
      if (k.startsWith(prefix)) {
        defaults[k] = v
      }
    }
    return defaults
  })

  // 当 weatherGroup 变化时，重新初始化
  useEffect(() => {
    const saved = loadSavedColormaps()
    if (saved) {
      setLocalParams(saved)
      return
    }
    const prefix = weatherGroup === 'china' ? 'china' : 'world'
    const defaults: Record<string, string> = {}
    for (const [k, v] of Object.entries(DEFAULT_COLORMAP_PARAMS)) {
      if (k.startsWith(prefix)) {
        defaults[k] = v
      }
    }
    setLocalParams(defaults)
  }, [weatherGroup])

  const handleChange = (mapKey: string, cmapKey: string) => {
    const next = { ...localParams, [mapKey]: cmapKey }
    setLocalParams(next)
    onChange(next)
  }

  const handleReset = () => {
    const prefix = weatherGroup === 'china' ? 'china' : 'world'
    const defaults: Record<string, string> = {}
    for (const [k, v] of Object.entries(DEFAULT_COLORMAP_PARAMS)) {
      if (k.startsWith(prefix)) {
        defaults[k] = v
      }
    }
    setLocalParams(defaults)
    onChange(defaults)
  }

  const handleSaveAsDefault = () => {
    saveColormapsAsDefault(localParams)
    onChange(localParams)
  }

  // 根据地图类型确定标签
  const labels = {
    cooling_energy: isZh ? '制冷节能' : 'Cooling Energy',
    heating_energy: isZh ? '制热节能' : 'Heating Energy',
    total_energy: isZh ? '总节能' : 'Total Energy',
    cooling_co2: isZh ? '制冷CO₂减排' : 'Cooling CO₂',
    heating_co2: isZh ? '制热CO₂减排' : 'Heating CO₂',
    total_co2: isZh ? '总CO₂减排' : 'Total CO₂',
  }

  const prefix = weatherGroup === 'china' ? 'china' : 'world'
  const maps = Object.keys(labels) as Array<keyof typeof labels>

  return (
    <Card className="glass-light">
      <CardHeader>
        <CardTitle>{isZh ? '地图色系选择' : 'Map Colormap Settings'}</CardTitle>
        <div className="mt-1 flex flex-wrap gap-2">
          <Button size="xs" variant="secondary" onClick={handleReset}>
            {isZh ? '重置默认' : 'Reset'}
          </Button>
          <Button size="xs" variant="secondary" onClick={handleSaveAsDefault}>
            {isZh ? '保存为默认' : 'Save as Default'}
          </Button>
        </div>
      </CardHeader>

      <div className="space-y-2">
        {maps.map((mapType) => {
          const mapKey = `${prefix}_${mapType}` as string
          const currentValue = localParams[mapKey] || DEFAULT_COLORMAP_PARAMS[mapKey] || 'Blues'
          return (
            <SingleMapSelector
              key={mapKey}
              mapKey={mapKey}
              label={labels[mapType]}
              value={currentValue}
              onChange={handleChange}
              isZh={isZh}
            />
          )
        })}
      </div>
    </Card>
  )
}
