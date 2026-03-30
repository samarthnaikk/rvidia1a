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

  const renderStatus = async (jobId) => {
    try {
      const peers = await getPeers(authToken, jobId)
      return peers.ready ? 'P2P Ready' : 'Waiting for peer'
    } catch {
      return 'Coordination unavailable'
    }
  }

  return (
    <section className="relative min-h-screen w-full bg-[#040811] px-6 pb-10 pt-8 text-slate-100 md:px-10 lg:px-14">
      <div className="mx-auto w-full max-w-[1100px] rounded-[12px] border border-white/15 bg-[#0b1322d9] p-6">
        <div className="mb-8 flex items-center justify-between">
          <h1 className="text-[34px] font-bold text-slate-100">Job Status & Results</h1>
          <button
            className="rounded border border-white/20 px-4 py-2 text-[12px] uppercase tracking-[2px] text-slate-300"
            onClick={onBackDashboard}
            type="button"
          >
            Back
          </button>
        </div>

        {errorMessage && <p className="mb-4 text-[13px] text-red-300">{errorMessage}</p>}

        <div className="space-y-4">
          {jobs.map((job) => (
            <article
              className={`rounded border p-4 ${highlightedJobId === job.id ? 'border-emerald-300/80 bg-emerald-300/5' : 'border-white/15 bg-[#08101d]'}`}
              key={job.id}
            >
              <p className="text-[11px] uppercase tracking-[2px] text-slate-400">Job ID</p>
              <p className="mb-3 break-all font-jetbrains text-[13px] text-slate-100">{job.id}</p>

              <p className="text-[12px] text-slate-300">Repo: {job.repo_url || 'Not provided'}</p>
              <p className="text-[12px] text-slate-300">Branch: {job.branch || 'main'}</p>
              <p className="text-[12px] text-slate-300">Command: {job.command}</p>
              <p className="text-[12px] text-slate-300">Server Status: {job.status}</p>
              <p className="text-[12px] text-slate-300">Artifact: {job.artifact_path || 'Not yet available'}</p>
              {job.error_message && <p className="mt-2 text-[12px] text-red-300">Error: {job.error_message}</p>}

              <P2PStatusLabel getStatus={renderStatus} jobId={job.id} />
            </article>
          ))}

          {jobs.length === 0 && <p className="text-[13px] text-slate-400">No jobs yet. Submit a new job from dashboard.</p>}
        </div>
      </div>
    </section>
  )
}

function P2PStatusLabel({ jobId, getStatus }) {
  const [status, setStatus] = useState('Checking...')

  useEffect(() => {
    let active = true
    getStatus(jobId).then((value) => {
      if (active) {
        setStatus(value)
      }
    })
    return () => {
      active = false
    }
  }, [jobId, getStatus])

  return <p className="mt-2 text-[12px] text-emerald-200">P2P: {status}</p>
}

export default JobResultsPage
