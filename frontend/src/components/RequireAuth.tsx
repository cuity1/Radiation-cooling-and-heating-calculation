import { PropsWithChildren } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export function RequireAuth({ children }: PropsWithChildren) {
  const { user, loading } = useAuth()
  const loc = useLocation()

  if (loading) {
    return <div className="text-sm text-text-secondary">加载中...</div>
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: loc }} />
  }

  return <>{children}</>
}

export function RequireAdmin({ children }: PropsWithChildren) {
  const { user, loading } = useAuth()
  const loc = useLocation()

  if (loading) {
    return <div className="text-sm text-text-secondary">加载中...</div>
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: loc }} />
  }

  if (user.role !== 'admin') {
    return <Navigate to="/" replace state={{ from: loc }} />
  }

  return <>{children}</>
}

