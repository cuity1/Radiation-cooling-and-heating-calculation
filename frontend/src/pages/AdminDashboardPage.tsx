import { useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import Button from '../components/ui/Button'
import Segmented from '../components/ui/Segmented'
import { apiDelete, apiGet, apiPost } from '../services/api'
import { getMaintenanceStatus, setMaintenanceMode } from '../services/maintenance'

type AdminUser = {
  id: number
  username: string
  role: string
  tier: 'normal' | 'pro' | 'permanent_pro' | string
  pro_expires_at: string | null
  is_active: boolean
  created_at: string
}

type CdkItem = {
  id: number
  code: string
  key_type: 'permanent' | 'temporary' | string
  created_at: string
  redeemed_at: string | null
  redeemed_by_user_id: number | null
}

type AdminJob = {
  id: string
  type: string
  status: string
  created_at: string
  updated_at: string
  user_id: number | null
  username: string | null
}

type AdminTab = 'users' | 'keys' | 'jobs' | 'system'

type TabDef = { key: AdminTab; label: string }

function keyTypeLabel(t: string) {
  if (t === 'permanent') return '永久'
  if (t === 'temporary') return '临时(1年)'
  return t
}

export default function AdminDashboardPage() {
  const qc = useQueryClient()
  const [tab, setTab] = useState<AdminTab>('users')

  const tabs: TabDef[] = useMemo(
    () => [
      { key: 'users', label: '用户管理' },
      { key: 'keys', label: 'KEY管理' },
      { key: 'jobs', label: '任务管理' },
      { key: 'system', label: '系统设置' },
    ],
    [],
  )

  const usersQ = useQuery({
    queryKey: ['admin', 'users'],
    queryFn: () => apiGet<AdminUser[]>('/admin/users'),
  })

  const cdksQ = useQuery({
    queryKey: ['admin', 'cdks'],
    queryFn: () => apiGet<CdkItem[]>('/admin/cdks'),
  })

  const jobsQ = useQuery({
    queryKey: ['admin', 'jobs', 'active'],
    queryFn: () => apiGet<AdminJob[]>('/admin/jobs/active'),
  })

  const resetPasswordM = useMutation({
    mutationFn: ({ userId, newPassword }: { userId: number; newPassword: string }) =>
      apiPost(`/admin/users/${userId}/reset-password?new_password=${encodeURIComponent(newPassword)}`, {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'users'] })
    },
  })

  const deleteUserM = useMutation({
    mutationFn: (userId: number) => apiDelete(`/admin/users/${userId}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'users'] })
    },
  })

  const updateUserTierM = useMutation({
    mutationFn: ({ userId, tier, proExpiresAt }: { userId: number; tier: string; proExpiresAt?: string }) =>
      apiPost(`/admin/users/${userId}/tier`, {
        tier,
        pro_expires_at: proExpiresAt,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'users'] })
    },
  })

  const checkExpiredUsersM = useMutation({
    mutationFn: () => apiPost<{ downgraded: number }>('/admin/users/check-expired', {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'users'] })
    },
  })

  const generateCdkM = useMutation({
    mutationFn: ({ count, keyType }: { count: number; keyType: 'permanent' | 'temporary' }) =>
      apiPost<{ codes: string[] }>(`/admin/generate-cdk?count=${count}&key_type=${encodeURIComponent(keyType)}`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'cdks'] }),
  })

  const deleteJobM = useMutation({
    mutationFn: (jobId: string) => apiDelete(`/admin/jobs/${jobId}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'jobs', 'active'] })
    },
  })

  const cancelJobM = useMutation({
    mutationFn: (jobId: string) => apiPost(`/admin/jobs/${jobId}/cancel`, {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'jobs', 'active'] })
    },
  })

  const maintenanceQ = useQuery({
    queryKey: ['admin', 'maintenance'],
    queryFn: async () => {
      const data = await getMaintenanceStatus()
      return data
    },
  })

  const toggleMaintenanceM = useMutation({
    mutationFn: (enabled: boolean) => setMaintenanceMode(enabled),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'maintenance'] })
    },
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-text-primary mb-1">管理员后台</h1>
        <p className="text-sm text-text-secondary">管理用户、KEY 激活码以及任务记录。</p>
      </div>

      <div className="flex items-center justify-between gap-3">
        <Segmented
          value={tab}
          onChange={(v) => setTab(v as AdminTab)}
          options={tabs.map((t) => ({ value: t.key, label: t.label }))}
        />
      </div>

      {tab === 'users' && (
        <section className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-sm font-semibold text-text-primary">用户管理</h2>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => checkExpiredUsersM.mutate()}
              disabled={checkExpiredUsersM.isPending}
            >
              检查过期并降级
            </Button>
          </div>

          <div className="rounded-field border border-border glass-light p-3 text-xs text-text-secondary">
            {usersQ.isLoading ? (
              <div>加载用户中...</div>
            ) : usersQ.isError ? (
              <div>加载失败</div>
            ) : (
              <table className="w-full border-separate border-spacing-y-1">
                <thead className="text-[11px] uppercase text-text-muted">
                  <tr>
                    <th className="text-left">ID</th>
                    <th className="text-left">用户名</th>
                    <th className="text-left">角色</th>
                    <th className="text-left">用户组</th>
                    <th className="text-left">到期时间</th>
                    <th className="text-left">状态</th>
                    <th className="text-left">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {usersQ.data?.map((u) => (
                    <tr key={u.id}>
                      <td>{u.id}</td>
                      <td>{u.username}</td>
                      <td>{u.role}</td>
                      <td>
                        <select
                          className="rounded-lg border border-border bg-bg-elevated px-2 py-1 text-xs text-text-primary"
                          value={u.tier}
                          onChange={(e) => {
                            const next = e.target.value
                            if (next === 'pro') {
                              const raw = window.prompt(
                                `为用户 ${u.username} 设置临时PRO到期时间（ISO格式，如 2027-02-09T00:00:00Z）。\n\n留空则默认：从现在起1年。`,
                                '',
                              )
                              const iso = raw?.trim() ? raw.trim() : undefined
                              updateUserTierM.mutate({ userId: u.id, tier: next, proExpiresAt: iso })
                            } else {
                              updateUserTierM.mutate({ userId: u.id, tier: next })
                            }
                          }}
                        >
                          <option value="normal">普通</option>
                          <option value="pro">PRO(一年)</option>
                          <option value="permanent_pro">永久PRO</option>
                        </select>
                      </td>
                      <td className="font-mono text-[11px]">{u.pro_expires_at ?? '-'}</td>
                      <td>{u.is_active ? '启用' : '禁用'}</td>
                      <td>
                        <div className="flex flex-wrap items-center gap-2">
                          <Button
                            size="xs"
                            variant="secondary"
                            onClick={() => {
                              const pwd = window.prompt(`为用户 ${u.username} 设置新密码：`)
                              if (!pwd) return
                              resetPasswordM.mutate({ userId: u.id, newPassword: pwd })
                            }}
                          >
                            重置密码
                          </Button>
                          <Button
                            size="xs"
                            variant="ghost"
                            onClick={() => {
                              const ok = window.confirm(
                                `确定要删除用户 ${u.username} (id=${u.id}) 吗？\n\n此操作不可恢复，将清理该用户登录会话，并解绑其历史任务记录。`,
                              )
                              if (!ok) return
                              deleteUserM.mutate(u.id)
                            }}
                          >
                            删除
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>
      )}

      {tab === 'keys' && (
        <section className="space-y-3">
          <h2 className="text-sm font-semibold text-text-primary">KEY 管理</h2>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                const countStr = window.prompt('生成多少个【永久KEY】？', '10')
                if (!countStr) return
                const n = Number(countStr)
                if (!Number.isFinite(n) || n <= 0) return
                generateCdkM.mutate({ count: n, keyType: 'permanent' })
              }}
            >
              生成永久KEY
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                const countStr = window.prompt('生成多少个【临时KEY(一年)】？', '10')
                if (!countStr) return
                const n = Number(countStr)
                if (!Number.isFinite(n) || n <= 0) return
                generateCdkM.mutate({ count: n, keyType: 'temporary' })
              }}
            >
              生成临时KEY
            </Button>
            {generateCdkM.data?.codes?.length ? (
              <span className="text-xs text-text-secondary">最近生成：{generateCdkM.data.codes.join(', ')}</span>
            ) : null}
          </div>

          <div className="rounded-field border border-border glass-light p-3 text-xs text-text-secondary max-h-80 overflow-auto">
            {cdksQ.isLoading ? (
              <div>加载 KEY 中...</div>
            ) : cdksQ.isError ? (
              <div>加载失败</div>
            ) : (
              <table className="w-full border-separate border-spacing-y-1">
                <thead className="text-[11px] uppercase text-text-muted">
                  <tr>
                    <th className="text-left">代码</th>
                    <th className="text-left">类型</th>
                    <th className="text-left">创建时间</th>
                    <th className="text-left">使用状态</th>
                  </tr>
                </thead>
                <tbody>
                  {cdksQ.data?.map((c) => (
                    <tr key={c.id}>
                      <td className="font-mono text-[11px]">{c.code}</td>
                      <td>{keyTypeLabel(c.key_type)}</td>
                      <td className="font-mono text-[11px]">{c.created_at}</td>
                      <td className="text-[11px] text-text-muted">
                        {c.redeemed_at ? `已使用 (user ${c.redeemed_by_user_id})` : '未使用'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>
      )}

      {tab === 'jobs' && (
        <section className="space-y-3">
          <h2 className="text-sm font-semibold text-text-primary">任务管理</h2>
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                const jobId = window.prompt('输入要删除的 job_id：')
                if (!jobId) return
                deleteJobM.mutate(jobId)
              }}
            >
              删除单个任务
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                const status = window.prompt('按状态清理任务 (queued/started/failed/succeeded/cancelled)：', 'queued')
                if (!status) return
                apiPost(`/admin/jobs/cleanup?status=${encodeURIComponent(status)}`, {}).then(() => {
                  qc.invalidateQueries({ queryKey: ['admin', 'jobs', 'active'] })
                })
              }}
            >
              按状态清理任务
            </Button>
          </div>
          <div className="rounded-field border border-border glass-light p-3 text-xs text-text-secondary">
            {jobsQ.isLoading ? (
              <div>加载任务中...</div>
            ) : jobsQ.isError ? (
              <div>加载失败</div>
            ) : jobsQ.data && jobsQ.data.length > 0 ? (
              <table className="w-full border-separate border-spacing-y-1">
                <thead className="text-[11px] uppercase text-text-muted">
                  <tr>
                    <th className="text-left">Job ID</th>
                    <th className="text-left">类型</th>
                    <th className="text-left">状态</th>
                    <th className="text-left">用户</th>
                    <th className="text-left">创建时间</th>
                    <th className="text-left">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {jobsQ.data.map((j) => (
                    <tr key={j.id}>
                      <td className="font-mono">{j.id}</td>
                      <td>{j.type}</td>
                      <td>{j.status}</td>
                      <td>{j.username ?? '-'}</td>
                      <td>{j.created_at}</td>
                      <td className="space-x-2">
                        {j.status !== 'cancelled' && (
                          <Button size="xs" variant="secondary" onClick={() => cancelJobM.mutate(j.id)}>
                            取消
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div>当前没有排队中或运行中的任务。</div>
            )}
          </div>
        </section>
      )}

      {tab === 'system' && (
        <section className="space-y-3">
          <h2 className="text-sm font-semibold text-text-primary">系统设置</h2>
          <div className="rounded-field border border-border glass-light p-4">
            <div className="flex items-center justify-between gap-4">
              <div>
                <div className="text-sm font-medium text-text-primary">维护模式</div>
                <div className="mt-1 text-xs text-text-secondary">
                  开启后，所有普通用户访问任何页面都将显示维护提示页面，管理员仍可访问管理后台。
                </div>
              </div>
              {maintenanceQ.isLoading ? (
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-gray-400"></div>
              ) : (
                <button
                  className={`relative inline-flex h-7 w-12 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-accent ${
                    maintenanceQ.data
                      ? 'bg-red-500 focus:ring-red-400'
                      : 'bg-gray-300 focus:ring-gray-400'
                  }`}
                  onClick={() => {
                    const next = !maintenanceQ.data
                    if (next) {
                      const ok = window.confirm('确定要开启维护模式吗？开启后普通用户将无法正常使用系统。')
                      if (!ok) return
                    }
                    toggleMaintenanceM.mutate(next)
                  }}
                  disabled={toggleMaintenanceM.isPending}
                >
                  <span
                    className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform ${
                      maintenanceQ.data ? 'translate-x-6' : 'translate-x-1'
                    }`}
                  />
                </button>
              )}
            </div>
          </div>
        </section>
      )}
    </div>
  )
}
