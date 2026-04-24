import type {
  ExtractResponse,
  JobDetail,
  JobStatus,
  PaginatedJobs,
  PaginatedRecords,
} from './types'

const BASE = import.meta.env.VITE_API_URL ?? ''

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init)
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`${res.status} ${res.statusText}: ${body}`)
  }
  return res.json() as Promise<T>
}

export function triggerExtraction(payload: {
  fecha_inicial: string
  fecha_final: string
  limit_requested: number
}): Promise<ExtractResponse> {
  return request('/rpa/extract', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function fetchJobs(params: {
  page?: number
  size?: number
  status?: JobStatus | null
}): Promise<PaginatedJobs> {
  const q = new URLSearchParams()
  if (params.page) q.set('page', String(params.page))
  if (params.size) q.set('size', String(params.size))
  if (params.status) q.set('status', params.status)
  return request(`/jobs?${q}`)
}

export function fetchJob(id: string): Promise<JobDetail> {
  return request(`/jobs/${id}`)
}

export function fetchRecords(params: {
  page?: number
  size?: number
  job_id?: string | null
}): Promise<PaginatedRecords> {
  const q = new URLSearchParams()
  if (params.page) q.set('page', String(params.page))
  if (params.size) q.set('size', String(params.size))
  if (params.job_id) q.set('job_id', params.job_id)
  return request(`/records?${q}`)
}
