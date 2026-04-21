import { useMemo } from 'react'
import Plot from 'react-plotly.js'
import type { MaterialPhase } from '../services/powerMap'
import { getPlotlyLayout } from '../lib/plotlyConfig'

export interface MaterialPhasePreviewChartProps {
  phases: MaterialPhase[]
  transitionMode: 'gradient' | 'step'
}

/**
 * 根据温度获取材料参数（与后端逻辑一致）
 */
function getMaterialProperties(
  temp: number,
  phases: MaterialPhase[],
  mode: 'gradient' | 'step'
): { emissivity: number; absorptivity: number } {
  if (phases.length === 0) {
    return { emissivity: 0.9, absorptivity: 0.6 }
  }

  if (mode === 'gradient') {
    // 渐变模式：高斯插值
    if (phases.length === 1) {
      return {
        emissivity: phases[0].emissivity,
        absorptivity: phases[0].absorptivity,
      }
    }

    // 计算带宽参数σ（基于数据点的平均间距）
    const sortedPhases = [...phases].sort((a, b) => a.temperature - b.temperature)
    const tempDiffs: number[] = []
    for (let i = 0; i < sortedPhases.length - 1; i++) {
      tempDiffs.push(Math.abs(sortedPhases[i + 1].temperature - sortedPhases[i].temperature))
    }
    const avgDiff = tempDiffs.length > 0 
      ? tempDiffs.reduce((sum, diff) => sum + diff, 0) / tempDiffs.length 
      : 5.0 // 默认5°C
    // 降低带宽：σ设为平均间距的0.25倍，至少0.5°C（更小的带宽使插值更接近数据点）
    const sigma = Math.max(avgDiff * 0.4, 0.5)

    // 高斯加权插值
    let weightedEmissivity = 0
    let weightedAbsorptivity = 0
    let totalWeight = 0

    for (const phase of phases) {
      const dist = Math.abs(phase.temperature - temp)
      // 高斯核函数：exp(-(x-xi)^2 / (2*σ^2))
      const weight = Math.exp(-(dist * dist) / (2 * sigma * sigma))
      
      weightedEmissivity += phase.emissivity * weight
      weightedAbsorptivity += phase.absorptivity * weight
      totalWeight += weight
    }

    // 归一化
    if (totalWeight > 0) {
      return {
        emissivity: weightedEmissivity / totalWeight,
        absorptivity: weightedAbsorptivity / totalWeight,
      }
    }

    // 如果权重为0（理论上不会发生），返回最近的点
    const closestPhase = phases.reduce((closest, phase) => {
      const closestDist = Math.abs(closest.temperature - temp)
      const currentDist = Math.abs(phase.temperature - temp)
      return currentDist < closestDist ? phase : closest
    })
    return {
      emissivity: closestPhase.emissivity,
      absorptivity: closestPhase.absorptivity,
    }
  } else {
    // 突变模式：使用最近温度点
    const closestPhase = phases.reduce((closest, phase) => {
      const closestDist = Math.abs(closest.temperature - temp)
      const currentDist = Math.abs(phase.temperature - temp)
      return currentDist < closestDist ? phase : closest
    })
    
    return {
      emissivity: closestPhase.emissivity,
      absorptivity: closestPhase.absorptivity,
    }
  }

  // 默认返回第一个相态的值
  return {
    emissivity: phases[0].emissivity,
    absorptivity: phases[0].absorptivity,
  }
}

