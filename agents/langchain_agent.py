"""
LangChain AgentExecutor pipeline for SRE incident analysis.

Pipeline stages (Python if/else routing — no LangGraph):

  Step 1: Context gathering  → RunnableParallel (all 4 info tools fire at once)
  Step 2: ReAct agent        → classify_action tool → RemediationIntent
  Step 3: Validation chain   → Pydantic schema + action allowlist check
  Step 4: Risk scoring       → risk_engine.classify_risk() (NO LLM)
  Step 5: Route              → LOW / HIGH / ESCALATE

Every state transition writes to incident_timeline via log_timeline_event.
LLM reasoning is stored in llm_decisions.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any, Literal

from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from agents.config import LLM_API_URL
from agents.langchain_tools import (
    ALL_TOOLS,
    RemediationIntent,
    classify_action,
    get_incident_history,
    get_pod_status,
    lookup_runbook,
    query_prometheus,
)
from agents.risk_engine import RiskTier, classify_risk, get_risk_reasoning, is_action_allowed

# ---------------------------------------------------------------------------
# LLM client — points at the existing llama.cpp compatible endpoint
# ---------------------------------------------------------------------------


def _get_llm() -> ChatOpenAI:
    """
    Returns a ChatOpenAI instance pointed at the local LLM endpoint.
    Compatible with llama.cpp server, Ollama, and OpenAI API.
    Set LLM_API_URL in .env to switch providers.
    """
    return ChatOpenAI(
        base_url=LLM_API_URL.replace("/v1/chat/completions", "/v1"),
        api_key="local",  # llama.cpp doesn't require a real key
        model="local-model",
        temperature=0.1,
        max_retries=2,
        timeout=60,
    )


# ---------------------------------------------------------------------------
# ReAct agent prompt
# ---------------------------------------------------------------------------

REACT_PROMPT_TEMPLATE = """You are an expert OpenShift SRE incident analysis agent.

You have access to the following tools:
{tools}

Use this format EXACTLY:
Thought: think about what to do
Action: tool_name
Action Input: the tool input
Observation: the tool result
... (repeat Thought/Action/Action Input/Observation as needed)
Thought: I now know the final answer
Final Answer: <your response>

For your Final Answer, you MUST call the classify_action tool last with all gathered context
and return the JSON output from classify_action as your Final Answer verbatim.

Available tool names: {tool_names}

Context about the current incident:
Alert: {alert_name}
Namespace: {namespace}
Cluster: {cluster}
Hostname: {hostname}
Correlation ID: {correlation_id}

Begin!

