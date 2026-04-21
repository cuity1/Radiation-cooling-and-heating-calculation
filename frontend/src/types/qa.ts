export interface QaQuestionSummary {
  id: number
  title: string
  excerpt: string
  answer_count: number
  author_username: string
  created_at: string // ISO string
  updated_at: string // ISO string
}

export interface QaAnswer {
  id: number
  body: string
  author_username: string
  created_at: string // ISO string
  updated_at: string // ISO string
}

export interface QaQuestionDetail {
  id: number
  title: string
  body: string
  author_username: string
  created_at: string // ISO string
  updated_at: string // ISO string
  answers: QaAnswer[]
}

