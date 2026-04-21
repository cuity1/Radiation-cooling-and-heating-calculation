import { api } from './api'
import type { CreateJobRequest, CreateJobResponse } from './schemas'

// 玻璃参数接口（对应玻璃材料的WindowMaterial:Glazing参数）
export interface GlassProperties {
  Name?: string | null  // 玻璃名称
  OpticalDataType?: string | null  // 光学数据类型 (SpectralAverage)
  Thickness?: number | null  // 厚度 (m)
  SolarTransmittance?: number | null  // 太阳透射率 (0-1)
  SolarReflectanceFront?: number | null  // 太阳反射率-正面 (0-1)
  SolarReflectanceBack?: number | null  // 太阳反射率-背面 (0-1)
  VisibleTransmittance?: number | null  // 可见光透射率 (0-1)
  VisibleReflectanceFront?: number | null  // 可见光反射率-正面 (0-1)
  VisibleReflectanceBack?: number | null  // 可见光反射率-背面 (0-1)
  InfraredTransmittance?: number | null  // 红外透射率 (0-1)
  Emissivity?: number | null  // 红外发射率-正面 (0-1)
  EmissivityBack?: number | null  // 红外发射率-背面 (0-1)
  Conductivity?: number | null  // 导热系数 (W/m-K)
  DirtCorrectionFactor?: number | null  // 污垢修正因子 (0-1)
  SolarDiffusing?: boolean | null  // 太阳散射
}

export interface GlassScenario {
  name: string
  desc: string
  glass: GlassProperties  // 玻璃参数
}

export interface GlobalParams {
  global_ach?: number | null  // Infiltration Air Changes per Hour (1/hr)
  global_lighting_w_per_m2?: number | null  // Lights Watts per Zone Floor Area (W/m2)
  global_thermostat_heat_c?: number | null  // Thermostat Constant Heating Setpoint (C)
  global_thermostat_cool_c?: number | null  // Thermostat Constant Cooling Setpoint (C)
  global_people_per_m2?: number | null  // People per Zone Floor Area (person/m2)
  phase_change_temp?: number | null  // Thermochromic Glass Phase Change Temperature (C)
}

export interface GlassComparisonParams {
  weather_group: 'china' | 'world' | 'world_weather2025'
  scenarios: GlassScenario[]  // 至少需要3个场景：glass_duibi, glass_shiyan1, glass_shiyan2
  idf_template_dir?: string  // IDF模板目录（可选，默认使用exe目录）
  global_params?: GlobalParams  // 全局参数（应用到所有IDF文件）
  enable_latent_heat?: boolean  // 是否启用蒸发潜热计算（可选，默认false）
  wet_fraction?: number  // 润湿面积比例（0-1，可选，默认1.0）
  // 色系参数：key 为图片标识（如 china_cooling_energy），value 为色系键
  // 可选色系键：Blues, coolwarm, coolwarm_r, YlGnBu, Greens, RdYlGn, PuOr, viridis
  // 默认值为空（使用服务端默认色系）
  colormap_params?: Record<string, string>
}

export async function createGlassComparisonJob({
  params,
  remark,
}: {
  params: GlassComparisonParams
  remark?: string
}): Promise<CreateJobResponse> {
  const req: CreateJobRequest = {
    type: 'compare_glass',
    remark,
    params: params as any,
  }
  const { data } = await api.post<CreateJobResponse>('/glass/compare', req)
  return data
}
