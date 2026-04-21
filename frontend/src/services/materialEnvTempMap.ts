import { api } from './api'
import type { CreateJobRequest, CreateJobResponse } from './schemas'

export interface MaterialPhase {
  temperature: number  // 温度 (°C)
  emissivity: number   // 发射率 (0-1)
  absorptivity: number // 吸收率 (0-1)
}

export interface MaterialEnvTempMapParams {
  weather_group: 'china' | 'world' | 'world_weather2025'  // 天气组选择
  phases: MaterialPhase[]  // 材料相态配置
  transition_mode: 'gradient' | 'step'  // 相态变化模式：渐变/突变
  h_coefficient?: number  // 对流换热系数（W/m²·K），默认 20
  /** 辐射制冷效率经验修正系数（0.5~1.0），用于补偿简化宽带模型对制冷效果的高估，默认 0.75 */
  cooling_efficiency_factor?: number
}

export async function createMaterialEnvTempMapJob({
  params,
  remark,
}: {
  params: MaterialEnvTempMapParams
  remark?: string
}): Promise<CreateJobResponse> {
  const req: CreateJobRequest = {
    type: 'material_env_temp_map',
    remark,
    params: params as any,
  }
  const { data } = await api.post<CreateJobResponse>('/jobs', req)
  return data
}
