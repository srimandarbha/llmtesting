import os
import sys
import json
import hashlib
import argparse
import requests
import psycopg2
from datetime import datetime
from sentence_transformers import SentenceTransformer

# Silence Hugging Face diagnostics
os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

DATABASE_TARGET = {
    "dbname": "rhokp",
    "user": "postgres",
    "password": "postgres",
    "host": "localhost",
    "port": "5432"
}

class BaseSreAgent:
    """Base class for all Blackboard agents"""
    def __init__(self, name):
        self.name = name

    def execute(self, state, db_config):
        raise NotImplementedError("Each agent must implement the execute method.")


class TelemetryAggregatorAgent(BaseSreAgent):
    """
    Agent 1: Telemetry Aggregator (0% LLM)
    Uses Kafka event JSON metadata to query database tables for cluster info, active Red Hat cases,
    and alert reoccurrence counts over the past 7 days.
    """
    def __init__(self):
        super().__init__("Telemetry Aggregator")

    def execute(self, state, db_config):
        print(f"\n[{self.name}] Connecting to PostgreSQL to aggregate alert telemetry...")
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()
        
        # Ingest Kafka payload fields from shared state
        cluster_id = state.get("cluster_id")
        namespace = state.get("namespace")
        alertname = state.get("alertname")
        
        # 1. Resolve alert fingerprint from DB
        cur.execute("""
            SELECT fingerprint, severity FROM alert_occurrences 
            WHERE alertname = %s AND namespace = %s AND cluster_id = %s;
        """, (alertname, namespace, cluster_id))
        row = cur.fetchone()
        
        if row:
            fingerprint = row[0]
            severity = row[1]
        else:
            # Fallback generation
            raw_str = f"{alertname}{namespace}prometheus{cluster_id}"
            fingerprint = hashlib.sha256(raw_str.encode("utf-8")).hexdigest()
            severity = "warning"
            
        state["alert_fingerprint"] = fingerprint
        state["severity"] = severity

        # 2. Fetch cluster metadata
        cur.execute("""
            SELECT name, openshift_version, environment 
            FROM clusters WHERE cluster_id = %s;
        """, (cluster_id,))
        cluster_info = cur.fetchone()
        cluster_name = cluster_info[0] if cluster_info else "Unknown"
        openshift_version = cluster_info[1] if cluster_info else "4.14.0"
        environment = cluster_info[2] if cluster_info else "production"

        # 3. Query reoccurrence count in the last 7 days
        cur.execute("""
            SELECT COUNT(*) FROM incidents 
            WHERE alert_fingerprint = %s AND sys_created_on > NOW() - INTERVAL '7 days';
        """, (fingerprint,))
        occurrences_last_7_days = cur.fetchone()[0] or 0

        # 4. Query recurrence aggregates
        cur.execute("""
            SELECT total_occurrences, total_incidents, reopen_count, mttr_seconds, resolution_quality_score, last_reopened_at
            FROM recurrence_intelligence WHERE fingerprint = %s;
        """, (fingerprint,))
        rec_info = cur.fetchone()
        
        total_occurrences = rec_info[0] if rec_info else 1
        total_incidents = rec_info[1] if rec_info else 1
        reopen_count = rec_info[2] if rec_info else 0
        mttr_seconds = rec_info[3] if rec_info else 0
        resolution_quality_score = float(rec_info[4]) if rec_info and rec_info[4] is not None else 100.0
        last_reopened_at = str(rec_info[5]) if rec_info and rec_info[5] else None

        # 5. Fetch associated Red Hat case details
        cur.execute("""
            SELECT c.case_id, c.title, c.status, c.resolution
            FROM redhat_cases c
            JOIN incidents i ON i.redhat_case_id = c.case_id
            WHERE i.alert_fingerprint = %s;
        """, (fingerprint,))
        cases = cur.fetchall()
        
        rh_cases = []
        for case in cases:
            rh_cases.append({
                "case_id": case[0],
                "title": case[1],
                "status": case[2],
                "resolution": case[3]
            })

        cur.close()
        conn.close()

        # Update Blackboard State
        state["operational_history"] = {
            "cluster_name": cluster_name,
            "cluster_environment": environment,
            "openshift_version": openshift_version,
            "occurrences_last_7_days": occurrences_last_7_days,
            "total_alert_occurrences": total_occurrences,
            "total_incidents_for_alert": total_incidents,
            "reopen_count": reopen_count,
            "average_mttr_seconds": mttr_seconds,
            "resolution_quality_score": resolution_quality_score,
            "last_reopened_at": last_reopened_at,
            "associated_redhat_cases": rh_cases
        }
        
        print(f"[{self.name}] Telemetry loaded. Weekly Frequency: {occurrences_last_7_days} incidents. Quality: {resolution_quality_score}%.")
        return state


