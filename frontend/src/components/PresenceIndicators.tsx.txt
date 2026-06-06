import React from 'react'

interface PresenceIndicatorsProps {
  viewers: string[]
}

const COLORS = [
  'bg-violet-600',
  'bg-blue-600',
  'bg-emerald-600',
  'bg-amber-600',
  'bg-rose-600',
  'bg-cyan-600',
]

export const PresenceIndicators: React.FC<PresenceIndicatorsProps> = ({ viewers }) => {
  if (viewers.length === 0) return null

  const shown = viewers.slice(0, 4)
  const overflow = viewers.length - shown.length

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-slate-400">Viewing:</span>
      <div className="flex -space-x-2">
        {shown.map((name, i) => {
          const initials = name
            .split('.')
            .map(s => s[0]?.toUpperCase() ?? '?')
            .join('')
            .slice(0, 2)
          return (
            <div
              key={name}
              title={name}
              className={`w-7 h-7 rounded-full ${COLORS[i % COLORS.length]} border-2 border-surface-800
                          flex items-center justify-center text-xs font-bold text-white
                          cursor-default select-none transition-transform hover:scale-110 hover:z-10`}
            >
              {initials}
            </div>
          )
        })}
        {overflow > 0 && (
          <div className="w-7 h-7 rounded-full bg-surface-600 border-2 border-surface-800
                          flex items-center justify-center text-xs text-slate-400 font-semibold">
            +{overflow}
          </div>
        )}
      </div>
      <span className="inline-flex items-center gap-1 text-xs text-emerald-400">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
        Live
      </span>
    </div>
  )
}
