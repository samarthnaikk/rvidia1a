import Navbar from '../components/Navbar'
import atmosphereGlow from '../assets/imagee.png'

function HomePage({ onLoginClick, onStartComputingClick }) {
  return (
    <div
      className="relative min-h-screen w-full overflow-hidden"
      style={{ background: 'linear-gradient(48.58deg, #B9D0BF 13.87%, #080808 48.2%, #A9BCB8 82.53%)' }}
    >
      <div
        className="pointer-events-none absolute left-1/2 top-1/2 h-[780px] w-[780px] -translate-x-1/2 -translate-y-1/2 bg-center bg-no-repeat opacity-55 mix-blend-screen blur-[36px]"
        style={{ backgroundImage: `url(${atmosphereGlow})`, backgroundSize: 'contain' }}
      />

      <Navbar onLoginClick={onLoginClick} />

      <section className="mx-auto mt-8 px-6 pb-10 pt-10 md:px-10">
        <div className="mx-auto max-w-[1120px] text-center">
          <h1 className="align-middle font-space text-center text-[64px] font-bold leading-[96px] tracking-[4.8px] text-[#d1d5db]">
            Power the Future of AI <br />
            With
            <br />
            <span className="mt-11 inline-block whitespace-nowrap text-[#0EFE95] text-[96px]">Decentralized Compute</span>
          </h1>

      <p className="mx-auto mt-32 max-w-[760px] text-center font-['Manrope'] text-[20px] font-normal text-[#B9CBBB] leading-[28px] tracking-[0px] text-slate-300/90 align-middle">
            Access high-performance GPUs and idle compute cycles at a fraction of centralized cost. Secure, scalable, and fully sovereign.
          </p>

          <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
            <button
              className="h-[52px] min-w-[210px] border border-emerald-400 bg-[#0EFE95] px-7 text-[12px] font-bold uppercase tracking-[3px] text-slate-900 transition hover:brightness-110"
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
        </div>
      </section>
    </div>
  )
}

export default HomePage
