import { PropsWithChildren } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { Card, CardDesc, CardHeader, CardTitle } from './ui/Card'
import Button from './ui/Button'
import { Link } from 'react-router-dom'

export function RequirePro({ children }: PropsWithChildren) {
  const { user, loading } = useAuth()
  const loc = useLocation()

  if (loading) {
    return <div className="text-sm text-text-secondary">加载中...</div>
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: loc }} />
  }

  // 检查是否为PRO用户
  if (user.tier !== 'pro' && user.tier !== 'permanent_pro') {
    return (
      <div className="space-y-5">
        <Card>
          <CardHeader>
            <CardTitle>需要PRO用户权限</CardTitle>
            <CardDesc>功量地图绘制功能仅对 Pro 用户开放</CardDesc>
          </CardHeader>
          <div className="rounded-xl border border-warning-soft bg-warning-soft p-4 text-sm text-text-secondary">
            <p className="mb-3">当前为普通用户账号，功量地图绘制功能仅对 Pro 用户开放。如需使用该功能，请升级为 Pro 用户。</p>
            <div className="flex gap-2">
              <Link to="/">
                <Button variant="secondary">返回首页</Button>
              </Link>
            </div>
          </div>
        </Card>
      </div>
    )
  }

  return <>{children}</>
}
