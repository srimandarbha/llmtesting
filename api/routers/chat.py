from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import psycopg2
from typing import Optional
from langchain_core.messages import SystemMessage, HumanMessage

from agents.config import DATABASE_TARGET
from agents.langchain_agent import _get_llm

router = APIRouter(prefix="/chat", tags=["Chat"])

class ChatRequest(BaseModel):
    query: str
    timeframe_hours: int = 8

class ChatResponse(BaseModel):
    answer: str

from api.routers.summaries import get_embed_model

def get_context_for_timeframe(hours: int, query: str = "") -> str:
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur = conn.cursor()
    
    if hours >= 24:
        # Use vector semantic search against historical summaries
        model = get_embed_model()
        query_vector = model.encode(query).tolist()
        
        cur.execute(
            """
            SELECT shift_name, summary_text, created_at, (embedding <-> %s::vector) as distance
            FROM historical_shift_summaries
            WHERE created_at >= NOW() - INTERVAL '%s hours'
            ORDER BY embedding <-> %s::vector
            LIMIT 5
            """,
            (query_vector, hours, query_vector)
        )
        historical = cur.fetchall()
        cur.close()
        conn.close()
        
        context = f"--- TOP 5 RELEVANT SHIFT SUMMARIES FROM LAST {hours} HOURS ---\n"
        if not historical:
            context += "No relevant historical summaries found.\n"
        for h in historical:
            context += f"### {h[0]} (Date: {h[2]})\n{h[1]}\n\n"
        return context

    # 1. Get incidents (for < 24 hours)
    cur.execute(
        """
        SELECT alert_name, cluster, status, risk_tier, created_at, resolved_at 
        FROM incidents_v2 
        WHERE created_at >= NOW() - INTERVAL '%s hours'
        ORDER BY created_at DESC
        """,
        (hours,)
    )
    incidents = cur.fetchall()
    
    # 2. Get shift handovers
    cur.execute(
        """
        SELECT 
            author, shift_identifier, cluster, handover_type, priority,
            action_required, related_incidents, resolution_notes,
            upgraded_version, operator_name, message, created_at
        FROM shift_handovers 
        WHERE created_at >= NOW() - INTERVAL '%s hours'
        ORDER BY created_at DESC
        """,
        (hours,)
    )
    handovers = cur.fetchall()
    
    cur.close()
    conn.close()
    
    context = f"--- INCIDENTS IN LAST {hours} HOURS ---\n"
    if not incidents:
        context += "No incidents recorded.\n"
    for inc in incidents:
        context += f"- [{inc[4]}] Alert: {inc[0]} | Cluster: {inc[1]} | Status: {inc[2]} | Risk: {inc[3]}\n"
        
    context += f"\n--- SHIFT HANDOVERS IN LAST {hours} HOURS ---\n"
    if not handovers:
        context += "No handovers recorded.\n"
    for ho in handovers:
        (author, shift_identifier, cluster, handover_type, priority,
         action_required, related_incidents, resolution_notes,
         upgraded_version, operator_name, message, created_at) = ho
         
        ho_str = f"- [{created_at}] {shift_identifier or author} on {cluster} | Type: {handover_type} | Priority: {priority}\n"
        ho_str += f"  Message: {message}\n"
        if related_incidents:
            ho_str += f"  Related Incidents: {related_incidents}\n"
        if action_required:
            ho_str += "  ACTION REQUIRED from next shift.\n"
        if resolution_notes:
            ho_str += f"  Resolution: {resolution_notes}\n"
        if upgraded_version:
            ho_str += f"  Upgraded Version: {upgraded_version}\n"
        if operator_name:
            ho_str += f"  Operator: {operator_name}\n"
            
        context += ho_str
        
    return context

@router.post("", response_model=ChatResponse)
async def chat_with_context(req: ChatRequest):
    try:
        query = req.query.strip()
        
        # ─── Command Interception ───
        if query.startswith("/checkalerts"):
            parts = query.split()
            cluster_name = parts[1] if len(parts) > 1 else None
            
            conn = psycopg2.connect(**DATABASE_TARGET)
            cur = conn.cursor()
            if cluster_name:
                cur.execute("SELECT id, alert_name, risk_tier, status FROM incidents_v2 WHERE cluster = %s AND status != 'RESOLVED' ORDER BY created_at DESC LIMIT 5", (cluster_name,))
                msg = f"🔍 **Live Alerts for Cluster: {cluster_name}**\n\n"
            else:
                cur.execute("SELECT id, alert_name, risk_tier, cluster, status FROM incidents_v2 WHERE status != 'RESOLVED' ORDER BY created_at DESC LIMIT 5")
                msg = "🔍 **Recent Live Alerts Across All Clusters**\n\n"
                
            rows = cur.fetchall()
            cur.close()
            conn.close()
            
            if not rows:
                msg += "No active alerts found."
            else:
                for r in rows:
                    if cluster_name:
                        msg += f"- **{r[1]}** (ID: `{r[0]}`) | Tier: {r[2]} | Status: {r[3]}\n"
                    else:
                        msg += f"- **{r[1]}** on {r[3]} (ID: `{r[0]}`) | Tier: {r[2]} | Status: {r[4]}\n"
            return {"answer": msg}
            
        elif query.startswith("/escalate"):
            parts = query.split()
            if len(parts) < 2:
                return {"answer": "⚠️ Please provide an incident ID: `/escalate [incident_id]`"}
            inc_id = parts[1]
            
            conn = psycopg2.connect(**DATABASE_TARGET)
            cur = conn.cursor()
            cur.execute("UPDATE incidents_v2 SET risk_tier = 'CRITICAL', status = 'ESCALATED', updated_at = NOW() WHERE id = %s RETURNING alert_name", (inc_id,))
            row = cur.fetchone()
            if row:
                cur.execute(
                    "INSERT INTO incident_timeline (incident_id, actor_type, action, notes) VALUES (%s, 'human', 'escalated', 'Escalated via Summaries Chat')",
                    (inc_id,)
                )
                conn.commit()
                cur.close()
                conn.close()
                return {"answer": f"🚨 **Escalated!** Incident `{inc_id}` ({row[0]}) has been escalated to CRITICAL priority."}
            else:
                conn.rollback()
                cur.close()
                conn.close()
                return {"answer": f"❌ Could not find incident with ID `{inc_id}`."}
        # ────────────────────────────

        context_str = get_context_for_timeframe(req.timeframe_hours, query=req.query)
        
        system_prompt = (
            "You are an expert SRE shift assistant. Use the provided context to accurately answer the user's questions "
            "regarding past incidents, alerts, and shift handover messages. Do not hallucinate outside the provided context."
        )
        
        user_prompt = f"Context:\n{context_str}\n\nUser Query:\n{req.query}"
        
        llm = _get_llm()
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        response = llm.invoke(messages)
        
        return {"answer": response.content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
