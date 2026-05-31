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
# pyrefly: ignore [missing-import]
from langchain_core.tools import tool
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field

from agents.config import (
    DATABASE_TARGET,
    EMBED_MODEL_NAME,
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
    analysis_summary: str = Field(
        default="",
        description="Detailed markdown analysis including existing tickets, maintenance, RedHat cases, diagnostics, remediation, and validation steps."
    )
    escalate_to: str = Field(
        default="SRE-Triage",
        description="Who to escalate to, based on the Escalation Matrix, if validation fails or risk is high."
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
def get_pod_status(input_json: str) -> str:
    """
    Query the Kubernetes API for the current status of a specific pod.
    Returns pod phase, container statuses, and any recent events.
    Use this to confirm the alert is still active before taking action.
    Input must be a JSON string with keys "namespace" and "pod_name".
    """
    pod_name = "unknown"
    namespace = "unknown"
    try:
        import json
        if isinstance(input_json, str):
            input_json = input_json.strip(" '`\n")
        args = json.loads(input_json) if isinstance(input_json, str) else input_json
        if isinstance(args, dict):
            namespace = args.get("namespace", "default")
            pod_name = args.get("pod_name", "")

        from agents.config import USE_MOCK_SERVERS
        if USE_MOCK_SERVERS:
            return json.dumps(
                {
                    "pod": pod_name,
                    "namespace": namespace,
                    "phase": "Failed",
                    "container_statuses": [
                        {
                            "name": "collector",
                            "state": "terminated",
                            "reason": "OOMKilled",
                            "exit_code": 137
                        }
                    ],
                    "message": "Pod was OOMKilled",
                    "reason": "OOMKilled",
                }
            )

        # pyrefly: ignore [missing-import]
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
def query_prometheus(input_json: str) -> str:
    """
    Execute an instant PromQL query against Prometheus.
    Use this to check real-time resource utilisation, alert firing state,
    and SLO metrics. Pass a JSON string with keys "metric_query" and "cluster".
    Example: '{"metric_query": "ALERTS{alertname=\\"PodCrashLooping\\"}", "cluster": "nzclu101"}'
    """
    metric_query = "unknown"
    cluster = "unknown"
    try:
        import json
        if isinstance(input_json, str):
            input_json = input_json.strip(" '`\n")
        args = json.loads(input_json) if isinstance(input_json, str) else input_json
        if isinstance(args, dict):
            metric_query = args.get("metric_query", "")
            cluster = args.get("cluster", "")
            
        from agents.config import USE_MOCK_SERVERS
        if USE_MOCK_SERVERS:
            import time
            return json.dumps(
                {
                    "query": metric_query,
                    "cluster": cluster,
                    "result_count": 1,
                    "results": [
                        {
                            "metric": {"__name__": "up", "namespace": "cluster-logging-operator"},
                            "value": [int(time.time()), "0"]
                        }
                    ],
                }
            )

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
        # pyrefly: ignore [missing-import]
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
        from agents.config import USE_MOCK_SERVERS
        if USE_MOCK_SERVERS:
            import json
            return json.dumps({
                "alert_name": alert_name,
                "runbook_hits": 1,
                "results": [{
                    "source_id": "mock_runbook_1",
                    "source_table": "rhokp_knowledge",
                    "similarity": 0.95,
                    "excerpt": f"Standard remediation for {alert_name}: Requires manual approval if risk is high. Check node status, drain node if kernel panic, or restart pods."
                }]
            })
            
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
def get_incident_history(input_json: str) -> str:
    """
    Query the Postgres database for the historical reoccurrence pattern of
    this alert on this cluster. Returns weekly incident count, reopen count,
    average MTTR, resolution quality score, and recent agent action count.
    Use this to assess whether auto-remediation has previously succeeded.
    Input must be a JSON string with keys "cluster" and "alert_name".
    """
    cluster = "unknown"
    alert_name = "unknown"
    try:
        import json
        if isinstance(input_json, str):
            input_json = input_json.strip(" '`\n")
        args = json.loads(input_json) if isinstance(input_json, str) else input_json
        if isinstance(args, dict):
            cluster = args.get("cluster", "")
            alert_name = args.get("alert_name", "")
        conn = psycopg2.connect(**DATABASE_TARGET)
        cur = conn.cursor()

        # Fingerprint logic was flawed because we lack namespace and operator component in this context.
        # Instead, query by alertname and cluster directly.

        # Weekly frequency
        cur.execute(
            """
            SELECT COUNT(i.*) FROM incidents i
            JOIN alert_occurrences a ON i.alert_fingerprint = a.fingerprint
            WHERE a.alertname = %s AND a.cluster_id = %s AND i.sys_created_on > NOW() - INTERVAL '7 days';
            """,
            (alert_name, cluster),
        )
        weekly_count = cur.fetchone()[0] or 0

        # Recurrence intelligence
        cur.execute(
            """
            SELECT SUM(total_occurrences), SUM(total_incidents), SUM(reopen_count),
                   AVG(mttr_seconds), AVG(resolution_quality_score)
            FROM recurrence_intelligence WHERE alertname = %s AND cluster_id = %s;
            """,
            (alert_name, cluster),
        )
        rec = cur.fetchone()

        # Agent auto-remediation count last 24h
        cur.execute(
            """
            SELECT COUNT(*) FROM incidents_v2
            WHERE alert_name = %s AND cluster = %s AND status = 'RESOLVED'
            AND updated_at >= NOW() - INTERVAL '24 hours';
            """,
            (alert_name, cluster),
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
    Validate and structure the gathered alert context, then instruct the ReAct
    agent (you) to produce a RemediationIntent JSON response.

    This tool does NOT make a second LLM call. The ReAct agent is the LLM.
    Calling this tool returns a structured prompt that YOU (the agent) must
    answer with a valid RemediationIntent JSON as your Final Answer.

    Input must be a JSON string with keys: alert_name, namespace, cluster,
    hostname, runbook_context, pod_status, prometheus_data, incident_history.

    Allowed actions: restart_pod | clear_evicted_pods | scale_up_replicas |
                     delete_pvc | drain_node | scale_down_deployment | escalate
    """
    try:
        if isinstance(context_json, str):
            context_json = context_json.strip(" '`\n")
        context = json.loads(context_json)
    except Exception:
        context = {"raw": context_json}

    try:
        import os
        matrix_path = os.path.join(os.path.dirname(__file__), "escalation_matrix.json")
        with open(matrix_path, "r") as f:
            escalation_matrix = f.read()
    except Exception:
        escalation_matrix = '{"default": "SRE-Triage"}'

    # Return a structured instruction — the ReAct agent will use this to produce the Final Answer
    instruction = textwrap.dedent(f"""
        Based on the following alert context, produce your Final Answer as a
        valid JSON object matching the RemediationIntent schema below.
        DO NOT include any text outside the JSON object.

        Schema:
        {{
          "action": "<restart_pod|clear_evicted_pods|scale_up_replicas|delete_pvc|drain_node|scale_down_deployment|escalate>",
          "namespace": "<kubernetes namespace>",
          "target": "<specific pod/node/deployment name -- never generic>",
          "reason": "<one-sentence reason derived only from context>",
          "confidence": <float 0.0-1.0>,
          "analysis_summary": "<markdown: 1) Remediation 2) Diagnostics 3) Validation 4) Tickets 5) RH Cases>",
          "escalate_to": "<team from escalation matrix>"
        }}

        Escalation Matrix: {escalation_matrix}

        Rules:
        - Use ONLY information from context. Never hallucinate resource names.
        - If context is insufficient, set action="escalate" and confidence<0.75.

        Alert Context:
        {json.dumps(context, indent=2)}
    """)

    return instruction


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
