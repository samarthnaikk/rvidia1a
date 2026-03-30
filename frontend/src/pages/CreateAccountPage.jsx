import createAccountRightImage from '../assets/image.png'
import { useState } from 'react'
import { login, signup } from '../lib/api'

function CreateAccountPage({ onBackToLogin, onCreateAccountSuccess }) {
  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')

  const handleCreateAccount = async () => {
    setIsSubmitting(true)
    setErrorMessage('')
    try {
      await signup({
        username,
        email,
        password,
        confirm_password: password,
      })
      const auth = await login({
        username_or_email: username,
        password,
      })
      onCreateAccountSuccess(auth.access_token)
    } catch (error) {
      setErrorMessage(error.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <section className="relative grid min-h-screen w-full grid-cols-1 overflow-hidden lg:grid-cols-2">
      <div className="pointer-events-none absolute inset-y-0 left-0 w-full bg-black lg:w-1/2" />
      <div className="pointer-events-none absolute inset-y-0 right-0 hidden w-1/2 items-center justify-center bg-black lg:flex">
        <img
          alt=""
          aria-hidden="true"
          className="h-[92%] w-[92%] object-contain"
          src={createAccountRightImage}
        />
      </div>

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

        <h1 className="text-[56px] font-bold uppercase leading-[1.05] tracking-[0.8px] text-slate-100">Initialize_Node</h1>
        <p className="mt-3 max-w-[520px] text-[16px] leading-[1.6] text-slate-400/80">
          Establish your cryptographic identity within the RVIDIA decentralized network. Ensure your encryption keys are secured offline.
        </p>

        <div className="mt-10 max-w-[520px] rounded-[10px] border border-white/10 bg-[#0c1321bf] p-7 shadow-[0_0_0_1px_rgba(51,65,85,0.4),0_20px_40px_rgba(2,6,23,0.45)] backdrop-blur-sm">
          <label className="mb-2 block text-[10px] uppercase tracking-[3px] text-emerald-300/80">E-Mail</label>
          <input
            className="font-jetbrains mb-5 h-[50px] w-full rounded-[6px] bg-[#0a0f19] px-4 text-[15px] text-slate-300 outline-none placeholder:text-slate-500/70 focus:ring-1 focus:ring-emerald-300/40"
            onChange={(event) => setEmail(event.target.value)}
            placeholder="e.g. ALPHA@gmail.com"
            type="email"
            value={email}
          />

          <label className="mb-2 block text-[10px] uppercase tracking-[3px] text-emerald-300/80">Username</label>
          <input
            className="font-jetbrains mb-5 h-[50px] w-full rounded-[6px] bg-[#0a0f19] px-4 text-[15px] text-slate-300 outline-none placeholder:text-slate-500/70 focus:ring-1 focus:ring-emerald-300/40"
            onChange={(event) => setUsername(event.target.value)}
            placeholder="e.g. ALPHA_VANGUARD_01"
            type="text"
            value={username}
          />

          <label className="mb-2 block text-[10px] uppercase tracking-[3px] text-emerald-300/80">Password</label>
          <input
            className="font-jetbrains mb-7 h-[50px] w-full rounded-[6px] bg-[#0a0f19] px-4 text-[15px] text-slate-300 outline-none placeholder:text-slate-500/70 focus:ring-1 focus:ring-emerald-300/40"
            onChange={(event) => setPassword(event.target.value)}
            placeholder="••••••••••••••••"
            type="password"
            value={password}
          />

          {errorMessage && <p className="mb-4 text-[13px] text-red-300">{errorMessage}</p>}

          <div className="mb-7 rounded-[8px] border border-white/10 bg-[#0f1726] px-4 py-3 text-[10px] leading-[1.6] tracking-[0.5px] text-slate-500">
            SECURITY_PROTOCOL: Keys are hashed locally. RVIDIA does not store plain-text secrets on centralized relays.
          </div>

          <button
            className="h-[56px] w-full rounded-[6px] border border-emerald-200/70 bg-[#95f2bd] text-[14px] font-bold uppercase tracking-[3px] text-[#0b2d1e] shadow-[0_0_22px_rgba(134,239,172,0.25)]"
            disabled={isSubmitting}
            onClick={handleCreateAccount}
            type="button"
          >
            {isSubmitting ? 'Creating_Account...' : 'Create_Account'}
          </button>

          <div className="mt-10 flex items-center justify-between border-t border-t-white/10 pt-6">
            <button
              className="text-[11px] uppercase tracking-[2px] text-slate-500 transition hover:text-slate-300"
              onClick={onBackToLogin}
              type="button"
            >
              ← Back To Login
            </button>
            <span className="text-[10px] uppercase tracking-[2px] text-slate-600">VER: 4.6.2-STABLE</span>
          </div>
        </div>
      </div>

      <div className="relative z-10" />

      <div className="pointer-events-none absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-white/8" />
    </section>
  )
}

export default CreateAccountPage
