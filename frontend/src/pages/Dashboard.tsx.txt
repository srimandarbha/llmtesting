import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { format, formatDistanceToNow } from 'date-fns'
import { api } from '../api/client'
import { StatusBadge, RiskBadge, ConfidenceBadge } from '../components/StatusBadge'

// ─── Stat card ────────────────────────────────────────────────────────────────

interface StatCardProps {
  label: string
  value: number | undefined
  icon: string
  accent: string
  description: string
}

const StatCard: React.FC<StatCardProps> = ({ label, value, icon, accent, description }) => (
  <div className={`glass-card p-5 border-l-4 ${accent} hover:scale-[1.01] transition-transform duration-200`}>
    <div className="flex items-start justify-between">
      <div>
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">{label}</p>
        <p className="text-4xl font-bold text-white mt-1">
          {value ?? <span className="text-slate-600 text-2xl">—</span>}
        </p>
        <p className="text-xs text-slate-500 mt-2">{description}</p>
      </div>
      <span className="text-2xl opacity-60">{icon}</span>
    </div>
  </div>
)

// ─── Status filter pills ───────────────────────────────────────────────────────

const STATUS_FILTERS = [
  { value: '', label: 'All' },
  { value: 'PENDING_APPROVAL', label: 'Pending' },
  { value: 'ANALYZING', label: 'Analyzing' },
  { value: 'EXECUTING', label: 'Executing' },
  { value: 'RESOLVED', label: 'Resolved' },
  { value: 'FAILED', label: 'Failed' },
  { value: 'ESCALATED', label: 'Escalated' },
]

// ─── Dashboard page ────────────────────────────────────────────────────────────

export const Dashboard: React.FC = () => {
  const navigate = useNavigate()
  const [statusFilter, setStatusFilter] = React.useState('')
  const [page, setPage] = React.useState(1)

  const { data: counts } = useQuery({
    queryKey: ['dashboard-counts'],
    queryFn: api.getDashboardCounts,
    refetchInterval: 10_000,
  })

  const { data: incidentsData, isLoading } = useQuery({
    queryKey: ['incidents', statusFilter, page],
    queryFn: () => api.getIncidents({ status: statusFilter || undefined, page }),
    refetchInterval: 15_000,
  })

  return (
    <div className="animate-fade-in space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">
          Incident <span className="text-gradient">Dashboard</span>
        </h1>
        <p className="text-slate-400 text-sm mt-1">
          Real-time view of all SRE incidents managed by the LangChain agent.
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Active"
          value={counts?.active}
          icon="⚡"
          accent="border-blue-500"
          description="Currently being processed"
        />
        <StatCard
          label="Pending Approval"
          value={counts?.pending_approval}
          icon="🔐"
          accent="border-orange-500"
          description="Awaiting human decision"
        />
        <StatCard
          label="Resolved Today"
          value={counts?.resolved_today}
          icon="✓"
          accent="border-emerald-500"
          description="Auto or human-approved fixes"
        />
        <StatCard
          label="Failed"
          value={counts?.failed}
          icon="✗"
          accent="border-red-500"
          description="Execution or agent failures"
        />
      </div>

      {/* Filter pills */}
      <div className="flex flex-wrap gap-2">
        {STATUS_FILTERS.map(f => (
          <button
            key={f.value}
            onClick={() => { setStatusFilter(f.value); setPage(1) }}
            className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all duration-200 ${
              statusFilter === f.value
                ? 'bg-brand-500 text-white shadow-lg shadow-brand-900/40'
                : 'bg-surface-700 text-slate-400 hover:text-white hover:bg-surface-600'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Incidents table */}
      <div className="glass-card overflow-hidden">
        <div className="px-4 py-3 border-b border-white/5 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-300">
            Incidents
            {incidentsData?.total !== undefined && (
              <span className="ml-2 text-slate-500 font-normal">({incidentsData.total} total)</span>
            )}
          </h2>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-16 text-slate-400">
            <div className="w-6 h-6 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mr-3" />
            Loading incidents...
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Alert</th>
                  <th>Cluster / Namespace</th>
                  <th>Status</th>
                  <th>Risk</th>
                  <th>Confidence</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {incidentsData?.items?.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="text-center text-slate-500 py-8">
                      No incidents found.
                    </td>
                  </tr>
                ) : (
                  incidentsData?.items?.map((incident: any) => (
                    <tr
                      key={incident.id}
                      onClick={() => navigate(`/incidents/${incident.id}`)}
                      className={incident.status === 'PENDING_APPROVAL' ? 'bg-orange-900/5' : ''}
                    >
                      <td>
                        <div className="font-medium text-slate-200">{incident.alert_name}</div>
                        <div className="text-xs text-slate-500 font-mono mt-0.5">
                          {incident.id.slice(0, 8)}…
                        </div>
                      </td>
                      <td>
                        <div className="text-slate-300">{incident.cluster}</div>
                        <div className="text-xs text-slate-500">{incident.namespace}</div>
                      </td>
                      <td>
                        <StatusBadge status={incident.status} animated />
                      </td>
                      <td>
                        <RiskBadge tier={incident.risk_tier} />
                      </td>
                      <td>
                        <ConfidenceBadge confidence={incident.llm_confidence} />
                      </td>
                      <td className="text-slate-400 text-xs">
                        <div>{format(new Date(incident.created_at), 'MMM d, HH:mm')}</div>
                        <div className="text-slate-600">
                          {formatDistanceToNow(new Date(incident.created_at), { addSuffix: true })}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {incidentsData && incidentsData.total > incidentsData.page_size && (
          <div className="px-4 py-3 border-t border-white/5 flex items-center justify-between">
            <span className="text-xs text-slate-500">
              Page {page} of {Math.ceil(incidentsData.total / incidentsData.page_size)}
            </span>
            <div className="flex gap-2">
              <button
                className="btn-ghost text-xs py-1.5"
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                ← Prev
              </button>
              <button
                className="btn-ghost text-xs py-1.5"
                onClick={() => setPage(p => p + 1)}
                disabled={incidentsData.items.length < incidentsData.page_size}
              >
                Next →
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
