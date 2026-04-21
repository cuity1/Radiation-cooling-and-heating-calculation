import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { Card, CardHeader, CardTitle, CardDesc } from '../components/ui/Card'
import Button from '../components/ui/Button'
import { listQuestions, createQuestion } from '../services/qa'
import type { QaQuestionSummary } from '../types/qa'
import { useAuth } from '../context/AuthContext'
import { formatLocalTime } from '../lib/time'
import { MessageCircle, Plus, Search, Clock } from 'lucide-react'

export default function QaIndexPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const nav = useNavigate()
  const qc = useQueryClient()

  const [search, setSearch] = useState('')
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')

  const q = useQuery({
    queryKey: ['qa', 'questions', search],
    queryFn: () => listQuestions(search),
  })

  const createM = useMutation({
    mutationFn: () => createQuestion(title, body),
    onSuccess: async (created) => {
      setTitle('')
      setBody('')
      await qc.invalidateQueries({ queryKey: ['qa', 'questions'] })
      nav(`/qa/${created.id}`)
    },
  })

  const questions: QaQuestionSummary[] = q.data ?? []

  const handleCreate = () => {
    if (!user) { nav('/login'); return }
    if (!title.trim() || !body.trim()) return
    createM.mutate()
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <Card className="animate-fade-slide-up">
        <CardHeader>
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-2.5">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent/15 text-accent">
                <MessageCircle size={18} />
              </div>
              <div>
                <CardTitle>{t('qa.title')}</CardTitle>
                <CardDesc className="text-xs">{t('qa.desc')}</CardDesc>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 text-xs text-text-muted">
                <Search size={12} />
                <span>{q.isLoading ? t('qa.loading') : `${questions.length} ${t('qa.totalQuestions', { count: questions.length }).split(' ').pop() ?? 'items'}`}</span>
              </div>
            </div>
          </div>
        </CardHeader>
        <div className="mt-2">
          <input
            className="w-full rounded-field border border-border glass-light px-3.5 py-2 text-sm bg-transparent text-text-primary placeholder:text-text-muted transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 hover:border-border-light"
            placeholder={t('qa.searchPlaceholder')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </Card>

      {/* Post question */}
      <Card className="animate-fade-slide-up stagger-1">
        <CardHeader>
          <CardTitle className="text-sm">{t('qa.postQuestion')}</CardTitle>
          <CardDesc className="text-xs">{t('qa.postDesc')}</CardDesc>
        </CardHeader>

        {!user && (
          <div className="mb-3 rounded-field border border-warning/20 bg-warning/8 px-3 py-2 text-xs text-text-secondary">
            {t('qa.loginRequired')}
            <button className="ml-2 text-accent underline-offset-2 hover:underline font-medium" onClick={() => nav('/login')}>
              {t('qa.goToLogin')}
            </button>
          </div>
        )}

        <div className="space-y-3">
          <input
            className="w-full rounded-field border border-border glass-light px-3.5 py-2 text-sm text-text-primary placeholder:text-text-muted transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 hover:border-border-light disabled:opacity-50"
            placeholder={t('qa.titlePlaceholder')}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            disabled={!user || createM.isPending}
          />
          <textarea
            className="w-full min-h-[100px] rounded-field border border-border glass-light px-3.5 py-2 text-sm text-text-primary placeholder:text-text-muted transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 hover:border-border-light disabled:opacity-50 resize-none"
            placeholder={t('qa.bodyPlaceholder')}
            value={body}
            onChange={(e) => setBody(e.target.value)}
            disabled={!user || createM.isPending}
          />
          <div className="flex items-center justify-end">
            <Button
              variant="primary"
              icon={<Plus size={13} />}
              loading={createM.isPending}
              disabled={!user || createM.isPending || !title.trim() || !body.trim()}
              onClick={handleCreate}
            >
              {createM.isPending ? t('qa.publishing') : t('qa.publish')}
            </Button>
          </div>
        </div>
      </Card>

      {/* Question list */}
      <div className="grid gap-2">
        {questions.map((question, i) => (
          <Link
            key={question.id}
            to={`/qa/${question.id}`}
            className={`block animate-fade-slide-up`}
            style={{ animationDelay: `${i * 40}ms` }}
          >
            <div className="glass-light rounded-2xl px-4 py-3.5 border border-border transition-all duration-200 hover:glass-strong hover:border-border-light card-lift group">
              <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-semibold text-text-primary line-clamp-2 group-hover:text-accent transition-colors duration-150">
                    {question.title}
                  </div>
                  <div className="mt-1 text-xs text-text-secondary line-clamp-2 leading-relaxed">
                    {question.excerpt}
                  </div>
                </div>
                <div className="flex flex-col items-start md:items-end gap-1 text-[11px] text-text-muted shrink-0 mt-1 md:mt-0">
                  <div className="flex items-center gap-1.5">
                    <span className="font-medium text-text-secondary">{question.author_username}</span>
                    <span>·</span>
                    <span>{t('qa.replyCount')} {question.answer_count}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Clock size={10} />
                    <span>{formatLocalTime(question.updated_at)}</span>
                  </div>
                </div>
              </div>
            </div>
          </Link>
        ))}

        {!q.isLoading && questions.length === 0 && (
          <div className="glass-light rounded-2xl p-10 text-center animate-scale-fade-in">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white/[0.04] text-text-muted mx-auto mb-3">
              <MessageCircle size={24} />
            </div>
            <p className="text-sm font-semibold text-text-secondary">{t('qa.noQuestions')}</p>
          </div>
        )}

        {q.isLoading && (
          <div className="glass-light rounded-2xl p-6 space-y-2">
            {[1, 2, 3].map(i => (
              <div key={i} className="flex flex-col gap-1.5 p-1">
                <div className="skeleton-shimmer h-3.5 w-3/4 rounded" />
                <div className="skeleton-shimmer h-2.5 w-1/2 rounded" />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
