import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Card, CardHeader, CardTitle, CardDesc } from '../components/ui/Card'
import Button from '../components/ui/Button'
import { getQuestion, createAnswer } from '../services/qa'
import type { QaQuestionDetail } from '../types/qa'
import { useAuth } from '../context/AuthContext'
import { formatLocalTime } from '../lib/time'
import { MdRenderer } from '../help/mdRenderer'

export default function QaDetailPage() {
  const { user } = useAuth()
  const nav = useNavigate()
  const { questionId } = useParams<{ questionId: string }>()
  const qc = useQueryClient()

  const [body, setBody] = useState('')

  const idNum = Number(questionId)

  const q = useQuery({
    queryKey: ['qa', 'question', idNum],
    queryFn: () => getQuestion(idNum),
    enabled: Number.isFinite(idNum),
  })

  const answerM = useMutation({
    mutationFn: () => createAnswer(idNum, body),
    onSuccess: async () => {
      setBody('')
      await qc.invalidateQueries({ queryKey: ['qa', 'question', idNum] })
      await qc.invalidateQueries({ queryKey: ['qa', 'questions'] })
    },
  })

  const handleReply = () => {
    if (!user) {
      nav('/login')
      return
    }
    if (!body.trim()) return
    answerM.mutate()
  }

  if (!Number.isFinite(idNum)) {
    return (
      <div className="text-sm text-danger">
        无效的问题 ID。
      </div>
    )
  }

  if (q.isLoading || !q.data) {
    return (
      <div className="text-sm text-text-secondary">
        {q.isLoading ? '加载中…' : '正在加载问题详情…'}
      </div>
    )
  }

  const data: QaQuestionDetail = q.data

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            {data.title}
          </CardTitle>
          <CardDesc>
            <span className="text-xs text-text-secondary">
              提问者：{data.author_username} · 创建于 {formatLocalTime(data.created_at)} · 最近更新 {formatLocalTime(data.updated_at)}
            </span>
          </CardDesc>
        </CardHeader>
        <div className="mt-2 text-sm leading-relaxed text-text-primary">
          <MdRenderer md={data.body} />
        </div>
        <div className="mt-4 text-xs text-text-muted">
          <Link to="/qa" className="text-accent underline-offset-2 hover:underline">
            返回问答列表
          </Link>
        </div>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>全部回复（{data.answers.length} 条）</CardTitle>
          <CardDesc>按时间顺序展示，方便追踪讨论过程。</CardDesc>
        </CardHeader>

        <div className="space-y-3">
          {data.answers.map((a) => (
            <div
              key={a.id}
              className="glass-light rounded-field border border-border px-3 py-2 text-sm text-text-primary"
            >
              <div className="mb-1 flex items-center justify-between text-xs text-text-muted">
                <span>{a.author_username}</span>
                <span>{formatLocalTime(a.created_at)}</span>
              </div>
              <div className="leading-relaxed">
                <MdRenderer md={a.body} />
              </div>
            </div>
          ))}

          {data.answers.length === 0 && (
            <div className="rounded-field border border-border px-3 py-3 text-xs text-text-secondary">
              还没有回复，欢迎留下你的看法或解答。
            </div>
          )}
        </div>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>回复问题</CardTitle>
          <CardDesc>从自己的使用经验或理解出发，给出建议或解读。</CardDesc>
        </CardHeader>

        {!user && (
          <div className="mb-3 rounded-field border border-border bg-bg-elevated px-3 py-2 text-xs text-text-secondary">
            登录后才能回复问题。
            <button
              className="ml-2 text-accent underline-offset-2 hover:underline"
              onClick={() => nav('/login')}
            >
              去登录
            </button>
          </div>
        )}

        <div className="space-y-3">
          <textarea
            className="w-full min-h-[100px] rounded-lg border border-border px-2.5 py-1.5 text-sm bg-bg-elevated text-text-primary placeholder:text-text-muted"
            placeholder="输入你的回复内容，仅支持纯文字。"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            disabled={!user || answerM.isPending}
          />
          <div className="flex items-center justify-end">
            <Button
              variant="secondary"
              onClick={handleReply}
              disabled={!user || answerM.isPending || !body.trim()}
            >
              {answerM.isPending ? '发送中…' : '发送回复'}
            </Button>
          </div>
        </div>
      </Card>
    </div>
  )
}

