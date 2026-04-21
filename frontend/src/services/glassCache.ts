/**
 * 玻璃对比工具参数本地缓存服务
 *
 * 功能：
 * - 自动保存参数到 localStorage
 * - 页面加载时自动恢复参数
 * - 缓存版本管理（兼容旧数据格式）
 * - 导入/导出参数配置
 * - 清除缓存
 */

import type { GlassScenario, GlobalParams } from './glass_materials'

/** 缓存版本号，用于数据迁移 */
const CACHE_VERSION = 1

/** localStorage 存储键 */
const STORAGE_KEY = 'glass-comparison-params'

/** 自动保存防抖延迟 (ms) */
const AUTO_SAVE_DEBOUNCE_MS = 1000

/** 自动保存定时器引用 */
let autoSaveTimer: ReturnType<typeof setTimeout> | null = null

/** 缓存数据结构 */
interface GlassParamsCache {
  version: number
  timestamp: number
  params: {
    weather_group: 'china' | 'world' | 'world_weather2025'
    idf_template_dir: string
    enable_latent_heat: boolean
    wet_fraction: number
    scenarios: GlassScenario[]
    global_params: GlobalParams
    colormap_params: Record<string, string>
  }
}

/** 默认玻璃参数值 */
export const DEFAULT_GLASS_VALUES = {
  Name: 'duibi',
  Thickness: 0.003,
  SolarTransmittance: 0.9,
  SolarReflectanceFront: 0.1,
  SolarReflectanceBack: 0,
  VisibleTransmittance: 0.9,
  VisibleReflectanceFront: 0.1,
  VisibleReflectanceBack: 0,
  InfraredTransmittance: 0,
  Emissivity: 0.84,
}

/** 默认全局参数 */
export const DEFAULT_GLOBAL_PARAMS: GlobalParams = {
  global_ach: 0.5,
  global_lighting_w_per_m2: 2,
  global_thermostat_heat_c: 20,
  global_thermostat_cool_c: 26,
  global_people_per_m2: 0.05,
  phase_change_temp: 26,
}

/** 默认场景配置 */
export function getDefaultScenarios(): GlassScenario[] {
  return [
    {
      name: '基准玻璃',
      desc: '普通透明玻璃 - duibi.idf 中的基准玻璃对象',
      glass: {
        ...DEFAULT_GLASS_VALUES,
        Name: 'duibi',
        SolarTransmittance: 0.9,
        Emissivity: 0.84,
      },
    },
    {
      name: '实验玻璃-高温态',
      desc: '在下方填写实验组玻璃在高温🔥时候的理化参数',
      glass: {
        ...DEFAULT_GLASS_VALUES,
        Name: 'shiyanhigh',
        SolarTransmittance: 0.344,
        VisibleTransmittance: 0.278,
        Emissivity: 0.86,
      },
    },
    {
      name: '实验玻璃-低温态',
      desc: '在下方填写实验组玻璃在低温❄时候的理化参数',
      glass: {
        ...DEFAULT_GLASS_VALUES,
        Name: 'shiyanlow',
        SolarTransmittance: 0.65,
        VisibleTransmittance: 0.639,
        Emissivity: 0.9,
      },
    },
  ]
}

/**
 * 获取默认色系参数
 */
export function getDefaultColormapParams(weatherGroup: 'china' | 'world' | 'world_weather2025'): Record<string, string> {
  const prefix = weatherGroup === 'china' ? 'china' : 'world'
  const defaults: Record<string, string> = {}

  const defaultParams: Record<string, string> = {
    'china_heating_energy': 'YlOrRd',
    'china_cooling_energy': 'YlGnBu',
    'china_heating_load': 'OrRd',
    'china_cooling_load': 'GnBu',
    'china_peak_heat': 'Reds',
    'china_peak_cool': 'Blues',
    'world_heating_energy': 'YlOrRd',
    'world_cooling_energy': 'YlGnBu',
    'world_heating_load': 'OrRd',
    'world_cooling_load': 'GnBu',
    'world_peak_heat': 'Reds',
    'world_peak_cool': 'Blues',
    'world_weather2025_heating_energy': 'YlOrRd',
    'world_weather2025_cooling_energy': 'YlGnBu',
    'world_weather2025_heating_load': 'OrRd',
    'world_weather2025_cooling_load': 'GnBu',
    'world_weather2025_peak_heat': 'Reds',
    'world_weather2025_peak_cool': 'Blues',
  }

  for (const [k, v] of Object.entries(defaultParams)) {
    if (k.startsWith(prefix)) {
      defaults[k] = v
    }
    if (k.startsWith('world_weather2025') && prefix === 'world_weather2025') {
      defaults[k] = v
    }
  }

  return defaults
}

