import { apiGet, apiPost } from './api'
import type { UserInfo } from '../types/auth'

export async function fetchCurrentUser(): Promise<UserInfo> {
  return apiGet<UserInfo>('/auth/me')
}

export async function login(username: string, password: string): Promise<UserInfo> {
  return apiPost<UserInfo>('/auth/login', { username, password })
}

export async function register(username: string, password: string): Promise<UserInfo> {
  return apiPost<UserInfo>('/auth/register', { username, password })
}

export async function logout(): Promise<void> {
  await apiPost('/auth/logout', {})
}

export async function redeemCdk(code: string): Promise<UserInfo> {
  return apiPost<UserInfo>('/auth/redeem-cdk', { code })
}

export async function changePassword(oldPassword: string, newPassword: string): Promise<void> {
  await apiPost('/auth/change-password', { old_password: oldPassword, new_password: newPassword })
}

