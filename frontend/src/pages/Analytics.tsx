import React from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, PieChart, Pie, Cell, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { api } from '../api/client'

const COLORS = ['#4f46e5', '#22c55e', '#f97316', '#ef4444', '#06b6d4']

const formatSeconds = (s: number) => {
  const m = Math.round(s / 60)
  return m < 60 ? `${m}m` : `${(m / 60).toFixed(1)}h`
}

export const Analytics: React.FC = () => {
  const { data, isLoading, error } = useQuery({
    queryKey: ['analytics'],
    queryFn: api.getAnalytics,
    staleTime: 60_000,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-400">
        <div className="w-6 h-6 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mr-3" />
        Loading analytics…
      </div>
    )
  }

  if (error || !data) {
    return <p className="text-red-400 text-center py-16">Failed to load analytics.</p>
  }

  const { mttr_by_cluster, resolution_stats, llm_accuracy, top_recurring_alerts } = data

  const resolutionPieData = [
    { name: 'Auto-Resolved', value: resolution_stats.auto_resolved },
    { name: 'Human-Intervened', value: resolution_stats.human_intervened },
  ]

  const llmAccuracyData = [
    { name: 'Approved As-Is', value: llm_accuracy.approved_as_is, fill: '#22c55e' },
    { name: 'Edited Then Approved', value: llm_accuracy.edited_before_approve, fill: '#f97316' },
    { name: 'Rejected', value: llm_accuracy.rejected, fill: '#ef4444' },
  ]

  return (
    <div className="animate-fade-in space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">
          Analytics <span className="text-gradient">&amp; Insights</span>
        </h1>
        <p className="text-slate-400 text-sm mt-1">
          MTTR trends, LLM accuracy, and incident patterns.
        </p>
      </div>

      {/* ─── Top row: Resolution split + LLM accuracy ─────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Resolution donut */}
        <div className="glass-card p-6">
          <h2 className="text-sm font-semibold text-slate-300 mb-4">
            🤖 Auto vs Human Resolution
          </h2>
          <div className="flex items-center gap-6">
            <ResponsiveContainer width={160} height={160}>
              <PieChart>
                <Pie
                  data={resolutionPieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={48}
                  outerRadius={70}
                  paddingAngle={4}
                  dataKey="value"
                >
                  {resolutionPieData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ background: '#1a1e35', border: '1px solid #ffffff10', borderRadius: 8 }}
                  labelStyle={{ color: '#94a3b8' }}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="space-y-3 flex-1">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full" style={{ background: COLORS[0] }} />
                  <span className="text-sm text-slate-300">Auto-Resolved</span>
                </div>
                <span className="text-lg font-bold text-white">{resolution_stats.auto_resolved_pct}%</span>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full" style={{ background: COLORS[1] }} />
                  <span className="text-sm text-slate-300">Human-Intervened</span>
                </div>
                <span className="text-lg font-bold text-white">{resolution_stats.human_intervened_pct}%</span>
              </div>
              <div className="pt-2 border-t border-white/5 text-xs text-slate-500">
                Total closed: {resolution_stats.total}
              </div>
            </div>
          </div>
        </div>

        {/* LLM accuracy bars */}
        <div className="glass-card p-6">
          <h2 className="text-sm font-semibold text-slate-300 mb-4">
            🧠 LLM Decision Accuracy
          </h2>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={llmAccuracyData} barSize={32}>
              <CartesianGrid strokeDasharray="3 3" stroke="#ffffff08" />
              <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ background: '#1a1e35', border: '1px solid #ffffff10', borderRadius: 8 }}
                cursor={{ fill: '#ffffff08' }}
              />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {llmAccuracyData.map((entry, i) => (
                  <Cell key={i} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <p className="text-xs text-slate-500 mt-2 text-center">
            Total HIGH-risk reviews: {llm_accuracy.total_high_risk}
          </p>
        </div>
      </div>

      {/* ─── MTTR chart ───────────────────────────────────────────────── */}
      {mttr_by_cluster.length > 0 && (
        <div className="glass-card p-6">
          <h2 className="text-sm font-semibold text-slate-300 mb-4">
            ⏱ MTTR by Alert Type (Top 20)
          </h2>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={mttr_by_cluster} layout="vertical" barSize={16}>
              <CartesianGrid strokeDasharray="3 3" stroke="#ffffff08" horizontal={false} />
              <XAxis
                type="number"
                tick={{ fill: '#94a3b8', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={formatSeconds}
              />
              <YAxis
                type="category"
                dataKey="alert_name"
                width={180}
                tick={{ fill: '#94a3b8', fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                contentStyle={{ background: '#1a1e35', border: '1px solid #ffffff10', borderRadius: 8 }}
                formatter={(v: any) => [formatSeconds(Number(v)), 'Avg MTTR']}
                cursor={{ fill: '#ffffff05' }}
              />
              <Bar dataKey="avg_mttr_seconds" fill="#4f46e5" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* ─── Top recurring incidents ──────────────────────────────────── */}
      {top_recurring_alerts.length > 0 && (
        <div className="glass-card overflow-hidden">
          <div className="px-6 py-4 border-b border-white/5">
            <h2 className="text-sm font-semibold text-slate-300">
              🔁 Top Recurring Alerts (Last 30 Days)
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Candidates to promote to LOW risk tier for fully automated resolution.
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Alert Name</th>
                  <th>Cluster</th>
                  <th>Occurrences (30d)</th>
                  <th>Promotion Candidate</th>
                </tr>
              </thead>
              <tbody>
                {top_recurring_alerts.map((row: any, i: number) => (
                  <tr key={i}>
                    <td className="font-medium text-slate-200">{row.alert_name}</td>
                    <td className="font-mono text-xs">{row.cluster}</td>
                    <td>
                      <div className="flex items-center gap-2">
                        <div
                          className="h-2 rounded-full bg-brand-500/70"
                          style={{ width: `${Math.min(100, (row.occurrences_30d / top_recurring_alerts[0].occurrences_30d) * 100)}%`, minWidth: 8 }}
                        />
                        <span className="text-slate-300 font-semibold">{row.occurrences_30d}</span>
                      </div>
                    </td>
                    <td>
                      {row.occurrences_30d >= 5 ? (
                        <span className="badge badge-resolved text-xs">✓ Consider promoting</span>
                      ) : (
                        <span className="text-slate-600 text-xs">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
