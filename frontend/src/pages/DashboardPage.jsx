import { useEffect, useState } from 'react'
import { acceptJobAccess, listJobs, listMarketplaceJobs, requestJobAccess } from '../lib/api'

function DashboardPage({ authToken, onBackHome, onGoSubmit, onGoResults, onLogout, currentUser }) {
  const defaultApiBase = 'http://157.180.74.2'
  const [marketplaceJobs, setMarketplaceJobs] = useState([])
  const [myJobs, setMyJobs] = useState([])
  const [hostError, setHostError] = useState('')
  const [rentError, setRentError] = useState('')
  const tokenForCmd = authToken || 'MISSING_TOKEN'
  const latestOwnedJob = myJobs[0] || null
  const renterJobId = latestOwnedJob?.id || '<CREATE_JOB_FIRST>'
  const renterRepoUrl = latestOwnedJob?.repo_url || '<REPO_URL>'
  const renterBranch = latestOwnedJob?.branch || 'main'
  const renterRunCommand =
    `python -m app.core.p2p_cli receiver --api-base ${defaultApiBase} --token ${tokenForCmd} ` +
    `--job-id ${renterJobId} --repo-url "${renterRepoUrl}" --branch "${renterBranch}"`

  const refreshMarketplace = async (active) => {
    try {
      const jobs = await listMarketplaceJobs(authToken)
      if (active) {
        setMarketplaceJobs(jobs)
        setHostError('')
      }
    } catch (error) {
      if (active) {
        setHostError(error.message)
      }
    }
  }

  useEffect(() => {
    let active = true

    refreshMarketplace(active)
    const intervalId = setInterval(() => refreshMarketplace(active), 5000)

    return () => {
      active = false
      clearInterval(intervalId)
    }
  }, [authToken])

  const handleRequestAccess = async (jobId) => {
    try {
      await requestJobAccess(authToken, jobId)
      await refreshMarketplace(true)
    } catch (error) {
      setHostError(error.message)
    }
  }

  const handleAcceptAccess = async (jobId) => {
    try {
      await acceptJobAccess(authToken, jobId)
      await refreshMarketplace(true)
    } catch (error) {
      setHostError(error.message)
    }
  }

  useEffect(() => {
    let active = true

    const loadMyJobs = async () => {
      try {
        const jobs = await listJobs(authToken)
        if (active) {
          setMyJobs(jobs)
          setRentError('')
        }
      } catch (error) {
        if (active) {
          setRentError(error.message)
        }
      }
    }

    loadMyJobs()
    const intervalId = setInterval(loadMyJobs, 5000)

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
            <p className="text-[12px] uppercase tracking-[3px] text-emerald-300/70">RVIDIA</p>
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
            <p className="mt-2 text-[15px] text-slate-400">Submit a GitHub repository and run it on distributed compute resources.</p>

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
              {rentError && <p className="text-[12px] text-red-300">{rentError}</p>}

              <div className="rounded border border-white/10 bg-[#060b14] p-3">
                <p className="text-[10px] uppercase tracking-[2px] text-slate-500">Renter Setup Command</p>
                <p className="mt-2 break-all font-jetbrains text-[11px] text-emerald-200">
                  cd backend && pip install -r requirements.txt
                </p>
              </div>

              <div className="rounded border border-white/10 bg-[#060b14] p-3">
                <p className="text-[10px] uppercase tracking-[2px] text-slate-500">Renter Run Command (After Job Creation)</p>
                <p className="mt-2 break-all font-jetbrains text-[11px] text-emerald-200">
                  {renterRunCommand}
                </p>
              </div>
            </div>
          </div>

          <div className="rounded-[12px] border border-white/15 bg-[#0b1322c9] p-6">
            <p className="text-[10px] uppercase tracking-[3px] text-emerald-300/75">Operational Mode</p>
            <h2 className="mt-3 text-[34px] font-bold uppercase tracking-[1px] text-slate-100">Host Compute</h2>
            <p className="mt-2 text-[15px] text-slate-400">Marketplace visibility is controlled by bilateral request/accept.</p>

            {hostError && <p className="mt-4 text-[12px] text-red-300">{hostError}</p>}

            <div className="mt-6 space-y-4">
              {marketplaceJobs.map((job) => (
                <article className="rounded border border-white/15 bg-[#08101d] p-4" key={job.job_id}>
                  <p className="text-[10px] uppercase tracking-[2px] text-slate-500">Open Job</p>
                  <p className="font-jetbrains mt-1 break-all text-[12px] text-slate-200">{job.job_id}</p>
                  <p className="mt-2 text-[12px] text-slate-300">Owner: user #{job.user_id}</p>
                  <p className="text-[12px] text-slate-300">Repo: {job.repo_url || 'Not provided'}</p>
                  <p className="text-[12px] text-slate-300">Branch: {job.branch || 'main'}</p>
                  <p className="text-[12px] text-emerald-200">Status: {job.status}</p>
                  <p className="text-[12px] text-slate-300">Access: {job.access_status}</p>

                  {job.can_request && (
                    <button
                      className="mt-3 rounded border border-emerald-200/70 bg-[#95f2bd] px-3 py-2 text-[11px] font-bold uppercase tracking-[2px] text-[#0b2d1e]"
                      onClick={() => handleRequestAccess(job.job_id)}
                      type="button"
                    >
                      Request Access
                    </button>
                  )}

                  {job.can_accept && (
                    <button
                      className="mt-3 rounded border border-emerald-200/70 bg-[#95f2bd] px-3 py-2 text-[11px] font-bold uppercase tracking-[2px] text-[#0b2d1e]"
                      onClick={() => handleAcceptAccess(job.job_id)}
                      type="button"
                    >
                      Accept Access
                    </button>
                  )}

                  <div className="mt-3 rounded border border-white/10 bg-[#060b14] p-3">
                    <p className="text-[10px] uppercase tracking-[2px] text-slate-500">Host Accept Command</p>
                    <p className="mt-2 break-all font-jetbrains text-[11px] text-emerald-200">
                      {`python -m app.core.p2p_cli host --api-base ${defaultApiBase} --token ${tokenForCmd} --job-id ${job.job_id}`}
                    </p>
                  </div>

                  {job.can_accept && (
                    <div className="mt-3 rounded border border-white/10 bg-[#060b14] p-3">
                      <p className="text-[10px] uppercase tracking-[2px] text-slate-500">Owner CLI Accept Command</p>
                      <p className="mt-2 break-all font-jetbrains text-[11px] text-emerald-200">
                        {`python -m app.core.p2p_cli accept-access --api-base ${defaultApiBase} --token ${tokenForCmd} --job-id ${job.job_id}`}
                      </p>
                    </div>
                  )}
                </article>
              ))}

              {marketplaceJobs.length === 0 && (
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
