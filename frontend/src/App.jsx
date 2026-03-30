const NAV_LINKS = [
  { label: 'Network', href: '#network', isActive: true },
  { label: 'Nodes', href: '#nodes', isActive: false },
  { label: 'Docs', href: '#docs', isActive: false },
]

const METRICS = [
  { label: 'Active Nodes', value: '12,482', valueClassName: 'text-emerald-400' },
  { label: 'Network TFLOPS', value: '842.1', valueClassName: 'text-sky-300' },
]

const classes = {
  main: 'relative min-h-screen overflow-x-hidden bg-transparent text-slate-100',
  backgroundOverlay:
    'pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,#00A2FD0D_0%,transparent_34%),radial-gradient(circle_at_70%_30%,rgba(213,228,221,0.28),transparent_38%),linear-gradient(118deg,rgba(202,218,209,0.48)_0%,rgba(16,22,27,0.16)_38%,rgba(3,8,20,0.88)_68%,rgba(167,188,175,0.4)_100%)]',
  navbar:
    'flex h-16 w-full items-center justify-between border-b border-b-white/15 bg-[#0206174D] px-8 text-[20px] font-bold leading-7 tracking-[2px]',
}

function Navbar() {
  return (
    <nav className={classes.navbar}>
      <div className="text-[20px] text-emerald-400">KINETIC_CORE</div>

      <div className="hidden items-center gap-8 text-[15px] font-medium tracking-[0.5px] text-slate-400 md:flex">
        {NAV_LINKS.map((link) => (
          <a
            key={link.label}
            className={link.isActive ? 'text-emerald-400' : ''}
            href={link.href}
          >
            {link.label}
          </a>
        ))}
      </div>

      <button
        className="hidden h-8 rounded-sm border border-white/30 px-5 text-[10px] font-semibold uppercase tracking-[3px] text-slate-200 md:block"
        type="button"
      >
        Log In
      </button>
    </nav>
  )
}

function HeroMetrics() {
  return (
    <div className="absolute bottom-4 left-4 flex gap-8 text-left">
      {METRICS.map((metric) => (
        <div key={metric.label}>
          <p className="text-[8px] uppercase tracking-[2px] text-slate-400">{metric.label}</p>
          <p className={`text-[33.99px] font-bold leading-none ${metric.valueClassName}`}>{metric.value}</p>
        </div>
      ))}
    </div>
  )
}

function App() {
  return (
    <main className={classes.main}>
      <div className={classes.backgroundOverlay} />

      <div className="relative mx-auto max-w-[1280px]">
        <Navbar />

        <section className="mx-auto px-6 pb-10 pt-10 md:px-10">
          <div className="mx-auto max-w-[1120px] text-center">
            <div className="mb-5 inline-flex rounded-full border border-emerald-300/30 bg-emerald-400/10 px-4 py-1 text-[11px] uppercase tracking-[3px] text-emerald-300">
              MAINNET BETA LIVE
            </div>

            <div className="border border-[#6f82b9] bg-[#ffffff14] px-4 py-5 md:px-10 md:py-6">
              <h1 className="font-space text-[58px] font-bold leading-[1.04] tracking-[1px] text-[#d1d5db] md:text-[72px]">
                Power the Future of AI with{' '}
                <span className="text-emerald-400">Decentralized Compute.</span>
              </h1>
            </div>

            <p className="mx-auto mt-6 max-w-[760px] text-[31.99px] leading-[1.5] tracking-[0.1px] text-slate-300/90 md:text-[27px]">
              Access high-performance GPUs and idle compute cycles at a fraction of centralized cost. Secure, scalable, and fully sovereign.
            </p>

            <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
              <button
                className="h-[52px] min-w-[210px] border border-emerald-400 bg-emerald-400 px-7 text-[12px] font-bold uppercase tracking-[3px] text-slate-900 transition hover:brightness-110"
                type="button"
              >
                Start Computing
              </button>
              <button
                className="h-[52px] min-w-[210px] border border-white/20 bg-white/5 px-7 text-[12px] font-bold uppercase tracking-[3px] text-slate-200 transition hover:bg-white/10"
                type="button"
              >
                Contribute Resources
              </button>
            </div>

            <div className="mt-14 overflow-hidden border border-white/10 bg-[#99aaa31a] p-4 backdrop-blur-[1px]">
              <div className="relative h-[295px] w-full rounded-sm border border-white/5 bg-[radial-gradient(circle_at_8%_40%,rgba(225,245,235,0.68),transparent_46%),radial-gradient(circle_at_65%_56%,rgba(14,91,99,0.36),transparent_42%),linear-gradient(114deg,#b9c9bf_0%,#2a3940_30%,#06131e_58%,#0f2630_100%)]">
                <div className="absolute inset-0 opacity-40 [background-image:radial-gradient(circle_at_20%_65%,rgba(188,232,223,0.55),transparent_40%),repeating-radial-gradient(circle_at_60%_65%,rgba(81,201,191,0.18)_0,rgba(81,201,191,0.08)_2px,transparent_6px)]" />

                <HeroMetrics />

                <div className="absolute bottom-4 right-4 text-right">
                  <p className="text-[8px] uppercase tracking-[2px] text-slate-400">Resource Distribution</p>
                  <p className="text-[33.99px] font-bold leading-none text-emerald-400">▮▮▮▮</p>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>
  )
}

export default App
