import axios from 'axios'
import { useNavigate } from 'react-router-dom'

export const api = axios.create({
  baseURL: '/api',
  timeout: 6_000_000, // 100分钟 (6000秒)
  withCredentials: true,
})

// 添加响应拦截器处理 401 未授权
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // 401 时跳转到登录页（需要在组件中使用 useNavigate）
      // 这里设置一个标记，让组件中可以使用
      window.dispatchEvent(new CustomEvent('auth:unauthorized'))
    }
    return Promise.reject(error)
  }
)

export async function apiGet<T>(path: string): Promise<T> {
  const { data } = await api.get<T>(path)
  return data
}

export async function apiPost<T>(path: string, body?: any): Promise<T> {
  const { data } = await api.post<T>(path, body)
  return data
}

export async function apiDelete<T>(path: string): Promise<T> {
  const { data } = await api.delete<T>(path)
  return data
}
