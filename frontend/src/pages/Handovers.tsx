import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { formatDistanceToNow, format } from 'date-fns'
import { api, Handover, HandoverType, HandoverPriority } from '../api/client'
import { useAuth } from '../hooks/useAuth'

// ---------------------------------------------------------------------------
// Static config
// ---------------------------------------------------------------------------

const HANDOVER_TYPES: { value: HandoverType; label: string; icon: string; color: string }[] = [
  { value: 'handover',         label: 'Shift Handover',     icon: '🤝', color: 'text-brand-400 bg-brand-500/15 border-brand-500/30' },
  { value: 'maintenance',      label: 'Maintenance',         icon: '🔧', color: 'text-amber-400 bg-amber-500/15 border-amber-500/30' },
  { value: 'upgrade',          label: 'Platform Upgrade',    icon: '⬆️', color: 'text-sky-400 bg-sky-500/15 border-sky-500/30' },
  { value: 'operator_upgrade', label: 'Operator Upgrade',    icon: '⚙️', color: 'text-violet-400 bg-violet-500/15 border-violet-500/30' },
  { value: 'incident_followup',label: 'Incident Follow-up',  icon: '🔴', color: 'text-rose-400 bg-rose-500/15 border-rose-500/30' },
  { value: 'change_freeze',    label: 'Change Freeze',       icon: '❄️', color: 'text-cyan-400 bg-cyan-500/15 border-cyan-500/30' },
  { value: 'escalation',       label: 'Escalation',          icon: '🚨', color: 'text-orange-400 bg-orange-500/15 border-orange-500/30' },
]

const PRIORITIES: { value: HandoverPriority; label: string; dot: string }[] = [
  { value: 'low',      label: 'Low',      dot: 'bg-slate-400' },
  { value: 'medium',   label: 'Medium',   dot: 'bg-amber-400' },
  { value: 'high',     label: 'High',     dot: 'bg-orange-500' },
  { value: 'critical', label: 'Critical', dot: 'bg-rose-500' },
]

const typeInfo = (t: HandoverType) =>
  HANDOVER_TYPES.find(x => x.value === t) ?? HANDOVER_TYPES[0]

