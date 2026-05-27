import axios from 'axios'

const API_BASE = '/api'

// Auth token (in production, pull from OIDC token store)
const getToken = () => localStorage.getItem('sre_token') || ''

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

// API calls
export const api = {
  getDashboardCounts: () =>
    apiClient.get<DashboardCounts>('/dashboard/counts').then(r => r.data),

  getIncidents: (params?: { status?: string; cluster?: string; page?: number }) =>
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
    apiClient.get('/analytics/summary').then(r => r.data),

  ingestAlert: (payload: Record<string, string>) =>
    apiClient.post('/alerts/ingest', payload).then(r => r.data),
}
