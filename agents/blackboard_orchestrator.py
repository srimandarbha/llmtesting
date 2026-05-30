import os
import sys
import json
import argparse
import psycopg2
from datetime import datetime

# Silence Hugging Face diagnostics
os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

# Import modular agents
from agents.telemetry_aggregator import TelemetryAggregatorAgent
from agents.live_state_validator import LiveStateValidationAgent
from agents.rag_recommender import RAGRecommenderAgent
from agents.gatekeeper_decider import GatekeeperDeciderAgent
from agents.config import DATABASE_TARGET

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
        print(f"Initializing Blackboard reasoning for Alert: {initial_state.get('alertname')}")
        print("Correlation ID: " + str(initial_state.get("correlation_id", "None")))
        print("="*60)
        
        current_state = initial_state.copy()
        for agent in self.agents:
            try:
                current_state = agent.execute(current_state, self.db_config)
                
                # Short-circuit logic for live state validation
                if current_state.get("is_currently_active") is False:
                    print(f"\n[Orchestrator] Alert is no longer active. Halting pipeline.")
                    current_state["routing_decision"] = {
                        "action_type": "close_ticket",
                        "assigned_to": "system",
                        "reasoning": current_state.get("resolution_reason", "Resolved")
                    }
                    break

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
        parser.print_help()
        print("\n[FATAL ERROR] No event argument specified. You must provide --event-json or --event-file.")
        sys.exit(1)

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
    orchestrator.register_agent(LiveStateValidationAgent())
    orchestrator.register_agent(RAGRecommenderAgent())
    orchestrator.register_agent(GatekeeperDeciderAgent())
    
    # Run multi-agent logic
    final_state = orchestrator.run_pipeline(initial_state)
    
    # --- Closed-Loop Verification & Execution ---
    routing = final_state.get("routing_decision", {})
    if routing.get("action_type") == "auto_remediate":
        print("\n[Orchestrator] Executing Auto-Remediation Intent...")
        remediation_json_str = final_state.get("final_output", {}).get("remediation", "{}")
        try:
            intent = json.loads(remediation_json_str)
            action = intent.get("action")
            target = intent.get("target")
            namespace = intent.get("namespace")
            
            intent["alert_summary"] = final_state.get("final_output", {}).get("alert_summary", "")
            
            print(f"[Execution Engine] Running strictly typed intent: {action} on {target} in {namespace}")
            # Mocking the ansible command output
            ansible_cmd = f"ansible-playbook ansible_playbooks/remediate.yml --extra-vars '{json.dumps(intent)}'"
            print(f"[Execution Engine] (MOCK) Executing: {ansible_cmd}")
            
            execution_success = True # Mocking a successful run
            
            # Real atomic INSERT into agent_action_log
            conn = psycopg2.connect(**DATABASE_TARGET)
            cur = conn.cursor()
            try:
                if execution_success:
                    print("[Execution Engine] SUCCESS: Intent executed successfully.")
                    cur.execute("INSERT INTO agent_action_log (alert_fingerprint, status, created_at) VALUES (%s, %s, NOW())", (final_state.get('alert_fingerprint'), 'SUCCESS'))
                    print(f"[Database] Inserted SUCCESS log for fingerprint {final_state.get('alert_fingerprint')}")
                else:
                    raise RuntimeError("Execution engine returned non-zero exit code.")
            except Exception as e:
                raise e
            finally:
                conn.commit()
                cur.close()
                conn.close()
                
        except Exception as e:
            print(f"\n[Execution Engine] CRITICAL FAILURE: {e}")
            print("[Execution Engine] Rolling back decision to human escalation.")
            final_state["routing_decision"]["action_type"] = "manual_action"
            final_state["routing_decision"]["assigned_to"] = "human-sre-queue"
            final_state["routing_decision"]["reasoning"] += f" | ESCALATED DUE TO EXECUTION FAILURE: {e}"
            try:
                conn = psycopg2.connect(**DATABASE_TARGET)
                cur = conn.cursor()
                cur.execute("INSERT INTO agent_action_log (alert_fingerprint, status, created_at) VALUES (%s, %s, NOW())", (final_state.get('alert_fingerprint'), 'FAILED'))
                print(f"[Database] Inserted FAILED log for fingerprint {final_state.get('alert_fingerprint')}")
                conn.commit()
                cur.close()
                conn.close()
            except Exception as db_err:
                print(f"[Database Error] Failed to log error state: {db_err}")

    print(f"\n[ServiceNow] Mocking REST API call to update SNOW Incident Work Notes...")
    print(f"[ServiceNow] Attached {len(final_state.get('final_output', {}).get('alert_summary', ''))} bytes of AI diagnostic summary to ticket {final_state.get('correlation_id', 'unknown')}.")
    
    # Output final state payload
    print("\nFINAL MULTI-AGENT STATE TRANSITION JSON:\n")
    print(json.dumps(final_state, indent=2, default=str))

if __name__ == "__main__":
    main()