/**
 * 创建空缓存数据结构
 */
function createEmptyCache(): GlassParamsCache {
  return {
    version: CACHE_VERSION,
    timestamp: Date.now(),
    params: {
      weather_group: 'china',
      idf_template_dir: 'model/model1',
      enable_latent_heat: false,
      wet_fraction: 1.0,
      scenarios: getDefaultScenarios(),
      global_params: DEFAULT_GLOBAL_PARAMS,
      colormap_params: getDefaultColormapParams('china'),
    },
  }
}

/**
 * 检查 localStorage 是否可用
 */
function isLocalStorageAvailable(): boolean {
  try {
    const test = '__localStorage_test__'
    localStorage.setItem(test, test)
    localStorage.removeItem(test)
    return true
  } catch {
    return false
  }
}

/**
 * 保存参数到 localStorage
 */
export function saveParamsToCache(params: GlassParamsCache['params']): boolean {
  if (!isLocalStorageAvailable()) {
    console.warn('localStorage is not available')
    return false
  }

  try {
    const cache: GlassParamsCache = {
      version: CACHE_VERSION,
      timestamp: Date.now(),
      params,
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(cache))
    return true
  } catch (err) {
    console.error('Failed to save params to cache:', err)
    return false
  }
}

/**
 * 从 localStorage 加载参数
 */
export function loadParamsFromCache(): GlassParamsCache['params'] | null {
  if (!isLocalStorageAvailable()) {
    return null
  }

  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null

    const cache = JSON.parse(raw) as GlassParamsCache

    // 版本检查和数据迁移
    if (cache.version !== CACHE_VERSION) {
      console.log('Cache version mismatch, clearing old cache')
      clearCache()
      return null
    }

    // 验证必要字段
    if (!cache.params || !Array.isArray(cache.params.scenarios)) {
      console.warn('Invalid cache structure, clearing')
      clearCache()
      return null
    }

    return cache.params
  } catch (err) {
    console.error('Failed to load params from cache:', err)
    clearCache()
    return null
  }
}

/**
 * 清除缓存
 */
export function clearCache(): boolean {
  if (!isLocalStorageAvailable()) {
    return false
  }

  try {
    localStorage.removeItem(STORAGE_KEY)
    return true
  } catch (err) {
    console.error('Failed to clear cache:', err)
    return false
  }
}

/**
 * 检查是否有缓存
 */
export function hasCache(): boolean {
  if (!isLocalStorageAvailable()) {
    return false
  }
  return localStorage.getItem(STORAGE_KEY) !== null
}

/**
 * 获取缓存时间戳
 */
export function getCacheTimestamp(): number | null {
  if (!isLocalStorageAvailable()) {
    return null
  }

  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null

    const cache = JSON.parse(raw) as GlassParamsCache
    return cache.timestamp
  } catch {
    return null
  }
}

/**
 * 格式化时间戳
 */
export function formatCacheTime(timestamp: number, locale: string = 'zh-CN'): string {
  const date = new Date(timestamp)
  return date.toLocaleString(locale, {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * 防抖保存
 */
export function debouncedSave(params: GlassParamsCache['params']): void {
  if (autoSaveTimer) {
    clearTimeout(autoSaveTimer)
  }
  autoSaveTimer = setTimeout(() => {
    saveParamsToCache(params)
    autoSaveTimer = null
  }, AUTO_SAVE_DEBOUNCE_MS)
}

/**
 * 取消待执行的自动保存
 */
export function cancelPendingSave(): void {
  if (autoSaveTimer) {
    clearTimeout(autoSaveTimer)
    autoSaveTimer = null
  }
}

/**
 * 导出参数为 JSON 文件
 */
export function exportParams(params: GlassParamsCache['params']): void {
  const exportData = {
    version: CACHE_VERSION,
    exportTime: new Date().toISOString(),
    params,
  }

  const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)

  const a = document.createElement('a')
  a.href = url
  a.download = `glass-params-${new Date().toISOString().slice(0, 10)}.json`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

/**
 * 从文件导入参数
 */
export function importParamsFromFile(file: File): Promise<GlassParamsCache['params'] | null> {
  return new Promise((resolve) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      try {
        const content = e.target?.result as string
        const data = JSON.parse(content)

        if (data.version !== CACHE_VERSION) {
          console.warn('Import version mismatch')
        }

        if (data.params && Array.isArray(data.params.scenarios)) {
          resolve(data.params)
        } else {
          console.warn('Invalid import data structure')
          resolve(null)
        }
      } catch (err) {
        console.error('Failed to parse import file:', err)
        resolve(null)
      }
    }
    reader.onerror = () => resolve(null)
    reader.readAsText(file)
  })
}
