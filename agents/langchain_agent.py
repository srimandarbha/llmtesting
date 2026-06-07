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
import re
from dataclasses import dataclass

def _extract_json_string(text: str) -> str:
    """Extracts JSON object from a string using brace counting to handle nesting."""
    start_idx = text.find('{')
    if start_idx == -1:
        return text
    
    brace_count = 0
    for i in range(start_idx, len(text)):
        if text[i] == '{':
            brace_count += 1
        elif text[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                return text[start_idx:i+1]
                
    return text

from typing import Any, Literal

from langchain.agents.agent import AgentExecutor
from langchain.agents.react.agent import create_react_agent
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
import psycopg2

from agents.config import LLM_API_URL, LLM_API_KEY, LLM_MODEL
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
from agents.config import DATABASE_TARGET

# ---------------------------------------------------------------------------
# LLM Observability Callback Handler
# ---------------------------------------------------------------------------

class IncidentTimelineCallbackHandler(BaseCallbackHandler):
    """Logs LLM intermediate steps (thoughts, tools, errors) to the database timeline."""
    
    def __init__(self, incident_id: uuid.UUID):
        self.incident_id = str(incident_id)

    def _log_to_db(self, action: str, notes: str = "", metadata: dict | None = None):
        try:
            conn = psycopg2.connect(**DATABASE_TARGET)
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO incident_timeline (incident_id, actor_type, action, notes, metadata_json)
                VALUES (%s, 'agent', %s, %s, %s)
                """,
                (self.incident_id, action, notes, json.dumps(metadata) if metadata else None)
            )
            conn.commit()
            cur.close()
            conn.close()
        except Exception:
            pass  # Best effort

    def on_agent_action(self, action: Any, **kwargs: Any) -> None:
        """Fires when the agent decides to use a tool, logging its internal thought process."""
        if hasattr(action, "log") and action.log:
            # ReAct format: "Thought: ...\nAction: ..."
            thought = action.log.split("Action:")[0].strip()
            if thought:
                self._log_to_db("LLM Thought", notes=thought)

    def on_tool_start(self, serialized: dict, input_str: str, **kwargs: Any) -> None:
        tool_name = serialized.get("name", "unknown_tool")
        if tool_name == "_Exception":
            return
        self._log_to_db(f"Executing Tool: {tool_name}", notes=f"Input: {input_str}")

    def on_tool_error(self, error: BaseException, **kwargs: Any) -> None:
        self._log_to_db("Tool Execution Failed", notes=str(error))

    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        self._log_to_db("LLM Generation Error", notes=str(error))


# ---------------------------------------------------------------------------
# LLM client — points at the existing llama.cpp compatible endpoint
# ---------------------------------------------------------------------------


def _get_llm():
    """
    Returns a ChatOpenAI instance pointed at the local LLM endpoint.
    Compatible with llama.cpp server, Ollama, and OpenAI API.
    Set LLM_API_URL in .env to switch providers.
    """
    from agents.config import USE_MOCK_LLM
    if USE_MOCK_LLM:
        from langchain_core.language_models.chat_models import BaseChatModel
        from langchain_core.messages import AIMessage
        from langchain_core.outputs import ChatResult, ChatGeneration
        
        class MockLLM(BaseChatModel):
            def _generate(self, messages, stop=None, run_manager=None, **kwargs):
                return ChatResult(generations=[ChatGeneration(message=AIMessage(content='''Thought: I have gathered the context.
Final Answer: {
  "action": "delete_pvc",
  "namespace": "machine-config-operator",
  "target": "pvc-aul12345",
  "reason": "Simulating a HIGH risk remediation action.",
  "confidence": 0.95,
  "analysis_summary": "Mock analysis summary for PVC deletion.",
  "escalate_to": "Storage-Admin"
}'''))])
            
            @property
            def _llm_type(self) -> str:
                return "mock"
                
        return MockLLM()

    return ChatOpenAI(
        base_url=LLM_API_URL.replace("/v1/chat/completions", "/v1"),
        api_key=LLM_API_KEY if LLM_API_KEY else "local",
        model=LLM_MODEL,
        temperature=0.1,
        max_retries=2,
        timeout=60,
        model_kwargs={"extra_body": {"reasoning": {"enabled": True}}},
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
Action Input: a valid JSON object containing the tool arguments
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
        json.dumps({"namespace": namespace, "pod_name": hostname.split(".")[0]})
    )
    prometheus_raw = query_prometheus.invoke(
        json.dumps({
            "metric_query": f'ALERTS{{alertname="{alert_name}", alertstate="firing"}}',
            "cluster": cluster,
        })
    )
    runbook_raw = lookup_runbook.invoke(alert_name)
    history_raw = get_incident_history.invoke(
        json.dumps({"cluster": cluster, "alert_name": alert_name})
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
    
    timeline_cb = IncidentTimelineCallbackHandler(incident_id)
    
    executor = AgentExecutor(
        agent=agent,
        tools=ALL_TOOLS,
        verbose=True,
        max_iterations=8,
        handle_parsing_errors=True,
        return_intermediate_steps=True,
        callbacks=[timeline_cb],
    )

    try:
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
    except Exception as e:
        # LLM parsing errors or max iterations hit
        raw_output = str(e)
        intermediate_steps = []

    # Collect tool call log for llm_decisions
    tool_calls: list[dict] = []
    for step in intermediate_steps:
        action_obj, observation = step
        tool_name = getattr(action_obj, "tool", "unknown")
        
        # Skip Langchain's internal parsing errors from showing up in the UI
        if tool_name == "_Exception":
            continue
            
        tool_calls.append(
            {
                "tool": tool_name,
                "input": getattr(action_obj, "tool_input", {}),
                "output": str(observation)[:1000],
            }
        )

    # ------------------------------------------------------------------
    # Step 3: Validation — parse and validate the classify_action output
    # ------------------------------------------------------------------
    _notify("ANALYZING", "Validating intent schema and action allowlist")

    try:
        clean_raw = _extract_json_string(raw_output)
        intent = RemediationIntent.model_validate_json(clean_raw)
    except Exception:
        # Try direct classify_action call with the gathered context as fallback
        fallback_prompt = classify_action.invoke({"context_json": context_payload})
        fallback_msg = llm.invoke(fallback_prompt)
        clean_fallback = _extract_json_string(fallback_msg.content)
        intent = RemediationIntent.model_validate_json(clean_fallback)

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
