import React, { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { Incident } from '../api/client'

interface ApprovalCardProps {
  incident: Incident
  currentUserId?: string
}

export const ApprovalCard: React.FC<ApprovalCardProps> = ({
  incident,
  currentUserId = 'dev-user',
}) => {
  const [reason, setReason] = useState('')
  const [editMode, setEditMode] = useState(false)
  const [editedIntent, setEditedIntent] = useState(
    JSON.stringify(incident.llm_intent_json, null, 2)
  )
  const [intentError, setIntentError] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const onSuccess = () => {
    queryClient.invalidateQueries({ queryKey: ['incident', incident.id] })
    queryClient.invalidateQueries({ queryKey: ['incidents'] })
  }

  const approveMutation = useMutation({
    mutationFn: () => api.approve(incident.id, reason, currentUserId),
    onSuccess,
  })

  const rejectMutation = useMutation({
    mutationFn: () => api.reject(incident.id, reason, currentUserId),
    onSuccess,
  })

  const editMutation = useMutation({
    mutationFn: () => {
      let parsed
      try {
        parsed = JSON.parse(editedIntent)
        setIntentError(null)
      } catch (e) {
        setIntentError('Invalid JSON — please fix before submitting')
        throw e
      }
      return api.editAndApprove(incident.id, parsed, reason, currentUserId)
    },
    onSuccess,
  })

  const escalateMutation = useMutation({
    mutationFn: () => api.escalate(incident.id, reason, currentUserId),
    onSuccess,
  })

  const isLoading =
    approveMutation.isPending ||
    rejectMutation.isPending ||
    editMutation.isPending ||
    escalateMutation.isPending

  const reasonValid = reason.trim().length >= 5

  return (
    <div className="glass-card border-orange-500/30 bg-orange-900/10 p-6 animate-pulse-pending animate-slide-in">
      {/* Header */}
      <div className="flex items-center gap-3 mb-5">
        <div className="w-10 h-10 rounded-full bg-orange-900/60 border border-orange-600/40
                        flex items-center justify-center text-lg">
          🔐
        </div>
        <div>
          <h3 className="font-semibold text-orange-300 text-base">Human Approval Required</h3>
          <p className="text-xs text-slate-400 mt-0.5">
            This action is classified as HIGH risk. Review carefully before approving.
          </p>
        </div>
      </div>

      {/* Proposed action summary */}
      <div className="bg-surface-700/60 rounded-xl p-4 mb-5 border border-white/5">
        <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
          Proposed Action
        </h4>
        {incident.llm_intent_json ? (
          <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
            <div>
              <span className="text-slate-500">Action</span>
              <p className="text-slate-100 font-semibold font-mono mt-0.5">
                {String(incident.llm_intent_json.action ?? '—')}
              </p>
            </div>
            <div>
              <span className="text-slate-500">Target</span>
              <p className="text-slate-100 font-semibold font-mono mt-0.5">
                {String(incident.llm_intent_json.target ?? '—')}
              </p>
            </div>
            <div>
              <span className="text-slate-500">Namespace</span>
              <p className="text-slate-100 font-mono mt-0.5">
                {String(incident.llm_intent_json.namespace ?? '—')}
              </p>
            </div>
            <div>
              <span className="text-slate-500">Confidence</span>
              <p className="text-slate-100 font-mono mt-0.5">
                {incident.llm_confidence !== null
                  ? `${Math.round((incident.llm_confidence ?? 0) * 100)}%`
                  : '—'}
              </p>
            </div>
            <div className="col-span-2">
              <span className="text-slate-500">Reason</span>
              <p className="text-slate-300 mt-0.5 italic">
                "{String(incident.llm_intent_json.reason ?? '—')}"
              </p>
            </div>
          </div>
        ) : (
          <p className="text-slate-400 text-sm">No intent data available.</p>
        )}
      </div>

      {/* Edit intent toggle */}
      <div className="mb-5">
        <button
          onClick={() => setEditMode(!editMode)}
          className="text-xs text-brand-400 hover:text-brand-300 transition-colors flex items-center gap-1.5"
        >
          <span>{editMode ? '▾' : '▸'}</span>
          {editMode ? 'Hide JSON editor' : 'Edit intent before approving'}
        </button>

        {editMode && (
          <div className="mt-3 animate-slide-in">
            <textarea
              className="input font-mono text-xs resize-none h-40"
              value={editedIntent}
              onChange={(e) => {
                setEditedIntent(e.target.value)
                setIntentError(null)
              }}
              spellCheck={false}
            />
            {intentError && (
              <p className="text-red-400 text-xs mt-1">⚠ {intentError}</p>
            )}
          </div>
        )}
      </div>

      {/* Reason field — REQUIRED */}
      <div className="mb-5">
        <label className="block text-xs font-semibold text-slate-400 mb-1.5">
          Reason <span className="text-red-400">*</span>
          <span className="text-slate-500 font-normal ml-1">(required, min 5 chars)</span>
        </label>
        <textarea
          className="input resize-none h-20 text-sm"
          placeholder='e.g. "Confirmed pod crash in CrashLoopBackOff — restart is safe"'
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
      </div>

      {/* Action buttons */}
      <div className="flex flex-wrap gap-3">
        {!editMode ? (
          <button
            className="btn-success flex-1"
            disabled={!reasonValid || isLoading}
            onClick={() => approveMutation.mutate()}
          >
            {approveMutation.isPending ? '⏳ Approving...' : '✓ Approve'}
          </button>
        ) : (
          <button
            className="btn-success flex-1"
            disabled={!reasonValid || isLoading}
            onClick={() => editMutation.mutate()}
          >
            {editMutation.isPending ? '⏳ Saving...' : '✓ Save & Approve'}
          </button>
        )}

        <button
          className="btn-danger"
          disabled={!reasonValid || isLoading}
          onClick={() => rejectMutation.mutate()}
        >
          {rejectMutation.isPending ? '⏳...' : '✗ Reject'}
        </button>

        <button
          className="btn-warning"
          disabled={!reasonValid || isLoading}
          onClick={() => escalateMutation.mutate()}
        >
          {escalateMutation.isPending ? '⏳...' : '⚡ Escalate to Oncall'}
        </button>
      </div>

      {/* Error display */}
      {(approveMutation.isError || rejectMutation.isError || editMutation.isError) && (
        <div className="mt-3 p-3 bg-red-900/30 border border-red-700/50 rounded-lg text-red-300 text-xs">
          ⚠ Action failed. Check the console and try again.
        </div>
      )}
    </div>
  )
}
