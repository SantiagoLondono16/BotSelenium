import { useState } from 'react'
import type { ExtractResponse, JobSummary } from './types'
import { NewJob } from './components/NewJob'
import { JobsTable } from './components/JobsTable'
import { RecordsTable } from './components/RecordsTable'

type Tab = 'new' | 'jobs' | 'records'

export default function App() {
  const [tab, setTab]             = useState<Tab>('new')
  const [lastJob, setLastJob]     = useState<ExtractResponse | null>(null)
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)

  function handleJobCreated(resp: ExtractResponse) {
    setLastJob(resp)
    setTab('jobs')
  }

  function handleSelectJob(job: JobSummary) {
    setSelectedJobId(job.id)
    setTab('records')
  }

  const tabs: Array<{ id: Tab; label: string }> = [
    { id: 'new',     label: 'Nueva extracción' },
    { id: 'jobs',    label: 'Ejecuciones' },
    { id: 'records', label: 'Registros' },
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b shadow-sm">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center gap-3">
          <svg
            className="w-6 h-6 text-blue-600"
            fill="none" stroke="currentColor" strokeWidth={2}
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round"
              d="M9 17v-6m6 6v-3M3 20h18M5 4h14a1 1 0 011 1v10a1 1 0 01-1 1H5a1 1 0 01-1-1V5a1 1 0 011-1z"
            />
          </svg>
          <h1 className="font-bold text-gray-800">RPA Extraction</h1>
          <span className="text-xs text-gray-400 ml-auto">Aquila · Savia Salud Subsidiado · US</span>
        </div>

        {/* Tabs */}
        <nav className="max-w-6xl mx-auto px-4 flex gap-1">
          {tabs.map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`
                px-4 py-2 text-sm font-medium border-b-2 transition-colors
                ${tab === t.id
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'}
              `}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      {/* Content */}
      <main className="max-w-6xl mx-auto px-4 py-6">
        {tab === 'new' && (
          <NewJob onJobCreated={handleJobCreated} />
        )}
        {tab === 'jobs' && (
          <JobsTable
            highlightJobId={lastJob?.job_id}
            onSelectJob={handleSelectJob}
          />
        )}
        {tab === 'records' && (
          <RecordsTable
            jobId={selectedJobId}
            onClearJob={() => setSelectedJobId(null)}
          />
        )}
      </main>
    </div>
  )
}
