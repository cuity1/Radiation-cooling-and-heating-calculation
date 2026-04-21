import { api } from './api'

export async function listAtmPresets(): Promise<string[]> {
  const { data } = await api.get<{ items: string[] }>('/presets/atm')
  return data.items
}

export async function getMaterialPreset(): Promise<{ reflectance: string; emissivity: string }> {
  const { data } = await api.get<{ items: { reflectance: string; emissivity: string } }>('/presets/material')
  return data.items
}
