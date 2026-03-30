import { useEffect } from 'react'

const websiteSteps = [
  {
    step: 'STEP_01',
    title: 'Create Account & Login',
    description:
      'Sign up from the web UI and authenticate. The frontend stores your JWT and uses it for protected routes like jobs, marketplace, and consent actions.',
    icon: 'shield',
  },
  {
    step: 'STEP_02',
    title: 'Submit GitHub Job',
    description:
      'From the dashboard, submit a public repository URL and branch. Backend creates a job record with queued status and coordination metadata.',
    icon: 'terminal',
  },
  {
    step: 'STEP_03',
    title: 'Request & Accept Access',
    description:
      'Hosts browse marketplace jobs and request access. Job owner accepts access; only then does the dashboard reveal the operational host/receiver commands.',
    icon: 'nodes',
  },
  {
    step: 'STEP_04',
    title: 'Run Host / Receiver',
    description:
      'The commands shown in dashboard launch CLI nodes. Receiver sends input ticket, host executes Docker workload, and result artifacts are transferred over P2P.',
    icon: 'terminal',
  },
  {
    step: 'STEP_05',
    title: 'Track Results in Web UI',
    description:
      'Status updates and completion metadata are persisted in backend. Results page reads final state and artifact metadata while command snippets stay consent-gated.',
    icon: 'shield',
  },
]

const cliSteps = [
  {
    step: 'CLI_01',
    title: 'Authenticate Once',
    description:
      'Use client CLI login or TUI login one time. Session token is persisted locally and reused for subsequent commands.',
    icon: 'shield',
  },
  {
    step: 'CLI_02',
    title: 'Create / Inspect Jobs',
    description:
      'Create jobs from GitHub repositories, list marketplace entries, and inspect job state from terminal without opening the website.',
    icon: 'terminal',
  },
  {
    step: 'CLI_03',
    title: 'Consent Handshake',
    description:
      'Run request-access and accept-access from CLI (or mixed with website). This keeps bilateral consent consistent across both interfaces.',
    icon: 'nodes',
  },
  {
    step: 'CLI_04',
    title: 'Execute P2P Pipeline',
    description:
      'Start p2p host and p2p receiver. Host clones repository, builds and runs Docker sandbox, then receiver downloads artifacts and execution logs.',
    icon: 'terminal',
  },
  {
    step: 'CLI_05',
    title: 'Recover on Drop-offs',
    description:
      'Heartbeat, failover, and checkpoint metadata keep coordination resilient. If peers disappear, job state can recover and continue from known phases.',
    icon: 'shield',
  },
]

const runtimeSteps = [
  {
    step: 'RUNTIME_01',
    title: 'Peer Registration',
    description:
      'Host and receiver register node IDs against the same job session. Backend tracks latest peer IDs and session version for synchronization.',
    icon: 'nodes',
  },
  {
    step: 'RUNTIME_02',
    title: 'Input Ticket Signal',
    description:
      'Receiver sends repository metadata as input_ticket signal. Host waits for this signal and starts execution only when valid payload arrives.',
    icon: 'terminal',
  },
  {
    step: 'RUNTIME_03',
    title: 'Container Execution',
    description:
      'Host clones repository, builds image, and runs container with isolation flags. GPU mode is attempted when available, with CPU fallback on runtime limits.',
    icon: 'sliders',
  },
  {
    step: 'RUNTIME_04',
    title: 'Artifact + Log Transfer',
    description:
      'Host shares result tickets over iroh. Receiver downloads artifacts and logs directly P2P, acknowledges transfer, and backend marks delivery/completion.',
    icon: 'terminal',
  },
  {
    step: 'RUNTIME_05',
    title: 'Checkpoint Visibility',
    description:
      'Checkpoint phase/data are persisted so operations can inspect progress, troubleshoot failures, and understand the last durable step in execution.',
    icon: 'shield',
  },
]

