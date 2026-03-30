import { useState } from 'react'
import { createJob, registerHost } from '../lib/api'

function JobSubmissionPage({ authToken, onBackDashboard, onJobCreated }) {
  const [selectedFile, setSelectedFile] = useState(null)
  const [command, setCommand] = useState('python main.py')
  const [hostNodeId, setHostNodeId] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [successMessage, setSuccessMessage] = useState('')

  const handleSubmit = async () => {
    if (!selectedFile) {
      setErrorMessage('Please select a file before creating a job.')
      return
    }

    setIsSubmitting(true)
    setErrorMessage('')
    setSuccessMessage('')

    try {
      const job = await createJob(authToken, {
        filename: selectedFile.name,
        command,
      })

      if (hostNodeId.trim()) {
        await registerHost(authToken, job.id, hostNodeId.trim())
      }

      setSuccessMessage(`Job created: ${job.id}`)
      onJobCreated(job.id)
    } catch (error) {
      setErrorMessage(error.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <section className="relative min-h-screen w-full bg-[#040811] px-6 pb-10 pt-8 text-slate-100 md:px-10 lg:px-14">
      <div className="mx-auto w-full max-w-[1000px] rounded-[12px] border border-white/15 bg-[#0b1322d9] p-6">
        <div className="mb-8 flex items-center justify-between">
          <h1 className="text-[34px] font-bold text-slate-100">Submit GPU Job</h1>
          <button
            className="rounded border border-white/20 px-4 py-2 text-[12px] uppercase tracking-[2px] text-slate-300"
            onClick={onBackDashboard}
            type="button"
          >
            Back
          </button>
        </div>

        <div className="mb-6">
          <label className="mb-2 block text-[11px] uppercase tracking-[2px] text-slate-400">Input File</label>
          <input
            className="w-full rounded border border-white/20 bg-[#09101d] p-3 text-slate-100"
            onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
            type="file"
          />
          <p className="mt-2 text-[12px] text-slate-400">
            {selectedFile ? `Selected: ${selectedFile.name}` : 'No file selected.'}
          </p>
        </div>

        <div className="mb-6">
          <label className="mb-2 block text-[11px] uppercase tracking-[2px] text-slate-400">Execution Command</label>
          <input
            className="w-full rounded border border-white/20 bg-[#09101d] p-3 text-slate-100"
            onChange={(event) => setCommand(event.target.value)}
            placeholder="python main.py"
            type="text"
            value={command}
          />
        </div>

        <div className="mb-8">
          <label className="mb-2 block text-[11px] uppercase tracking-[2px] text-slate-400">Host Node ID (optional)</label>
          <input
            className="w-full rounded border border-white/20 bg-[#09101d] p-3 text-slate-100"
            onChange={(event) => setHostNodeId(event.target.value)}
            placeholder="iroh host node id"
            type="text"
            value={hostNodeId}
          />
        </div>

        {errorMessage && <p className="mb-4 text-[13px] text-red-300">{errorMessage}</p>}
        {successMessage && <p className="mb-4 text-[13px] text-emerald-300">{successMessage}</p>}

        <button
          className="h-[48px] rounded-[6px] border border-emerald-200/70 bg-[#95f2bd] px-6 text-[13px] font-bold uppercase tracking-[3px] text-[#0b2d1e]"
          disabled={isSubmitting}
          onClick={handleSubmit}
          type="button"
        >
          {isSubmitting ? 'Submitting...' : 'Create Job'}
        </button>
      </div>
    </section>
  )
}

export default JobSubmissionPage
