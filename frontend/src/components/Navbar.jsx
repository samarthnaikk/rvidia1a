import { NAV_LINKS, APP_CLASSES } from '../constants/appData'

function Navbar({ onLoginClick }) {
  return (
    <nav className={APP_CLASSES.navbar}>
      <div className="text-[20px] text-emerald-400">RVIDIA</div>

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
        onClick={onLoginClick}
        type="button"
      >
        Log In
      </button>
    </nav>
  )
}

export default Navbar
