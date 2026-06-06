import React, { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
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

const EventDetailModal = ({ event, nextEvent, onClose }: { event: TimelineEvent, nextEvent?: TimelineEvent, onClose: () => void }) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const hasMetadata = event.metadata_json && Object.keys(event.metadata_json).length > 0;
  const statusClass = event.to_status ? `badge-${event.to_status.toLowerCase().replace('_', '-')}` : 'bg-slate-700 text-slate-300';
  
  const startTime = format(new Date(event.timestamp), 'yyyy-MM-dd HH:mm:ss');
  const endTime = nextEvent ? format(new Date(nextEvent.timestamp), 'yyyy-MM-dd HH:mm:ss') : (['RESOLVED', 'FAILED', 'ESCALATED', 'REJECTED'].includes(event.to_status || '') ? startTime : 'Ongoing...');

  return createPortal(
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-surface-800 border border-white/10 rounded-xl p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto shadow-2xl" onClick={e => e.stopPropagation()}>
        <div className="flex justify-between items-start mb-6">
          <div>
            <h3 className="text-xl font-semibold text-slate-200 mb-2">Stage Details</h3>
            <div className="flex items-center gap-2">
              <span className="text-sm text-slate-400">Status:</span>
              <span className={`px-2.5 py-1 rounded-full text-xs font-semibold tracking-wide ${statusClass}`}>
                {event.to_status || 'UNKNOWN'}
              </span>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white text-2xl leading-none">&times;</button>
        </div>

        <div className="space-y-4">
          <div className="bg-surface-700/50 rounded-lg p-4 border border-white/5">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-slate-500 block text-xs uppercase tracking-wider mb-1">Start Time</span>
                <span className="text-slate-300 font-mono">{startTime}</span>
              </div>
              <div>
                <span className="text-slate-500 block text-xs uppercase tracking-wider mb-1">End Time</span>
                <span className="text-slate-300 font-mono">{endTime}</span>
              </div>
              <div className="col-span-2 mt-2">
                <span className="text-slate-500 block text-xs uppercase tracking-wider mb-1">Action / Event</span>
                <span className="text-slate-200">{event.action}</span>
              </div>
              {event.notes && (
                <div className="col-span-2 mt-2">
                  <span className="text-slate-500 block text-xs uppercase tracking-wider mb-1">Notes</span>
                  <span className="text-slate-300 italic">{event.notes}</span>
                </div>
              )}
            </div>
          </div>

          {hasMetadata && (
            <div>
              <span className="text-slate-500 block text-xs uppercase tracking-wider mb-2">Attached Metadata</span>
              <pre className="text-sm bg-slate-900 rounded-lg p-4 overflow-x-auto text-slate-300 font-mono border border-white/5">
                {JSON.stringify(event.metadata_json, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
};

export const Timeline: React.FC<TimelineProps> = ({ events }) => {
  const [selectedEventIndex, setSelectedEventIndex] = useState<number | null>(null);

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
              <span className="text-[10px] no-invert">{actor.icon}</span>
            </div>

            {/* Content */}
            <div 
              className="group cursor-pointer hover:bg-white/5 p-2 -mx-2 rounded transition-colors"
              onClick={() => setSelectedEventIndex(idx)}
            >
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
                <p className="text-xs text-slate-400 mt-1 italic line-clamp-2">"{event.notes}"</p>
              )}
            </div>
          </div>
        )
      })}

      {selectedEventIndex !== null && (
        <EventDetailModal 
          event={events[selectedEventIndex]} 
          nextEvent={selectedEventIndex < events.length - 1 ? events[selectedEventIndex + 1] : undefined}
          onClose={() => setSelectedEventIndex(null)} 
        />
      )}
    </div>
  )
}
