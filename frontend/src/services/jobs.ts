import { api } from './api'
import type { CreateJobRequest, CreateJobResponse } from './schemas'
import type { JobDetail, JobResult, JobStats, JobSummary } from '../types/jobs'

export async function createJob(req: CreateJobRequest): Promise<CreateJobResponse> {
  const { data } = await api.post<CreateJobResponse>('/jobs', req)
  return data
}

export async function listJobs(): Promise<JobSummary[]> {
  const { data } = await api.get<JobSummary[]>('/jobs')
  return data
}

export async function getJob(jobId: string): Promise<JobDetail> {
  const { data } = await api.get<JobDetail>(`/jobs/${jobId}`)
  return data
}

export async function getJobResult(jobId: string): Promise<JobResult> {
  const { data } = await api.get<JobResult>(`/jobs/${jobId}/result`)
  return data
}

export async function getJobStats(): Promise<JobStats> {
  const { data } = await api.get<JobStats>('/jobs/stats')
  return data
}
