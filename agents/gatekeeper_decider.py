import json
import requests
from agents.base_agent import BaseSreAgent
from agents.config import LLM_API_URL

class GatekeeperDeciderAgent(BaseSreAgent):
    """
    Agent 3: Gatekeeper Decider (Cognitive LLM/Policy Decider)
    Reviews reoccurrence rates, cluster envs, and LLM confidence scores.
    If the alert has recurred frequently (occurrences_last_7_days >= 5) and confidence
    indicates the automated plan won't resolve the underlying issue, it escalates to human queue.
    Synthesizes the complete alert summary.
    """
    def __init__(self, llm_url=LLM_API_URL):
        super().__init__("Gatekeeper Decider")
        self.llm_url = llm_url

    def execute(self, state, db_config):
        print(f"\n[{self.name}] Assessing weekly reoccurrence metrics and safety boundaries...")
        
        history = state.get("operational_history", {})
        remediation = state.get("remediation_plan", {})
        
        env = history.get("cluster_environment", "production")
        weekly_incidents = history.get("occurrences_last_7_days", 0)
        reopen_count = history.get("reopen_count", 0)
        quality_score = history.get("resolution_quality_score", 100.0)
        confidence = remediation.get("confidence_score", 0.0)
        risk = remediation.get("risk_level", "low")
        
        action_type = "auto_remediate"
        assigned_to = "auto-remediation-webhook"
        reasoning_parts = []
        escalate_to_human = False

        # --- Reoccurrence and LLM confidence verification policy ---
        if weekly_incidents >= 5:
            # Construct a prompt for the LLM to decide if the remediation will fix it
            llm_prompt = (
                f"Analyze the following OpenShift SRE alert recurrence pattern and determine if the "
                f"proposed automated remediation plan is unlikely to fix the underlying issue permanently (e.g., if the "
                f"proposed action is just a temporary band-aid, or if the reoccurrence rate combined with the "
                f"reopen count and support cases suggests a deeper systemic problem that requires human SRE inspection).\\n\\n"
                f"Alert Name: {state['alertname']}\\n"
                f"Namespace: {state['namespace']}\\n"
                f"Weekly Frequency: {weekly_incidents} occurrences in the last 7 days\\n"
                f"Reopen Count: {reopen_count}\\n"
                f"Resolution Quality Score: {quality_score}%\\n"
                f"Associated Red Hat Cases: {json.dumps(history.get('associated_redhat_cases', []))}\\n\\n"
                f"Proposed Remediation Plan:\\n{remediation.get('proposed_action', 'No recommendation.')}\\n\\n"
                f"Retrieved Runbook/Incident Context:\\n" + ("\\n".join(remediation.get('retrieved_context', [])) if remediation.get('retrieved_context') else "None") + "\\n\\n"
                f"Evaluate if this proposed remediation plan will permanently fix the issue. You MUST respond with either "
                f"'REMEDIATION_WILL_FIX: YES' or 'REMEDIATION_WILL_FIX: NO', followed by a one-sentence reason."
            )
            
            llm_decision = None
            llm_reason = None
            
            try:
                payload = {
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are an expert OpenShift SRE Gatekeeper evaluating alert auto-remediations. "
                                "Your goal is to decide whether an automated remediation is sufficient, or if "
                                "the alert must be escalated to a human because the remediation is unlikely to fix "
                                "the underlying issue permanently. Output 'REMEDIATION_WILL_FIX: YES' or "
                                "'REMEDIATION_WILL_FIX: NO' followed by your explanation."
                            )
                        },
                        {"role": "user", "content": llm_prompt}
                    ],
                    "temperature": 0.1
                }
                response = requests.post(self.llm_url, json=payload, timeout=45)
                if response.status_code == 200:
                    content = response.json()["choices"][0]["message"]["content"].strip()
                    print(f"[{self.name}] LLM Reoccurrence Decision response:\\n{content}")
                    if "REMEDIATION_WILL_FIX: NO" in content:
                        llm_decision = "NO"
                        reason_part = content.split("REMEDIATION_WILL_FIX: NO")[-1].strip(" :-\\n")
                        llm_reason = reason_part if reason_part else "LLM decided the remediation will not fix the issue."
                    elif "REMEDIATION_WILL_FIX: YES" in content:
                        llm_decision = "YES"
                        reason_part = content.split("REMEDIATION_WILL_FIX: YES")[-1].strip(" :-\\n")
                        llm_reason = reason_part if reason_part else "LLM decided the remediation will fix the issue."
            except Exception as e:
                print(f"[{self.name}] Warning: Failed to query LLM for reoccurrence decision: {e}")
            
            if llm_decision == "NO":
                escalate_to_human = True
                reasoning_parts.append(
                    f"Alert is highly reoccurring ({weekly_incidents} incidents in the last 7 days) and "
                    f"LLM decided automated remediation will not fix the issue permanently. Reason: {llm_reason}"
                )
            elif llm_decision == "YES":
                reasoning_parts.append(
                    f"Alert is highly reoccurring ({weekly_incidents} incidents in the last 7 days) but "
                    f"LLM decided automated remediation will fix the issue permanently. Reason: {llm_reason}"
                )
            else:
                # Rule-based fallback if LLM is offline or output is ambiguous
                print(f"[{self.name}] LLM decision unavailable or ambiguous. Falling back to rule-based heuristics.")
                if reopen_count > 0 or quality_score < 75.0 or confidence < 0.75:
                    escalate_to_human = True
                    reasoning_parts.append(
                        f"Alert is highly reoccurring ({weekly_incidents} incidents in the last 7 days) "
                        f"with a history of reopens ({reopen_count}) or low resolution quality ({quality_score}%). "
                        f"Rule-based fallback: automated remediation is insufficient."
                    )
                else:
                    reasoning_parts.append(
                        f"Alert is reoccurring ({weekly_incidents} times this week) but history is stable. "
                        f"Rule-based fallback: auto-remediation is allowed to proceed."
                    )
        else:
            reasoning_parts.append(f"Alert frequency is within limits ({weekly_incidents} incidents this week).")

        # --- Production Criticality policies ---
        if not escalate_to_human:
            if env == "production":
                if risk in ("high", "medium"):
                    escalate_to_human = True
                    reasoning_parts.append(
                        f"Cluster is production and remediation risk level is {risk.upper()}. "
                        f"Auto-remediation of medium/high risk alerts is restricted in prod."
                    )
            elif confidence < 0.70:
                escalate_to_human = True
                reasoning_parts.append(f"LLM confidence score ({confidence:.2%}) is below the automation gate (70%).")

        # --- High-Speed Local Circuit Breakers ---
        if not escalate_to_human:
            agent_remediations_last_24h = history.get("agent_remediations_last_24h", 0)
            last_agent_action_time = history.get("last_agent_action_time", None)
            
            # 1. Chronic Flapping Circuit Breaker
            if agent_remediations_last_24h >= 3:
                escalate_to_human = True
                reasoning_parts.append("CHRONIC FLAPPING DETECTED: Agent has applied fixes 3 times in 24h to no avail.")
                print(f"[{self.name}] 24-hour Circuit Breaker TRIPPED.")
                
            # 2. 15-Minute Cooldown
            elif last_agent_action_time:
                # Mocking the 15 minute check (in reality, compare last_agent_action_time with datetime.now())
                import datetime
                if isinstance(last_agent_action_time, datetime.datetime):
                    if (datetime.datetime.now() - last_agent_action_time).total_seconds() < 900:
                        escalate_to_human = True
                        reasoning_parts.append("Cooldown enforced. Waiting for previous automation to converge (15m lock).")
                        print(f"[{self.name}] 15-minute Cooldown TRIPPED.")
                        
        # --- JIT SNOW API Locking ---
        if not escalate_to_human:
            print(f"[{self.name}] Attempting JIT SNOW API Lock acquisition...")
            # In a real environment, this makes a synchronous REST call to SNOW to bypass DB lag
            snow_ticket_id = state.get("correlation_id", "unknown")
            recent_human = history.get("recent_human_activity", False)
            staleness = history.get("snow_db_staleness_seconds", 300)
            
            # SLA Timeout: e.g. 45 minutes without human activity
            sla_timeout_exceeded = (staleness > 2700 and not recent_human)
            
            try:
                # Mocking the direct SNOW API GET request
                mock_api_status = "In Progress" if recent_human else "New"
                mock_api_assigned_to = "Human SRE" if recent_human else ""
                
                if mock_api_status == "In Progress" or mock_api_assigned_to != "":
                    if sla_timeout_exceeded:
                        print(f"[{self.name}] JIT Lock: SLA Timeout Exceeded. Forcing Lock.")
                        reasoning_parts.append("Forced JIT Lock acquired due to SLA timeout (>45m inactivity).")
                    else:
                        print(f"[{self.name}] JIT Lock FAILED: Ticket is owned by a human.")
                        escalate_to_human = True
                        reasoning_parts.append("Aborted auto-remediation: JIT Lock failed. A human SRE is currently engaged.")
                else:
                    # Mocking the direct SNOW API PATCH request to set lock
                    print(f"[{self.name}] JIT Lock acquired successfully.")
                    reasoning_parts.append("JIT Lock acquired successfully via SNOW API.")
            except Exception as e:
                print(f"[{self.name}] Warning: JIT Lock API request failed: {e}")
                escalate_to_human = True
                reasoning_parts.append(f"Aborted auto-remediation: JIT Lock API request failed.")

        if escalate_to_human:
            action_type = "manual_action"
            assigned_to = "human-sre-queue"

        reasoning = " ".join(reasoning_parts)

        # --- Generate Alert Summary & Remediation Steps ---
        proposed_action = remediation.get("proposed_action", "No recommendation.")
        retrieved = remediation.get("retrieved_context", [])
        cases = history.get("associated_redhat_cases", [])

        # Create structured references block
        ref_block = "RAG References:\\n"
        if retrieved:
            for r in retrieved:
                ref_block += f" - {r.split(']')[0] + ']'}\\n"
        if cases:
            ref_block += "Red Hat Cases:\\n"
            for c in cases:
                ref_block += f" - [{c['case_id']}] {c['title']} (Status: {c['status']})\\n"
        if not retrieved and not cases:
            ref_block += " - No prior documents/support tickets available."

        alert_summary = (
            f"### SRE Outage Alert Summary\\n"
            f"- **Alert**: {state['alertname']} (Namespace: {state['namespace']})\\n"
            f"- **Cluster**: {state['cluster_id']} ({history.get('cluster_name', 'Unknown')})\\n"
            f"- **Hostname**: {state.get('hostname', 'unknown-host')}\\n"
            f"- **Trigger Time**: {state.get('startAt', 'unknown-time')}\\n"
            f"- **Correlation ID**: {state.get('correlation_id', 'none')}\\n\\n"
            f"### Incident Telemetry & Trends\\n"
            f"- **Weekly Frequency**: {weekly_incidents} incidents created on this cluster in the last 7 days.\\n"
            f"- **Reopen History**: {reopen_count} total ticket reopens.\\n"
            f"- **Resolution Quality**: {quality_score:.2f}% calculated SRE satisfaction.\\n\\n"
            f"### Referenced Support Sources\\n"
            f"{ref_block}\\n"
            f"### Decision Routing Reasoning\\n"
            f"{reasoning}"
        )

        # Try to synthesize using llama.cpp if online
        try:
            context_str = "\\n".join(retrieved) if retrieved else "No RAG context retrieved."
            summary_prompt = (
                f"Compile a summary and remediation plan based on these details:\\n"
                f"Cluster: {state['cluster_id']}\\nHostname: {state.get('hostname')}\\n"
                f"Alert: {state['alertname']}\\nWeekly frequency: {weekly_incidents}\\n"
                f"RAG details: {context_str}\\nDecision: {action_type} - {reasoning}"
            )
            response = requests.post(self.llm_url, json={
                "messages": [
                    {"role": "system", "content": "You compile brief summary reports of cluster alerts."},
                    {"role": "user", "content": summary_prompt}
                ],
                "temperature": 0.3
            }, timeout=5)
            if response.status_code == 200:
                alert_summary = response.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            pass

        # Update Blackboard State
        state["routing_decision"] = {
            "action_type": action_type,
            "assigned_to": assigned_to,
            "reasoning": reasoning
        }
        state["final_output"] = {
            "remediation": proposed_action,
            "alert_summary": alert_summary
        }
        
        print(f"[{self.name}] Decision: {action_type.upper()}. Escalated to human: {escalate_to_human}")
        return state