export default function MaterialPhasePreviewChart({
  phases,
  transitionMode,
}: MaterialPhasePreviewChartProps) {
  // 生成插值曲线数据
  const chartData = useMemo(() => {
    if (phases.length === 0) {
      return {
        temperatureRange: [],
        emissivityCurve: [],
        absorptivityCurve: [],
        phasePoints: { temperature: [], emissivity: [], absorptivity: [] },
      }
    }

    // 确定温度范围（扩展一些以便显示）
    const sortedPhases = [...phases].sort((a, b) => a.temperature - b.temperature)
    const minTemp = Math.min(...phases.map((p) => p.temperature))
    const maxTemp = Math.max(...phases.map((p) => p.temperature))
    const tempRange = maxTemp - minTemp
    const padding = Math.max(5, tempRange * 0.1) // 至少5°C的边距，或10%的范围
    
    const startTemp = Math.floor(minTemp - padding)
    const endTemp = Math.ceil(maxTemp + padding)
    
    // 生成温度点（每0.5°C一个点，用于平滑曲线）
    const temperatureRange: number[] = []
    const emissivityCurve: number[] = []
    const absorptivityCurve: number[] = []
    
    for (let temp = startTemp; temp <= endTemp; temp += 0.5) {
      const props = getMaterialProperties(temp, phases, transitionMode)
      temperatureRange.push(temp)
      emissivityCurve.push(props.emissivity)
      absorptivityCurve.push(props.absorptivity)
    }

    // 提取相态点数据（用于在图上标记）
    const phasePoints = {
      temperature: phases.map((p) => p.temperature),
      emissivity: phases.map((p) => p.emissivity),
      absorptivity: phases.map((p) => p.absorptivity),
    }

    return {
      temperatureRange,
      emissivityCurve,
      absorptivityCurve,
      phasePoints,
    }
  }, [phases, transitionMode])

  if (phases.length === 0) {
    return (
      <div className="rounded-field border border-border glass-light p-8 text-center text-sm text-text-muted">
        请添加至少一个相态点以预览曲线
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* 发射率-温度曲线 */}
      <div className="rounded-field border border-border glass-light p-4">
        <div className="mb-3">
          <div className="text-sm font-semibold text-text-primary">发射率 - 温度曲线</div>
          <div className="text-xs text-text-muted mt-1">
            {transitionMode === 'gradient' ? '线性插值模式' : '突变模式（最近值）'}
          </div>
        </div>
        <div className="h-[300px]">
          <Plot
            data={[
              {
                x: chartData.temperatureRange,
                y: chartData.emissivityCurve,
                type: 'scatter',
                mode: 'lines',
                name: '插值曲线',
                line: { color: 'rgba(54, 162, 235, 0.8)', width: 2 },
              },
              {
                x: chartData.phasePoints.temperature,
                y: chartData.phasePoints.emissivity,
                type: 'scatter',
                mode: 'markers',
                name: '相态点',
                marker: {
                  color: 'rgba(255, 99, 132, 1)',
                  size: 8,
                  symbol: 'circle',
                },
              },
            ]}
            layout={getPlotlyLayout({
              autosize: true,
              margin: { l: 60, r: 20, t: 20, b: 50 },
              xaxis: {
                title: {
                  text: '温度 (°C)',
                  // 减小 standoff，使"温度(°C)"整体向上靠近坐标轴，避免与曲线重叠
                  standoff: 0,
                },
              },
              yaxis: {
                title: { text: '发射率 (ε)' },
                range: [0, 1.05],
              },
              legend: {
                orientation: 'h',
                y: -0.2,
                x: 0.5,
                xanchor: 'center',
              },
              showlegend: true,
            })}
            config={{
              displayModeBar: false,
              responsive: true,
            }}
            style={{ width: '100%', height: '100%' }}
          />
        </div>
      </div>

      {/* 吸收率-温度曲线 */}
      <div className="rounded-field border border-border glass-light p-4">
        <div className="mb-3">
          <div className="text-sm font-semibold text-text-primary">吸收率 - 温度曲线</div>
          <div className="text-xs text-text-muted mt-1">
            {transitionMode === 'gradient' ? '线性插值模式' : '突变模式（最近值）'}
          </div>
        </div>
        <div className="h-[300px]">
          <Plot
            data={[
              {
                x: chartData.temperatureRange,
                y: chartData.absorptivityCurve,
                type: 'scatter',
                mode: 'lines',
                name: '插值曲线',
                line: { color: 'rgba(75, 192, 192, 0.8)', width: 2 },
              },
              {
                x: chartData.phasePoints.temperature,
                y: chartData.phasePoints.absorptivity,
                type: 'scatter',
                mode: 'markers',
                name: '相态点',
                marker: {
                  color: 'rgba(255, 99, 132, 1)',
                  size: 8,
                  symbol: 'circle',
                },
              },
            ]}
            layout={getPlotlyLayout({
              autosize: true,
              margin: { l: 60, r: 20, t: 20, b: 50 },
              xaxis: {
                title: {
                  text: '温度 (°C)',
                  // 同样上移 x 轴标题，保持两张图风格一致
                  standoff: 0,
                },
              },
              yaxis: {
                title: { text: '吸收率 (α)' },
                range: [0, 1.05],
              },
              legend: {
                orientation: 'h',
                y: -0.2,
                x: 0.5,
                xanchor: 'center',
              },
              showlegend: true,
            })}
            config={{
              displayModeBar: false,
              responsive: true,
            }}
            style={{ width: '100%', height: '100%' }}
          />
        </div>
      </div>
    </div>
  )
}
