import React from 'react'
import { format } from 'date-fns'
import type { TimelineEvent } from '../api/client'

const ACTOR_ICONS: Record<string, { icon: string; dotClass: string; label: string }> = {
  agent:  { icon: '🤖', dotClass: 'timeline-dot-agent',  label: 'AGENT'  },
  human:  { icon: '👤', dotClass: 'timeline-dot-human',  label: 'HUMAN'  },
  system: { icon: '⚙️', dotClass: 'timeline-dot-system', label: 'SYSTEM' },
}

const ACTOR_LABEL_COLORS: Record<string, string> = {
  agent:  'text-blue-400',
  human:  'text-emerald-400',
  system: 'text-slate-400',
}

interface TimelineProps {
  events: TimelineEvent[]
}

export const Timeline: React.FC<TimelineProps> = ({ events }) => {
  if (events.length === 0) {
    return (
      <div className="text-center py-8 text-slate-500 text-sm">
        No timeline events yet.
      </div>
    )
  }

  return (
    <div className="animate-fade-in">
      {events.map((event, idx) => {
        const actor = ACTOR_ICONS[event.actor_type] || ACTOR_ICONS.system
        const isLast = idx === events.length - 1

        return (
          <div key={event.id} className={`timeline-item ${isLast ? 'pb-0' : ''}`}>
            {/* Timeline dot */}
            <div className={`timeline-dot ${actor.dotClass}`}>
              <span className="text-[10px]">{actor.icon}</span>
            </div>

            {/* Content */}
            <div className="group">
              <div className="flex flex-wrap items-center gap-2 mb-0.5">
                <span className={`text-xs font-bold uppercase tracking-widest ${ACTOR_LABEL_COLORS[event.actor_type]}`}>
                  [{actor.label}{event.actor_id ? ` · ${event.actor_id}` : ''}]
                </span>
                <span className="text-xs text-slate-500 font-mono">
                  {format(new Date(event.timestamp), 'yyyy-MM-dd HH:mm:ss')}
                </span>
                {event.to_status && (
                  <span className="text-xs text-slate-500">
                    → <span className="text-slate-300 font-medium">{event.to_status}</span>
                  </span>
                )}
              </div>

              <p className="text-sm text-slate-200 leading-relaxed">{event.action}</p>

              {event.notes && (
                <p className="text-xs text-slate-400 mt-1 italic">"{event.notes}"</p>
              )}

              {event.metadata_json && Object.keys(event.metadata_json).length > 0 && (
                <details className="mt-1.5">
                  <summary className="text-xs text-slate-500 cursor-pointer hover:text-slate-300 transition-colors">
                    Show metadata
                  </summary>
                  <pre className="mt-1 text-xs bg-surface-700 rounded-lg p-2 overflow-x-auto text-slate-300 font-mono">
                    {JSON.stringify(event.metadata_json, null, 2)}
                  </pre>
                </details>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
