import { api } from './api'

export type ActiveInputNode = {
  id: string
  path: string
  original_name: string
  updated_at: string
}

export type UploadsActiveResponse = {
  reflectance: ActiveInputNode | null
  emissivity: ActiveInputNode | null
  // Optional: only needed for transparent materials.
  transmittance?: ActiveInputNode | null
  ready: boolean
}

export async function getUploadsActive(): Promise<UploadsActiveResponse> {
  const { data } = await api.get<UploadsActiveResponse>('/uploads/active')
  return data
}

export type UploadResult = {
  kind: 'reflectance' | 'emissivity' | 'transmittance'
  processed_id: string
  processed_path: string
  original_name: string
  rows: number
  tips: string[]
  preview: number[][]
  active_ready: boolean
}

export async function uploadInput(
  kind: 'reflectance' | 'emissivity' | 'transmittance',
  file: File,
): Promise<UploadResult> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post<UploadResult>(`/uploads/${kind}`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function clearInput(
  kind: 'reflectance' | 'emissivity' | 'transmittance',
): Promise<{ kind: string; cleared: boolean; ready: boolean }> {
  const { data } = await api.delete<{ kind: string; cleared: boolean; ready: boolean }>(`/uploads/${kind}`)
  return data
}

export type UseSampleResponse = {
  reflectance: {
    processed_id: string
    processed_path: string
    original_name: string
    rows: number
    tips: string[]
    preview: number[][]
  }
  emissivity: {
    processed_id: string
    processed_path: string
    original_name: string
    rows: number
    tips: string[]
    preview: number[][]
  }
  transmittance: {
    processed_id: string
    processed_path: string
    original_name: string
    rows: number
    tips: string[]
    preview: number[][]
  } | null
  ready: boolean
}

export async function useSampleData(): Promise<UseSampleResponse> {
  const { data } = await api.post<UseSampleResponse>('/uploads/use-sample')
  return data
}

// --- Atmospheric DLL uploads (per-user) ---

export type AtmUploadResult = {
  original_name: string
  stored_name: string
  path: string
}

export async function uploadAtmPreset(file: File): Promise<AtmUploadResult> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post<AtmUploadResult>('/uploads/atm', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}