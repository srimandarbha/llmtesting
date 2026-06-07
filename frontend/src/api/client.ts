import axios from 'axios'

const API_BASE = '/api'

// Auth token (in production, pull from OIDC token store)
const getToken = () => localStorage.getItem('sre_token') || 'dev-api-key-change-in-prod'

export const apiClient = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
})

apiClient.interceptors.request.use((config) => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Types
export interface Incident {
  id: string
  correlation_id: string | null
  cluster: string
  namespace: string
  alert_name: string
  hostname: string | null
  status: string
  risk_tier: string | null
  llm_confidence: number | null
  llm_intent_json: Record<string, unknown> | null
  analysis_summary: string | null
  escalate_to: string | null
  awx_job_id: string | null
  created_at: string
  updated_at: string
  resolved_at: string | null
  timeline: TimelineEvent[]
  human_actions: HumanAction[]
  llm_decisions: LLMDecision[]
}

export interface TimelineEvent {
  id: number
  timestamp: string
  actor_type: 'agent' | 'human' | 'system'
  actor_id: string | null
  action: string
  from_status: string | null
  to_status: string | null
  notes: string | null
  metadata_json: Record<string, unknown> | null
}

export interface HumanAction {
  id: number
  user_id: string
  action: string
  original_intent_json: Record<string, unknown> | null
  final_intent_json: Record<string, unknown> | null
  reason: string
  timestamp: string
}

export interface LLMDecision {
  id: number
  prompt_used: string | null
  raw_llm_output: string | null
  parsed_intent: Record<string, unknown> | null
  confidence: number | null
  tool_calls_json: Record<string, unknown> | null
  timestamp: string
}

export interface DashboardCounts {
  active: number
  pending_approval: number
  resolved_today: number
  failed: number
}

export interface FlappingAlert {
  alert_name: string
  cluster: string
  flapping_count: number
  reopen_count: number
}

export interface SentimentTrend {
  date: string
  average_score: number
  total_resolutions: number
}

export interface RedHatCaseSummary {
  open_cases: number
  critical_escalation_pct: number
  avg_vendor_mttr_days: number
}

export interface ComponentIncident {
  component: string
  incident_count: number
}

export interface FleetRisk {
  average_risk_pct: number
  critical_cves_active: number
}

export interface EnvironmentDistribution {
  environment: string
  incident_count: number
}

export interface AnalyticsSummary {
  mttr_by_cluster: any[]
  resolution_stats: any
  llm_accuracy: any
  top_recurring_alerts: any[]
  flapping_alerts: FlappingAlert[]
  sentiment_trend: SentimentTrend[]
  redhat_cases_summary: RedHatCaseSummary
  component_incidents: ComponentIncident[]
  fleet_risk: FleetRisk
  environment_distribution: EnvironmentDistribution[]
}

// API calls
export const api = {
  getDashboardCounts: () =>
    apiClient.get<DashboardCounts>('/dashboard/counts').then(r => r.data),

  getIncidents: (params?: { status?: string; cluster?: string; alert_name?: string; page?: number }) =>
    apiClient.get('/incidents', { params }).then(r => r.data),

  getIncident: (id: string) =>
    apiClient.get<Incident>(`/incidents/${id}`).then(r => r.data),

  approve: (id: string, reason: string, user_id: string) =>
    apiClient.post(`/incidents/${id}/approve`, { reason, user_id }).then(r => r.data),

  reject: (id: string, reason: string, user_id: string) =>
    apiClient.post(`/incidents/${id}/reject`, { reason, user_id }).then(r => r.data),

  editAndApprove: (id: string, modified_intent: object, reason: string, user_id: string) =>
    apiClient.post(`/incidents/${id}/edit`, { modified_intent, reason, user_id }).then(r => r.data),

  escalate: (id: string, reason: string, user_id: string) =>
    apiClient.post(`/incidents/${id}/escalate`, { reason, user_id }).then(r => r.data),

  getAnalytics: () =>
    apiClient.get<AnalyticsSummary>('/analytics/summary').then(r => r.data),

  ingestAlert: (payload: Record<string, string>) =>
    apiClient.post('/alerts/ingest', payload).then(r => r.data),

  getHandovers: (params?: {
    cluster?: string
    handover_type?: string
    priority?: string
    action_required?: boolean
    limit?: number
  }) =>
    apiClient.get<Handover[]>('/handovers', { params }).then(r => r.data),

  getHandoverClusters: () =>
    apiClient.get<string[]>('/handovers/clusters').then(r => r.data),

  createHandover: (payload: {
    author: string
    shift_identifier: string
    cluster: string
    handover_type: string
    priority: string
    action_required: boolean
    related_incidents: string
    message: string
    start_time?: string | null
    end_time?: string | null
    upgraded_version?: string | null
    operator_name?: string | null
  }) =>
    apiClient.post<Handover>('/handovers', payload).then(r => r.data),

  getTickerHandovers: () =>
    apiClient.get<Handover[]>('/handovers/active_ticker').then(r => r.data),

  updateHandover: (id: string, payload: {
    is_active?: boolean
    resolution_notes?: string
    action_required?: boolean
  }) =>
    apiClient.patch<Handover>(`/handovers/${id}`, payload).then(r => r.data),

  chatWithContext: (payload: { query: string; timeframe_hours: number }) =>
    apiClient.post<{ answer: string }>('/chat', payload).then(r => r.data),

  previewSummary: () =>
    apiClient.post<{ shift_name: string; preview_text: string }>('/summaries/preview').then(r => r.data),

  saveSummary: (payload: { shift_name: string; summary_text: string }) =>
    apiClient.post<{ status: string; id: string }>('/summaries/save', payload).then(r => r.data),

  getHistoricalSummaries: () =>
    apiClient.get<HistoricalSummary[]>('/summaries/historical').then(r => r.data),
}

export interface HistoricalSummary {
  id: string
  shift_name: string
  summary_text: string
  is_auto_generated: boolean
  created_at: string
}

export interface Handover {
  id: string
  author: string
  shift_identifier: string
  cluster: string
  handover_type: HandoverType
  priority: HandoverPriority
  action_required: boolean
  related_incidents: string
  message: string
  created_at: string
  start_time: string | null
  end_time: string | null
  is_active: boolean
  resolution_notes: string | null
  upgraded_version: string | null
  operator_name: string | null
}

export type HandoverType =
  | 'handover'
  | 'maintenance'
  | 'upgrade'
  | 'operator_upgrade'
  | 'incident_followup'
  | 'change_freeze'
  | 'escalation'

export type HandoverPriority = 'low' | 'medium' | 'high' | 'critical'

