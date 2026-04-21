import { api } from './api'

export async function fetchUserManual(): Promise<string> {
  const res = await api.get<{ content: string }>('/user-manual')
  return res.data.content
}
