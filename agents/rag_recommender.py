import requests
import psycopg2
# pyrefly: ignore [missing-import]
from sentence_transformers import SentenceTransformer
from agents.base_agent import BaseSreAgent
from agents.config import LLM_API_URL, EMBED_MODEL_NAME

class RAGRecommenderAgent(BaseSreAgent):
    """
    Agent 2: RAG Recommender (Cognitive LLM + Vector Hybrid)
    Vector queries playbooks and incident post-mortems. Generates remediation plan and score.
    """
    def __init__(self, embed_model_name=EMBED_MODEL_NAME, llm_url=LLM_API_URL):
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
        short_desc = f"Alert '{alertname}' firing in namespace '{state['namespace']}' on host '{state.get('hostname', 'unknown')}'"
        query_vector = self.embed_model.encode(short_desc).tolist()
        
        # Query closest playbooks, incident resolutions, and official runbooks using HYBRID SEARCH
        search_keyword = f"%{alertname}%"
        cur.execute("""
            SELECT * FROM (
                SELECT source_id, source_table, text_chunk, 
                       CASE WHEN source_id ILIKE %s THEN (embedding <-> %s::vector) - 0.4 ELSE (embedding <-> %s::vector) END AS distance
                FROM operational_knowledge_embeddings
                UNION ALL
                SELECT rhokp_id AS source_id, section_type AS source_table, raw_text AS text_chunk, 
                       CASE WHEN rhokp_id ILIKE %s THEN (embedding <-> %s::vector) - 0.4 ELSE (embedding <-> %s::vector) END AS distance
                FROM rhokp_knowledge
            ) AS combined_results
            WHERE distance < 0.75
            ORDER BY distance
            LIMIT 2;
        """, (search_keyword, query_vector, query_vector, search_keyword, query_vector, query_vector))
        
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
            "Using ONLY the context below, output a strictly typed JSON object representing the remediation intent.\n"
            "The JSON must have this exact structure: {\"action\": \"restart_pod|delete_pvc|scale_deployment|escalate_to_support|patch_resource|delete_resource|drain_node\", \"namespace\": \"...\", \"target\": \"...\"}\n"
            "For the 'target' field, you MUST use the specific host or object name provided in the ALERT, rather than generic terms from the context.\n"
            "Do NOT output any raw bash commands, explanations, or markdown formatting."
        )
        user_prompt = f"VERIFIED CONTEXT:\n{context_str}\n\nALERT:\n{short_desc}"
        
        try:
            response = requests.post(self.llm_url, json={
                "messages": [
                    {"role": "system", "content": system_instructions},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.2
            }, timeout=45)
            if response.status_code == 200:
                proposed_action = response.json()["choices"][0]["message"]["content"].strip()
                # Clean up any markdown code blocks the LLM might have added
                if proposed_action.startswith("```json"):
                    proposed_action = proposed_action[7:]
                elif proposed_action.startswith("```"):
                    proposed_action = proposed_action[3:]
                if proposed_action.endswith("```"):
                    proposed_action = proposed_action[:-3]
                proposed_action = proposed_action.strip()
        except Exception as e:
            print(f"[{self.name}] LLM API Call Error: {e}")

        if not proposed_action:
            # Fallback deterministic structured JSON
            if rows:
                print(f"[{self.name}] Warning: LLM failed to generate intent. Defaulting to safe investigation fallback.")
                proposed_action = '{"action": "investigate", "namespace": "' + state.get('namespace', 'unknown') + '", "target": "requires-human-review"}'
            else:
                proposed_action = '{"action": "investigate", "namespace": "' + state.get('namespace', 'unknown') + '", "target": "cluster"}'
        if proposed_action and proposed_action.startswith("{"):
            import json
            try:
                parsed = json.loads(proposed_action)
                extracted_action = parsed.get("action", "")
                if extracted_action in ["drain_node", "patch_resource"]:
                    risk_level = "high"
                elif extracted_action in ["delete_resource", "delete_pvc"]:
                    risk_level = "high" if risk_level == "high" else "medium"
            except Exception:
                pass

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
