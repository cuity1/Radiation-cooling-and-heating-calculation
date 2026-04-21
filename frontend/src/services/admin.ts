import { api } from './api'

export async function cleanupQueuedJobs(): Promise<{ cancelled: number }> {
  const { data } = await api.post<{ cancelled: number }>('/admin/jobs/cleanup?status=queued')
  return data
}

export async function updateUserTier(userId: number, tier: string, proExpiresAt?: string): Promise<{ ok: boolean }> {
  const { data } = await api.post<{ ok: boolean }>(`/admin/users/${userId}/tier`, {
    tier,
    pro_expires_at: proExpiresAt,
  })
  return data
}

export async function checkExpiredUsers(): Promise<{ downgraded: number }> {
  const { data } = await api.post<{ downgraded: number }>('/admin/users/check-expired')
  return data
}