{agent_scratchpad}"""


# ---------------------------------------------------------------------------
# Pipeline result dataclass
# ---------------------------------------------------------------------------


@dataclass
class AgentPipelineResult:
    """Complete result from one run of run_incident_pipeline()."""

    incident_id: uuid.UUID
    intent: RemediationIntent
    risk_tier: RiskTier
    risk_reasoning: str
    tool_calls: list[dict]
    raw_agent_output: str
    action: Literal["auto_execute", "pending_approval", "escalate"]


# ---------------------------------------------------------------------------
# Main pipeline function
# ---------------------------------------------------------------------------


def run_incident_pipeline(
    incident_id: uuid.UUID,
    alert_name: str,
    namespace: str,
    cluster: str,
    hostname: str,
    correlation_id: str,
    on_status_update: Any | None = None,  # callable(incident_id, status, notes)
) -> AgentPipelineResult:
    """
    Run the full 5-step LangChain agent pipeline for one incident.

    Parameters
    ----------
    incident_id:
        UUID of the incident record in incidents_v2.
    alert_name, namespace, cluster, hostname, correlation_id:
        Alert context fields from the normalized event.
    on_status_update:
        Optional async callback invoked on every status change.
        Signature: on_status_update(incident_id, new_status, notes)

    Returns
    -------
    AgentPipelineResult with intent, risk_tier, and routing action.
    """

    def _notify(status: str, notes: str = ""):
        if on_status_update:
            on_status_update(incident_id, status, notes)

    # ------------------------------------------------------------------
    # Step 1: Context gathering — run info tools before ReAct loop
    # ------------------------------------------------------------------
    _notify("ANALYZING", "Gathering context from k8s, Prometheus, runbooks, history")

    pod_status_raw = get_pod_status.invoke(
        {"namespace": namespace, "pod_name": hostname.split(".")[0]}
    )
    prometheus_raw = query_prometheus.invoke(
        {
            "metric_query": f'ALERTS{{alertname="{alert_name}", alertstate="firing"}}',
            "cluster": cluster,
        }
    )
    runbook_raw = lookup_runbook.invoke({"alert_name": alert_name})
    history_raw = get_incident_history.invoke(
        {"cluster": cluster, "alert_name": alert_name}
    )

    # Aggregate context for classify_action
    context_payload = json.dumps(
        {
            "alert_name": alert_name,
            "namespace": namespace,
            "cluster": cluster,
            "hostname": hostname,
            "pod_status": json.loads(pod_status_raw),
            "prometheus_data": json.loads(prometheus_raw),
            "runbook_context": json.loads(runbook_raw),
            "incident_history": json.loads(history_raw),
        }
    )

    # ------------------------------------------------------------------
    # Step 2: ReAct agent — produce RemediationIntent via classify_action
    # ------------------------------------------------------------------
    _notify("ANALYZING", "Running ReAct classification agent")

    llm = _get_llm()
    prompt = PromptTemplate.from_template(REACT_PROMPT_TEMPLATE)

    agent = create_react_agent(llm=llm, tools=ALL_TOOLS, prompt=prompt)
    executor = AgentExecutor(
        agent=agent,
        tools=ALL_TOOLS,
        verbose=True,
        max_iterations=8,
        handle_parsing_errors=True,
        return_intermediate_steps=True,
    )

    agent_result = executor.invoke(
        {
            "alert_name": alert_name,
            "namespace": namespace,
            "cluster": cluster,
            "hostname": hostname,
            "correlation_id": correlation_id,
        }
    )

    raw_output: str = agent_result.get("output", "")
    intermediate_steps: list = agent_result.get("intermediate_steps", [])

    # Collect tool call log for llm_decisions
    tool_calls: list[dict] = []
    for step in intermediate_steps:
        action_obj, observation = step
        tool_calls.append(
            {
                "tool": getattr(action_obj, "tool", "unknown"),
                "input": getattr(action_obj, "tool_input", {}),
                "output": str(observation)[:1000],
            }
        )

    # ------------------------------------------------------------------
    # Step 3: Validation — parse and validate the classify_action output
    # ------------------------------------------------------------------
    _notify("ANALYZING", "Validating intent schema and action allowlist")

    try:
        intent = RemediationIntent.model_validate_json(raw_output)
    except Exception:
        # Try direct classify_action call with the gathered context as fallback
        fallback_raw = classify_action.invoke({"context_json": context_payload})
        intent = RemediationIntent.model_validate_json(fallback_raw)

    # Allowlist validation
    if not is_action_allowed(intent.action) and intent.action != "escalate":
        intent = RemediationIntent(
            action="escalate",
            namespace=intent.namespace,
            target=intent.target,
            reason=f"Action '{intent.action}' is not in the approved allowlist.",
            confidence=0.0,
        )

    # ------------------------------------------------------------------
    # Step 4: Risk scoring — HARDCODED, NO LLM
    # ------------------------------------------------------------------
    risk_tier = classify_risk(intent)
    risk_reasoning = get_risk_reasoning(intent, risk_tier)

    # ------------------------------------------------------------------
    # Step 5: Route
    # ------------------------------------------------------------------
    if risk_tier == "LOW":
        action = "auto_execute"
        _notify("EXECUTING", f"Risk=LOW. Auto-executing via AWX. {risk_reasoning}")
    elif risk_tier == "HIGH":
        action = "pending_approval"
        _notify("PENDING_APPROVAL", f"Risk=HIGH. Awaiting human approval. {risk_reasoning}")
    else:  # ESCALATE
        action = "escalate"
        _notify("ESCALATED", f"Risk=ESCALATE. Paging oncall. {risk_reasoning}")

    return AgentPipelineResult(
        incident_id=incident_id,
        intent=intent,
        risk_tier=risk_tier,
        risk_reasoning=risk_reasoning,
        tool_calls=tool_calls,
        raw_agent_output=raw_output,
        action=action,
    )
