import { api } from './api'
import type { CreateJobRequest, CreateJobResponse } from './schemas'

export interface MaterialPhase {
  temperature: number  // 温度 (°C)
  emissivity: number   // 发射率 (0-1)
  absorptivity: number // 吸收率 (0-1)
}

export interface RadiationCoolingClothingParams {
  weather_group: 'china' | 'world' | 'world_weather2025'  // 天气组选择
  phases: MaterialPhase[]  // 材料相态配置
  transition_mode: 'gradient' | 'step'  // 相态变化模式：渐变/突变
  enable_latent_heat?: boolean  // 是否启用蒸发冷却（使用天气文件中的相对湿度）
  wet_fraction?: number  // 蒸发冷却强度（0-1，可选，默认1.0）
  clothing_area_per_person: number  // 衣物面积/人（m²）
}

export async function createRadiationCoolingClothingJob({
  params,
  remark,
}: {
  params: RadiationCoolingClothingParams
  remark?: string
}): Promise<CreateJobResponse> {
  const req: CreateJobRequest = {
    type: 'radiation_cooling_clothing',
    remark,
    params: params as any,
  }
  const { data } = await api.post<CreateJobResponse>('/jobs', req)
  return data
}
