import HeroMetrics from '../components/HeroMetrics'
import Navbar from '../components/Navbar'

function HomePage({ onLoginClick, onStartComputingClick }) {
  return (
    <div className="relative mx-auto max-w-[1280px]">
      <Navbar onLoginClick={onLoginClick} />

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
              onClick={onStartComputingClick}
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
  )
}

export default HomePage