const priorityInfo = (p: HandoverPriority) =>
  PRIORITIES.find(x => x.value === p) ?? PRIORITIES[1]

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function TypeBadge({ type }: { type: HandoverType }) {
  const t = typeInfo(type)
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${t.color}`}>
      <span className="no-invert">{t.icon}</span>
      {t.label}
    </span>
  )
}

function PriorityDot({ priority }: { priority: HandoverPriority }) {
  const p = priorityInfo(priority)
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-slate-400">
      <span className={`w-2 h-2 rounded-full ${p.dot}`} />
      {p.label}
    </span>
  )
}

function ActionBadge({ required }: { required: boolean }) {
  if (!required) return null
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold bg-rose-500/20 text-rose-400 border border-rose-500/40 animate-pulse">
      ⚡ Action Required
    </span>
  )
}

// ---------------------------------------------------------------------------
// Handover Card
// ---------------------------------------------------------------------------

function HandoverCard({ ho }: { ho: Handover }) {
  const queryClient = useQueryClient()
  const [isResolving, setIsResolving] = useState(false)
  const [notes, setNotes] = useState('')

  const updateMutation = useMutation({
    mutationFn: (updates: { is_active?: boolean, resolution_notes?: string, action_required?: boolean }) => 
      api.updateHandover(ho.id, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['handovers'] })
      queryClient.invalidateQueries({ queryKey: ['activeTicker'] })
      setIsResolving(false)
    }
  })

  const borderColor =
    ho.priority === 'critical' ? 'border-l-rose-500' :
    ho.priority === 'high'     ? 'border-l-orange-500' :
    ho.priority === 'medium'   ? 'border-l-amber-500' :
                                  'border-l-slate-600'

  return (
    <div className={`glass-card p-5 border-l-4 ${borderColor} transition-all hover:scale-[1.005]`}>
      {/* Header row */}
      <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-bold text-white text-sm">{ho.shift_identifier || ho.author}</span>
            {ho.cluster && ho.cluster !== 'ALL' && (
              <span className="px-2 py-0.5 rounded-md bg-surface-700 border border-white/10 text-xs text-slate-300 font-mono">
                {ho.cluster}
              </span>
            )}
            {ho.cluster === 'ALL' && (
              <span className="px-2 py-0.5 rounded-md bg-brand-500/10 border border-brand-500/20 text-xs text-brand-400 font-mono">
                ALL CLUSTERS
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 flex-wrap mt-0.5">
            <TypeBadge type={ho.handover_type} />
            <PriorityDot priority={ho.priority} />
            <ActionBadge required={ho.action_required} />
          </div>
        </div>
        <div className="text-xs text-slate-500 shrink-0" title={format(new Date(ho.created_at), 'PPPppp')}>
          {formatDistanceToNow(new Date(ho.created_at), { addSuffix: true })}
        </div>
      </div>

      {/* Message */}
      <div className="text-slate-300 text-sm whitespace-pre-wrap leading-relaxed mb-3">
        {ho.message}
      </div>

      {/* Upgrade Details */}
      {(ho.upgraded_version || ho.operator_name) && (
        <div className="flex items-center gap-4 text-xs text-slate-300 bg-sky-900/20 p-3 rounded-lg mb-3 border border-sky-500/20">
          {ho.handover_type === 'upgrade' && (
            <div><span className="text-sky-400 font-semibold mr-2">Target Version:</span>{ho.upgraded_version}</div>
          )}
          {ho.handover_type === 'operator_upgrade' && (
            <div className="flex gap-4">
              <div><span className="text-violet-400 font-semibold mr-2">Operator:</span>{ho.operator_name}</div>
              <div><span className="text-violet-400 font-semibold mr-2">Version:</span>{ho.upgraded_version}</div>
            </div>
          )}
        </div>
      )}

      {/* Start/End Time for Maintenance */}
      {ho.handover_type === 'maintenance' && (ho.start_time || ho.end_time) && (
        <div className="flex items-center gap-4 text-xs text-slate-400 bg-black/20 p-2 rounded mb-3 font-mono">
          {ho.start_time && <div>Start: {format(new Date(ho.start_time), 'PPp')}</div>}
          {ho.end_time && <div>End: {format(new Date(ho.end_time), 'PPp')}</div>}
        </div>
      )}

      {/* Action / Maintenance Controls */}
      {(ho.action_required || ho.handover_type === 'maintenance' || ho.resolution_notes) && (
        <div className="mt-3 p-3 bg-surface-700/50 rounded-lg border border-white/5">
          {ho.handover_type === 'maintenance' && (
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400">Maintenance Window Status</span>
              <button 
                className={`btn text-xs py-1 px-3 ${ho.is_active ? 'btn-danger' : 'btn-success'}`}
                onClick={() => updateMutation.mutate({ is_active: !ho.is_active })}
                disabled={updateMutation.isPending}
              >
                {ho.is_active ? 'Disable Window' : 'Enable Window'}
              </button>
            </div>
          )}

          {ho.action_required && !isResolving && (
            <div className="flex items-center justify-between">
              <span className="text-xs text-rose-400 font-semibold">Action pending from next shift</span>
              <button 
                className="btn btn-primary text-xs py-1 px-3"
                onClick={() => setIsResolving(true)}
              >
                Resolve Action
              </button>
            </div>
          )}

          {isResolving && (
            <div className="space-y-2">
              <label className="text-xs text-slate-400">Resolution Notes (Required)</label>
              <textarea 
                className="input w-full min-h-[60px] text-xs"
                placeholder="What action was taken?"
                value={notes}
                onChange={e => setNotes(e.target.value)}
              />
              <div className="flex justify-end gap-2">
                <button className="btn btn-ghost text-xs py-1" onClick={() => setIsResolving(false)}>Cancel</button>
                <button 
                  className="btn btn-success text-xs py-1" 
                  disabled={!notes.trim() || updateMutation.isPending}
                  onClick={() => updateMutation.mutate({ action_required: false, is_active: false, resolution_notes: notes })}
                >
                  Submit Resolution
                </button>
              </div>
            </div>
          )}

          {ho.resolution_notes && !ho.action_required && (
            <div className="mt-2">
              <span className="text-xs text-emerald-400 font-semibold mb-1 block">✓ Action Resolved</span>
              <p className="text-xs text-slate-300 bg-black/20 p-2 rounded border-l-2 border-emerald-500">
                {ho.resolution_notes}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Related incidents */}
      {ho.related_incidents && (
        <div className="flex items-center gap-2 flex-wrap mt-2 pt-2 border-t border-white/5">
          <span className="text-xs text-slate-500 uppercase tracking-wide">Related:</span>
          {ho.related_incidents.split(',').map(id => id.trim()).filter(Boolean).map(id => (
            <span key={id} className="px-2 py-0.5 rounded bg-surface-700 border border-white/10 text-xs font-mono text-slate-400">
              {id}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// User Identity Modal (for the localStorage stub)
// ---------------------------------------------------------------------------

function IdentityModal({ onClose }: { onClose: () => void }) {
  const { user, updateUser } = useAuth()
  const [name, setName]   = useState(user.displayName)
  const [shift, setShift] = useState(user.shift ?? '')
  const [role, setRole]   = useState(user.role)

  const save = () => {
    updateUser({ displayName: name, shift, role })
    onClose()
  }

  return (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-surface-800 border border-white/10 rounded-2xl p-6 w-96 shadow-2xl animate-fade-in"
        onClick={e => e.stopPropagation()}
      >
        <h3 className="text-base font-bold text-white mb-1">Your Shift Identity</h3>
        <p className="text-xs text-slate-500 mb-5">
          Used as the Shift Identifier on new handover notes.{' '}
          <span className="text-brand-400">SSO will auto-populate this when integrated.</span>
        </p>
        <div className="space-y-3">
          <div>
            <label className="block text-xs uppercase tracking-wider text-slate-500 mb-1">Full Name</label>
            <input id="identity-name" className="input w-full" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Jane Smith" />
          </div>
          <div>
            <label className="block text-xs uppercase tracking-wider text-slate-500 mb-1">Shift</label>
            <input id="identity-shift" className="input w-full" value={shift} onChange={e => setShift(e.target.value)} placeholder="e.g. Morning, Night, APAC" />
          </div>
          <div>
            <label className="block text-xs uppercase tracking-wider text-slate-500 mb-1">Role</label>
            <select id="identity-role" className="input w-full" value={role} onChange={e => setRole(e.target.value)}>
              <option value="SRE">SRE</option>
              <option value="SRE Lead">SRE Lead</option>
              <option value="On-Call">On-Call</option>
              <option value="Platform Eng">Platform Eng</option>
            </select>
          </div>
        </div>
        <div className="mt-6 flex justify-end gap-3">
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button id="identity-save" className="btn btn-primary" onClick={save}>Save Identity</button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

type FilterState = {
  cluster:       string
  handover_type: string
  priority:      string
}

export const Handovers: React.FC = () => {
  const { user, shiftIdentifier, isAuthenticated } = useAuth()
  const queryClient = useQueryClient()

  // Form state
  const [shiftId,          setShiftId]          = useState(shiftIdentifier)
  const [cluster,          setCluster]          = useState('ALL')
  const [handoverType,     setHandoverType]     = useState<HandoverType>('handover')
  const [priority,         setPriority]         = useState<HandoverPriority>('medium')
  const [actionRequired,   setActionRequired]   = useState(false)
  const [relatedIncidents, setRelatedIncidents] = useState('')
  const [message,          setMessage]          = useState('')
  const [startTime,        setStartTime]        = useState('')
  const [endTime,          setEndTime]          = useState('')
  const [upgradedVersion,  setUpgradedVersion]  = useState('')
  const [operatorName,     setOperatorName]     = useState('')
  const [showIdentity,     setShowIdentity]     = useState(false)
  const [filters,          setFilters]          = useState<FilterState>({
    cluster: '', handover_type: '', priority: '',
  })

  // Sync shift identifier when user changes via identity modal
  React.useEffect(() => {
    if (shiftIdentifier) setShiftId(shiftIdentifier)
  }, [shiftIdentifier])

  // Fetch available clusters
  const { data: availableClusters } = useQuery({
    queryKey: ['handoverClusters'],
    queryFn: api.getHandoverClusters,
    staleTime: 60_000,
  })

  // Query with filters
  const filterParams = Object.fromEntries(
    Object.entries(filters).filter(([, v]) => v !== '')
  )

  const { data: handovers, isLoading } = useQuery({
    queryKey: ['handovers', filterParams],
    queryFn:  () => api.getHandovers(filterParams),
    refetchInterval: 15_000,
  })

  const mutation = useMutation({
    mutationFn: api.createHandover,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['handovers'] })
      queryClient.invalidateQueries({ queryKey: ['activeTicker'] })
      setMessage('')
      setRelatedIncidents('')
      setActionRequired(false)
      setStartTime('')
      setEndTime('')
      setUpgradedVersion('')
      setOperatorName('')
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const authorName = user.displayName || shiftId || 'Anonymous'
    if (!shiftId.trim() || !message.trim()) return
    mutation.mutate({
      author:            authorName,
      shift_identifier:  shiftId.trim(),
      cluster:           cluster || 'ALL',
      handover_type:     handoverType,
      priority,
      action_required:   actionRequired,
      related_incidents: relatedIncidents.trim(),
      message:           message.trim(),
      start_time:        startTime ? new Date(startTime).toISOString() : null,
      end_time:          endTime ? new Date(endTime).toISOString() : null,
      upgraded_version:  upgradedVersion.trim() || null,
      operator_name:     operatorName.trim() || null,
    })
  }

  const setFilter = (key: keyof FilterState, val: string) =>
    setFilters(prev => ({ ...prev, [key]: val }))

  const activeFiltersCount = Object.values(filters).filter(Boolean).length

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-fade-in">

      {/* Page header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">
            Shift <span className="text-gradient">Handovers</span>
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Structured notes to pass critical information between SRE shifts.
          </p>
        </div>
        <button
          id="identity-btn"
          onClick={() => setShowIdentity(true)}
          className="flex items-center gap-2 px-3 py-2 rounded-xl bg-surface-700 border border-white/10 hover:border-brand-500/40 transition-all text-sm"
          title="Set your identity"
        >
          <span className="w-7 h-7 rounded-full bg-brand-500/20 border border-brand-500/40 flex items-center justify-center text-brand-400 text-xs font-bold">
            {(user.displayName || '?')[0]?.toUpperCase()}
          </span>
          <div className="text-left hidden sm:block">
            <p className="text-xs font-semibold text-slate-200 leading-none">
              {user.displayName || 'Set Identity'}
            </p>
            {user.shift && (
              <p className="text-[10px] text-slate-500 leading-none mt-0.5">{user.shift} Shift · {user.role}</p>
            )}
          </div>
          <span className="text-slate-500 text-xs no-invert">✏️</span>
        </button>
      </div>

      {/* Identity not set warning */}
      {!isAuthenticated && (
        <div
          className="flex items-center gap-3 p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400 text-sm cursor-pointer hover:bg-amber-500/15 transition-colors"
          onClick={() => setShowIdentity(true)}
        >
          <span className="text-xl no-invert">👤</span>
          <span>Set your identity so your name appears on handover notes. <strong>Click to configure →</strong></span>
        </div>
      )}

      {/* Compose Form */}
      <div className="glass-card p-6">
        <h2 className="text-sm font-semibold text-slate-300 mb-5 uppercase tracking-wider">
          New Handover Note
        </h2>
        <form onSubmit={handleSubmit} className="space-y-5">

          {/* Row 1: Shift Identifier + Cluster */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5" htmlFor="ho-shift-id">
                Shift Identifier <span className="text-rose-400">*</span>
              </label>
              <input
                id="ho-shift-id"
                type="text"
                className="input w-full"
                placeholder="e.g. Jane Smith · Morning Shift"
                value={shiftId}
                onChange={e => setShiftId(e.target.value)}
              />
              <p className="text-[10px] text-slate-600 mt-1">Auto-filled from your identity. Edit as needed.</p>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5" htmlFor="ho-cluster">
                Cluster
              </label>
              <select
                id="ho-cluster"
                className="input w-full font-mono"
                value={cluster}
                onChange={e => setCluster(e.target.value)}
              >
                <option value="ALL">ALL</option>
                {availableClusters?.map(c => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Row 2: Type + Priority */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5" htmlFor="ho-type">
                Handover Type
              </label>
              <select
                id="ho-type"
                className="input w-full"
                value={handoverType}
                onChange={e => setHandoverType(e.target.value as HandoverType)}
              >
                {HANDOVER_TYPES.map(t => (
                  <option key={t.value} value={t.value}>{t.icon} {t.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5">
                Priority
              </label>
              <div className="flex gap-2">
                {PRIORITIES.map(p => (
                  <button
                    key={p.value}
                    type="button"
                    id={`ho-priority-${p.value}`}
                    onClick={() => setPriority(p.value)}
                    className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg border text-xs font-medium transition-all ${
                      priority === p.value
                        ? `${p.dot.replace('bg-', 'border-').replace('-500', '-500').replace('-400', '-400')} bg-white/10 text-white border-opacity-60`
                        : 'border-white/10 text-slate-500 hover:text-slate-300 hover:border-white/20'
                    }`}
                  >
                    <span className={`w-2 h-2 rounded-full ${p.dot}`} />
                    {p.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Optional: Start/End Times for Maintenance */}
          {handoverType === 'maintenance' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-amber-500/5 p-4 rounded-xl border border-amber-500/20">
              <div>
                <label className="block text-xs font-medium text-amber-400/80 mb-1.5">Start Time (Optional)</label>
                <input 
                  type="datetime-local" 
                  className="input w-full text-sm" 
                  value={startTime}
                  onChange={e => setStartTime(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-amber-400/80 mb-1.5">End Time (Optional)</label>
                <input 
                  type="datetime-local" 
                  className="input w-full text-sm" 
                  value={endTime}
                  onChange={e => setEndTime(e.target.value)}
                />
              </div>
            </div>
          )}

          {/* Upgrade Specific Fields */}
          {handoverType === 'upgrade' && (
            <div className="grid grid-cols-1 gap-4 bg-sky-500/5 p-4 rounded-xl border border-sky-500/20">
              <div>
                <label className="block text-xs font-medium text-sky-400/80 mb-1.5">Version Upgraded To <span className="text-rose-400">*</span></label>
                <input 
                  type="text" 
                  className="input w-full" 
                  placeholder="e.g. 4.13.1"
                  value={upgradedVersion}
                  onChange={e => setUpgradedVersion(e.target.value)}
                />
              </div>
            </div>
          )}
          
          {handoverType === 'operator_upgrade' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-violet-500/5 p-4 rounded-xl border border-violet-500/20">
              <div>
                <label className="block text-xs font-medium text-violet-400/80 mb-1.5">Operator Name <span className="text-rose-400">*</span></label>
                <input 
                  type="text" 
                  className="input w-full" 
                  placeholder="e.g. OpenShift GitOps"
                  value={operatorName}
                  onChange={e => setOperatorName(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-violet-400/80 mb-1.5">Operator Version <span className="text-rose-400">*</span></label>
                <input 
                  type="text" 
                  className="input w-full" 
                  placeholder="e.g. 1.10.1"
                  value={upgradedVersion}
                  onChange={e => setUpgradedVersion(e.target.value)}
                />
              </div>
            </div>
          )}

          {/* Row 3: Related Incidents + Action Required */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5" htmlFor="ho-related">
                Related Alerts/Incidents
              </label>
              <input
                id="ho-related"
                type="text"
                className="input w-full font-mono"
                placeholder="ALERT0012345/INC0012345"
                value={relatedIncidents}
                onChange={e => setRelatedIncidents(e.target.value)}
              />
              <p className="text-[10px] text-slate-600 mt-1">Comma-separated alert/incident IDs</p>
            </div>
            <div className="flex flex-col justify-end">
              <label className="block text-xs font-medium text-slate-400 mb-1.5">
                Action Required
              </label>
              <button
                type="button"
                id="ho-action-toggle"
                onClick={() => setActionRequired(v => !v)}
                className={`flex items-center gap-3 p-3 rounded-xl border transition-all w-full ${
                  actionRequired
                    ? 'bg-rose-500/15 border-rose-500/50 text-rose-400'
                    : 'bg-surface-700 border-white/10 text-slate-500 hover:border-white/20'
                }`}
              >
                <div className={`w-10 h-6 rounded-full transition-all relative ${actionRequired ? 'bg-rose-500' : 'bg-slate-600'}`}>
                  <div className={`absolute top-1 w-4 h-4 rounded-full bg-white shadow transition-all ${actionRequired ? 'left-5' : 'left-1'}`} />
                </div>
                <span className="text-sm font-medium">
                  {actionRequired ? '⚡ Next shift must act' : 'No action needed'}
                </span>
              </button>
            </div>
          </div>

          {/* Message */}
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1.5" htmlFor="ho-message">
              Message <span className="text-rose-400">*</span>
            </label>
            <textarea
              id="ho-message"
              className="input w-full min-h-[120px] resize-y"
              placeholder="Describe ongoing issues, tasks for next shift, relevant observations, or context..."
              value={message}
              onChange={e => setMessage(e.target.value)}
            />
          </div>

          {/* Submit */}
          <div className="flex items-center justify-between pt-1">
            {mutation.isError && (
              <p className="text-xs text-rose-400">Failed to post. Please try again.</p>
            )}
            <div className="ml-auto">
              <button
                id="ho-submit"
                type="submit"
                className="btn btn-primary"
                disabled={
                  mutation.isPending || 
                  !shiftId.trim() || 
                  !message.trim() ||
                  (handoverType === 'upgrade' && !upgradedVersion.trim()) ||
                  (handoverType === 'operator_upgrade' && (!operatorName.trim() || !upgradedVersion.trim()))
                }
              >
                {mutation.isPending ? (
                  <span className="flex items-center gap-2">
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Posting...
                  </span>
                ) : 'Post Handover Note'}
              </button>
            </div>
          </div>
        </form>
      </div>

      {/* Filter Bar */}
      <div className="glass-card p-4">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider mr-1">Filter:</span>

          {/* Type filter */}
          <select
            id="filter-type"
            className="input py-1.5 text-xs"
            value={filters.handover_type}
            onChange={e => setFilter('handover_type', e.target.value)}
          >
            <option value="">All Types</option>
            {HANDOVER_TYPES.map(t => (
              <option key={t.value} value={t.value}>{t.icon} {t.label}</option>
            ))}
          </select>

          {/* Priority filter */}
          <select
            id="filter-priority"
            className="input py-1.5 text-xs"
            value={filters.priority}
            onChange={e => setFilter('priority', e.target.value)}
          >
            <option value="">All Priorities</option>
            {PRIORITIES.map(p => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>

          {/* Cluster filter */}
          <select
            id="filter-cluster"
            className="input py-1.5 text-xs font-mono w-36"
            value={filters.cluster}
            onChange={e => setFilter('cluster', e.target.value)}
          >
            <option value="">All Clusters</option>
            <option value="ALL">ALL</option>
            {availableClusters?.map(c => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>

          {activeFiltersCount > 0 && (
            <button
              id="filter-clear"
              className="text-xs text-brand-400 hover:text-brand-300 transition-colors"
              onClick={() => setFilters({ cluster: '', handover_type: '', priority: '' })}
            >
              ✕ Clear ({activeFiltersCount})
            </button>
          )}
        </div>
      </div>

      {/* Feed */}
      <div className="space-y-4">
        <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
          Recent Handovers
          {activeFiltersCount > 0 && (
            <span className="ml-2 px-2 py-0.5 rounded-full bg-brand-500/20 text-brand-400 text-xs normal-case">
              filtered
            </span>
          )}
        </h2>

        {isLoading ? (
          <div className="flex items-center justify-center py-12 text-slate-400">
            <div className="w-6 h-6 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mr-3" />
            Loading handovers...
          </div>
        ) : handovers?.length === 0 ? (
          <div className="glass-card p-10 text-center text-slate-500">
            <p className="text-3xl mb-3">🤝</p>
            <p>No handover notes found{activeFiltersCount > 0 ? ' matching these filters' : ''}.</p>
          </div>
        ) : (
          handovers?.map((ho: Handover) => (
            <HandoverCard key={ho.id} ho={ho} />
          ))
        )}
      </div>

      {/* Identity Modal */}
      {showIdentity && <IdentityModal onClose={() => setShowIdentity(false)} />}
    </div>
  )
}
