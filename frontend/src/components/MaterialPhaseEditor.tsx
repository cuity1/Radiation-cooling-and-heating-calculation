import { useState, useMemo } from 'react'
import Button from './ui/Button'
import { Card, CardDesc, CardHeader, CardTitle } from './ui/Card'
import MaterialPhasePreviewChart from './MaterialPhasePreviewChart'
import type { MaterialPhase } from '../services/powerMap'

// 扩展MaterialPhase，添加唯一ID
interface MaterialPhaseWithId extends MaterialPhase {
  _id: string
}

function NumberInput({
  value,
  onChange,
  min,
  max,
  step,
  placeholder,
  disabled,
}: {
  value: number | null
  onChange: (value: number | null) => void
  min?: number
  max?: number
  step?: number
  placeholder?: string
  disabled?: boolean
}) {
  return (
    <input
      type="number"
      value={value ?? ''}
      onChange={(e) => {
        const val = e.target.value
        if (val === '') {
          onChange(null)
        } else {
          const num = parseFloat(val)
          if (!isNaN(num)) {
            onChange(num)
          }
        }
      }}
      min={min}
      max={max}
      step={step}
      placeholder={placeholder}
      disabled={disabled}
      className="w-full rounded-field border border-border glass-light px-3.5 py-2.5 text-sm text-text-primary placeholder:text-text-muted transition-all duration-150 focus:outline-none focus:ring-2 focus-visible:ring-2 focus-visible:ring-accent/50 focus-visible:border-accent/50 hover:border-border-light hover:bg-bg-elevated"
    />
  )
}

export interface MaterialPhaseEditorProps {
  phases: MaterialPhase[]
  onChange: (phases: MaterialPhase[]) => void
  transitionMode: 'gradient' | 'step'
  onTransitionModeChange: (mode: 'gradient' | 'step') => void
}

