import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchJobs } from '../api'
import type { JobSummary, JobStatus } from '../types'
import { StatusBadge } from './StatusBadge'

interface Props {
  /** When set, the table will auto-refresh while the job is running/pending. */
  highlightJobId?: string | null
  onSelectJob: (job: JobSummary) => void
}

const STATUS_OPTIONS: Array<JobStatus | ''> = ['', 'pending', 'running', 'success', 'failed']

export function JobsTable({ highlightJobId, onSelectJob }: Props) {
  const [jobs, setJobs]         = useState<JobSummary[]>([])
  const [total, setTotal]       = useState(0)
  const [page, setPage]         = useState(1)
  const [statusFilter, setStatusFilter] = useState<JobStatus | ''>('')
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState<string | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchJobs({
        page,
        size: 20,
        status: statusFilter || null,
      })
      setJobs(data.items)
      setTotal(data.total)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [page, statusFilter])

  // Load when page/filter changes.
  useEffect(() => { load() }, [load])

  // Auto-refresh every 5 s while there are running/pending jobs.
  useEffect(() => {
    const hasActive = jobs.some(j => j.status === 'pending' || j.status === 'running')
    if (hasActive || highlightJobId) {
      intervalRef.current = setInterval(load, 5000)
    } else {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [jobs, highlightJobId, load])

  const totalPages = Math.max(1, Math.ceil(total / 20))

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold">Ejecuciones</h2>
        <div className="flex items-center gap-2">
          <select
            value={statusFilter}
            onChange={e => { setStatusFilter(e.target.value as JobStatus | ''); setPage(1) }}
            className="border rounded px-2 py-1 text-sm"
          >
            {STATUS_OPTIONS.map(s => (
              <option key={s} value={s}>{s || 'Todos los estados'}</option>
            ))}
          </select>
          <button
            onClick={load}
            className="text-sm text-blue-600 hover:underline"
          >
            Actualizar
          </button>
        </div>
      </div>

      {error && <p className="text-sm text-red-600 mb-2">{error}</p>}

      <div className="overflow-x-auto rounded border">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 text-left">
            <tr>
              <th className="px-3 py-2 font-medium">ID</th>
              <th className="px-3 py-2 font-medium">Estado</th>
              <th className="px-3 py-2 font-medium">Período</th>
              <th className="px-3 py-2 font-medium">Filas</th>
              <th className="px-3 py-2 font-medium">Creado</th>
              <th className="px-3 py-2 font-medium"></th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {loading && jobs.length === 0 ? (
              <tr><td colSpan={6} className="px-3 py-4 text-center text-gray-500">Cargando…</td></tr>
            ) : jobs.length === 0 ? (
              <tr><td colSpan={6} className="px-3 py-4 text-center text-gray-400">Sin resultados</td></tr>
            ) : jobs.map(job => (
              <tr
                key={job.id}
                className={job.id === highlightJobId ? 'bg-blue-50' : 'hover:bg-gray-50'}
              >
                <td className="px-3 py-2 font-mono text-xs text-gray-500 whitespace-nowrap">
                  {job.id.slice(0, 8)}…
                </td>
                <td className="px-3 py-2"><StatusBadge status={job.status} /></td>
                <td className="px-3 py-2 whitespace-nowrap">
                  {job.fecha_inicial} → {job.fecha_final}
                </td>
                <td className="px-3 py-2">
                  {job.total_extracted ?? '—'} / {job.limit_requested}
                </td>
                <td className="px-3 py-2 text-xs text-gray-500 whitespace-nowrap">
                  {new Date(job.created_at).toLocaleString('es-CO')}
                </td>
                <td className="px-3 py-2">
                  <button
                    onClick={() => onSelectJob(job)}
                    className="text-blue-600 hover:underline text-xs"
                  >
                    Ver registros
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between mt-3 text-sm text-gray-600">
        <span>{total} ejecución{total !== 1 ? 'es' : ''}</span>
        <div className="flex gap-2">
          <button
            disabled={page <= 1}
            onClick={() => setPage(p => p - 1)}
            className="px-2 py-0.5 border rounded disabled:opacity-40"
          >
            ‹
          </button>
          <span>{page} / {totalPages}</span>
          <button
            disabled={page >= totalPages}
            onClick={() => setPage(p => p + 1)}
            className="px-2 py-0.5 border rounded disabled:opacity-40"
          >
            ›
          </button>
        </div>
      </div>
    </div>
  )
}
