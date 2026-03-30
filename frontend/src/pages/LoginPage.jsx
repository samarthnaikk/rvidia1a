import rightSideBackground from '../assets/bg.png'
import operationalOverlayImage from '../assets/Overlay+Border+Shadow+OverlayBlur.png'

function LoginPage({ onCreateAccountClick, onLoginSuccess }) {
  return (
    <section className="relative grid min-h-screen w-full grid-cols-1 overflow-hidden lg:grid-cols-2">
      <div className="pointer-events-none absolute inset-y-0 left-0 w-full bg-black lg:w-1/2" />
      <img
        alt=""
        aria-hidden="true"
        className="pointer-events-none absolute inset-y-0 right-0 hidden h-full w-1/2 object-cover lg:block"
        src={rightSideBackground}
      />

      <div className="relative z-10 border-r border-r-white/10 bg-black px-9 pb-10 pt-28 lg:px-[72px]">
        <div className="mb-14 flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded border border-emerald-300/45 bg-emerald-300/10 shadow-[0_0_18px_rgba(110,231,183,0.14)]">
            <div className="grid grid-cols-2 gap-[2px]">
              <span className="h-[5px] w-[5px] rounded-[1px] bg-emerald-300" />
              <span className="h-[5px] w-[5px] rounded-[1px] bg-emerald-300/70" />
              <span className="h-[5px] w-[5px] rounded-[1px] bg-emerald-300/70" />
              <span className="h-[5px] w-[5px] rounded-[1px] bg-emerald-300" />
            </div>
          </div>
          <p className="text-[29px] font-bold tracking-[2px] text-emerald-300">RVIDIA</p>
        </div>

        <h1 className="text-[56px] font-bold leading-[1.08] tracking-[0.4px] text-slate-100">Access the Core</h1>
        <p className="mt-3 max-w-[520px] text-[16px] leading-[1.6] text-slate-400/80">
          Secure entry point for decentralized compute node management.
        </p>

        <div className="mt-10 max-w-[520px] rounded-[10px] border border-white/10 bg-[#0c1321bf] p-7 shadow-[0_0_0_1px_rgba(51,65,85,0.4),0_20px_40px_rgba(2,6,23,0.45)] backdrop-blur-sm">
          <label className="mb-2 block text-[10px] uppercase tracking-[3px] text-slate-500">E-Mail</label>
          <input
            className="font-jetbrains mb-5 h-[50px] w-full border-b border-b-white/10 bg-transparent px-1 text-[15px] text-slate-300 outline-none placeholder:text-slate-500/70 focus:border-b-emerald-300/60"
            placeholder="user@gmail.com"
            type="email"
          />

          <div className="mb-2 flex items-center justify-between">
            <label className="block text-[10px] uppercase tracking-[3px] text-slate-500">Password</label>
            <button className="text-[10px] uppercase tracking-[2px] text-emerald-300/70" type="button">
              Forgot Password
            </button>
          </div>
          <input
            className="font-jetbrains mb-7 h-[50px] w-full border-b border-b-white/10 bg-transparent px-1 text-[15px] text-slate-300 outline-none placeholder:text-slate-500/70 focus:border-b-emerald-300/60"
            placeholder="••••••••"
            type="password"
          />

          <button
            className="h-[56px] w-full rounded-[2px] border border-emerald-200/70 bg-[#95f2bd] text-[14px] font-bold uppercase tracking-[3px] text-[#0b2d1e] shadow-[0_0_22px_rgba(134,239,172,0.25)]"
            onClick={onLoginSuccess}
            type="button"
          >
            Log In
          </button>

          <div className="my-8 text-center text-[10px] uppercase tracking-[3px] text-slate-500">Third Party Verification</div>

          <button
            className="mx-auto block h-[42px] w-[190px] rounded-[2px] border border-white/10 bg-transparent text-[11px] uppercase tracking-[2px] text-slate-400"
            type="button"
          >
            ⟠ Google
          </button>
        </div>

        <p className="mt-12 max-w-[520px] text-center text-[14px] text-slate-500">
          New to the infrastructure?{' '}
          <button
            className="font-semibold text-emerald-300 transition hover:text-emerald-200"
            onClick={onCreateAccountClick}
            type="button"
          >
            Create Account
          </button>
        </p>
      </div>

      <div className="relative z-10 px-9 pb-10 pt-[168px] lg:px-[72px]">
        <img
          alt="Operational status panel"
          className="w-full max-w-[560px] select-none"
          src={operationalOverlayImage}
        />

        <h2 className="mt-16 max-w-[560px] text-[56px] font-bold leading-[1.1] text-slate-100">
          Empowering the Next Generation of <span className="text-emerald-300">Compute.</span>
        </h2>

        <p className="mt-6 max-w-[560px] text-[18px] leading-[1.55] text-slate-400/85">
          Join the global mesh of high-performance clusters. Rent or lease processing power with instantaneous settlement.
        </p>

        <div className="mt-10 flex flex-wrap gap-3">
          <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.03] px-4 py-2 text-[10px] uppercase tracking-[2px] text-slate-400">
            <span className="mr-2 h-2 w-2 rounded-full bg-emerald-300 shadow-[0_0_12px_#86efac]" />
            Network Stable
          </span>
          <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.03] px-4 py-2 text-[10px] uppercase tracking-[2px] text-slate-400">
            <span className="mr-2 h-2 w-2 rounded-full border border-slate-400" />
            E2E_Encrypted
          </span>
        </div>

        <p className="absolute bottom-6 right-10 text-[10px] uppercase tracking-[2px] text-slate-600">V2.0.4 - Stable</p>
      </div>

      <div className="pointer-events-none absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-white/8" />
    </section>
  )
}

export default LoginPage
