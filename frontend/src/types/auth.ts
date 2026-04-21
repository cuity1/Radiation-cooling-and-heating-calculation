export type UserInfo = {
  id: number
  username: string
  role: 'admin' | 'user'
  tier: 'normal' | 'pro' | 'permanent_pro'
  pro_expires_at?: string
}

