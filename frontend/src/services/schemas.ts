import type { JobType } from '../types/jobs'

export interface CreateJobRequest {
  type: JobType
  remark?: string
  params: Record<string, any>
}

export interface CreateJobResponse {
  job_id: string
}
