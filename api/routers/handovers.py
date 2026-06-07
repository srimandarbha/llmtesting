"""
Shift Handovers API — v2

Structured handover notes between SRE shifts. Each note captures:
  - shift_identifier : outgoing engineer / shift label
  - cluster          : target cluster or ALL
  - handover_type    : handover | maintenance | upgrade | operator_upgrade |
                       incident_followup | change_freeze | escalation
  - priority         : low | medium | high | critical
  - action_required  : bool — next shift must act
  - related_incidents: comma-separated incident IDs
  - message          : free-text body

SSO NOTE: `author` is kept for legacy compatibility. When SSO is live,
populate it from the OIDC token in the request (e.g. via a Depends()).
"""

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
import psycopg2
import uuid
from typing import List, Optional
from datetime import datetime

from agents.config import DATABASE_TARGET

router = APIRouter(prefix="/handovers", tags=["Handovers"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class HandoverCreate(BaseModel):
    # SSO-ready: when OIDC is integrated, author/shift_identifier will be
    # injected server-side from the bearer token. Until then, clients send them.
    author: str
    shift_identifier: str
    cluster: str = "ALL"
    handover_type: str = "handover"   # matches handover_type_enum values
    priority: str = "medium"          # matches handover_priority_enum values
    action_required: bool = False
    related_incidents: str = ""
    message: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    upgraded_version: Optional[str] = None
    operator_name: Optional[str] = None


class HandoverOut(BaseModel):
    id: uuid.UUID
    author: str
    shift_identifier: str
    cluster: str
    handover_type: str
    priority: str
    action_required: bool
    related_incidents: str
    message: str
    created_at: datetime
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    is_active: bool = True
    resolution_notes: Optional[str] = None
    upgraded_version: Optional[str] = None
    operator_name: Optional[str] = None

class HandoverUpdate(BaseModel):
    is_active: Optional[bool] = None
    resolution_notes: Optional[str] = None
    action_required: Optional[bool] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_TYPES = {
    "handover", "maintenance", "upgrade", "operator_upgrade",
    "incident_followup", "change_freeze", "escalation",
}
_VALID_PRIORITIES = {"low", "medium", "high", "critical"}


def _row_to_dict(row: tuple) -> dict:
    return {
        "id":                 row[0],
        "author":             row[1],
        "shift_identifier":   row[2],
        "cluster":            row[3],
        "handover_type":      row[4],
        "priority":           row[5],
        "action_required":    row[6],
        "related_incidents":  row[7],
        "message":            row[8],
        "created_at":         row[9],
        "start_time":         row[10] if len(row) > 10 else None,
        "end_time":           row[11] if len(row) > 11 else None,
        "is_active":          row[12] if len(row) > 12 else True,
        "resolution_notes":   row[13] if len(row) > 13 else None,
        "upgraded_version":   row[14] if len(row) > 14 else None,
        "operator_name":      row[15] if len(row) > 15 else None,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=HandoverOut)
async def create_handover(handover: HandoverCreate):
    """Create a new shift handover note."""
    # Normalise / validate enum values
    h_type    = handover.handover_type if handover.handover_type in _VALID_TYPES     else "handover"
    h_prio    = handover.priority       if handover.priority       in _VALID_PRIORITIES else "medium"
    # shift_identifier defaults to author if not provided
    shift_id  = handover.shift_identifier.strip() or handover.author.strip()

    # Validation
    if h_type == "upgrade" and not handover.upgraded_version:
        raise HTTPException(status_code=400, detail="upgraded_version is required for Platform Upgrades")
    if h_type == "operator_upgrade" and (not handover.operator_name or not handover.upgraded_version):
        raise HTTPException(status_code=400, detail="operator_name and upgraded_version are required for Operator Upgrades")

    conn = psycopg2.connect(**DATABASE_TARGET)
    cur  = conn.cursor()
    new_id = uuid.uuid4()

    cur.execute(
        """
        INSERT INTO shift_handovers
            (id, author, shift_identifier, cluster, handover_type,
             priority, action_required, related_incidents, message, created_at,
             start_time, end_time, is_active, upgraded_version, operator_name)
        VALUES (%s, %s, %s, %s, %s::handover_type_enum,
                %s::handover_priority_enum, %s, %s, %s, NOW(), %s, %s, TRUE, %s, %s)
        RETURNING id, author, shift_identifier, cluster, handover_type,
                  priority, action_required, related_incidents, message, created_at,
                  start_time, end_time, is_active, resolution_notes, upgraded_version, operator_name
        """,
        (
            str(new_id),
            handover.author,
            shift_id,
            handover.cluster or "ALL",
            h_type,
            h_prio,
            handover.action_required,
            handover.related_incidents,
            handover.message,
            handover.start_time,
            handover.end_time,
            handover.upgraded_version,
            handover.operator_name
        )
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return _row_to_dict(row)


@router.get("", response_model=List[HandoverOut])
async def list_handovers(
    limit:          int           = Query(50, ge=1, le=200),
    cluster:        Optional[str] = Query(None, description="Filter by cluster name"),
    handover_type:  Optional[str] = Query(None, description="Filter by type"),
    priority:       Optional[str] = Query(None, description="Filter by priority"),
    action_required: Optional[bool] = Query(None, description="Filter action-required notes"),
):
    """
    List shift handovers, newest first.
    Supports optional filtering by cluster, type, priority, action_required.
    """
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur  = conn.cursor()

    conditions = []
    params: list = []

    if cluster:
        conditions.append("cluster = %s")
        params.append(cluster)
    if handover_type and handover_type in _VALID_TYPES:
        conditions.append("handover_type = %s::handover_type_enum")
        params.append(handover_type)
    if priority and priority in _VALID_PRIORITIES:
        conditions.append("priority = %s::handover_priority_enum")
        params.append(priority)
    if action_required is not None:
        conditions.append("action_required = %s")
        params.append(action_required)

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.append(limit)

    cur.execute(
        f"""
        SELECT id, author, shift_identifier, cluster, handover_type,
               priority, action_required, related_incidents, message, created_at,
               start_time, end_time, is_active, resolution_notes, upgraded_version, operator_name
        FROM shift_handovers
        {{where_clause}}
        ORDER BY created_at DESC
        LIMIT %s
        """.replace('{where_clause}', where_clause),
        params,
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [_row_to_dict(r) for r in rows]

@router.get("/active_ticker", response_model=List[HandoverOut])
async def get_active_ticker():
    """Fetch active handovers for the global floating pane."""
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, author, shift_identifier, cluster, handover_type,
               priority, action_required, related_incidents, message, created_at,
               start_time, end_time, is_active, resolution_notes, upgraded_version, operator_name
        FROM shift_handovers
        WHERE is_active = TRUE 
          AND (action_required = TRUE OR handover_type = 'maintenance')
          AND (end_time IS NULL OR end_time > NOW())
        ORDER BY priority DESC, created_at DESC
        """
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [_row_to_dict(r) for r in rows]

@router.patch("/{handover_id}", response_model=HandoverOut)
async def update_handover(handover_id: str, updates: HandoverUpdate):
    """Update active status or resolution notes for a handover."""
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur = conn.cursor()

    set_clauses = []
    params = []
    
    if updates.is_active is not None:
        set_clauses.append("is_active = %s")
        params.append(updates.is_active)
    if updates.resolution_notes is not None:
        set_clauses.append("resolution_notes = %s")
        params.append(updates.resolution_notes)
    if updates.action_required is not None:
        set_clauses.append("action_required = %s")
        params.append(updates.action_required)

    if not set_clauses:
        cur.close()
        conn.close()
        return {} # No-op

    params.append(handover_id)
    
    cur.execute(
        f"""
        UPDATE shift_handovers
        SET {', '.join(set_clauses)}
        WHERE id = %s
        RETURNING id, author, shift_identifier, cluster, handover_type,
                  priority, action_required, related_incidents, message, created_at,
                  start_time, end_time, is_active, resolution_notes, upgraded_version, operator_name
        """,
        params
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return _row_to_dict(row) if row else {}

@router.get("/clusters", response_model=List[str])
async def list_handover_clusters():
    """
    List all available clusters from the clusters table for the dropdown.
    """
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur  = conn.cursor()
    cur.execute("SELECT cluster_id FROM clusters ORDER BY cluster_id")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [r[0] for r in rows]

