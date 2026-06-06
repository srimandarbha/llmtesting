import React from 'react'

const STATUS_CONFIG: Record<string, { label: string; className: string; dot?: string }> = {
  RECEIVED:         { label: 'Received',         className: 'badge-received',  dot: 'bg-slate-400' },
  ANALYZING:        { label: 'Analyzing',        className: 'badge-analyzing', dot: 'bg-blue-400' },
  PENDING_APPROVAL: { label: 'Pending Approval', className: 'badge-pending',   dot: 'bg-orange-400' },
  EXECUTING:        { label: 'Executing',        className: 'badge-executing', dot: 'bg-violet-400' },
  VERIFYING:        { label: 'Verifying',        className: 'badge-verifying', dot: 'bg-cyan-400' },
  RESOLVED:         { label: 'Resolved',         className: 'badge-resolved',  dot: 'bg-emerald-400' },
  REJECTED:         { label: 'Rejected',         className: 'badge-rejected',  dot: 'bg-rose-400' },
  ESCALATED:        { label: 'Escalated',        className: 'badge-escalated', dot: 'bg-amber-400' },
  FAILED:           { label: 'Failed',           className: 'badge-failed',    dot: 'bg-red-400' },
}

const RISK_CONFIG: Record<string, { label: string; className: string }> = {
  LOW:     { label: 'LOW',     className: 'risk-low' },
  HIGH:    { label: 'HIGH',   className: 'risk-high' },
  ESCALATE:{ label: 'ESCALATE',className: 'risk-escalate' },
}

interface StatusBadgeProps {
  status: string
  animated?: boolean
  size?: 'sm' | 'md'
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, animated = false, size = 'md' }) => {
  const config = STATUS_CONFIG[status] || { label: status, className: 'badge-received', dot: 'bg-slate-400' }

  return (
    <span
      className={`badge ${config.className} ${size === 'sm' ? 'text-xs' : ''} ${
        animated && status === 'PENDING_APPROVAL' ? 'animate-pulse-pending' : ''
      }`}
    >
      {config.dot && (
        <span
          className={`w-1.5 h-1.5 rounded-full ${config.dot} ${
            ['ANALYZING', 'EXECUTING', 'VERIFYING'].includes(status) ? 'animate-pulse' : ''
          }`}
        />
      )}
      {config.label}
    </span>
  )
}

interface RiskBadgeProps {
  tier: string | null
}

export const RiskBadge: React.FC<RiskBadgeProps> = ({ tier }) => {
  if (!tier) return null
  const config = RISK_CONFIG[tier] || { label: tier, className: 'badge bg-slate-700 text-slate-300' }
  return <span className={config.className}>{config.label}</span>
}

interface ConfidenceBadgeProps {
  confidence: number | null
}

export const ConfidenceBadge: React.FC<ConfidenceBadgeProps> = ({ confidence }) => {
  if (confidence === null) return null
  const pct = Math.round(confidence * 100)
  const color = pct >= 85 ? 'text-emerald-400' : pct >= 70 ? 'text-amber-400' : 'text-red-400'
  return (
    <span className={`font-mono text-sm font-semibold ${color}`}>
      {pct}%
    </span>
  )
}
