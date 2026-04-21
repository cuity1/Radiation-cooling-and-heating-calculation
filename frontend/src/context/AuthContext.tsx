import { createContext, PropsWithChildren, useContext, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { UserInfo } from '../types/auth'
import { fetchCurrentUser, login as apiLogin, logout as apiLogout, register as apiRegister } from '../services/auth'

type AuthContextValue = {
  user: UserInfo | null
  loading: boolean
  error: string | null
  login: (username: string, password: string) => Promise<void>
  register: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  refresh: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: PropsWithChildren) {
  const [user, setUser] = useState<UserInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 监听 401 未授权事件
  useEffect(() => {
    const handleUnauthorized = () => {
      setUser(null)
      const path = window.location.pathname
      // 公开路由（主页、登录、注册）不需要跳转登录页
      if (path !== '/' && !path.includes('/login') && !path.includes('/register')) {
        navigate('/login', { replace: true })
      }
    }
    window.addEventListener('auth:unauthorized', handleUnauthorized)
    return () => window.removeEventListener('auth:unauthorized', handleUnauthorized)
  }, [navigate])

  async function refresh() {
    setLoading(true)
    setError(null)
    try {
      const me = await fetchCurrentUser()
      setUser(me)
    } catch {
      setUser(null)
    } finally {
      setLoading(false)
    }
  }

  async function handleLogin(username: string, password: string) {
    setError(null)
    try {
      const u = await apiLogin(username, password)
      setUser(u)
    } catch (e: any) {
      const code = e?.response?.data?.detail
      setError(code === 'invalid_credentials' ? '账户或密码错误' : (code ?? '登录失败'))
      throw e
    }
  }

  async function handleRegister(username: string, password: string) {
    setError(null)
    try {
      const u = await apiRegister(username, password)
      setUser(u)
    } catch (e: any) {
      const code = e?.response?.data?.detail
      setError(code === 'username_taken' ? '该用户名已被使用' : (code ?? '注册失败'))
      throw e
    }
  }

  async function handleLogout() {
    setError(null)
    try {
      await apiLogout()
    } finally {
      setUser(null)
    }
  }

  const value: AuthContextValue = {
    user,
    loading,
    error,
    login: handleLogin,
    register: handleRegister,
    logout: handleLogout,
    refresh,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

