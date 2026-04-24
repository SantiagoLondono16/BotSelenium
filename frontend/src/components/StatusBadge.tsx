import type { JobStatus } from '../types'

const MAP: Record<JobStatus, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  running: 'bg-blue-100 text-blue-800',
  success: 'bg-green-100 text-green-800',
  failed:  'bg-red-100 text-red-800',
}

export function StatusBadge({ status }: { status: JobStatus }) {
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-semibold ${MAP[status]}`}>
      {status}
    </span>
  )
}
