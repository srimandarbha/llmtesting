import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import psycopg2
from langchain_core.messages import SystemMessage, HumanMessage
from sentence_transformers import SentenceTransformer

from agents.config import DATABASE_TARGET, EMBED_MODEL_NAME
from agents.langchain_agent import _get_llm

router = APIRouter(prefix="/summaries", tags=["Summaries"])

embed_model = None

def get_embed_model():
    global embed_model
    if embed_model is None:
        embed_model = SentenceTransformer(EMBED_MODEL_NAME)
    return embed_model

def get_previous_shift_window():
    """
    Returns (shift_name, start_time, end_time) for the immediately preceding shift.
    Shifts: 00:00-08:00, 08:00-16:00, 16:00-00:00.
    """
    now = datetime.now(timezone.utc)
    hour = now.hour
    
    if 0 <= hour < 8:
        # Prev shift: yesterday 16:00 to today 00:00
        end_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_time = end_time - timedelta(hours=8)
        shift_name = f"Shift 3 (16:00-00:00) {start_time.strftime('%Y-%m-%d')}"
    elif 8 <= hour < 16:
        # Prev shift: today 00:00 to 08:00
        end_time = now.replace(hour=8, minute=0, second=0, microsecond=0)
        start_time = end_time - timedelta(hours=8)
        shift_name = f"Shift 1 (00:00-08:00) {start_time.strftime('%Y-%m-%d')}"
    else:
        # Prev shift: today 08:00 to 16:00
        end_time = now.replace(hour=16, minute=0, second=0, microsecond=0)
        start_time = end_time - timedelta(hours=8)
        shift_name = f"Shift 2 (08:00-16:00) {start_time.strftime('%Y-%m-%d')}"
        
    return shift_name, start_time, end_time

class SummaryPreviewResponse(BaseModel):
    shift_name: str
    preview_text: str

@router.post("/preview", response_model=SummaryPreviewResponse)
async def preview_summary():
    shift_name, start_time, end_time = get_previous_shift_window()
    
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur = conn.cursor()
    
    # Fetch incidents
    cur.execute(
        """
        SELECT alert_name, cluster, status, risk_tier, created_at
        FROM incidents_v2 
        WHERE created_at >= %s AND created_at < %s
        ORDER BY created_at ASC
        """,
        (start_time, end_time)
    )
    incidents = cur.fetchall()
    
    # Fetch handovers
    cur.execute(
        """
        SELECT 
            author, shift_identifier, cluster, handover_type, priority,
            action_required, related_incidents, resolution_notes,
            upgraded_version, operator_name, message, created_at
        FROM shift_handovers 
        WHERE created_at >= %s AND created_at < %s
        ORDER BY created_at ASC
        """,
        (start_time, end_time)
    )
    handovers = cur.fetchall()
    
    cur.close()
    conn.close()
    
    context = f"--- INCIDENTS FROM {start_time} TO {end_time} ---\n"
    if not incidents:
        context += "No incidents recorded.\n"
    for inc in incidents:
        context += f"- Alert: {inc[0]} | Cluster: {inc[1]} | Status: {inc[2]} | Risk: {inc[3]}\n"
        
    context += f"\n--- SHIFT HANDOVERS FROM {start_time} TO {end_time} ---\n"
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
        
    system_prompt = (
        "You are an SRE shift supervisor. Write a clear, comprehensive markdown report "
        "summarizing the events of the shift based on the provided logs. Group related events, "
        "highlight ongoing maintenance or issues, and provide a quick executive summary at the top.\n"
        "CRITICAL REQUIREMENTS:\n"
        "- If a handover has 'Resolution' notes or was completed, you MUST state that it was resolved and what the resolution was.\n"
        "- You MUST include all 'Related Incidents' (e.g., INC123456) for each handover.\n"
        "- Do not omit any crucial operational metadata like target versions or operator names."
    )
    
    user_prompt = f"Shift Log:\n{context}\n\nPlease generate the Final Shift Report."
    
    llm = _get_llm()
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]
    
    response = llm.invoke(messages)
    
    return {
        "shift_name": shift_name,
        "preview_text": response.content
    }

class SummarySaveRequest(BaseModel):
    shift_name: str
    summary_text: str
    is_auto_generated: bool = False

@router.post("/save")
async def save_summary(req: SummarySaveRequest):
    try:
        model = get_embed_model()
        vector_coord = model.encode(req.summary_text).tolist()
        
        conn = psycopg2.connect(**DATABASE_TARGET)
        cur = conn.cursor()
        
        new_id = uuid.uuid4()
        
        cur.execute(
            """
            INSERT INTO historical_shift_summaries (id, shift_name, summary_text, embedding, is_auto_generated)
            VALUES (%s, %s, %s, %s::vector, %s)
            """,
            (str(new_id), req.shift_name, req.summary_text, vector_coord, req.is_auto_generated)
        )
        conn.commit()
        cur.close()
        conn.close()
        return {"status": "success", "id": str(new_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/historical")
async def get_historical_summaries():
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur = conn.cursor()
    
    cur.execute(
        """
        SELECT id, shift_name, summary_text, is_auto_generated, created_at 
        FROM historical_shift_summaries 
        ORDER BY created_at DESC 
        LIMIT 20
        """
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    return [
        {
            "id": r[0],
            "shift_name": r[1],
            "summary_text": r[2],
            "is_auto_generated": r[3],
            "created_at": r[4]
        }
        for r in rows
    ]