export default function MaterialPhaseEditor({
  phases,
  onChange,
  transitionMode,
  onTransitionModeChange,
}: MaterialPhaseEditorProps) {
  // 使用useState维护每个相态点的唯一ID（基于索引，但稳定）
  const [phaseIds] = useState<string[]>(() => {
    return Array.from({ length: 1000 }, (_, i) => `phase-${i}`) // 预生成足够多的ID
  })

  // 为每个相态点添加唯一ID（使用索引作为ID）
  const phasesWithId = useMemo(() => {
    return phases.map((phase, index) => ({
      ...phase,
      _id: phaseIds[index] || `phase-${index}`,
    })) as MaterialPhaseWithId[]
  }, [phases, phaseIds])

  const addPhase = () => {
    const newPhase: MaterialPhase = {
      temperature: 20,
      emissivity: 0.9,
      absorptivity: 0.6,
    }
    onChange([...phases, newPhase])
  }

  const removePhase = (index: number) => {
    const newPhases = phases.filter((_, i) => i !== index)
    onChange(newPhases)
  }

  const updatePhase = (index: number, field: keyof MaterialPhase, value: number | null) => {
    if (value === null) return
    
    const newPhases = [...phases]
    newPhases[index] = { ...newPhases[index], [field]: value }
    onChange(newPhases)
  }

  // 按温度排序（仅用于显示顺序，不改变实际索引）
  const sortedPhasesWithIndex = useMemo(() => {
    return phasesWithId
      .map((phase, originalIndex) => ({ phase, originalIndex }))
      .sort((a, b) => a.phase.temperature - b.phase.temperature)
  }, [phasesWithId])

  return (
    <Card className="glass-light">
      <CardHeader>
        <CardTitle>材料相态配置</CardTitle>
        <CardDesc>配置材料在不同温度下的发射率和吸收率，请使用在【制冷功率】Fully transparent环境下计算得到的光谱结果数据。相态点为环境温度</CardDesc>
      </CardHeader>

      <div className="space-y-4">
        {/* 相态变化模式选择 */}
        <div className="space-y-2">
          <div className="text-xs font-semibold text-text-secondary">相态变化模式</div>
          <div className="flex gap-2">
            <button
              onClick={() => onTransitionModeChange('gradient')}
              className={`px-4 py-2 text-sm font-medium rounded-xl border transition-colors ${
                transitionMode === 'gradient'
                  ? 'border-accent bg-accent/10 text-accent'
                  : 'border-border glass-light text-text-secondary hover:text-text-primary'
              }`}
            >
              渐变（高斯插值，平滑过渡）
            </button>
            <button
              onClick={() => onTransitionModeChange('step')}
              className={`px-4 py-2 text-sm font-medium rounded-xl border transition-colors ${
                transitionMode === 'step'
                  ? 'border-accent bg-accent/10 text-accent'
                  : 'border-border glass-light text-text-secondary hover:text-text-primary'
              }`}
            >
              突变（使用最近温度点）
            </button>
          </div>
          <div className="text-xs text-text-muted">
            {transitionMode === 'gradient'
              ? '使用高斯插值对所有相态点进行加权平均，实现平滑过渡'
              : '使用距离当前温度最近的相态点的值'}
          </div>
        </div>

        {/* 相态列表 */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="text-xs font-semibold text-text-secondary">相态点列表</div>
            <Button variant="secondary" size="sm" onClick={addPhase}>
              添加相态点
            </Button>
          </div>

          {sortedPhasesWithIndex.length === 0 ? (
            <div className="text-sm text-text-muted text-center py-4">
              暂无相态点，请至少添加一个相态点
            </div>
          ) : (
            <div className="space-y-3">
              {sortedPhasesWithIndex.map(({ phase, originalIndex }, sortedIndex) => {
                const displayIndex = sortedIndex + 1
                return (
                  <div
                    key={phase._id}
                    className="rounded-xl border border-border glass-light p-4 space-y-3"
                  >
                    <div className="flex items-center justify-between">
                      <div className="text-sm font-semibold text-text-primary">相态点 {displayIndex}</div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removePhase(originalIndex)}
                        className="text-danger hover:text-danger/80"
                      >
                        删除
                      </Button>
                    </div>
                    <div className="grid gap-3 md:grid-cols-3">
                      <div className="space-y-1">
                        <div className="text-xs font-semibold text-text-muted">温度 (°C)</div>
                        <NumberInput
                          value={phase.temperature}
                          onChange={(v) => updatePhase(originalIndex, 'temperature', v)}
                          min={-50}
                          max={100}
                          step={0.1}
                          placeholder="例如：20"
                        />
                      </div>
                      <div className="space-y-1">
                        <div className="text-xs font-semibold text-text-muted">发射率 (0-1)</div>
                        <NumberInput
                          value={phase.emissivity}
                          onChange={(v) => updatePhase(originalIndex, 'emissivity', v)}
                          min={0}
                          max={1}
                          step={0.01}
                          placeholder="例如：0.9"
                        />
                      </div>
                      <div className="space-y-1">
                        <div className="text-xs font-semibold text-text-muted">吸收率 (0-1)</div>
                        <NumberInput
                          value={phase.absorptivity}
                          onChange={(v) => updatePhase(originalIndex, 'absorptivity', v)}
                          min={0}
                          max={1}
                          step={0.01}
                          placeholder="例如：0.6"
                        />
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* 预览图表 */}
        <div className="space-y-2">
          <div className="text-xs font-semibold text-text-secondary">插值曲线预览</div>
          <MaterialPhasePreviewChart phases={phases} transitionMode={transitionMode} />
        </div>

        <div className="glass-light rounded-xl border border-border p-3 text-xs text-text-secondary">
          <strong className="text-text-primary">说明：</strong>
          <ul className="list-disc list-inside ml-2 mt-1 space-y-1">
            <li>至少需要添加一个相态点才能提交计算</li>
            <li>温度点可以重复，但建议按温度顺序排列</li>
            <li>发射率和吸收率取值范围为 0-1</li>
            <li>渐变模式：使用高斯插值对所有相态点进行加权平均，实现平滑过渡</li>
            <li>突变模式：使用距离当前温度最近的相态点的值</li>
            <li>上方图表实时显示插值后的温度-发射率和温度-吸收率曲线</li>
          </ul>
        </div>
      </div>
    </Card>
  )
}
