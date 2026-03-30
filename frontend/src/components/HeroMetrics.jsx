import { METRICS } from '../constants/appData'

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

export default HeroMetrics
