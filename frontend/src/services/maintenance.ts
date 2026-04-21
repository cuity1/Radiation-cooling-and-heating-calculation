import { apiGet, apiPost } from './api'

export type MaintenanceStatus = { maintenance: boolean }

export async function getMaintenanceStatus(): Promise<boolean> {
  const data = await apiGet<MaintenanceStatus>('/maintenance')
  return data.maintenance
}

export async function setMaintenanceMode(enabled: boolean): Promise<void> {
  await apiPost('/admin/maintenance', { enabled })
}
