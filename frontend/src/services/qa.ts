import { apiGet, apiPost } from './api'
import type { QaQuestionSummary, QaQuestionDetail, QaAnswer } from '../types/qa'

export async function listQuestions(query?: string): Promise<QaQuestionSummary[]> {
  const q = query && query.trim() ? `?q=${encodeURIComponent(query.trim())}` : ''
  return apiGet<QaQuestionSummary[]>(`/qa/questions${q}`)
}

export async function getQuestion(id: number): Promise<QaQuestionDetail> {
  return apiGet<QaQuestionDetail>(`/qa/questions/${id}`)
}

export async function createQuestion(title: string, body: string): Promise<QaQuestionDetail> {
  return apiPost<QaQuestionDetail>('/qa/questions', { title, body })
}

export async function createAnswer(questionId: number, body: string): Promise<QaAnswer> {
  return apiPost<QaAnswer>(`/qa/questions/${questionId}/answers`, { body })
}

