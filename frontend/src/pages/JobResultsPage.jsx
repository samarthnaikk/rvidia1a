import { useEffect, useState } from 'react'
import { getPeers, listJobs } from '../lib/api'

function JobResultsPage({ authToken, onBackDashboard, highlightedJobId }) {
  const [jobs, setJobs] = useState([])
  const [errorMessage, setErrorMessage] = useState('')

  useEffect(() => {
    let active = true

    const loadJobs = async () => {
      try {
        const data = await listJobs(authToken)
        if (active) {
          setJobs(data)
          setErrorMessage('')
        }
      } catch (error) {
        if (active) {
          setErrorMessage(error.message)
        }
      }
    }

    loadJobs()
    const intervalId = setInterval(loadJobs, 5000)

    return () => {
      active = false
      clearInterval(intervalId)
    }
  }, [authToken])

  const normalizeStatus = (statusValue) => {
    const normalized = (statusValue || '').toLowerCase()
    if (normalized.includes('complete') || normalized.includes('success') || normalized === 'done') {
      return 'COMPLETED'
    }
    if (normalized.includes('fail') || normalized.includes('error')) {
      return 'FAILED'
    }
    return 'RUNNING'
  }

  return (
    <section className="relative min-h-screen w-full overflow-hidden bg-[#050a12] px-2 pb-10 pt-2 text-slate-100 md:px-3 lg:px-4">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_82%_18%,rgba(110,255,181,0.13),transparent_32%),linear-gradient(118deg,rgba(6,12,20,0.98)_0%,rgba(4,9,16,0.98)_46%,rgba(4,8,14,1)_100%)]" />

      <div className="relative z-10 mx-auto w-full max-w-[1560px]">
        <div className="mb-6 flex items-center justify-between px-2 pt-2">
          <h1 className="font-space text-[32px] font-bold tracking-[1px] text-slate-100">Job Status & Results</h1>
          <button
            className="font-jetbrains rounded border border-white/20 px-4 py-2 text-[11px] uppercase tracking-[2px] text-slate-300"
            onClick={onBackDashboard}
            type="button"
          >
            Back
          </button>
        </div>

        {errorMessage && <p className="font-jetbrains mb-4 px-2 text-[13px] text-red-300">{errorMessage}</p>}

        <div className="space-y-4">
          {jobs.map((job) => (
            <article
              className={`border p-6 ${highlightedJobId === job.id ? 'border-emerald-300/65 bg-[linear-gradient(102deg,#111c26_0%,#0b131f_45%,#0a111b_100%)]' : 'border-white/10 bg-[linear-gradient(102deg,#0f1722_0%,#0b121c_45%,#0a1119_100%)]'}`}
              key={job.id}
            >
              <div className="grid items-center gap-6 lg:grid-cols-[1.1fr_1.35fr_1fr_auto]">
                <div className="border-l-[4px] border-emerald-200 pl-6">
                  <p className="font-jetbrains text-[12px] font-medium uppercase tracking-[2px] text-slate-500">Job Identifier</p>
                  <p className={`font-jetbrains mt-2 text-[30px] font-semibold leading-[36px] tracking-[0px] ${normalizeStatus(job.status) === 'COMPLETED' ? 'text-slate-100' : 'text-emerald-300'}`}>
                    {job.id}
                  </p>

                  <div className="mt-4 flex flex-wrap items-center gap-2.5">
                    <StatusBadge status={normalizeStatus(job.status)} />
                    <P2PStatusBadge authToken={authToken} jobId={job.id} />
                  </div>

                  {job.error_message && <p className="font-jetbrains mt-3 text-[13px] text-red-300">Error: {job.error_message}</p>}
                </div>

                <div className="border-l border-l-white/10 pl-6">
                  <p className="font-jetbrains break-words text-[14px] font-medium leading-[20px] tracking-[0px] text-slate-100">{job.command || 'No command provided'}</p>
                  <p className="font-jetbrains mt-2 truncate text-[14px] font-medium leading-[20px] tracking-[0px] text-slate-400" title={job.repo_url || 'Not provided'}>
                    {job.repo_url || 'Not provided'}
                  </p>
                  <p className="font-jetbrains mt-2 text-[14px] font-medium leading-[20px] tracking-[0px] text-slate-400">branch: {job.branch || 'main'}</p>
                </div>

                <div className="border-l border-l-white/10 pl-6">
                  <p className="font-jetbrains text-[12px] font-medium uppercase tracking-[2px] text-slate-500">Artifact Path</p>
                  <div className="mt-2 bg-[#f8fbff0f] px-4 py-3">
                    <p className="font-jetbrains break-words text-[14px] font-medium leading-[20px] tracking-[0px] text-slate-200">
                      {job.artifact_path || 'Not yet available'}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3 lg:justify-end">
                  {normalizeStatus(job.status) === 'COMPLETED' ? (
                    <>
                      <button
                        className="font-jetbrains h-[52px] border border-emerald-200/35 px-6 text-[14px] font-medium uppercase tracking-[2px] leading-[20px] text-emerald-200 transition hover:border-emerald-200/60"
                        type="button"
                      >
                        Logs
                      </button>
                      <button
                        className="grid h-[52px] w-[52px] place-items-center rounded-[16px] border border-white/15 text-[24px] text-slate-200 transition hover:border-white/40"
                        type="button"
                        aria-label="Download artifact"
                      >
                        ⇩
                      </button>
                    </>
                  ) : (
                    <button
                      className="grid h-[52px] w-[52px] place-items-center rounded-[16px] border border-white/15 text-[24px] text-slate-200 transition hover:border-white/40"
                      type="button"
                      aria-label="Expand job details"
                    >
                      ⌄
                    </button>
                  )}
                </div>
              </div>
            </article>
          ))}

          {jobs.length === 0 && <p className="font-jetbrains px-2 text-[13px] text-slate-400">No jobs yet. Submit a new job from dashboard.</p>}
        </div>
      </div>
    </section>
  )
}

function StatusBadge({ status }) {
  const isCompleted = status === 'COMPLETED'
  const isFailed = status === 'FAILED'

  return (
    <span
      className={`font-jetbrains inline-flex items-center border px-3 py-1.5 text-[14px] font-medium uppercase leading-[20px] tracking-[0px] ${
        isCompleted
          ? 'border-emerald-200/30 bg-emerald-300/12 text-emerald-200'
          : isFailed
            ? 'border-red-200/30 bg-red-300/10 text-red-200'
            : 'border-emerald-200/30 bg-emerald-300/12 text-emerald-200'
      }`}
    >
      {isCompleted ? '● Completed' : isFailed ? '● Failed' : '↺ Running'}
    </span>
  )
}

function P2PStatusBadge({ jobId, authToken }) {
  const [status, setStatus] = useState('Checking...')

  useEffect(() => {
    let active = true

    const loadPeerState = async () => {
      try {
        const peers = await getPeers(authToken, jobId)
        if (active) {
          setStatus(peers.ready ? 'P2P Ready' : 'Waiting')
        }
      } catch {
        if (active) {
          setStatus('Unavailable')
        }
      }
    }

    loadPeerState()

    return () => {
      active = false
    }
  }, [authToken, jobId])

  const isReady = status === 'P2P Ready'

  return (
    <span
      className={`font-jetbrains inline-flex items-center border px-3 py-1.5 text-[14px] font-medium uppercase leading-[20px] tracking-[0px] ${
        isReady ? 'border-emerald-200/30 bg-emerald-300/12 text-emerald-200' : 'border-white/15 bg-white/5 text-slate-300'
      }`}
    >
      ⟷ {status}
    </span>
  )
}

export default JobResultsPage
