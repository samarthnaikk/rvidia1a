import { useEffect, useState } from 'react'
import { listOpenJobs } from '../lib/api'

function DashboardPage({ authToken, onBackHome, onGoSubmit, onGoResults, onLogout, currentUser }) {
  const [selectedFile, setSelectedFile] = useState(null)
  const [openJobs, setOpenJobs] = useState([])
  const [hostError, setHostError] = useState('')

  useEffect(() => {
    let active = true

    const loadOpenJobs = async () => {
      try {
        const jobs = await listOpenJobs(authToken)
        if (active) {
          setOpenJobs(jobs)
          setHostError('')
        }
      } catch (error) {
        if (active) {
          setHostError(error.message)
        }
      }
    }

    loadOpenJobs()
    const intervalId = setInterval(loadOpenJobs, 5000)

    return () => {
      active = false
      clearInterval(intervalId)
    }
  }, [authToken])

  return (
    <section className="relative min-h-screen w-full bg-[#040811] px-6 pb-10 pt-8 text-slate-100 md:px-10 lg:px-14">
      <div className="mx-auto w-full max-w-[1200px]">
        <div className="mb-10 flex items-center justify-between">
          <div>
            <p className="text-[12px] uppercase tracking-[3px] text-emerald-300/70">Kinetic Core</p>
            <h1 className="mt-2 text-[42px] font-bold leading-[1.1] text-slate-100">
              Unified <span className="text-emerald-300">Dashboard</span>
            </h1>
            <p className="mt-3 text-[14px] text-slate-400">
              Signed in as <span className="text-emerald-200">{currentUser?.username || 'Unknown User'}</span>
            </p>
          </div>

          <div className="flex gap-3">
            <button
              className="rounded border border-white/20 px-4 py-2 text-[12px] uppercase tracking-[2px] text-slate-300 transition hover:border-emerald-300/60 hover:text-emerald-200"
              onClick={onBackHome}
              type="button"
            >
              Back Home
            </button>
            <button
              className="rounded border border-red-300/30 px-4 py-2 text-[12px] uppercase tracking-[2px] text-red-200 transition hover:border-red-300/60"
              onClick={onLogout}
              type="button"
            >
              Logout
            </button>
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <div className="rounded-[12px] border border-emerald-300/25 bg-[#0b1322c9] p-6 shadow-[0_0_32px_rgba(16,185,129,0.12)]">
            <p className="text-[10px] uppercase tracking-[3px] text-emerald-300/75">Operational Mode</p>
            <h2 className="mt-3 text-[34px] font-bold uppercase tracking-[1px] text-slate-100">Rent Compute</h2>
            <p className="mt-2 text-[15px] text-slate-400">Upload your task file to rent distributed compute resources.</p>

            <label className="mt-7 block rounded-[10px] border border-dashed border-emerald-300/45 bg-[#0d1729] px-5 py-10 text-center">
              <span className="block text-[12px] uppercase tracking-[3px] text-slate-400">Drop file here or click to upload</span>
              <span className="mt-3 block text-[13px] text-emerald-200/90">
                {selectedFile ? selectedFile.name : 'No file selected'}
              </span>
              <input
                className="hidden"
                onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
                type="file"
              />
            </label>

            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <button
                className="h-[48px] w-full rounded-[6px] border border-emerald-200/70 bg-[#95f2bd] text-[13px] font-bold uppercase tracking-[3px] text-[#0b2d1e]"
                onClick={onGoSubmit}
                type="button"
              >
                Submit GPU Job
              </button>

              <button
                className="h-[48px] w-full rounded-[6px] border border-white/20 bg-transparent text-[12px] font-bold uppercase tracking-[2px] text-slate-300"
                onClick={onGoResults}
                type="button"
              >
                View Job Status / Results
              </button>
            </div>

            <div className="mt-5 space-y-3">
              <div className="rounded border border-white/10 bg-[#060b14] p-3">
                <p className="text-[10px] uppercase tracking-[2px] text-slate-500">Renter Setup Command</p>
                <p className="mt-2 break-all font-jetbrains text-[11px] text-emerald-200">
                  cd backend && pip install -r requirements.txt
                </p>
              </div>

              <div className="rounded border border-white/10 bg-[#060b14] p-3">
                <p className="text-[10px] uppercase tracking-[2px] text-slate-500">Renter Run Command (After Job Creation)</p>
                <p className="mt-2 break-all font-jetbrains text-[11px] text-emerald-200">
                  python -m app.core.p2p_cli receiver --api-base http://localhost:8000 --token {authToken || 'MISSING_TOKEN'} --job-id &lt;JOB_ID&gt; --host-node-id &lt;HOST_NODE_ID&gt; --file-path /absolute/path/to/input.file --command "python {'{input}'}"
                </p>
              </div>
            </div>
          </div>

          <div className="rounded-[12px] border border-white/15 bg-[#0b1322c9] p-6">
            <p className="text-[10px] uppercase tracking-[3px] text-emerald-300/75">Operational Mode</p>
            <h2 className="mt-3 text-[34px] font-bold uppercase tracking-[1px] text-slate-100">Host Compute</h2>
            <p className="mt-2 text-[15px] text-slate-400">Open jobs are visible below. Accept any job using terminal commands only.</p>

            {hostError && <p className="mt-4 text-[12px] text-red-300">{hostError}</p>}

            <div className="mt-6 space-y-4">
              {openJobs.map((job) => (
                <article className="rounded border border-white/15 bg-[#08101d] p-4" key={job.id}>
                  <p className="text-[10px] uppercase tracking-[2px] text-slate-500">Open Job</p>
                  <p className="font-jetbrains mt-1 break-all text-[12px] text-slate-200">{job.id}</p>
                  <p className="mt-2 text-[12px] text-slate-300">Owner: user #{job.user_id}</p>
                  <p className="text-[12px] text-slate-300">File: {job.filename}</p>
                  <p className="text-[12px] text-slate-300">Command: {job.command}</p>
                  <p className="text-[12px] text-emerald-200">Status: {job.status}</p>

                  <div className="mt-3 rounded border border-white/10 bg-[#060b14] p-3">
                    <p className="text-[10px] uppercase tracking-[2px] text-slate-500">Host Accept Command</p>
                    <p className="mt-2 break-all font-jetbrains text-[11px] text-emerald-200">
                      python -m app.core.p2p_cli host --api-base http://localhost:8000 --token {authToken || 'MISSING_TOKEN'} --job-id {job.id}
                    </p>
                  </div>
                </article>
              ))}

              {openJobs.length === 0 && (
                <p className="text-[13px] text-slate-400">No open jobs currently available for hosting.</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

export default DashboardPage
