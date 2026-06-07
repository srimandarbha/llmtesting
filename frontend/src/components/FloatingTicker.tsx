import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, Handover } from '../api/client'
import { format } from 'date-fns'

export const FloatingTicker: React.FC = () => {
  const { data: handovers } = useQuery({
    queryKey: ['activeTicker'],
    queryFn: api.getTickerHandovers,
    refetchInterval: 30_000, // Poll every 30 seconds
  })

  // State to dismiss ticker if empty or manually closed
  const [isDismissed, setIsDismissed] = useState(false)

  if (isDismissed) return null
  if (!handovers || handovers.length === 0) return null

  return (
    <div className="bg-surface-800/95 backdrop-blur-md border-b border-white/10 w-full z-[100] shadow-md">
      <div className="flex items-center px-4 py-2 gap-3 max-w-[1400px] mx-auto relative overflow-hidden">
        {/* Static Prefix */}
        <div className="flex items-center gap-2 shrink-0 z-10 bg-surface-800 pr-2">
          <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse" />
          <span className="text-xs font-bold uppercase tracking-widest text-slate-300">
            Active Alerts
          </span>
          <div className="w-px h-4 bg-white/20 mx-1" />
        </div>

        {/* Marquee Container */}
        <div className="flex-1 overflow-hidden relative h-6 flex items-center">
          <div className="animate-marquee whitespace-nowrap flex items-center gap-8 text-sm">
            {handovers.map((ho) => {
              const isActionRequired = ho.action_required
              const isMaintenance = ho.handover_type === 'maintenance'
              
              const colorClass = isActionRequired
                ? 'text-rose-400 font-medium'
                : isMaintenance
                ? 'text-amber-400 font-medium'
                : 'text-slate-300'

              const icon = isActionRequired ? '⚡ Action Required:' : '🔧 Maintenance:'
              
              let timeText = ''
              if (isMaintenance && ho.end_time) {
                timeText = ` (Ends ${format(new Date(ho.end_time), 'HH:mm')})`
              }

              return (
                <span key={ho.id} className="inline-flex items-center gap-2">
                  <span className={`${colorClass}`}>
                    {icon} {ho.shift_identifier || ho.author} - {ho.cluster === 'ALL' ? 'ALL CLUSTERS' : ho.cluster}
                  </span>
                  <span className="text-slate-400 truncate max-w-xl">
                    "{ho.message}" {timeText}
                  </span>
                </span>
              )
            })}
          </div>
        </div>

        {/* Dismiss Button */}
        <div className="shrink-0 z-10 bg-surface-800 pl-2">
          <button
            onClick={() => setIsDismissed(true)}
            className="text-slate-500 hover:text-slate-300 transition-colors"
            title="Dismiss Ticker"
          >
            ✕
          </button>
        </div>
      </div>
    </div>
  )
}
