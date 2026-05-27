import React, { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { format } from 'date-fns'
import { api } from '../api/client'
import { StatusBadge, RiskBadge, ConfidenceBadge } from '../components/StatusBadge'
import { Timeline } from '../components/Timeline'
import { ApprovalCard } from '../components/ApprovalCard'
import { PresenceIndicators } from '../components/PresenceIndicators'
import { useIncidentWebSocket } from '../hooks/useWebSocket'

export const IncidentDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [viewers, setViewers] = useState<string[]>([])
  const [showReasoning, setShowReasoning] = useState(false)
  const currentUser = localStorage.getItem('sre_user_id') || 'dev-user'

  const { data: incident, isLoading, error } = useQuery({
    queryKey: ['incident', id],
    queryFn: () => api.getIncident(id!),
    enabled: !!id,
    refetchInterval: 20_000,
  })

  // Real-time WebSocket updates
  useIncidentWebSocket(id ?? null, currentUser, (msg) => {
    if (msg.type === 'presence' && msg.viewers) {
      setViewers(msg.viewers)
    }
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-400">
        <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mr-3" />
        Loading incident…
      </div>
    )
  }

  if (error || !incident) {
    return (
      <div className="text-center py-16">
        <p className="text-red-400 text-lg">Incident not found.</p>
        <button className="btn-ghost mt-4" onClick={() => navigate('/')}>← Back</button>
      </div>
    )
  }

  return (
    <div className="animate-fade-in space-y-6 max-w-5xl">
      {/* Back link */}
      <button
        className="text-slate-400 hover:text-white text-sm flex items-center gap-1.5 transition-colors"
        onClick={() => navigate('/')}
      >
        ← Back to Dashboard
      </button>

      {/* ─── Header ─────────────────────────────────────────────────────── */}
      <div className="glass-card p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-xl font-bold text-white truncate">{incident.alert_name}</h1>
              <StatusBadge status={incident.status} animated size="md" />
              <RiskBadge tier={incident.risk_tier} />
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-6 gap-y-2 mt-4 text-sm">
              <div>
                <span className="text-slate-500 text-xs">Cluster</span>
                <p className="text-slate-200 font-medium">{incident.cluster}</p>
              </div>
              <div>
                <span className="text-slate-500 text-xs">Namespace</span>
                <p className="text-slate-200 font-mono text-xs">{incident.namespace}</p>
              </div>
              <div>
                <span className="text-slate-500 text-xs">Hostname</span>
                <p className="text-slate-200 font-mono text-xs">{incident.hostname ?? '—'}</p>
              </div>
              <div>
                <span className="text-slate-500 text-xs">Confidence</span>
                <div className="mt-0.5">
                  <ConfidenceBadge confidence={incident.llm_confidence} />
                </div>
              </div>
              <div>
                <span className="text-slate-500 text-xs">Correlation ID</span>
                <p className="text-slate-300 font-mono text-xs truncate">{incident.correlation_id ?? '—'}</p>
              </div>
              <div>
                <span className="text-slate-500 text-xs">Created</span>
                <p className="text-slate-300 text-xs">
                  {format(new Date(incident.created_at), 'MMM d yyyy, HH:mm:ss')}
                </p>
              </div>
              {incident.awx_job_id && (
                <div>
                  <span className="text-slate-500 text-xs">AWX Job</span>
                  <p className="text-brand-400 font-mono text-xs">#{incident.awx_job_id}</p>
                </div>
              )}
              {incident.resolved_at && (
                <div>
                  <span className="text-slate-500 text-xs">Resolved</span>
                  <p className="text-emerald-400 text-xs">
                    {format(new Date(incident.resolved_at), 'MMM d, HH:mm:ss')}
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Presence indicators */}
          <PresenceIndicators viewers={viewers} />
        </div>
      </div>

      {/* ─── Approval card (shown only when PENDING_APPROVAL) ──────────── */}
      {incident.status === 'PENDING_APPROVAL' && (
        <ApprovalCard incident={incident} currentUserId={currentUser} />
      )}

      {/* ─── Timeline ────────────────────────────────────────────────────── */}
      <div className="glass-card p-6">
        <h2 className="text-sm font-semibold text-slate-300 mb-5 flex items-center gap-2">
          <span className="text-base">📋</span> Incident Timeline
          <span className="ml-auto text-xs text-slate-500 font-normal">
            {incident.timeline.length} events
          </span>
        </h2>
        <Timeline events={incident.timeline} />
      </div>

      {/* ─── LLM Reasoning (collapsible) ─────────────────────────────────── */}
      {incident.llm_decisions.length > 0 && (
        <div className="glass-card overflow-hidden">
          <button
            className="w-full px-6 py-4 flex items-center justify-between hover:bg-white/3 transition-colors"
            onClick={() => setShowReasoning(!showReasoning)}
          >
            <div className="flex items-center gap-2">
              <span>🧠</span>
              <span className="text-sm font-semibold text-slate-300">LLM Reasoning & Tool Calls</span>
            </div>
            <span className="text-slate-500 text-sm">{showReasoning ? '▴' : '▾'}</span>
          </button>

          {showReasoning && (
            <div className="border-t border-white/5 p-6 space-y-4 animate-slide-in">
              {incident.llm_decisions.slice(0, 1).map(decision => (
                <div key={decision.id} className="space-y-4">
                  {/* Tool calls */}
                  {decision.tool_calls_json && Array.isArray(decision.tool_calls_json) && (
                    <div>
                      <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                        Tool Calls ({(decision.tool_calls_json as any[]).length})
                      </h4>
                      <div className="space-y-2">
                        {(decision.tool_calls_json as any[]).map((call, i) => (
                          <details key={i} className="bg-surface-700 rounded-lg overflow-hidden">
                            <summary className="px-3 py-2 cursor-pointer text-xs font-mono text-brand-400 hover:text-brand-300 transition-colors">
                              {call.tool}({typeof call.input === 'object' ? JSON.stringify(call.input) : call.input})
                            </summary>
                            <pre className="px-3 pb-3 text-xs text-slate-300 overflow-x-auto">
                              {typeof call.output === 'string'
                                ? call.output
                                : JSON.stringify(call.output, null, 2)}
                            </pre>
                          </details>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Parsed intent */}
                  {decision.parsed_intent && (
                    <div>
                      <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                        Final Intent JSON
                      </h4>
                      <pre className="bg-surface-700 rounded-lg p-3 text-xs font-mono text-slate-300 overflow-x-auto">
                        {JSON.stringify(decision.parsed_intent, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ─── Human Actions log ───────────────────────────────────────────── */}
      {incident.human_actions.length > 0 && (
        <div className="glass-card p-6">
          <h2 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
            <span>👤</span> Human Actions
          </h2>
          <div className="space-y-3">
            {incident.human_actions.map(action => (
              <div key={action.id} className="flex items-start gap-3 p-3 bg-surface-700/50 rounded-lg">
                <div className={`w-2 h-2 rounded-full mt-1.5 ${
                  action.action === 'APPROVED' ? 'bg-emerald-400'
                  : action.action === 'REJECTED' ? 'bg-rose-400'
                  : action.action === 'EDITED' ? 'bg-blue-400'
                  : 'bg-amber-400'
                }`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-semibold text-slate-200">{action.user_id}</span>
                    <span className={`badge text-xs ${
                      action.action === 'APPROVED' ? 'badge-resolved'
                      : action.action === 'REJECTED' ? 'badge-rejected'
                      : 'badge-analyzing'
                    }`}>{action.action}</span>
                    <span className="text-xs text-slate-500">
                      {format(new Date(action.timestamp), 'MMM d, HH:mm:ss')}
                    </span>
                  </div>
                  <p className="text-sm text-slate-400 mt-1 italic">"{action.reason}"</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
