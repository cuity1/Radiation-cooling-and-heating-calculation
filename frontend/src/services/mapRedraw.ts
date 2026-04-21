/** 解析后的 CSV 数据 */
export interface KoppenDataEntry {
  FQ: string   // Köppen 气候区代码，如 'Af', 'Cfa' 等
  value: number
}

export type KoppenData = KoppenDataEntry[]

/**
 * 解析 CSV 文本（客户端直接解析，不需要后端）
 * 只需要 FQ 列（气候区代码）和任意一列数值即可。
 * 支持的 CSV 格式（任意列顺序）：
 *   ID,QID,FQ,results
 *   FQ,VALUE
 *   fq,value
 *   气候区,结果
 *
 * @param text CSV 文件原始文本
 * @returns 解析后的 KoppenData 数组
 */
export function parseKoppenCSV(text: string): KoppenData {
  const lines = text.trim().split(/\r?\n/)
  if (lines.length < 2) return []

  const header = lines[0].split(',').map((h) => h.trim().toLowerCase())

  // 找 FQ 所在列（支持多种命名）
  const fqIndex = header.findIndex(
    (h) => h === 'fq' || h === 'zone' || h === 'climate' || h === 'koppen'
  )
  if (fqIndex === -1) return []

  // 找数值列（排除 FQ 本身，优先找 results / value / data 等）
  const valueCandidates = ['results', 'value', 'data', 'val', 'num']
  let valueIndex = -1
  for (const candidate of valueCandidates) {
    const idx = header.findIndex((h) => h === candidate)
    if (idx !== -1) {
      valueIndex = idx
      break
    }
  }
  // 如果没找到候选名称，就用 FQ 后面的第一个非空列
  if (valueIndex === -1) {
    valueIndex = header.findIndex((_, i) => i !== fqIndex && header[i] !== '')
  }
  if (valueIndex === -1) return []

  const result: KoppenData = []
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim()
    if (!line) continue
    const parts = line.split(',')
    if (parts.length <= Math.max(fqIndex, valueIndex)) continue

    const fq = parts[fqIndex]?.trim()
    const rawValue = parts[valueIndex]?.trim()
    if (!fq || !rawValue) continue

    const value = parseFloat(rawValue)
    if (isNaN(value)) continue

    result.push({ FQ: fq, value })
  }

  return result
}

/** 33 个标准 Köppen 气候区代码（用于定义绘图顺序） */
export const KOPPEN_CODES = [
  'Af', 'Am', 'As', 'Aw',
  'BSh', 'BSk', 'BWh', 'BWk',
  'Cfa', 'Cfb', 'Cfc',
  'Csa', 'Csb', 'Csc',
  'Cwa', 'Cwb', 'Cwc',
  'Dfa', 'Dfb', 'Dfc', 'Dfd',
  'Dsa', 'Dsb', 'Dsc', 'Dsd',
  'Dwa', 'Dwb', 'Dwc', 'Dwd',
  'EF', 'ET', 'EF+ET',
] as const

/** 获取所有代码对应的数值数组（缺少的代码返回 0） */
export function buildOrderedValues(
  data: KoppenData,
  orderedCodes: readonly string[] = KOPPEN_CODES,
): number[] {
  const map = new Map<string, number>()
  for (const entry of data) {
    map.set(entry.FQ, entry.value)
  }
  return orderedCodes.map((code) => map.get(code) ?? 0)
}

/** 获取数据的最小值和最大值 */
export function getDataRange(data: KoppenData): [number, number] {
  if (data.length === 0) return [0, 1]
  const values = data.map((d) => d.value)
  return [Math.min(...values), Math.max(...values)]
}

/** 获取自动计算的刻度数组（nicks 自适应） */
export function getNiceTicks(vmin: number, vmax: number, count = 6): number[] {
  if (vmin === vmax) return [vmin]
  const range = vmax - vmin
  const rawStep = range / (count - 1)
  const magnitude = Math.pow(10, Math.floor(Math.log10(rawStep)))
  const normalized = rawStep / magnitude
  let niceStep: number
  if (normalized <= 1) niceStep = 1 * magnitude
  else if (normalized <= 2) niceStep = 2 * magnitude
  else if (normalized <= 5) niceStep = 5 * magnitude
  else niceStep = 10 * magnitude

  const ticks: number[] = []
  let tick = Math.ceil(vmin / niceStep) * niceStep
  while (tick <= vmax + niceStep * 0.001) {
    ticks.push(tick)
    tick += niceStep
  }
  return ticks
}
