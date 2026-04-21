import { useMemo, useState, useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { BookOpen, List, X, ArrowLeft, ChevronRight } from 'lucide-react'

import Button from '../components/ui/Button'
import { MdRenderer, parseToc, TocSidebar, type TocEntry } from '../help/mdRenderer'
import { fetchUserManual } from '../services/userManual'

export default function UserManualPage() {
  const { t } = useTranslation()
  const [tocOpen, setTocOpen] = useState(true)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['user-manual'],
    queryFn: fetchUserManual,
    staleTime: 5 * 60 * 1000,
  })

  const toc = useMemo<TocEntry[]>(() => (data ? parseToc(data) : []), [data])

  return (
    <div className="min-h-screen bg-bg-primary">
      {/* Manual header */}
      <header className="sticky top-0 z-30 border-b border-border glass backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 gap-4">
          <div className="flex items-center gap-2 min-w-0">
            <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-accent-soft text-accent">
              <BookOpen size={16} />
            </div>
            <span className="truncate text-sm font-semibold text-text-primary">
              {t('userManual.title', '用户手册')}
            </span>
          </div>

          <div className="flex items-center gap-2">
            {/* TOC toggle */}
            <button
              onClick={() => setTocOpen(v => !v)}
              className={`flex h-8 w-8 items-center justify-center rounded-lg border text-xs transition-colors ${
                tocOpen
                  ? 'border-accent bg-accent-soft text-accent'
                  : 'border-border bg-bg-elevated text-text-secondary hover:text-text-primary'
              }`}
              title={tocOpen ? '隐藏目录' : '显示目录'}
            >
              <List size={14} />
            </button>

            {/* Back button */}
            <button
              onClick={() => window.close()}
              className="flex h-8 items-center gap-1 rounded-lg border border-border bg-bg-elevated px-2.5 text-xs text-text-secondary transition-colors hover:text-text-primary hover:bg-white/5"
            >
              <ArrowLeft size={13} />
              <span className="hidden sm:inline">返回</span>
            </button>
          </div>
        </div>
      </header>

      {/* Content */}
      <div className="mx-auto max-w-7xl px-4 py-6">
        {/* Loading */}
        {isLoading && (
          <div className="flex flex-col items-center justify-center py-32 gap-4">
            <div className="animate-spin rounded-full h-9 w-9 border-b-2 border-accent"></div>
            <span className="text-sm text-text-secondary">{t('userManual.loading', '正在加载手册...')}</span>
          </div>
        )}

        {/* Error */}
        {isError && (
          <div className="flex flex-col items-center justify-center py-32 gap-4">
            <div className="rounded-field border border-border bg-bg-elevated px-5 py-3 text-sm text-text-secondary">
              {t('userManual.error', '加载手册失败')}
            </div>
            <Button variant="secondary" size="sm" onClick={() => window.location.reload()}>
              {t('userManual.retry', '重试')}
            </Button>
          </div>
        )}

        {/* Content */}
        {data && (
          <div className="flex gap-6">
            {/* TOC sidebar */}
            <aside
              className={`
                flex-shrink-0 w-64 overflow-y-auto
                transition-all duration-200
                ${tocOpen ? 'visible opacity-100' : 'invisible opacity-0 w-0 overflow-hidden'}
              `}
            >
              <div className="sticky top-20 rounded-field border border-border bg-bg-elevated p-4">
                <div className="mb-3 flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wider text-text-muted">目录</span>
                </div>
                <TocSidebar toc={toc} />
              </div>
            </aside>

            {/* Main content */}
            <div className="flex-1 min-w-0">
              <div className="rounded-field border border-border bg-bg-elevated px-6 py-6 md:px-10 md:py-8">
                <MdRenderer md={data} />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
