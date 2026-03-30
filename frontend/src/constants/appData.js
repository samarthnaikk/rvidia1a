export const NAV_LINKS = [
  { label: 'Network', href: '#network', isActive: true },
  { label: 'Nodes', href: '#nodes', isActive: false },
  { label: 'Docs', href: '#docs', isActive: false },
]

export const METRICS = [
  { label: 'Active Nodes', value: '12,482', valueClassName: 'text-emerald-400' },
  { label: 'Network TFLOPS', value: '842.1', valueClassName: 'text-sky-300' },
]

export const APP_CLASSES = {
  main: 'relative min-h-screen overflow-x-hidden bg-transparent text-slate-100',
  backgroundOverlay:
    'pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,#00A2FD0D_0%,transparent_34%),radial-gradient(circle_at_70%_30%,rgba(213,228,221,0.28),transparent_38%),linear-gradient(118deg,rgba(202,218,209,0.48)_0%,rgba(16,22,27,0.16)_38%,rgba(3,8,20,0.88)_68%,rgba(167,188,175,0.4)_100%)]',
  navbar:
    'flex h-16 w-full items-center justify-between border-b border-b-white/15 bg-[#0206174D] px-8 text-[20px] font-bold leading-7 tracking-[2px]',
}
