import { HELP_DOCS_RAW, type HelpDocKey } from './generatedHelpDocs'

export type { HelpDocKey }

const TITLES: Record<HelpDocKey, string> = {
  cooling: '辐射制冷（Cooling）',
  heating: '辐射制热（Heating）',
  wind_cloud: '风速与制冷效率云图（Wind cloud）',
  solar_efficiency: '光热转化效率计算（理论光热 vs 光照）',
  emissivity_solar_cloud: '大气发射率 - 太阳光强云图',
  power_components: '功率分量曲线图（Power components）',
  angular_power: '天空窗口角分辨分析（Angular profile）',
  in_situ_era5: '原位模拟（ERA5 in-situ simulation）',
  material_comparison: '功量地图绘制（Power Map）',
}

export function getHelpDoc(key: HelpDocKey): { title: string; md: string } {
  return { title: TITLES[key], md: HELP_DOCS_RAW[key] }
}

