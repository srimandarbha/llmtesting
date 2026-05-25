import requests
from agents.base_agent import BaseSreAgent
from agents.config import PROMETHEUS_URL, SPLUNK_URL, SPLUNK_CONTROLLER_NAME

class LiveStateValidationAgent(BaseSreAgent):
    def __init__(self, prometheus_url=PROMETHEUS_URL, splunk_url=SPLUNK_URL, splunk_controller_name=SPLUNK_CONTROLLER_NAME):
        super().__init__("Live State Validator")
        self.prometheus_url = prometheus_url
        self.splunk_url = splunk_url
        self.splunk_controller_name = splunk_controller_name

    def execute(self, state, db_config):
        print(f"\n[{self.name}] Validating live alert state against Prometheus and Splunk...")
        
        cluster_id = state.get("cluster_id")
        namespace = state.get("namespace")
        alertname = state.get("alertname")
        
        is_firing = True
        argocd_resolved = False
        
        # 1. Query Prometheus
        try:
            prom_resp = requests.get(f"{self.prometheus_url}/api/v1/query", params={"query": f'ALERTS{{alertname="{alertname}", alertstate="firing"}}'}, timeout=2)
            if prom_resp.status_code == 200:
                data = prom_resp.json()
                if "data" in data and "result" in data["data"]:
                    results = data["data"]["result"]
                    if len(results) == 0:
                        is_firing = False
                        print(f"[{self.name}] Prometheus check: Alert is NO LONGER firing.")
        except Exception as e:
            print(f"[{self.name}] Failed to query Prometheus: {e}")

        # 2. Query Splunk
        try:
            splunk_query = f'search index=main app.kubernetes.io/name={self.splunk_controller_name} namespace="{namespace}" "Sync operation" "succeeded"'
            splunk_resp = requests.get(f"{self.splunk_url}/services/search/jobs/export", params={"search": splunk_query, "output_mode": "json"}, timeout=2)
            if splunk_resp.status_code == 200:
                content = splunk_resp.text
                if "Sync operation" in content and "succeeded" in content:
                    argocd_resolved = True
                    print(f"[{self.name}] Splunk check: ArgoCD recently synced this namespace successfully.")
        except Exception as e:
            print(f"[{self.name}] Failed to query Splunk: {e}")
            
        # 3. Update the Blackboard State
        if not is_firing or argocd_resolved:
            state["is_currently_active"] = False
            state["resolution_reason"] = "Auto-resolved by ArgoCD / Drift reconciled"
        else:
            state["is_currently_active"] = True
            
        return state