class RAGRecommenderAgent(BaseSreAgent):
    """
    Agent 2: RAG Recommender (Cognitive LLM + Vector Hybrid)
    Vector queries playbooks and incident post-mortems. Generates remediation plan and score.
    """
    def __init__(self, embed_model_name='all-MiniLM-L6-v2', llm_url="http://127.0.0.1:8080/v1/chat/completions"):
        super().__init__("RAG Recommender")
        self.embed_model_name = embed_model_name
        self.llm_url = llm_url
        self._embed_model = None

    @property
    def embed_model(self):
        if self._embed_model is None:
            print(f"[{self.name}] Loading local semantic embedding layers ({self.embed_model_name})...")
            self._embed_model = SentenceTransformer(self.embed_model_name)
        return self._embed_model

    def execute(self, state, db_config):
        print(f"\n[{self.name}] Fetching semantic RAG context from pgvector database...")
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()
        
        alertname = state["alertname"]
        short_desc = f"Alert '{alertname}' firing in namespace '{state['namespace']}'"
        query_vector = self.embed_model.encode(short_desc).tolist()
        
        # Query closest playbooks and incident resolutions
        cur.execute("""
            SELECT source_id, source_table, text_chunk, (embedding <-> %s::vector) AS distance
            FROM operational_knowledge_embeddings
            ORDER BY embedding <-> %s::vector
            LIMIT 2;
        """, (query_vector, query_vector))
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        retrieved_context = []
        references = []
        best_distance = 2.0
        
        for row in rows:
            source_id, source_table, text_chunk, distance = row
            retrieved_context.append(f"[{source_table.upper()} ID: {source_id}] {text_chunk}")
            references.append(source_id)
            if distance < best_distance:
                best_distance = distance

        context_str = "\n\n".join(retrieved_context) if retrieved_context else "No documentation found."
        confidence = max(0.0, min(1.0, 1.0 - (best_distance / 1.2))) if rows else 0.50
        
        # Identify risk levels
        risk_level = "low"
        alert_lower = alertname.lower()
        if "coredns" in alert_lower or "dns" in alert_lower or "network" in alert_lower:
            risk_level = "medium"
        elif "etcd" in alert_lower or "kubevirt" in alert_lower or "apiserver" in alert_lower or "storage" in alert_lower:
            risk_level = "high"

        # Call local llama.cpp completion API if online
        proposed_action = None
        system_instructions = (
            "You are an OpenShift SRE Assistant.\n"
            "Using ONLY the context below, output a clean step-by-step remediation command block.\n"
            "Use standard OpenShift commands ('oc')."
        )
        user_prompt = f"VERIFIED CONTEXT:\n{context_str}\n\nALERT:\n{short_desc}"
        
        try:
            response = requests.post(self.llm_url, json={
                "messages": [
                    {"role": "system", "content": system_instructions},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.2
            }, timeout=5)
            if response.status_code == 200:
                proposed_action = response.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            pass

        if not proposed_action:
            # Fallback deterministic text chunk extract
            if rows:
                primary_chunk = rows[0][2]
                if "remediation:" in primary_chunk.lower():
                    parts = primary_chunk.lower().split("remediation:")
                    proposed_action = f"Mitigation: {parts[1].strip().capitalize()}"
                elif "resolution notes:" in primary_chunk.lower():
                    parts = primary_chunk.lower().split("resolution notes:")
                    proposed_action = f"Resolution: {parts[1].split('|')[0].strip().capitalize()}"
                else:
                    proposed_action = f"Follow steps in {rows[0][0]}: {primary_chunk[:180]}..."
            else:
                proposed_action = "Run 'oc get pods -A' and verify health checks for operator workloads."

        # Update Blackboard State
        state["remediation_plan"] = {
            "proposed_action": proposed_action,
            "confidence_score": round(confidence, 4),
            "risk_level": risk_level,
            "reference_sources": references,
            "retrieved_context": retrieved_context
        }
        
        print(f"[{self.name}] Synthesised plan. Confidence: {confidence:.2%}, Risk: {risk_level.upper()}")
        return state


class GatekeeperDeciderAgent(BaseSreAgent):
    """
    Agent 3: Gatekeeper Decider (Cognitive LLM/Policy Decider)
    Reviews reoccurrence rates, cluster envs, and LLM confidence scores.
    If the alert has recurred frequently (occurrences_last_7_days >= 5) and confidence
    indicates the automated plan won't resolve the underlying issue, it escalates to human queue.
    Synthesizes the complete alert summary.
    """
    def __init__(self, llm_url="http://127.0.0.1:8080/v1/chat/completions"):
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
                f"reopen count and support cases suggests a deeper systemic problem that requires human SRE inspection).\n\n"
                f"Alert Name: {state['alertname']}\n"
                f"Namespace: {state['namespace']}\n"
                f"Weekly Frequency: {weekly_incidents} occurrences in the last 7 days\n"
                f"Reopen Count: {reopen_count}\n"
                f"Resolution Quality Score: {quality_score}%\n"
                f"Associated Red Hat Cases: {json.dumps(history.get('associated_redhat_cases', []))}\n\n"
                f"Proposed Remediation Plan:\n{remediation.get('proposed_action', 'No recommendation.')}\n\n"
                f"Retrieved Runbook/Incident Context:\n" + ("\n".join(remediation.get('retrieved_context', [])) if remediation.get('retrieved_context') else "None") + "\n\n"
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
                    print(f"[{self.name}] LLM Reoccurrence Decision response:\n{content}")
                    if "REMEDIATION_WILL_FIX: NO" in content:
                        llm_decision = "NO"
                        reason_part = content.split("REMEDIATION_WILL_FIX: NO")[-1].strip(" :-\n")
                        llm_reason = reason_part if reason_part else "LLM decided the remediation will not fix the issue."
                    elif "REMEDIATION_WILL_FIX: YES" in content:
                        llm_decision = "YES"
                        reason_part = content.split("REMEDIATION_WILL_FIX: YES")[-1].strip(" :-\n")
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

        if escalate_to_human:
            action_type = "manual_action"
            assigned_to = "human-sre-queue"

        reasoning = " ".join(reasoning_parts)

        # --- Generate Alert Summary & Remediation Steps ---
        proposed_action = remediation.get("proposed_action", "No recommendation.")
        retrieved = remediation.get("retrieved_context", [])
        cases = history.get("associated_redhat_cases", [])

        # Create structured references block
        ref_block = "RAG References:\n"
        if retrieved:
            for r in retrieved:
                ref_block += f" - {r.split(']')[0] + ']'}\n"
        if cases:
            ref_block += "Red Hat Cases:\n"
            for c in cases:
                ref_block += f" - [{c['case_id']}] {c['title']} (Status: {c['status']})\n"
        if not retrieved and not cases:
            ref_block += " - No prior documents/support tickets available."

        alert_summary = (
            f"### SRE Outage Alert Summary\n"
            f"- **Alert**: {state['alertname']} (Namespace: {state['namespace']})\n"
            f"- **Cluster**: {state['cluster_id']} ({history.get('cluster_name', 'Unknown')})\n"
            f"- **Hostname**: {state.get('hostname', 'unknown-host')}\n"
            f"- **Trigger Time**: {state.get('startAt', 'unknown-time')}\n"
            f"- **Correlation ID**: {state.get('correlation_id', 'none')}\n\n"
            f"### Incident Telemetry & Trends\n"
            f"- **Weekly Frequency**: {weekly_incidents} incidents created on this cluster in the last 7 days.\n"
            f"- **Reopen History**: {reopen_count} total ticket reopens.\n"
            f"- **Resolution Quality**: {quality_score:.2f}% calculated SRE satisfaction.\n\n"
            f"### Referenced Support Sources\n"
            f"{ref_block}\n"
            f"### Decision Routing Reasoning\n"
            f"{reasoning}"
        )

        # Try to synthesize using llama.cpp if online
        try:
            context_str = "\n".join(retrieved) if retrieved else "No RAG context retrieved."
            summary_prompt = (
                f"Compile a summary and remediation plan based on these details:\n"
                f"Cluster: {state['cluster_id']}\nHostname: {state.get('hostname')}\n"
                f"Alert: {state['alertname']}\nWeekly frequency: {weekly_incidents}\n"
                f"RAG details: {context_str}\nDecision: {action_type} - {reasoning}"
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


class BlackboardOrchestrator:
    """Manages agent registration, state transitions, and the pipeline execution loop"""
    def __init__(self, db_config):
        self.db_config = db_config
        self.agents = []

    def register_agent(self, agent):
        self.agents.append(agent)
        print(f"Registered agent: {agent.name}")

    def run_pipeline(self, initial_state):
        print("\n" + "="*60)
        print(f"Initializing Blackboard reasoning for Alert: {initial_state['alertname']}")
        print("Correlation ID: " + initial_state.get("correlation_id", "None"))
        print("="*60)
        
        current_state = initial_state.copy()
        for agent in self.agents:
            try:
                current_state = agent.execute(current_state, self.db_config)
            except Exception as e:
                print(f"[Orchestrator Error] Agent '{agent.name}' failed to execute: {e}")
                import traceback
                traceback.print_exc()
                sys.exit(1)
                
        print("\n" + "="*60)
        print("Reasoning process completed successfully.")
        print("="*60)
        return current_state


def main():
    parser = argparse.ArgumentParser(description="Kafka SRE Alert Multi-Agent Orchestrator")
    parser.add_argument("--event-json", type=str, help="Raw Kafka event JSON string")
    parser.add_argument("--event-file", type=str, help="Path to JSON file containing Kafka event")
    
    args = parser.parse_args()
    
    event_data = None
    if args.event_json:
        try:
            event_data = json.loads(args.event_json)
        except json.JSONDecodeError:
            # Fallback to ast.literal_eval for Python-like dict structures (handles single quotes or unescaped values)
            import ast
            try:
                event_data = ast.literal_eval(args.event_json)
            except Exception:
                print("[Error] Failed to parse --event-json argument. Please verify the JSON syntax and quote escaping.")
                raise
    elif args.event_file:
        with open(args.event_file, "r") as f:
            event_data = json.load(f)
    else:
        # Default mock event for local validation
        event_data = {
            "cluster": "prod-us-east-1",
            "hostname": "master-node-0.prod-us-east-1.openshift.com",
            "correlation_id": "kafka-correlation-10029",
            "namespace": "openshift-dns",
            "startAt": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "alertname": "CoreDNSErrorsHigh"
        }
        print("No event argument specified. Running with mock Kafka event:")
        print(json.dumps(event_data, indent=2))

    # Bootstrap initial state from Kafka event keys
    initial_state = {
        "cluster_id": event_data.get("cluster"),
        "hostname": event_data.get("hostname"),
        "correlation_id": event_data.get("correlation_id"),
        "namespace": event_data.get("namespace"),
        "startAt": event_data.get("startAt"),
        "alertname": event_data.get("alertname")
    }
    
    # Setup orchestrator
    orchestrator = BlackboardOrchestrator(db_config=DATABASE_TARGET)
    orchestrator.register_agent(TelemetryAggregatorAgent())
    orchestrator.register_agent(RAGRecommenderAgent())
    orchestrator.register_agent(GatekeeperDeciderAgent())
    
    # Run multi-agent logic
    final_state = orchestrator.run_pipeline(initial_state)
    
    # Output final state payload
    print("\nFINAL MULTI-AGENT STATE TRANSITION JSON:\n")
    print(json.dumps(final_state, indent=2))


if __name__ == "__main__":
    main()
