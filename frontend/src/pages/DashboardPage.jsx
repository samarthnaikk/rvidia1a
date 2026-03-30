import { useState } from 'react'

function DashboardPage({ onBackHome }) {
  const [selectedFile, setSelectedFile] = useState(null)
  const [userQuery, setUserQuery] = useState('')

  return (
    <section className="relative min-h-screen w-full bg-[#040811] px-6 pb-10 pt-8 text-slate-100 md:px-10 lg:px-14">
      <div className="mx-auto w-full max-w-[1200px]">
        <div className="mb-10 flex items-center justify-between">
          <div>
            <p className="text-[12px] uppercase tracking-[3px] text-emerald-300/70">Kinetic Core</p>
            <h1 className="mt-2 text-[42px] font-bold leading-[1.1] text-slate-100">
              Unified <span className="text-emerald-300">Dashboard</span>
            </h1>
          </div>
          <button
            className="rounded border border-white/20 px-4 py-2 text-[12px] uppercase tracking-[2px] text-slate-300 transition hover:border-emerald-300/60 hover:text-emerald-200"
            onClick={onBackHome}
            type="button"
          >
            Back Home
          </button>
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
          </div>

          <div className="rounded-[12px] border border-white/15 bg-[#0b1322c9] p-6">
            <p className="text-[10px] uppercase tracking-[3px] text-emerald-300/75">Operational Mode</p>
            <h2 className="mt-3 text-[34px] font-bold uppercase tracking-[1px] text-slate-100">Host Compute</h2>
            <p className="mt-2 text-[15px] text-slate-400">Search for a user to host or assign compute access.</p>

            <div className="mt-7">
              <label className="mb-2 block text-[10px] uppercase tracking-[3px] text-slate-500">Search User</label>
              <input
                className="font-jetbrains h-[52px] w-full rounded-[8px] border border-white/15 bg-[#0a101d] px-4 text-[15px] text-slate-200 outline-none placeholder:text-slate-500 focus:border-emerald-300/60"
                onChange={(event) => setUserQuery(event.target.value)}
                placeholder="Enter username or wallet id"
                type="text"
                value={userQuery}
              />
            </div>

            <button
              className="mt-4 h-[48px] w-full rounded-[6px] border border-emerald-200/70 bg-[#95f2bd] text-[13px] font-bold uppercase tracking-[3px] text-[#0b2d1e]"
              type="button"
            >
              Search User
            </button>
          </div>
        </div>
      </div>
    </section>
  )
}

export default DashboardPage
