import os
import sys
import json
import argparse
import requests
import psycopg2
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
    Queries transactional database tables to assemble historical context, flapping counts,
    and linked Red Hat support tickets.
    """
    def __init__(self):
        super().__init__("Telemetry Aggregator")

    def execute(self, state, db_config):
        print(f"\n[{self.name}] Scanning database for alert and cluster telemetry...")
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()
        
        sys_id = state["incident_id"]
        fingerprint = state["alert_fingerprint"]
        cluster_id = state["cluster_id"]
        
        # 1. Fetch cluster environment details
        cur.execute("""
            SELECT name, openshift_version, environment 
            FROM clusters WHERE cluster_id = %s;
        """, (cluster_id,))
        cluster_info = cur.fetchone()
        cluster_name = cluster_info[0] if cluster_info else "Unknown"
        openshift_version = cluster_info[1] if cluster_info else "4.14.0"
        environment = cluster_info[2] if cluster_info else "production"

        # 2. Fetch recurrence aggregates
        cur.execute("""
            SELECT total_occurrences, total_incidents, reopen_count, mttr_seconds, last_reopened_at
            FROM recurrence_intelligence WHERE fingerprint = %s;
        """, (fingerprint,))
        rec_info = cur.fetchone()
        
        total_occurrences = rec_info[0] if rec_info else 1
        total_incidents = rec_info[1] if rec_info else 1
        reopen_count = rec_info[2] if rec_info else 0
        mttr_seconds = rec_info[3] if rec_info else 0
        last_reopened_at = str(rec_info[4]) if rec_info and rec_info[4] else None

        # 3. Fetch associated Red Hat case details
        cur.execute("""
            SELECT c.case_id, c.title, c.status, c.resolution
            FROM redhat_cases c
            JOIN incidents i ON i.redhat_case_id = c.case_id
            WHERE i.sys_id = %s;
        """, (sys_id,))
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
            "total_alert_occurrences": total_occurrences,
            "total_incidents_for_alert": total_incidents,
            "reopen_count": reopen_count,
            "average_mttr_seconds": mttr_seconds,
            "last_reopened_at": last_reopened_at,
            "associated_redhat_cases": rh_cases
        }
        
        print(f"[{self.name}] Telemetry gathered for cluster '{cluster_id}' ({environment}).")
        return state


class RAGRecommenderAgent(BaseSreAgent):
    """
    Agent 2: RAG Recommender (Cognitive LLM + Vector Hybrid)
    Performs vector semantic searches to retrieve runbooks and past solutions.
    Runs LLM synthesis via llama.cpp or falls back to a deterministic recommendation template.
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
        print(f"\n[{self.name}] Retrieving relevant runbooks and past incidents from vector index...")
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()
        
        short_desc = state["short_description"]
        query_vector = self.embed_model.encode(short_desc).tolist()
        
        # Query pgvector for the closest 2 playbooks/resolutions
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

        context_str = "\n\n".join(retrieved_context) if retrieved_context else "No prior post-mortems or runbooks found."
        
        # Calculate base confidence score based on vector distance:
        # Distance of 0 = 100% confidence, distance of 1.2+ = 0% confidence
        confidence = max(0.0, min(1.0, 1.0 - (best_distance / 1.2))) if rows else 0.50
        
        # Determine risk level based on description keywords
        risk_level = "low"
        desc_lower = short_desc.lower()
        if "coredns" in desc_lower or "dns" in desc_lower or "network" in desc_lower:
            risk_level = "medium"
        elif "etcd" in desc_lower or "kubevirt" in desc_lower or "apiserver" in desc_lower or "storage" in desc_lower:
            risk_level = "high"

        # Try to synthesize using local llama.cpp completions endpoint
        proposed_action = None
        system_instructions = (
            "You are an expert OpenShift SRE Assistant.\n"
            "Using ONLY the verified context below, output a clean step-by-step remediation plan.\n"
            "Do not hallucinate and always use standard OpenShift CLI commands ('oc')."
        )
        user_prompt = f"VERIFIED CONTEXT:\n{context_str}\n\nINCIDENT TO SOLVE:\n{short_desc}"
        
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
                print(f"[{self.name}] Successfully synthesized remediation plan using local LLM.")
        except Exception:
            # Fallback to local rule-based context parsing if LLM is offline
            pass

        if not proposed_action:
            print(f"[{self.name}] LLM connection offline. Applying deterministic context synthesizer...")
            # Fallback text formatting
            if rows:
                primary_chunk = rows[0][2]
                # Try extracting resolution or mitigation steps from the chunk
                if "remediation:" in primary_chunk.lower():
                    parts = primary_chunk.lower().split("remediation:")
                    proposed_action = f"Mitigation step from RAG: {parts[1].strip().capitalize()}"
                elif "resolution notes:" in primary_chunk.lower():
                    parts = primary_chunk.lower().split("resolution notes:")
                    proposed_action = f"Historical SRE fix: {parts[1].split('|')[0].strip().capitalize()}"
                else:
                    proposed_action = f"Follow runbook guidelines found in vector source '{rows[0][0]}': {primary_chunk[:150]}..."
            else:
                proposed_action = "Inspect operator pods via 'oc get pods -A' and check event logs with 'oc get events -n openshift-monitoring'."

        # Update Blackboard State
        state["remediation_plan"] = {
            "proposed_action": proposed_action,
            "confidence_score": round(confidence, 4),
            "risk_level": risk_level,
            "reference_sources": references
        }
        
        print(f"[{self.name}] Remediation proposed. Confidence: {confidence:.2%}, Risk: {risk_level.upper()}")
        return state


