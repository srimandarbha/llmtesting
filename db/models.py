"""
SQLAlchemy async ORM models for the LangChain Incident Tracking system.

Key design decisions:
- incidents_v2 uses UUID primary key (gen_random_uuid from pgcrypto).
- incident_timeline is append-only — no update method exposed.
- All timestamps are TIMESTAMPTZ (timezone-aware).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Incident (core record)
# ---------------------------------------------------------------------------

VALID_STATUSES = (
    "RECEIVED",
    "ANALYZING",
    "PENDING_APPROVAL",
    "EXECUTING",
    "VERIFYING",
    "RESOLVED",
    "REJECTED",
    "ESCALATED",
    "FAILED",
)

VALID_RISK_TIERS = ("LOW", "HIGH", "ESCALATE")


class Incident(Base):
    __tablename__ = "incidents_v2"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    correlation_id: Mapped[str | None] = mapped_column(String, unique=True)
    cluster: Mapped[str] = mapped_column(String, nullable=False)
    namespace: Mapped[str] = mapped_column(String, nullable=False)
    alert_name: Mapped[str] = mapped_column(String, nullable=False)
    hostname: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="RECEIVED",
        server_default="RECEIVED",
    )
    risk_tier: Mapped[str | None] = mapped_column(String)
    llm_confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))
    llm_intent_json: Mapped[dict | None] = mapped_column(JSONB)
    awx_job_id: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column()

    # Relationships
    timeline: Mapped[list[IncidentTimelineEvent]] = relationship(
        back_populates="incident",
        order_by="IncidentTimelineEvent.timestamp",
        lazy="selectin",
    )
    human_actions: Mapped[list[HumanAction]] = relationship(
        back_populates="incident",
        order_by="HumanAction.timestamp",
        lazy="selectin",
    )
    llm_decisions: Mapped[list[LLMDecision]] = relationship(
        back_populates="incident",
        order_by="LLMDecision.timestamp",
        lazy="selectin",
    )

    __table_args__ = (
        CheckConstraint(f"status IN {VALID_STATUSES}", name="ck_incident_status"),
        CheckConstraint(
            f"risk_tier IN {VALID_RISK_TIERS} OR risk_tier IS NULL",
            name="ck_incident_risk_tier",
        ),
        Index("idx_incidents_v2_status", "status"),
        Index("idx_incidents_v2_cluster_alert", "cluster", "alert_name"),
        Index("idx_incidents_v2_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Incident id={self.id} alert={self.alert_name} status={self.status}>"


# ---------------------------------------------------------------------------
# Incident Timeline (append-only audit log)
# ---------------------------------------------------------------------------


class IncidentTimelineEvent(Base):
    __tablename__ = "incident_timeline"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents_v2.id", ondelete="CASCADE"),
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    actor_type: Mapped[str] = mapped_column(
        String, nullable=False
    )  # agent | human | system
    actor_id: Mapped[str | None] = mapped_column(String)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    from_status: Mapped[str | None] = mapped_column(String)
    to_status: Mapped[str | None] = mapped_column(String)
    notes: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)

    incident: Mapped[Incident] = relationship(back_populates="timeline")

    __table_args__ = (
        CheckConstraint(
            "actor_type IN ('agent', 'human', 'system')",
            name="ck_timeline_actor_type",
        ),
        Index("idx_timeline_incident_id", "incident_id", "timestamp"),
    )

    def __repr__(self) -> str:
        return (
            f"<TimelineEvent incident={self.incident_id} "
            f"actor={self.actor_type} action={self.action}>"
        )


# ---------------------------------------------------------------------------
# Human Actions
# ---------------------------------------------------------------------------


class HumanAction(Base):
    __tablename__ = "human_actions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents_v2.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)  # APPROVED|REJECTED|EDITED|ESCALATED
    original_intent_json: Mapped[dict | None] = mapped_column(JSONB)
    final_intent_json: Mapped[dict | None] = mapped_column(JSONB)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    incident: Mapped[Incident] = relationship(back_populates="human_actions")

    __table_args__ = (
        CheckConstraint(
            "action IN ('APPROVED','REJECTED','EDITED','ESCALATED')",
            name="ck_human_action_type",
        ),
        Index("idx_human_actions_incident", "incident_id", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<HumanAction user={self.user_id} action={self.action}>"


# ---------------------------------------------------------------------------
# LLM Decisions
# ---------------------------------------------------------------------------


class LLMDecision(Base):
    __tablename__ = "llm_decisions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents_v2.id", ondelete="CASCADE"),
        nullable=False,
    )
    prompt_used: Mapped[str | None] = mapped_column(Text)
    raw_llm_output: Mapped[str | None] = mapped_column(Text)
    parsed_intent: Mapped[dict | None] = mapped_column(JSONB)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))
    tool_calls_json: Mapped[dict | None] = mapped_column(JSONB)
    timestamp: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    incident: Mapped[Incident] = relationship(back_populates="llm_decisions")

    __table_args__ = (
        Index("idx_llm_decisions_incident", "incident_id", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<LLMDecision incident={self.incident_id} conf={self.confidence}>"


# ---------------------------------------------------------------------------
# Helper: append a timeline event (enforces append-only contract)
# ---------------------------------------------------------------------------


async def log_timeline_event(
    session: Any,
    incident_id: uuid.UUID,
    actor_type: str,
    action: str,
    from_status: str | None = None,
    to_status: str | None = None,
    actor_id: str | None = None,
    notes: str | None = None,
    metadata: dict | None = None,
) -> IncidentTimelineEvent:
    """
    Always INSERTs a new row. Never updates existing rows.
    This is the ONLY way timeline events should be written.
    """
    event = IncidentTimelineEvent(
        incident_id=incident_id,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        from_status=from_status,
        to_status=to_status,
        notes=notes,
        metadata_json=metadata,
    )
    session.add(event)
    return event


# ---------------------------------------------------------------------------
# Cluster Inventory
# ---------------------------------------------------------------------------

class ClusterInventory(Base):
    __tablename__ = "cluster_inventory"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    current_version: Mapped[str] = mapped_column(String, nullable=False)
    active_cves: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<ClusterInventory id={self.id} name={self.name} version={self.current_version}>"
