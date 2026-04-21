import { api } from './api'
import type { CreateJobRequest, CreateJobResponse } from './schemas'

// 材料参数接口（对应 batch_run.py 的 FIELD_ORDER）
export interface MaterialProperties {
  Name?: string | null  // 材料名称（通常与场景名称相同，如 duibi, shiyan1, shiyan2）
  Roughness?: string | null  // 粗糙度（如 Smooth, MediumRough, Rough, VeryRough）
  Thickness?: number | null  // 厚度 (m)
  Conductivity?: number | null  // 导热系数 (W/m-K)
  Density?: number | null  // 密度 (kg/m3)
  SpecificHeat?: number | null  // 比热容 (J/kg-K)
  ThermalAbsorptance?: number | null  // 热吸收率（红外发射率 ε，0-1）
  SolarAbsorptance?: number | null  // 太阳吸收率（α，0-1）
  VisibleAbsorptance?: number | null  // 可见光吸收率（0-1）
}

export interface MaterialScenario {
  name: string
  desc: string
  material: MaterialProperties  // 材料参数（对应 batch_run.py 的完整字段）
}

export interface GlobalParams {
  global_ach?: number | null  // Infiltration Air Changes per Hour (1/hr)
  global_lighting_w_per_m2?: number | null  // Lights Watts per Zone Floor Area (W/m2)
  global_thermostat_heat_c?: number | null  // Thermostat Constant Heating Setpoint (C)
  global_thermostat_cool_c?: number | null  // Thermostat Constant Cooling Setpoint (C)
  global_people_per_m2?: number | null  // People per Zone Floor Area (person/m2)
}

export interface MaterialComparisonParams {
  weather_group: 'china' | 'world' | 'world_weather2025'
  scenarios: MaterialScenario[]  // 至少需要3个场景：duibi, shiyan1, shiyan2
  idf_template_dir?: string  // IDF模板目录（可选，默认使用exe目录）
  global_params?: GlobalParams  // 全局参数（应用到所有IDF文件）
  enable_latent_heat?: boolean  // 是否启用蒸发潜热计算（可选，默认false）
  wet_fraction?: number  // 润湿面积比例（0-1，可选，默认1.0）
  // 色系参数：key 为图片标识（如 china_cooling_energy），value 为色系键
  // 可选色系键：Blues, coolwarm, coolwarm_r, YlGnBu, Greens, RdYlGn, PuOr, viridis
  // 默认值为空（使用服务端默认色系）
  colormap_params?: Record<string, string>
}

export async function createMaterialComparisonJob({
  params,
  remark,
}: {
  params: MaterialComparisonParams
  remark?: string
}): Promise<CreateJobResponse> {
  const req: CreateJobRequest = {
    type: 'compare_materials',
    remark,
    params: params as any,
  }
  const { data } = await api.post<CreateJobResponse>('/materials/compare', req)
  return data
}
