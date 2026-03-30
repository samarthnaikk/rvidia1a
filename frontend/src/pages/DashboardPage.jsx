import { useEffect, useState } from 'react'
import {
  acceptJobAccess,
  getContributorSummaries,
  getDailyAnalytics,
  getP2PTelemetry,
  listJobs,
  listMarketplaceJobs,
  requestJobAccess,
} from '../lib/api'

function DashboardPage({ authToken, onBackHome, onGoSubmit, onGoResults, onLogout, currentUser }) {
  const defaultApiBase = (() => {
    const configured = import.meta.env.VITE_API_BASE_URL
    if (configured && typeof configured === 'string') {
      return configured.replace(/\/$/, '')
    }
    const host = window.location.hostname
    if (host === 'localhost' || host === '127.0.0.1') {
      return 'http://localhost:8000'
    }
    return `${window.location.origin}/api`
  })()
  const [marketplaceJobs, setMarketplaceJobs] = useState([])
  const [myJobs, setMyJobs] = useState([])
  const [telemetry, setTelemetry] = useState(null)
  const [contributors, setContributors] = useState([])
  const [analyticsSeries, setAnalyticsSeries] = useState([])
  const [insightsError, setInsightsError] = useState('')
  const [hostError, setHostError] = useState('')
  const [rentError, setRentError] = useState('')
  const tokenForCmd = authToken || 'MISSING_TOKEN'
  const latestOwnedJob = myJobs[0] || null
  const renterJobId = latestOwnedJob?.id || '<CREATE_JOB_FIRST>'
  const renterRepoUrl = latestOwnedJob?.repo_url || '<REPO_URL>'
  const renterBranch = latestOwnedJob?.branch || 'main'
  const canShowRenterRunCommand = latestOwnedJob?.access_status === 'accepted'
  const renterRunCommand =
    `python -m app.core.p2p_cli receiver --api-base ${defaultApiBase} --token ${tokenForCmd} ` +
    `--job-id ${renterJobId} --repo-url "${renterRepoUrl}" --branch "${renterBranch}"`

  const formatGb = (mb) => {
    if (!mb || Number.isNaN(Number(mb))) {
      return 'Unknown'
    }
    return `${Math.max(1, Math.round(Number(mb) / 1024))} GB`
  }

  const formatUtc = (value) => {
    if (!value) return 'Unknown'
    const parsed = new Date(value)
    if (Number.isNaN(parsed.getTime())) return 'Unknown'
    return parsed.toLocaleString()
  }

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

  useEffect(() => {
    let active = true

    const loadInsights = async () => {
      try {
        const [telemetryData, contributorData, analyticsData] = await Promise.all([
          getP2PTelemetry(authToken),
          getContributorSummaries(authToken),
          getDailyAnalytics(authToken, 14),
        ])
        if (!active) return
        setTelemetry(telemetryData)
        setContributors(Array.isArray(contributorData?.contributors) ? contributorData.contributors : [])
        setAnalyticsSeries(Array.isArray(analyticsData?.series) ? analyticsData.series : [])
        setInsightsError('')
      } catch (error) {
        if (active) {
          setInsightsError(error.message)
        }
      }
    }

    loadInsights()
    const intervalId = setInterval(loadInsights, 10000)

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
                {canShowRenterRunCommand ? (
                  <p className="mt-2 break-all font-jetbrains text-[11px] text-emerald-200">{renterRunCommand}</p>
                ) : (
                  <p className="mt-2 text-[12px] text-slate-400">Command will appear after access is accepted.</p>
                )}
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

                  <div className="mt-3 rounded border border-white/10 bg-[#060b14] p-3">
                    <p className="text-[10px] uppercase tracking-[2px] text-slate-500">Host Machine Specs</p>
                    <p className="mt-2 text-[12px] text-slate-300">CPU: {job.cpu_model || 'Unknown'}</p>
                    <p className="text-[12px] text-slate-300">
                      Cores: {job.cpu_physical_cores || 'N/A'}P / {job.cpu_logical_cores || 'N/A'}L
                    </p>
                    <p className="text-[12px] text-slate-300">GPU: {job.gpu_model || 'Unknown'}</p>
                    <p className="text-[12px] text-slate-300">VRAM: {job.gpu_vram || formatGb(job.gpu_vram_mb)}</p>
                    <p className="text-[12px] text-slate-300">System RAM: {formatGb(job.memory_total_mb)}</p>
                    <p className="text-[12px] text-emerald-200">Machine Score: {job.machine_score ?? 'N/A'}</p>
                  </div>

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

                  {job.access_status === 'accepted' ? (
                    <div className="mt-3 rounded border border-white/10 bg-[#060b14] p-3">
                      <p className="text-[10px] uppercase tracking-[2px] text-slate-500">Host Accept Command</p>
                      <p className="mt-2 break-all font-jetbrains text-[11px] text-emerald-200">
                        {`python -m app.core.p2p_cli host --api-base ${defaultApiBase} --token ${tokenForCmd} --job-id ${job.job_id}`}
                      </p>
                    </div>
                  ) : (
                    <div className="mt-3 rounded border border-white/10 bg-[#060b14] p-3">
                      <p className="text-[10px] uppercase tracking-[2px] text-slate-500">Host Command</p>
                      <p className="mt-2 text-[12px] text-slate-400">Command will appear after access is accepted.</p>
                    </div>
                  )}

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

        <div className="mt-8 rounded-[12px] border border-white/15 bg-[#0b1322c9] p-6">
          <p className="text-[10px] uppercase tracking-[3px] text-emerald-300/75">Operations Insights</p>
          <h2 className="mt-3 text-[30px] font-bold uppercase tracking-[1px] text-slate-100">Real-Time Usage Dashboard</h2>
          <p className="mt-2 text-[14px] text-slate-400">
            Live system telemetry, contributor history, and 14-day usage analytics.
          </p>

          {insightsError && <p className="mt-4 text-[12px] text-red-300">{insightsError}</p>}

          <div className="mt-6 grid gap-4 md:grid-cols-3">
            <div className="rounded border border-white/10 bg-[#060b14] p-4">
              <p className="text-[10px] uppercase tracking-[2px] text-slate-500">Active Hosts</p>
              <p className="mt-2 text-[24px] font-bold text-emerald-200">{telemetry?.active_hosts ?? '-'}</p>
              <p className="mt-1 text-[11px] text-slate-400">Live heartbeat contributors</p>
            </div>
            <div className="rounded border border-white/10 bg-[#060b14] p-4">
              <p className="text-[10px] uppercase tracking-[2px] text-slate-500">Active Receivers</p>
              <p className="mt-2 text-[24px] font-bold text-emerald-200">{telemetry?.active_receivers ?? '-'}</p>
              <p className="mt-1 text-[11px] text-slate-400">In-session requesters</p>
            </div>
            <div className="rounded border border-white/10 bg-[#060b14] p-4">
              <p className="text-[10px] uppercase tracking-[2px] text-slate-500">Pending Failovers</p>
              <p className="mt-2 text-[24px] font-bold text-emerald-200">{telemetry?.pending_failovers ?? '-'}</p>
              <p className="mt-1 text-[11px] text-slate-400">Jobs awaiting recovery</p>
            </div>
          </div>

          <div className="mt-5 rounded border border-white/10 bg-[#060b14] p-4">
            <p className="text-[10px] uppercase tracking-[2px] text-slate-500">Task Status Distribution</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {Object.entries(telemetry?.status_counts || {}).map(([status, count]) => (
                <span
                  key={status}
                  className="rounded border border-white/10 bg-[#0d1424] px-3 py-1 text-[11px] uppercase tracking-[1px] text-slate-300"
                >
                  {status}: {count}
                </span>
              ))}
              {Object.keys(telemetry?.status_counts || {}).length === 0 && (
                <p className="text-[12px] text-slate-400">No status data yet.</p>
              )}
            </div>
          </div>

          <div className="mt-6 grid gap-6 lg:grid-cols-2">
            <div className="rounded border border-white/10 bg-[#060b14] p-4">
              <p className="text-[10px] uppercase tracking-[2px] text-slate-500">Contributor History</p>
              <div className="mt-3 max-h-[320px] space-y-3 overflow-y-auto pr-1">
                {contributors.slice(0, 12).map((item) => (
                  <article key={item.node_id} className="rounded border border-white/10 bg-[#0d1424] p-3">
                    <p className="font-jetbrains break-all text-[11px] text-emerald-200">{item.node_id}</p>
                    <p className="mt-1 text-[12px] text-slate-300">
                      Jobs: {item.jobs_total} | Completed: {item.completed_jobs} | Failed: {item.failed_jobs}
                    </p>
                    <p className="text-[12px] text-slate-300">
                      Success: {item.success_rate}% | Avg Score: {item.avg_machine_score ?? 'N/A'}
                    </p>
                    <p className="text-[11px] text-slate-400">Last Seen: {formatUtc(item.last_seen_at)}</p>
                    <p className="text-[11px] text-slate-400">GPU: {item.gpu_model || 'Unknown'}</p>
                  </article>
                ))}
                {contributors.length === 0 && <p className="text-[12px] text-slate-400">No contributor history yet.</p>}
              </div>
            </div>

            <div className="rounded border border-white/10 bg-[#060b14] p-4">
              <p className="text-[10px] uppercase tracking-[2px] text-slate-500">14-Day Usage Analytics</p>
              <div className="mt-3 max-h-[320px] overflow-y-auto pr-1">
                <table className="w-full border-collapse text-left">
                  <thead>
                    <tr className="text-[10px] uppercase tracking-[1px] text-slate-500">
                      <th className="py-2">Date</th>
                      <th className="py-2">Sub</th>
                      <th className="py-2">Done</th>
                      <th className="py-2">Fail</th>
                      <th className="py-2">Contrib</th>
                    </tr>
                  </thead>
                  <tbody>
                    {analyticsSeries.map((row) => (
                      <tr key={row.date} className="border-t border-white/10 text-[12px] text-slate-300">
                        <td className="py-2">{row.date}</td>
                        <td className="py-2">{row.submitted}</td>
                        <td className="py-2 text-emerald-200">{row.completed}</td>
                        <td className="py-2 text-red-300">{row.failed}</td>
                        <td className="py-2">{row.active_contributors}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {analyticsSeries.length === 0 && <p className="text-[12px] text-slate-400">No analytics data yet.</p>}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

export default DashboardPage
