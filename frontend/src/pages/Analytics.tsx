import React, { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, PieChart, Pie, Cell, LineChart, Line, Treemap,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { api } from '../api/client'

const COLORS = ['#4f46e5', '#22c55e', '#f97316', '#ef4444', '#06b6d4']

const formatSeconds = (s: number) => {
  const m = Math.round(s / 60)
  return m < 60 ? `${m}m` : `${(m / 60).toFixed(1)}h`
}

export const Analytics: React.FC = () => {
  const [visiblePanels, setVisiblePanels] = useState({
    highLevelMetrics: true,
    resolutionSplit: true,
    sentimentTrend: true,
    environmentDistribution: true,
    mttrChart: true,
    componentsRow: true,
    recurringIncidents: true,
    flappingLeaderboard: true,
  })
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)

  useEffect(() => {
    const saved = localStorage.getItem('analytics_panels')
    if (saved) {
      try { setVisiblePanels(JSON.parse(saved)) } catch (e) {}
    }
  }, [])

  const togglePanel = (key: keyof typeof visiblePanels) => {
    const next = { ...visiblePanels, [key]: !visiblePanels[key] };
    setVisiblePanels(next);
    localStorage.setItem('analytics_panels', JSON.stringify(next));
  }

  const toggleAllPanels = (val: boolean) => {
    const next = Object.keys(visiblePanels).reduce((acc, key) => {
      acc[key as keyof typeof visiblePanels] = val;
      return acc;
    }, {} as typeof visiblePanels);
    setVisiblePanels(next);
    localStorage.setItem('analytics_panels', JSON.stringify(next));
  }

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

  const { 
    mttr_by_cluster, resolution_stats, llm_accuracy, top_recurring_alerts,
    flapping_alerts, sentiment_trend, redhat_cases_summary, component_incidents,
    fleet_risk, environment_distribution 
  } = data

  const resolutionPieData = [
    { name: 'Auto-Resolved', value: resolution_stats?.auto_resolved || 0 },
    { name: 'Human-Intervened', value: resolution_stats?.human_intervened || 0 },
  ]

  const llmAccuracyData = [
    { name: 'Approved As-Is', value: llm_accuracy?.approved_as_is || 0, fill: '#22c55e' },
    { name: 'Edited Then Approved', value: llm_accuracy?.edited_before_approve || 0, fill: '#f97316' },
    { name: 'Rejected', value: llm_accuracy?.rejected || 0, fill: '#ef4444' },
  ]

  return (
    <div className="animate-fade-in space-y-8 pb-12">
      {/* Header and Controls */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">
            Analytics <span className="text-gradient">&amp; Insights</span>
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            MTTR trends, LLM accuracy, and incident patterns.
          </p>
        </div>
        
        {/* Panel Toggles */}
        <div className="relative">
          <button 
            onClick={() => setIsDropdownOpen(!isDropdownOpen)}
            className="btn btn-ghost bg-slate-900/50 text-sm border-slate-700 hover:bg-slate-800"
          >
            <span className="text-xs font-semibold text-slate-400 uppercase mr-2">Visible Panels</span>
            <span className="text-slate-300 font-bold bg-surface-700 px-2 py-0.5 rounded text-xs border border-white/5">
              {Object.values(visiblePanels).filter(Boolean).length}/{Object.keys(visiblePanels).length}
            </span>
            <span className="ml-2 text-slate-500 text-xs no-invert">▼</span>
          </button>
          
          {isDropdownOpen && (
            <>
              {/* Invisible backdrop to close dropdown when clicking outside */}
              <div className="fixed inset-0 z-40" onClick={() => setIsDropdownOpen(false)} />
              
              <div className="absolute right-0 top-full mt-2 w-64 bg-surface-800 border border-white/10 rounded-xl shadow-2xl z-50 p-2 max-h-96 overflow-y-auto animate-fade-in">
                <div className="flex items-center justify-between px-3 py-2 mb-2 border-b border-white/5">
                  <button 
                    onClick={() => toggleAllPanels(true)}
                    className="text-xs font-semibold text-brand-400 hover:text-brand-300 transition-colors"
                  >
                    ✓ Select All
                  </button>
                  <button 
                    onClick={() => toggleAllPanels(false)}
                    className="text-xs font-medium text-slate-500 hover:text-slate-400 transition-colors"
                  >
                    Clear All
                  </button>
                </div>
                
                {Object.entries(visiblePanels).map(([key, isVisible]) => (
                  <label key={key} className="flex items-center gap-3 px-3 py-2 hover:bg-white/5 rounded-lg cursor-pointer transition-colors text-sm text-slate-300">
                    <input 
                      type="checkbox" 
                      className="rounded border-slate-600 bg-surface-700 text-brand-500 focus:ring-brand-500 focus:ring-offset-surface-800 w-4 h-4 cursor-pointer"
                      checked={isVisible}
                      onChange={() => togglePanel(key as keyof typeof visiblePanels)}
                    />
                    <span>{key.replace(/([A-Z])/g, ' $1').replace(/^./, str => str.toUpperCase())}</span>
                  </label>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* ─── High-Level Metrics Row ──────────────────────────────────────── */}
      {visiblePanels.highLevelMetrics && fleet_risk && redhat_cases_summary && sentiment_trend && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <div className="glass-card p-6 border-t-4 border-red-500">
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">Fleet Vulnerability Risk</h2>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-3xl font-bold text-white">{fleet_risk.average_risk_pct}%</span>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              {fleet_risk.critical_cves_active} Critical CVEs Active
            </p>
          </div>

          <div className="glass-card p-6 border-t-4 border-blue-500">
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">Open Red Hat Cases</h2>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-3xl font-bold text-white">{redhat_cases_summary.open_cases}</span>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              {redhat_cases_summary.critical_escalation_pct}% of incidents escalated
            </p>
          </div>

          <div className="glass-card p-6 border-t-4 border-purple-500">
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">Vendor MTTR</h2>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-3xl font-bold text-white">{redhat_cases_summary.avg_vendor_mttr_days}</span>
              <span className="text-sm text-slate-400">days</span>
            </div>
            <p className="text-xs text-slate-500 mt-1">Average time to close RH support tickets</p>
          </div>

          <div className="glass-card p-6 border-t-4 border-emerald-500">
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">Avg SRE Sentiment</h2>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-3xl font-bold text-white">
                {sentiment_trend && sentiment_trend.length > 0 ? (sentiment_trend[sentiment_trend.length - 1].average_score * 100).toFixed(0) : 0}%
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1">Resolution quality score (last 24h)</p>
          </div>
        </div>
      )}

      {/* ─── Top row: Resolution split + LLM accuracy ─────────────────── */}
      {visiblePanels.resolutionSplit && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
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
                    contentStyle={{ background: 'var(--chart-tooltip-bg)', border: '1px solid var(--chart-tooltip-border)', borderRadius: 8 }}
                    labelStyle={{ color: 'var(--chart-tick-text)' }}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-3 flex-1">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full" style={{ background: COLORS[0] }} />
                    <span className="text-sm text-slate-300">Auto-Resolved</span>
                  </div>
                  <span className="text-lg font-bold text-white">{resolution_stats?.auto_resolved_pct}%</span>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full" style={{ background: COLORS[1] }} />
                    <span className="text-sm text-slate-300">Human-Intervened</span>
                  </div>
                  <span className="text-lg font-bold text-white">{resolution_stats?.human_intervened_pct}%</span>
                </div>
                <div className="pt-2 border-t border-white/5 text-xs text-slate-500">
                  Total closed: {resolution_stats?.total}
                </div>
              </div>
            </div>
          </div>

          <div className="glass-card p-6">
            <h2 className="text-sm font-semibold text-slate-300 mb-4">
              🧠 LLM Decision Accuracy
            </h2>
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={llmAccuracyData} barSize={32}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid-line)" />
                <XAxis dataKey="name" tick={{ fill: 'var(--chart-tick-text)', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: 'var(--chart-tick-text)', fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{ background: 'var(--chart-tooltip-bg)', border: '1px solid var(--chart-tooltip-border)', borderRadius: 8 }}
                  cursor={{ fill: 'var(--chart-cursor-bg)' }}
                />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {llmAccuracyData.map((entry, i) => (
                    <Cell key={i} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <p className="text-xs text-slate-500 mt-2 text-center">
              Total HIGH-risk reviews: {llm_accuracy?.total_high_risk}
            </p>
          </div>
        </div>
      )}

      {/* ─── Middle row: Sentiment Trend + Environment ─────────────────── */}
      {(visiblePanels.sentimentTrend || visiblePanels.environmentDistribution) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {visiblePanels.sentimentTrend && (
            <div className="glass-card p-6">
              <h2 className="text-sm font-semibold text-slate-300 mb-4">
                📈 SRE Sentiment & Resolution Quality
              </h2>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={sentiment_trend || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid-line)" />
                  <XAxis dataKey="date" tick={{ fill: 'var(--chart-tick-text)', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: 'var(--chart-tick-text)', fontSize: 11 }} axisLine={false} tickLine={false} domain={[0, 1]} />
                  <Tooltip
                    contentStyle={{ background: 'var(--chart-tooltip-bg)', border: '1px solid var(--chart-tooltip-border)', borderRadius: 8 }}
                    formatter={(v: number) => [`${(v * 100).toFixed(1)}%`, 'Avg Score']}
                  />
                  <Line type="monotone" dataKey="average_score" stroke="#06b6d4" strokeWidth={3} dot={{ r: 4, fill: '#06b6d4' }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {visiblePanels.environmentDistribution && (
            <div className="glass-card p-6">
              <h2 className="text-sm font-semibold text-slate-300 mb-4">
                🌍 Incident Distribution by Environment
              </h2>
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie
                    data={environment_distribution || []}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={80}
                    paddingAngle={5}
                    dataKey="incident_count"
                    nameKey="environment"
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  >
                    {(environment_distribution || []).map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ background: 'var(--chart-tooltip-bg)', border: '1px solid var(--chart-tooltip-border)', borderRadius: 8 }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {/* ─── MTTR chart ───────────────────────────────────────────────── */}
      {visiblePanels.mttrChart && mttr_by_cluster?.length > 0 && (
        <div className="glass-card p-6">
          <h2 className="text-sm font-semibold text-slate-300 mb-4">
            ⏱ MTTR by Alert Type (Top 20)
          </h2>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={mttr_by_cluster} layout="vertical" barSize={16}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid-line)" horizontal={false} />
              <XAxis
                type="number"
                tick={{ fill: 'var(--chart-tick-text)', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={formatSeconds}
              />
              <YAxis
                type="category"
                dataKey="alert_name"
                width={180}
                tick={{ fill: 'var(--chart-tick-text)', fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                contentStyle={{ background: 'var(--chart-tooltip-bg)', border: '1px solid var(--chart-tooltip-border)', borderRadius: 8 }}
                formatter={(v: any) => [formatSeconds(Number(v)), 'Avg MTTR']}
                cursor={{ fill: 'var(--chart-cursor-bg)' }}
              />
              <Bar dataKey="avg_mttr_seconds" fill="#4f46e5" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* ─── Components Row ───────────────────────────────────────────── */}
      {visiblePanels.componentsRow && component_incidents?.length > 0 && (
        <div className="glass-card p-6">
          <h2 className="text-sm font-semibold text-slate-300 mb-4">
            🧩 Problematic Components (Incidents by Operator)
          </h2>
          <ResponsiveContainer width="100%" height={260}>
            <Treemap
              data={component_incidents.map((c: any) => ({ name: c.component, size: c.incident_count }))}
              dataKey="size"
              stroke="var(--chart-treemap-stroke)"
              content={((props: any) => {
                const { x, y, width, height, name, index } = props;
                return (
                  <g>
                    <rect
                      x={x}
                      y={y}
                      width={width}
                      height={height}
                      fill={COLORS[index % COLORS.length]}
                      stroke="var(--chart-treemap-stroke)"
                    />
                    {width > 50 && height > 30 && (
                      <text
                        x={x + width / 2}
                        y={y + height / 2}
                        textAnchor="middle"
                        fill="var(--chart-treemap-text)"
                        fontSize={11}
                        pointerEvents="none"
                      >
                        {name}
                      </text>
                    )}
                  </g>
                );
              }) as any}
            >
              <Tooltip
                contentStyle={{ background: 'var(--chart-tooltip-bg)', border: '1px solid var(--chart-tooltip-border)', borderRadius: 8 }}
                formatter={(value: number) => [value, 'Incidents']}
              />
            </Treemap>
          </ResponsiveContainer>
        </div>
      )}

      {/* ─── Top recurring incidents ──────────────────────────────────── */}
      {visiblePanels.recurringIncidents && top_recurring_alerts?.length > 0 && (
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

      {/* ─── Flapping Alerts Leaderboard ──────────────────────────────── */}
      {visiblePanels.flappingLeaderboard && flapping_alerts?.length > 0 && (
        <div className="glass-card overflow-hidden">
          <div className="px-6 py-4 border-b border-white/5">
            <h2 className="text-sm font-semibold text-slate-300">
              🚨 "Nuisance" Alert Leaderboard (Flapping & Reopened)
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Alerts causing highest SRE fatigue. Needs threshold tuning or remediation fix.
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Alert Name</th>
                  <th>Cluster</th>
                  <th>Flapping Count</th>
                  <th>Reopen Count</th>
                  <th>Total Fatigue Score</th>
                </tr>
              </thead>
              <tbody>
                {flapping_alerts.map((row: any, i: number) => (
                  <tr key={i}>
                    <td className="font-medium text-slate-200">{row.alert_name}</td>
                    <td className="font-mono text-xs">{row.cluster}</td>
                    <td><span className="text-amber-400">{row.flapping_count}</span></td>
                    <td><span className="text-red-400">{row.reopen_count}</span></td>
                    <td>
                      <span className="font-bold text-slate-200 px-2 py-1 bg-surface-700 rounded">
                        {row.flapping_count + row.reopen_count}
                      </span>
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
