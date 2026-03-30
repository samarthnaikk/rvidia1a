const requesterSteps = [
  {
    step: 'STEP_01',
    title: 'Connect & Authenticate',
    description:
      'Secure your session by linking a Web3 wallet. Kinetic generates a non-custodial Access Key for API interactions.',
    icon: 'wallet',
  },
  {
    step: 'STEP_02',
    title: 'Define Task',
    description:
      'Select from pre-configured AI containers (CNN, LLM, Transformer) or push your custom Docker repository directly.',
    icon: 'terminal',
  },
  {
    step: 'STEP_03',
    title: 'Resource Allocation',
    description:
      'Configure VRAM, CPU cores, and TFLOPS requirements. Set your max budget in $KNT tokens per epoch.',
    icon: 'sliders',
  },
  {
    step: 'STEP_04',
    title: 'Distributed Execution',
    description:
      'The Core shatters the workload into shards, dispatching them to verified global contributor nodes in parallel.',
    icon: 'nodes',
  },
  {
    step: 'STEP_05',
    title: 'Verify & Download',
    description:
      'Consensus-based verification confirms accuracy. Once validated, retrieve your final weights or inference results.',
    icon: 'shield',
  },
]

function StepIcon({ type }) {
  if (type === 'wallet') {
    return (
      <svg viewBox="0 0 24 24" fill="none" className="h-8 w-8 text-[#8df9c6]">
        <rect x="3" y="5" width="16" height="14" rx="2" stroke="currentColor" strokeWidth="1.8" />
        <path d="M19 9h2a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1h-2V9Z" stroke="currentColor" strokeWidth="1.8" />
        <circle cx="18" cy="12" r="1" fill="currentColor" />
      </svg>
    )
  }

  if (type === 'terminal') {
    return (
      <svg viewBox="0 0 24 24" fill="none" className="h-8 w-8 text-[#8df9c6]">
        <rect x="3" y="5" width="18" height="14" rx="2" stroke="currentColor" strokeWidth="1.8" />
        <path d="m7 10 3 2-3 2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M12.5 15H16" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    )
  }

  if (type === 'sliders') {
    return (
      <svg viewBox="0 0 24 24" fill="none" className="h-8 w-8 text-[#8df9c6]">
        <path d="M6 4v16M12 4v16M18 4v16" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        <rect x="4.5" y="8" width="3" height="4" rx="1" stroke="currentColor" strokeWidth="1.8" />
        <rect x="10.5" y="12" width="3" height="4" rx="1" stroke="currentColor" strokeWidth="1.8" />
        <rect x="16.5" y="6" width="3" height="4" rx="1" stroke="currentColor" strokeWidth="1.8" />
      </svg>
    )
  }

  if (type === 'nodes') {
    return (
      <svg viewBox="0 0 24 24" fill="none" className="h-8 w-8 text-[#8df9c6]">
        <circle cx="12" cy="12" r="2" stroke="currentColor" strokeWidth="1.8" />
        <circle cx="12" cy="4.5" r="1.5" stroke="currentColor" strokeWidth="1.8" />
        <circle cx="19.5" cy="12" r="1.5" stroke="currentColor" strokeWidth="1.8" />
        <circle cx="12" cy="19.5" r="1.5" stroke="currentColor" strokeWidth="1.8" />
        <circle cx="4.5" cy="12" r="1.5" stroke="currentColor" strokeWidth="1.8" />
        <path d="M12 6v4M14 12h4M12 14v4M6 12h4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    )
  }

  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-8 w-8 text-[#8df9c6]">
      <path d="M12 3 5 6v6c0 4.2 2.8 7.9 7 9 4.2-1.1 7-4.8 7-9V6l-7-3Z" stroke="currentColor" strokeWidth="1.8" />
      <path d="m9.5 12.5 1.7 1.7 3.3-3.7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function DemoArchitecturePage() {
  return (
    <div className="w-full bg-black text-white">
      <section className="relative flex min-h-screen w-full items-center justify-center overflow-hidden px-6 py-10 text-center">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_12%,rgba(120,255,198,0.17),transparent_34%),radial-gradient(circle_at_50%_52%,rgba(59,132,246,0.2),transparent_48%),radial-gradient(circle_at_50%_90%,rgba(120,255,198,0.1),transparent_34%)]" />
        <div className="pointer-events-none absolute left-1/2 top-1/2 h-[94vh] w-[94vw] -translate-x-1/2 -translate-y-1/2 rounded-[48%] border border-emerald-100/10 blur-[2px]" />
        <div className="pointer-events-none absolute left-1/2 top-1/2 h-[92vh] w-[72vw] -translate-x-1/2 -translate-y-1/2 rounded-[50%] bg-[radial-gradient(circle,rgba(126,255,208,0.12)_0%,rgba(26,58,84,0.08)_45%,transparent_72%)] blur-2xl" />

        <div className="relative z-10 mx-auto max-w-[980px]">
          <span className="inline-flex rounded-full border border-[#87ffcf52] bg-[#75ffbf14] px-6 py-2 font-['JetBrains_Mono'] text-[11px] uppercase tracking-[2px] text-[#95ffd2]">
            Protocol Documentation V2.4
          </span>

          <h1 className="mt-10 text-[clamp(56px,8.4vw,96px)] font-bold leading-[0.98] tracking-[-1.8px] text-slate-100">
            The Architecture of
            <br />
            <span className="mt-6 inline-block text-[#92ffcd]">RVIDIA</span>
          </h1>

          <p className="mx-auto mt-12 max-w-[860px] text-[clamp(18px,2vw,38px)] font-normal leading-[1.72] text-slate-300/70">
            A decentralized engine for containerized AI workloads. Whether you are scaling models or
            providing high-performance hardware, RVIDIA orchestrates every cycle with cryptographic
            precision.
          </p>
        </div>
      </section>

      <section className="relative min-h-screen w-full overflow-hidden px-6 pb-20 pt-10 md:px-10 lg:px-14 2xl:px-20">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(120,255,198,0.09),transparent_45%)]" />

        <div className="relative z-10 mx-auto w-full max-w-[1580px]">
          <div className="flex items-end gap-6">
            <div>
              <h2 className="text-[clamp(28px,3vw,56px)] font-bold uppercase tracking-[-0.8px] text-[#95ffd2]">
                01 / The Requester Path
              </h2>
              <p className="mt-2 font-['JetBrains_Mono'] text-[11px] uppercase tracking-[3px] text-slate-400">
                Deploy & Execute Distributed Models
              </p>
            </div>
            <div className="mb-3 hidden h-px flex-1 bg-gradient-to-r from-[#95ffd2]/40 to-transparent md:block" />
          </div>

          <div className="mt-10 grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-5">
            {requesterSteps.map((item) => (
              <article
                key={item.step}
                className="flex min-h-[420px] flex-col rounded-xl border border-white/8 bg-[linear-gradient(145deg,rgba(133,255,206,0.09)_0%,rgba(22,33,52,0.32)_22%,rgba(5,8,16,0.88)_70%)] p-7 shadow-[0_0_0_1px_rgba(255,255,255,0.02),0_22px_50px_rgba(0,0,0,0.45)]"
              >
                <p className="font-['JetBrains_Mono'] text-[11px] uppercase tracking-[2px] text-[#79d8ac]">
                  {item.step}
                </p>

                <div className="mt-8">
                  <StepIcon type={item.icon} />
                </div>

                <h3 className="mt-6 text-[clamp(30px,1.75vw,36px)] font-bold leading-[1.15] text-slate-100">
                  {item.title}
                </h3>

                <p className="mt-5 text-[clamp(16px,1vw,20px)] leading-[1.6] text-slate-300/70">
                  {item.description}
                </p>
              </article>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}

export default DemoArchitecturePage