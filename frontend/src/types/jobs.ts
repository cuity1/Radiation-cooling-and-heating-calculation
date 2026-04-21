export type JobType =
  | 'cooling'
  | 'heating'
  | 'in_situ_simulation'
  | 'energy_map'
  | 'compare_materials'
  | 'compare_glass'
  | 'radiation_cooling_clothing'
  | 'material_env_temp_cloud'
  | 'mock';
export type JobStatus = 'queued' | 'started' | 'succeeded' | 'failed' | 'cancelled';

export interface JobSummary {
  id: string;
  type: JobType;
  status: JobStatus;
  remark?: string;
  created_at: string; // ISO string
  updated_at: string; // ISO string
}

export interface JobDetail extends JobSummary {
  params: Record<string, any>;
  result_ready: boolean;
  error_message: string | null;
  user_id: number | null;
}

export interface JobResult {
  job_id: string;
  generated_at: string; // ISO string
  summary: Record<string, any>;
  plots: any[]; // Define more strictly later
  artifacts: any[]; // Define more strictly later
}

export interface JobStats {
  total_jobs: number;
  today_jobs: number;
}
