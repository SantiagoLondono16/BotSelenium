import { useState } from 'react'
import { triggerExtraction } from '../api'
import type { ExtractResponse } from '../types'

interface Props {
  onJobCreated: (response: ExtractResponse) => void
}

export function NewJob({ onJobCreated }: Props) {
  const today = new Date().toISOString().slice(0, 10)

  const [fechaInicial, setFechaInicial] = useState('2026-03-03')
  const [fechaFinal, setFechaFinal]     = useState(today)
  const [limit, setLimit]               = useState(500)
  const [loading, setLoading]           = useState(false)
  const [error, setError]               = useState<string | null>(null)
  const [success, setSuccess]           = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setSuccess(null)
    setLoading(true)
    try {
      const resp = await triggerExtraction({
        fecha_inicial: fechaInicial,
        fecha_final: fechaFinal,
        limit_requested: limit,
      })
      setSuccess(`Job creado: ${resp.job_id}`)
      onJobCreated(resp)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-lg">
      <h2 className="text-lg font-semibold mb-4">Nueva extracción</h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">Fecha inicial</label>
          <input
            type="date"
            value={fechaInicial}
            onChange={e => setFechaInicial(e.target.value)}
            required
            className="border rounded px-3 py-1.5 w-full text-sm"
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Fecha final</label>
          <input
            type="date"
            value={fechaFinal}
            onChange={e => setFechaFinal(e.target.value)}
            required
            className="border rounded px-3 py-1.5 w-full text-sm"
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">
            Límite de filas: <span className="font-bold">{limit}</span>
          </label>
          <input
            type="range"
            min={1}
            max={10000}
            step={50}
            value={limit}
            onChange={e => setLimit(Number(e.target.value))}
            className="w-full"
          />
          <div className="flex justify-between text-xs text-gray-400 mt-0.5">
            <span>1</span><span>10 000</span>
          </div>
        </div>

        {error   && <p className="text-sm text-red-600">{error}</p>}
        {success && <p className="text-sm text-green-600">{success}</p>}

        <button
          type="submit"
          disabled={loading}
          className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-semibold px-4 py-2 rounded text-sm"
        >
          {loading ? 'Enviando…' : 'Iniciar extracción'}
        </button>
      </form>
    </div>
  )
}
