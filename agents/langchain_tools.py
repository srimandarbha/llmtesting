"""
LangChain @tool definitions for the SRE Incident Agent.

Each tool is a thin adapter over an existing data source:
  - get_pod_status       → Kubernetes Python client
  - query_prometheus     → Prometheus HTTP API (existing PROMETHEUS_URL)
  - lookup_runbook       → pgvector RAG search (reuses existing query logic)
  - get_incident_history → Postgres (existing recurrence_intelligence table)
  - classify_action      → LLM structured output (Pydantic RemediationIntent)

Tools are intentionally idempotent and read-only.
The ONLY write path is through AWX (never from these tools).
"""

from __future__ import annotations

import json
import textwrap
from typing import Literal, Optional

import psycopg2
import requests
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from agents.config import (
    DATABASE_TARGET,
    EMBED_MODEL_NAME,
    LLM_API_URL,
    PROMETHEUS_URL,
)

# ---------------------------------------------------------------------------
# Pydantic schema for the LLM's structured output
# ---------------------------------------------------------------------------


class RemediationIntent(BaseModel):
    """
    Strictly typed intent produced by the LangChain ReAct agent.
    The 'action' field is restricted to the known action allowlist.
    AWX extra_vars are ALWAYS sourced from this validated model — never raw LLM output.
    """

    action: Literal[
        "restart_pod",
        "clear_evicted_pods",
        "scale_up_replicas",
        "delete_pvc",
        "drain_node",
        "scale_down_deployment",
        "escalate",
    ] = Field(description="The remediation action to take")
    namespace: str = Field(description="The Kubernetes namespace to act on")
    target: str = Field(
        description="The specific pod, node, or deployment name to act on"
    )
    reason: str = Field(
        description="One-sentence reason for this action derived from context"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score 0.0–1.0 for this remediation intent",
    )

    def to_awx_extra_vars(self) -> dict:
        """
        Produces validated extra_vars dict for AWX job templates.
        ONLY this method should supply extra_vars — never raw strings.
        """
        return {
            "action": self.action,
            "namespace": self.namespace,
            "target": self.target,
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# Tool 1: Kubernetes pod status
# ---------------------------------------------------------------------------


@tool
def get_pod_status(namespace: str, pod_name: str) -> str:
    """
    Query the Kubernetes API for the current status of a specific pod.
    Returns pod phase, container statuses, and any recent events.
    Use this to confirm the alert is still active before taking action.
    """
    try:
        from kubernetes import client as k8s_client, config as k8s_config

        try:
            k8s_config.load_incluster_config()
        except Exception:
            k8s_config.load_kube_config()

        v1 = k8s_client.CoreV1Api()
        pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)

        container_statuses = []
        if pod.status.container_statuses:
            for cs in pod.status.container_statuses:
                state_info = {}
                if cs.state.running:
                    state_info = {"state": "running"}
                elif cs.state.waiting:
                    state_info = {
                        "state": "waiting",
                        "reason": cs.state.waiting.reason,
                        "message": cs.state.waiting.message,
                    }
                elif cs.state.terminated:
                    state_info = {
                        "state": "terminated",
                        "reason": cs.state.terminated.reason,
                        "exit_code": cs.state.terminated.exit_code,
                    }
                container_statuses.append({"name": cs.name, **state_info})

        return json.dumps(
            {
                "pod": pod_name,
                "namespace": namespace,
                "phase": pod.status.phase,
                "container_statuses": container_statuses,
                "message": pod.status.message,
                "reason": pod.status.reason,
            }
        )
    except Exception as e:
        return json.dumps(
            {
                "error": str(e),
                "pod": pod_name,
                "namespace": namespace,
                "phase": "Unknown",
                "note": "Could not reach Kubernetes API. Proceeding with alert context only.",
            }
        )


# ---------------------------------------------------------------------------
# Tool 2: Prometheus metric query
# ---------------------------------------------------------------------------