const commandPlaybook = [
  {
    step: 'PLAY_01',
    title: 'Open Website + Login',
    detail: 'Start with the web flow first so consent and command snippets are generated from the same backend session.',
    commands: [
      '# Visit website',
      'http://157.180.74.2',
      '',
      '# In browser:',
      '1) Create account or login',
      '2) Submit a GitHub repo job',
      '3) Request and accept access from dashboard',
    ],
  },
  {
    step: 'PLAY_02',
    title: 'Clone + Backend Boot',
    detail: 'Use local backend in dev mode so the job IDs from website and CLI match exactly.',
    commands: [
      'git clone https://github.com/samarthnaikk/rvidia1a.git',
      'cd rvidia1a',
      'python -m venv .venv',
      'source .venv/bin/activate',
      'pip install -r backend/requirements.txt',
      'cd backend && python run.py',
    ],
  },
  {
    step: 'PLAY_03',
    title: 'Run Receiver + Host',
    detail: 'Run commands from accepted dashboard cards or execute manually using the same --api-base and --job-id.',
    commands: [
      '# Receiver terminal',
      'python -m app.core.p2p_cli receiver --api-base http://157.180.74.2 --token <JWT> --job-id <JOB_ID> --repo-url "https://github.com/samarthnaikk/rvidia1a" --branch "main"',
      '',
      '# Host terminal',
      'python -m app.core.p2p_cli host --api-base http://157.180.74.2 --token <JWT> --job-id <JOB_ID>',
    ],
  },
  {
    step: 'PLAY_04',
    title: 'Observe Checkpoints + Results',
    detail: 'Inspect runtime progression from backend and verify artifacts/logs in both terminal output and job result pages.',
    commands: [
      'curl -H "Authorization: Bearer <JWT>" http://157.180.74.2/p2p/jobs/<JOB_ID>/peers',
      '',
      '# Look for:',
      'checkpoint_phase',
      'checkpoint_data',
      'checkpoint_updated_at',
    ],
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

function DemoArchitecturePage({ onBackClick }) {
  useEffect(() => {
    const nodes = Array.from(document.querySelectorAll('[data-reveal]'))
    if (!nodes.length) {
      return undefined
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const target = entry.target
            target.classList.remove('opacity-0', 'translate-y-8')
            target.classList.add('opacity-100', 'translate-y-0')
            observer.unobserve(target)
          }
        })
      },
      { threshold: 0.2, rootMargin: '0px 0px -60px 0px' },
    )

    nodes.forEach((node) => observer.observe(node))
    return () => observer.disconnect()
  }, [])

  const renderSection = (title, subtitle, steps) => (
    <section className="relative min-h-screen w-full overflow-hidden px-6 pb-20 pt-10 md:px-10 lg:px-14 2xl:px-20">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(120,255,198,0.09),transparent_45%)]" />

      <div className="relative z-10 mx-auto w-full max-w-[1580px]">
        <div data-reveal className="flex translate-y-8 items-end gap-6 opacity-0 transition-all duration-700">
          <div>
            <h2 className="text-[clamp(28px,3vw,56px)] font-bold uppercase tracking-[-0.8px] text-[#95ffd2]">{title}</h2>
            <p className="mt-2 font-['JetBrains_Mono'] text-[11px] uppercase tracking-[3px] text-slate-400">{subtitle}</p>
          </div>
          <div className="mb-3 hidden h-px flex-1 bg-gradient-to-r from-[#95ffd2]/40 to-transparent md:block" />
        </div>

        <div className="mt-10 grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-5">
          {steps.map((item) => (
            <article
              key={item.step}
              data-reveal
              className="flex min-h-[420px] translate-y-8 flex-col rounded-xl border border-white/8 bg-[linear-gradient(145deg,rgba(133,255,206,0.09)_0%,rgba(22,33,52,0.32)_22%,rgba(5,8,16,0.88)_70%)] p-7 opacity-0 shadow-[0_0_0_1px_rgba(255,255,255,0.02),0_22px_50px_rgba(0,0,0,0.45)] transition-all duration-700"
            >
              <p className="font-['JetBrains_Mono'] text-[11px] uppercase tracking-[2px] text-[#79d8ac]">{item.step}</p>

              <div className="mt-8">
                <StepIcon type={item.icon} />
              </div>

              <h3 className="mt-6 text-[clamp(30px,1.75vw,36px)] font-bold leading-[1.15] text-slate-100">{item.title}</h3>

              <p className="mt-5 text-[clamp(16px,1vw,20px)] leading-[1.6] text-slate-300/70">{item.description}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  )

  return (
    <div className="w-full bg-black text-white">
      <button
        className="fixed left-6 top-6 z-30 rounded border border-white/25 bg-black/45 px-4 py-2 font-['JetBrains_Mono'] text-[11px] uppercase tracking-[2px] text-slate-200 backdrop-blur transition hover:border-[#95ffd2]/70 hover:text-[#95ffd2]"
        onClick={onBackClick}
        type="button"
      >
        Back to Home
      </button>

      <section className="relative flex min-h-screen w-full items-center justify-center overflow-hidden px-6 py-10 text-center">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_12%,rgba(120,255,198,0.17),transparent_34%),radial-gradient(circle_at_50%_52%,rgba(59,132,246,0.2),transparent_48%),radial-gradient(circle_at_50%_90%,rgba(120,255,198,0.1),transparent_34%)]" />
        <div className="pointer-events-none absolute left-1/2 top-1/2 h-[94vh] w-[94vw] -translate-x-1/2 -translate-y-1/2 rounded-[48%] border border-emerald-100/10 blur-[2px]" />
        <div className="pointer-events-none absolute left-1/2 top-1/2 h-[92vh] w-[72vw] -translate-x-1/2 -translate-y-1/2 rounded-[50%] bg-[radial-gradient(circle,rgba(126,255,208,0.12)_0%,rgba(26,58,84,0.08)_45%,transparent_72%)] blur-2xl" />

        <div data-reveal className="relative z-10 mx-auto max-w-[980px] translate-y-8 opacity-0 transition-all duration-700">
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

      {renderSection('01 / Website Demo Flow', 'Dashboard, Consent, Commands, and Results', websiteSteps)}
      {renderSection('02 / CLI Demo Flow', 'Terminal-First Operations and TUI', cliSteps)}
      {renderSection('03 / Runtime + Checkpoint Flow', 'Signals, Execution, Delivery, and Recovery', runtimeSteps)}

      <section className="relative w-full overflow-hidden px-6 pb-24 pt-4 md:px-10 lg:px-14 2xl:px-20">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_18%,rgba(59,132,246,0.12),transparent_56%)]" />
        <div className="relative z-10 mx-auto w-full max-w-[1580px]">
          <div data-reveal className="translate-y-8 opacity-0 transition-all duration-700">
            <h2 className="text-[clamp(26px,2.8vw,52px)] font-bold uppercase tracking-[-0.8px] text-[#95ffd2]">
              04 / Demo Command Playbook
            </h2>
            <p className="mt-2 font-['JetBrains_Mono'] text-[11px] uppercase tracking-[3px] text-slate-400">
              Copy-Ready Steps For Website + CLI Demo
            </p>
          </div>

          <div className="mt-10 grid grid-cols-1 gap-6 lg:grid-cols-2">
            {commandPlaybook.map((item) => (
              <article
                key={item.step}
                data-reveal
                className="translate-y-8 rounded-xl border border-white/10 bg-[linear-gradient(160deg,rgba(133,255,206,0.08)_0%,rgba(18,24,40,0.5)_36%,rgba(6,9,17,0.9)_74%)] p-6 opacity-0 shadow-[0_0_0_1px_rgba(255,255,255,0.02),0_18px_40px_rgba(0,0,0,0.38)] transition-all duration-700"
              >
                <p className="font-['JetBrains_Mono'] text-[11px] uppercase tracking-[2px] text-[#79d8ac]">{item.step}</p>
                <h3 className="mt-3 text-[clamp(24px,1.8vw,32px)] font-bold leading-[1.18] text-slate-100">{item.title}</h3>
                <p className="mt-3 text-[15px] leading-[1.7] text-slate-300/80">{item.detail}</p>

                <pre className="mt-5 overflow-x-auto rounded-lg border border-white/10 bg-[#05090f] p-4 font-['JetBrains_Mono'] text-[12px] leading-[1.7] text-[#b7ffd9]">
                  {item.commands.join('\n')}
                </pre>
              </article>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}

export default DemoArchitecturePage