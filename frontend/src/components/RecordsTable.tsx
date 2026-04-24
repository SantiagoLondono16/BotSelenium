import { useCallback, useEffect, useState } from 'react'
import { fetchRecords } from '../api'
import type { RecordOut } from '../types'

interface Props {
  /** If provided, only show records from this job. */
  jobId?: string | null
  onClearJob?: () => void
}

export function RecordsTable({ jobId, onClearJob }: Props) {
  const [records, setRecords]   = useState<RecordOut[]>([])
  const [total, setTotal]       = useState(0)
  const [page, setPage]         = useState(1)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState<string | null>(null)

  // Reset to page 1 when jobId filter changes.
  useEffect(() => { setPage(1) }, [jobId])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchRecords({ page, size: 20, job_id: jobId })
      setRecords(data.items)
      setTotal(data.total)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [page, jobId])

  useEffect(() => { load() }, [load])

  const totalPages = Math.max(1, Math.ceil(total / 20))

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold">Registros</h2>
          {jobId && (
            <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded">
              Job {jobId.slice(0, 8)}…
              {onClearJob && (
                <button onClick={onClearJob} className="ml-1 hover:text-blue-900">×</button>
              )}
            </span>
          )}
        </div>
        <button onClick={load} className="text-sm text-blue-600 hover:underline">
          Actualizar
        </button>
      </div>

      {error && <p className="text-sm text-red-600 mb-2">{error}</p>}

      <div className="overflow-x-auto rounded border">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 text-left">
            <tr>
              <th className="px-3 py-2 font-medium">No. Orden</th>
              <th className="px-3 py-2 font-medium">Cód. Autorización</th>
              <th className="px-3 py-2 font-medium">Paciente</th>
              <th className="px-3 py-2 font-medium">Documento</th>
              <th className="px-3 py-2 font-medium">Fecha servicio</th>
              <th className="px-3 py-2 font-medium">Sede</th>
              <th className="px-3 py-2 font-medium">No. Acceso</th>
              <th className="px-3 py-2 font-medium">Régimen</th>
              <th className="px-3 py-2 font-medium">Capturado</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {loading && records.length === 0 ? (
              <tr><td colSpan={9} className="px-3 py-4 text-center text-gray-500">Cargando…</td></tr>
            ) : records.length === 0 ? (
              <tr><td colSpan={9} className="px-3 py-4 text-center text-gray-400">Sin registros</td></tr>
            ) : records.map(r => (
              <tr key={r.id} className="hover:bg-gray-50">
                <td className="px-3 py-2 font-mono text-xs">{r.external_row_id ?? '—'}</td>
                <td className="px-3 py-2 font-mono text-xs">
                  {(r.raw_row_json as Record<string, string>)['authorization_code'] ?? '—'}
                </td>
                <td className="px-3 py-2">{r.patient_name ?? '—'}</td>
                <td className="px-3 py-2">{r.patient_document ?? '—'}</td>
                <td className="px-3 py-2 whitespace-nowrap">
                  {r.date_service_or_facturation ?? '—'}
                </td>
                <td className="px-3 py-2">{r.site ?? '—'}</td>
                <td className="px-3 py-2 font-mono text-xs">{r.contract ?? '—'}</td>
                <td className="px-3 py-2">
                  {(r.raw_row_json as Record<string, string>)['regime'] ?? '—'}
                </td>
                <td className="px-3 py-2 text-xs text-gray-500 whitespace-nowrap">
                  {new Date(r.captured_at).toLocaleString('es-CO')}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between mt-3 text-sm text-gray-600">
        <span>{total} registro{total !== 1 ? 's' : ''}</span>
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
