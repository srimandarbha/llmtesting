"""
Pydantic schemas for FastAPI request/response models.

These are the ONLY contracts between the API layer and clients.
All human actions flow through these schemas — never raw JSON from LLM.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Alert Ingestion
# ---------------------------------------------------------------------------


class AlertIngestRequest(BaseModel):
    """Normalized alert payload from Kafka/webhook. Matches event.json schema."""

    cluster: str = Field(..., description="Cluster ID (e.g. nzclu101)")
    hostname: str
    correlation_id: str = Field(..., description="Unique correlation ID for deduplication")
    namespace: str
    alert_name: str = Field(..., alias="alertname")
    start_at: str | None = Field(None, alias="startAt")
    awx_template_id: str = Field(default="1", description="AWX job template ID to use for execution")

    model_config = {"populate_by_name": True}


class AlertIngestResponse(BaseModel):
    incident_id: uuid.UUID
    status: str
    message: str


# ---------------------------------------------------------------------------
# Incident (read)
# ---------------------------------------------------------------------------


class TimelineEventOut(BaseModel):
    id: int
    timestamp: datetime
    actor_type: str
    actor_id: str | None
    action: str
    from_status: str | None
    to_status: str | None
    notes: str | None
    metadata_json: dict | None


class HumanActionOut(BaseModel):
    id: int
    user_id: str
    action: str
    original_intent_json: dict | None
    final_intent_json: dict | None
    reason: str
    timestamp: datetime


class LLMDecisionOut(BaseModel):
    id: int
    prompt_used: str | None
    raw_llm_output: str | None
    parsed_intent: dict | None
    confidence: float | None
    tool_calls_json: list | None
    timestamp: datetime


class IncidentOut(BaseModel):
    id: uuid.UUID
    correlation_id: str | None
    cluster: str
    namespace: str
    alert_name: str
    hostname: str | None
    status: str
    risk_tier: str | None
    llm_confidence: float | None
    llm_intent_json: dict | None
    analysis_summary: str | None = None
    escalate_to: str | None = None
    awx_job_id: str | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    timeline: list[TimelineEventOut] = []
    human_actions: list[HumanActionOut] = []
    llm_decisions: list[LLMDecisionOut] = []


class IncidentListOut(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[IncidentOut]


# ---------------------------------------------------------------------------
# Human-in-the-Loop action requests
# ---------------------------------------------------------------------------


class ApproveRequest(BaseModel):
    reason: str = Field(..., min_length=5, description="Mandatory reason for approval")
    user_id: str = Field(..., description="Authenticated user ID — never anonymous")


class RejectRequest(BaseModel):
    reason: str = Field(..., min_length=5, description="Mandatory reason for rejection")
    user_id: str


class EditAndApproveRequest(BaseModel):
    modified_intent: dict = Field(
        ...,
        description="Modified intent JSON. Must still validate against RemediationIntent schema.",
    )
    reason: str = Field(..., min_length=5, description="Mandatory reason for edit")
    user_id: str


class EscalateRequest(BaseModel):
    reason: str = Field(..., min_length=5, description="Mandatory reason for escalation")
    user_id: str


class HumanActionResponse(BaseModel):
    incident_id: uuid.UUID
    new_status: str
    message: str


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


class MTTRDataPoint(BaseModel):
    cluster: str
    alert_name: str
    avg_mttr_seconds: float
    incident_count: int


class ResolutionStats(BaseModel):
    auto_resolved: int
    human_intervened: int
    total: int
    auto_resolved_pct: float
    human_intervened_pct: float


class LLMAccuracyStats(BaseModel):
    approved_as_is: int
    edited_before_approve: int
    rejected: int
    total_high_risk: int


class FlappingAlert(BaseModel):
    alert_name: str
    cluster: str
    flapping_count: int
    reopen_count: int

class SentimentTrend(BaseModel):
    date: str
    average_score: float
    total_resolutions: int

class RedHatCaseSummary(BaseModel):
    open_cases: int
    critical_escalation_pct: float
    avg_vendor_mttr_days: float

class ComponentIncident(BaseModel):
    component: str
    incident_count: int

class FleetRisk(BaseModel):
    average_risk_pct: int
    critical_cves_active: int

class EnvironmentDistribution(BaseModel):
    environment: str
    incident_count: int

class AnalyticsSummaryOut(BaseModel):
    mttr_by_cluster: list[MTTRDataPoint]
    resolution_stats: ResolutionStats
    llm_accuracy: LLMAccuracyStats
    top_recurring_alerts: list[dict[str, Any]]
    flapping_alerts: list[FlappingAlert]
    sentiment_trend: list[SentimentTrend]
    redhat_cases_summary: RedHatCaseSummary
    component_incidents: list[ComponentIncident]
    fleet_risk: FleetRisk
    environment_distribution: list[EnvironmentDistribution]