@tool
def query_prometheus(metric_query: str, cluster: str) -> str:
    """
    Execute an instant PromQL query against Prometheus.
    Use this to check real-time resource utilisation, alert firing state,
    and SLO metrics. Pass a valid PromQL expression as metric_query.
    Example: 'ALERTS{alertname="PodCrashLooping", alertstate="firing"}'
    """
    try:
        resp = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": metric_query},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("data", {}).get("result", [])
        return json.dumps(
            {
                "query": metric_query,
                "cluster": cluster,
                "result_count": len(results),
                "results": results[:10],  # cap to avoid token overflow
            }
        )
    except Exception as e:
        return json.dumps(
            {
                "error": str(e),
                "query": metric_query,
                "cluster": cluster,
                "note": "Prometheus unavailable. Proceeding without live metrics.",
            }
        )


# ---------------------------------------------------------------------------
# Tool 3: RAG runbook lookup
# ---------------------------------------------------------------------------

_embed_model = None


def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        _embed_model = SentenceTransformer(EMBED_MODEL_NAME)
    return _embed_model


@tool
def lookup_runbook(alert_name: str) -> str:
    """
    Search the pgvector runbook knowledge base for remediation procedures
    relevant to the given alert name. Returns the top 2 matching runbook
    excerpts with their source IDs and similarity scores.
    Always call this before recommending any action.
    """
    try:
        embed_model = _get_embed_model()
        query_text = f"Remediation procedure for alert: {alert_name}"
        query_vector = embed_model.encode(query_text).tolist()
        search_keyword = f"%{alert_name}%"

        conn = psycopg2.connect(**DATABASE_TARGET)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT * FROM (
                SELECT source_id, source_table, text_chunk,
                       CASE WHEN source_id ILIKE %s
                            THEN (embedding <-> %s::vector) - 0.4
                            ELSE (embedding <-> %s::vector) END AS distance
                FROM operational_knowledge_embeddings
                UNION ALL
                SELECT rhokp_id AS source_id, section_type AS source_table,
                       raw_text AS text_chunk,
                       CASE WHEN rhokp_id ILIKE %s
                            THEN (embedding <-> %s::vector) - 0.4
                            ELSE (embedding <-> %s::vector) END AS distance
                FROM rhokp_knowledge
            ) AS combined
            WHERE distance < 0.75
            ORDER BY distance
            LIMIT 2;
            """,
            (search_keyword, query_vector, query_vector,
             search_keyword, query_vector, query_vector),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()

        results = []
        for row in rows:
            source_id, source_table, text_chunk, distance = row
            results.append(
                {
                    "source_id": source_id,
                    "source_table": source_table,
                    "similarity": round(1.0 - float(distance), 4),
                    "excerpt": textwrap.shorten(text_chunk, width=500),
                }
            )

        return json.dumps(
            {
                "alert_name": alert_name,
                "runbook_hits": len(results),
                "results": results,
            }
        )
    except Exception as e:
        return json.dumps(
            {
                "error": str(e),
                "alert_name": alert_name,
                "note": "RAG search failed. LLM should reason from alert name alone.",
            }
        )


# ---------------------------------------------------------------------------
# Tool 4: Incident history lookup
# ---------------------------------------------------------------------------


@tool
def get_incident_history(cluster: str, alert_name: str) -> str:
    """
    Query the Postgres database for the historical reoccurrence pattern of
    this alert on this cluster. Returns weekly incident count, reopen count,
    average MTTR, resolution quality score, and recent agent action count.
    Use this to assess whether auto-remediation has previously succeeded.
    """
    try:
        conn = psycopg2.connect(**DATABASE_TARGET)
        cur = conn.cursor()

        # Fingerprint-based lookup
        import hashlib
        raw = f"{alert_name}{''}prometheus{cluster}"
        fingerprint = hashlib.sha256(raw.encode()).hexdigest()

        # Weekly frequency
        cur.execute(
            """
            SELECT COUNT(*) FROM incidents
            WHERE alert_fingerprint = %s AND sys_created_on > NOW() - INTERVAL '7 days';
            """,
            (fingerprint,),
        )
        weekly_count = cur.fetchone()[0] or 0

        # Recurrence intelligence
        cur.execute(
            """
            SELECT total_occurrences, total_incidents, reopen_count,
                   mttr_seconds, resolution_quality_score
            FROM recurrence_intelligence WHERE fingerprint = %s;
            """,
            (fingerprint,),
        )
        rec = cur.fetchone()

        # Agent auto-remediation count last 24h
        cur.execute(
            """
            SELECT COUNT(*) FROM agent_action_log
            WHERE alert_fingerprint = %s AND status = 'SUCCESS'
            AND created_at >= NOW() - INTERVAL '24 hours';
            """,
            (fingerprint,),
        )
        agent_24h = cur.fetchone()[0] or 0

        cur.close()
        conn.close()

        return json.dumps(
            {
                "cluster": cluster,
                "alert_name": alert_name,
                "weekly_occurrences": weekly_count,
                "total_occurrences": rec[0] if rec else 0,
                "total_incidents": rec[1] if rec else 0,
                "reopen_count": rec[2] if rec else 0,
                "avg_mttr_seconds": rec[3] if rec else 0,
                "resolution_quality_score": float(rec[4]) if rec and rec[4] else 100.0,
                "agent_auto_remediations_last_24h": agent_24h,
            }
        )
    except Exception as e:
        return json.dumps(
            {
                "error": str(e),
                "cluster": cluster,
                "alert_name": alert_name,
                "note": "History unavailable. Treating as new incident.",
            }
        )


# ---------------------------------------------------------------------------
# Tool 5: LLM action classification
# ---------------------------------------------------------------------------


@tool
def classify_action(context_json: str) -> str:
    """
    Call the LLM to classify the alert context into a typed RemediationIntent.
    Input must be a JSON string with keys: alert_name, namespace, cluster,
    hostname, runbook_context, pod_status, prometheus_data, incident_history.
    Returns a JSON string matching the RemediationIntent schema.
    The 'confidence' field reflects how certain the model is.
    """
    try:
        context = json.loads(context_json)
    except Exception:
        context = {"raw": context_json}

    system_prompt = textwrap.dedent(
        """
        You are an expert OpenShift/Kubernetes SRE.
        Given alert context, produce a strictly typed remediation intent in JSON.

        Output MUST be valid JSON matching this schema exactly:
        {
          "action": "<one of: restart_pod|clear_evicted_pods|scale_up_replicas|delete_pvc|drain_node|scale_down_deployment|escalate>",
          "namespace": "<kubernetes namespace>",
          "target": "<specific pod/node/deployment name from the alert, never generic>",
          "reason": "<one sentence reason based only on context provided>",
          "confidence": <float 0.0 to 1.0>
        }

        Rules:
        - Use ONLY information from the provided context. Never hallucinate resource names.
        - If context is insufficient or ambiguous, set action="escalate" and confidence<0.75.
        - Do NOT include markdown, explanations, or any text outside the JSON object.
        """
    )

    user_prompt = (
        f"Alert context:\n{json.dumps(context, indent=2)}\n\n"
        "Produce the remediation intent JSON:"
    )

    try:
        resp = requests.post(
            LLM_API_URL,
            json={
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.1,
            },
            timeout=45,
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()

        # Strip any accidental markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip().rstrip("```").strip()

        # Validate against Pydantic schema
        intent = RemediationIntent.model_validate_json(raw)
        return intent.model_dump_json()

    except Exception as e:
        # Fallback: safe escalation
        fallback = RemediationIntent(
            action="escalate",
            namespace=context.get("namespace", "unknown"),
            target=context.get("hostname", "unknown"),
            reason=f"LLM classification failed: {e}. Defaulting to escalation.",
            confidence=0.0,
        )
        return fallback.model_dump_json()


# ---------------------------------------------------------------------------
# Exported tools list for AgentExecutor
# ---------------------------------------------------------------------------

ALL_TOOLS = [
    get_pod_status,
    query_prometheus,
    lookup_runbook,
    get_incident_history,
    classify_action,
]
