import { api } from './api'

export type ConfigResponse = {
  user?: { id: number; username: string }
  path: string
  content: string
  parsed: Record<string, Record<string, string>>
}

export async function getConfig(): Promise<ConfigResponse> {
  const { data } = await api.get<ConfigResponse>('/config')
  return data
}

export async function putConfig(content: string): Promise<ConfigResponse> {
  const { data } = await api.put<ConfigResponse>('/config', { content })
  return data
}

export async function restoreConfig(): Promise<ConfigResponse> {
  const { data } = await api.post<ConfigResponse>('/config/restore')
  return data
}
