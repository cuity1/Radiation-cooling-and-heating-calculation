import { api } from './api'

export type WindCloudRequest = {
  wind_min: number
  wind_max: number
  wind_points: number
  emissivity_min: number
  emissivity_max: number
  emissivity_points: number
  s_solar: number | null
}

export type WindCloudResponse = {
  wind: number[]
  emissivity: number[]
  delta_t: number[][]
  h_conv: number[][]
  meta: {
    t_env_c?: number
    t_a1?: number
    s_solar: number
    avg_emissivity: number
    r_sol: number
    alpha_s: number
    delta_t_definition?: string
    model?: string
    grid?: {
      wind_points: number
      emissivity_points: number
    }
  }
}

export async function computeWindCloud(req: WindCloudRequest): Promise<WindCloudResponse> {
  const { data } = await api.post<WindCloudResponse>('/tools/wind-cloud', req)
  return data
}

export type SolarEfficiencyRequest = {
  angle_steps: number
  t_a_points?: number
  s_solar_points?: number
  t_a_min?: number
  t_a_max?: number
  s_solar_min?: number
  s_solar_max?: number
}

export type SolarEfficiencyResponse = {
  t_a_range: number[]
  s_solar_range: number[]
  p_heat: number[][]
  meta: {
    angle_steps: number
    grid?: {
      t_a_points: number
      s_solar_points: number
      t_a_min: number
      t_a_max: number
      s_solar_min: number
      s_solar_max: number
    }
  }
}

export async function computeSolarEfficiency(req: SolarEfficiencyRequest): Promise<SolarEfficiencyResponse> {
  const { data } = await api.post<SolarEfficiencyResponse>('/tools/solar-efficiency', req)
  return data
}

export type EmissivitySolarCloudRequest = {
  n_emissivity: number
  n_solar: number
  solar_max: number
}

export type EmissivitySolarCloudResponse = {
  atm_emissivity: number[]
  solar_irradiance: number[]
  cooling_power: number[][]
  meta: {
    avg_emissivity: number
    r_sol: number
    alpha_s: number
    t_a1: number
    delta_t: number
    n_emissivity: number
    n_solar: number
    solar_max: number
  }
}

export async function computeEmissivitySolarCloud(
  req: EmissivitySolarCloudRequest,
): Promise<EmissivitySolarCloudResponse> {
  const { data } = await api.post<EmissivitySolarCloudResponse>('/tools/emissivity-solar', req)
  return data
}

export type PowerComponentsRequest = {
  angle_steps: number
  h_cond_wm2k: number
  enable_natural_convection: boolean
  phase_temp_c: number | null
  phase_power_wm2: number
  phase_half_width_c: number
}

export type PowerComponentsResponse = {
  t_film: number[]
  t_a1: number
  components: Record<string, number[]>
  meta: {
    angle_steps: number
    h_cond_wm2k: number
    enable_natural_convection: boolean
    phase_temp_c: number | null
    phase_power_wm2: number
    phase_half_width_c: number
  }
}

export async function computePowerComponents(req: PowerComponentsRequest): Promise<PowerComponentsResponse> {
  const { data } = await api.post<PowerComponentsResponse>('/tools/power-components', req)
  return data
}

export type AngularPowerRequest = {
  temp_diff_c: number
  angle_steps: number
}

export type AngularPowerResponse = {
  theta_deg: number[]
  power_density_per_sr: number[]
  power_density_total: number | null
  hemispherical_solid_angle: number | null
  half_power_angle_deg: number | null
  meta: {
    temp_diff_c: number
    angle_steps: number
    T_a_K?: number
    T_s_K?: number
    wavelength_range_um?: number[]
    dlam_nm?: number
  }
}

export async function computeAngularPower(req: AngularPowerRequest): Promise<AngularPowerResponse> {
  const { data } = await api.post<AngularPowerResponse>('/tools/angular-power', req)
  return data
}

// --- Material–Environment Temperature Cloud Map (Cooling Power) ---

export type MaterialEnvTempCloudRequest = {
  t_env_min_c: number
  t_env_max_c: number
  h_c_wm2k: number
  enable_natural_convection?: boolean
  enable_latent_heat?: boolean
  relative_humidity?: number | null
  wet_fraction?: number
  phase_temp_c?: number | null
  phase_power_wm2?: number
  phase_half_width_c?: number
}

export type MaterialEnvTempCloudResponse = {
  t_env_c: number[]
  t_film_c: number[]
  cooling_power: number[][]
  meta: {
    h_c_wm2k: number
    temp_step_c: number
    alpha_sol: number
    alpha_sol_visible: number
    avg_emissivity: number
    S_solar: number
    T_a1_ref_c: number
    enable_natural_convection?: boolean
    enable_latent_heat?: boolean
    relative_humidity?: number | null
    wet_fraction?: number
    phase_temp_c?: number | null
    phase_power_wm2?: number
    phase_half_width_c?: number
  }
}

export async function computeMaterialEnvTempCloud(
  req: MaterialEnvTempCloudRequest,
): Promise<MaterialEnvTempCloudResponse> {
  const { data } = await api.post<MaterialEnvTempCloudResponse>('/tools/material-env-temp-cloud', req)
  return data
}

// --- MODTRAN transmittance ---

export type ModtranTemplateParams = {
  lines: string[]
  params: {
    model_type: string
    atmosphere_model: number
    aerosol_model: number
    observer_zenith_deg: number
    observer_azimuth_deg: number
    solar_zenith_deg: number
    solar_azimuth_deg: number
    ground_alt_km: number
    start_cm1: number
    end_cm1: number
    res_cm1: number
    out_res_cm1: number
  }
}

export async function listModtranTemplates(): Promise<string[]> {
  const { data } = await api.get<{ templates: string[] }>('/tools/modtran/templates')
  return data.templates
}

export async function getModtranTemplateParams(name: string): Promise<ModtranTemplateParams> {
  const { data } = await api.get<ModtranTemplateParams>('/tools/modtran/template-params', {
    params: { name },
  })
  return data
}

export type ModtranRunRequest = {
  template: string
  model_type: string
  atmosphere_model: number
  aerosol_model: number
  observer_zenith_deg: number
  observer_azimuth_deg: number
  solar_zenith_deg: number
  solar_azimuth_deg: number
  ground_alt_km: number
  start_cm1: number
  end_cm1: number
  res_cm1: number
  out_res_cm1: number
  export_excel?: boolean
}

export type ModtranRunResponse = {
  run_id: string
  downloads: Record<string, string>
  meta: {
    duration_sec: number
    bin_dir: string
    usr_dir: string
    rows: number
    spectrum_source: string
  }
  preview: Array<Record<string, number>>
}

export async function runModtranTransmittance(req: ModtranRunRequest): Promise<ModtranRunResponse> {
  const { data } = await api.post<ModtranRunResponse>('/tools/modtran/run', req)
  return data
}
