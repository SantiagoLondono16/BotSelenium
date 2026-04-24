// Matches the Pydantic schemas in app/schemas/

export type JobStatus = 'pending' | 'running' | 'success' | 'failed'

export interface JobSummary {
  id: string
  status: JobStatus
  fecha_inicial: string
  fecha_final: string
  limit_requested: number
  total_extracted: number | null
  created_at: string
}

export interface JobDetail extends JobSummary {
  error_message: string | null
  started_at: string | null
  finished_at: string | null
}

export interface PaginatedJobs {
  total: number
  page: number
  size: number
  items: JobSummary[]
}

export interface RecordOut {
  id: string
  job_id: string
  external_row_id: string | null
  patient_name: string | null
  patient_document: string | null
  date_service_or_facturation: string | null
  site: string | null
  contract: string | null
  raw_row_json: Record<string, unknown>
  captured_at: string
}

export interface PaginatedRecords {
  total: number
  page: number
  size: number
  items: RecordOut[]
}

export interface ExtractResponse {
  job_id: string
  status: JobStatus
}