class GatekeeperDeciderAgent(BaseSreAgent):
    """
    Agent 3: Gatekeeper Decider (Cognitive LLM/Policy Decider)
    Evaluates risk profiles, cluster criticality, and confidence rankings to decide the routing.
    """
    def __init__(self):
        super().__init__("Gatekeeper Decider")

    def execute(self, state, db_config):
        print(f"\n[{self.name}] Applying policy matrices to proposed SRE recommendations...")
        
        history = state.get("operational_history", {})
        remediation = state.get("remediation_plan", {})
        
        env = history.get("cluster_environment", "production")
        confidence = remediation.get("confidence_score", 0.0)
        risk = remediation.get("risk_level", "low")
        
        # Policy Evaluation logic
        action_type = "manual_action"
        assigned_to = "human-sre-queue"
        reasoning_parts = []

        # Rule 1: Hard confidence constraint
        if confidence < 0.70:
            reasoning_parts.append(f"Confidence score ({confidence:.2%}) is below the automation gate limit (70%).")
        
        # Rule 2: Production environment restrictions
        elif env == "production":
            if risk == "high":
                reasoning_parts.append("Cluster is production and risk index is HIGH. Requires human verification.")
            elif risk == "medium":
                reasoning_parts.append("Cluster is production and risk index is MEDIUM. Auto-remediation is disabled for medium-risk items in prod.")
            else:
                action_type = "auto_remediate"
                assigned_to = "auto-remediation-webhook"
                reasoning_parts.append("Cluster is production, but the risk index is LOW and confidence score matches rules. Approved for automated release.")
        
        # Rule 3: Non-production environment policies (Dev, Staging, DR)
        else:
            if risk == "high":
                reasoning_parts.append(f"Cluster environment is non-critical '{env}', but risk index is HIGH. Requires human triage.")
            else:
                action_type = "auto_remediate"
                assigned_to = "auto-remediation-webhook"
                reasoning_parts.append(f"Cluster environment is non-critical '{env}' and risk is {risk.upper()}. Approved for auto-remediation.")

        reasoning = " ".join(reasoning_parts)

        # Update Blackboard State
        state["routing_decision"] = {
            "action_type": action_type,
            "assigned_to": assigned_to,
            "reasoning": reasoning
        }
        
        print(f"[{self.name}] Action complete. Decision: {action_type.upper()} -> Routed to: {assigned_to}")
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
        print(f"Initializing Blackboard reasoning for Incident {initial_state['number']}")
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


def bootstrap_initial_state(db_config, incident_identifier):
    """Queries the database to construct the initial blackboard payload dictionary"""
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor()
    
    # Query incident details
    cur.execute("""
        SELECT sys_id, number, alert_fingerprint, cluster_id, short_description 
        FROM incidents 
        WHERE sys_id = %s OR number = %s;
    """, (incident_identifier, incident_identifier))
    row = cur.fetchone()
    cur.close()
    conn.close()
    
    if not row:
        print(f"[Error] Incident '{incident_identifier}' not found in database.")
        sys.exit(1)
        
    return {
        "incident_id": row[0],
        "number": row[1],
        "alert_fingerprint": row[2],
        "cluster_id": row[3],
        "short_description": row[4]
    }


def main():
    parser = argparse.ArgumentParser(description="ServiceNow Incident SRE Multi-Agent Orchestration CLI")
    parser.add_argument("--incident", type=str, required=True, help="Incident number (INCXXXX) or ServiceNow sys_id")
    
    args = parser.parse_args()
    
    # Bootstrap state
    initial_state = bootstrap_initial_state(DATABASE_TARGET, args.incident)
    
    # Setup orchestrator
    orchestrator = BlackboardOrchestrator(db_config=DATABASE_TARGET)
    
    # Register agents in pipeline order
    orchestrator.register_agent(TelemetryAggregatorAgent())
    orchestrator.register_agent(RAGRecommenderAgent())
    orchestrator.register_agent(GatekeeperDeciderAgent())
    
    # Run pipeline
    final_state = orchestrator.run_pipeline(initial_state)
    
    # Output final state payload
    print("\nFINAL MULTI-AGENT STATE TRANSITION JSON:\n")
    print(json.dumps(final_state, indent=2))


if __name__ == "__main__":
    main()
