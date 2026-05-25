import os
import re
import sys
import logging
import requests
import psycopg2
# pyrefly: ignore [missing-import]
from sentence_transformers import SentenceTransformer
from agents.config import DATABASE_TARGET, LLM_API_URL, EMBED_MODEL_NAME

# Silence Hugging Face logging noise completely
os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)


class OpenShiftSREAgent:
    def __init__(self):
        # Your persistent session database credentials applied automatically
        self.db_config = DATABASE_TARGET
        # 1. Your Local Retrieval Layer (all-MiniLM-L6-v2)
        print("Loading local semantic vector layers...", file=sys.stderr)
        self.embed_model = SentenceTransformer(EMBED_MODEL_NAME)
        
        # 2. FIX: OpenAI-compatible Endpoint hosted natively by llama.cpp
        self.llm_v1_url = LLM_API_URL

    def get_raw_rag_context(self, user_input):
        """Your existing pgvector search logic to pull ground-truth runbooks"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        
        query_vector = self.embed_model.encode(user_input).tolist()
        cur.execute("""
            SELECT raw_text FROM rhokp_knowledge
            ORDER BY embedding <-> %s::vector
            LIMIT 2;
        """, (query_vector,))
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        return "\n\n".join([row[0] for row in rows]) if rows else "No runbook context found."

    def invoke_sre_agent(self, user_query):
        """Fetches pieces together: Query -> Retrieve Context -> Build Chat Payload -> llama.cpp Inference"""
        
        # Step A: Pull the raw text snippet from your pgvector database
        print(f"\n[Step 1] Retrieving runbook context for: '{user_query}'...")
        raw_context = self.get_raw_rag_context(user_query)
        
        # Step B: Set up system directives to ground the model and avoid hallucinations
        system_instructions = (
            "You are an advanced, specialized Site Reliability Engineer (SRE) Autonomous Assistant managing "
            "an enterprise Red Hat OpenShift cluster fleet.\n\n"
            "Your objective is to answer the user query using ONLY the verified Runbook Context provided. "
            "If the context doesn't contain relevant instructions, tell the user exactly what commands to "
            "run to inspect the state, but do not make up a solution.\n\n"
            "Verify all CLI tools used match OpenShift standards ('oc' instead of 'kubectl')."
        )
        
        user_message_content = f"VERIFIED RUNBOOK CONTEXT:\n{raw_context}\n\nUSER INCIDENT QUERY:\n{user_query}"

        # Step C: Formulate standard ChatCompletion structure for llama.cpp
        payload = {
            "messages": [
                {"role": "system", "content": system_instructions},
                {"role": "user", "content": user_message_content}
            ],
            "temperature": 0.2,   # Lower temperature ensures strict technical accuracy
            "stream": False
        }
        
        print("[Step 2] Routing context-grounded prompt to local llama.cpp engine...")
        try:
            response = requests.post(self.llm_v1_url, json=payload, timeout=60)
            if response.status_code == 200:
                # Extract clean string out of the open standard choices array
                return response.json()["choices"][0]["message"]["content"]
            else:
                return f"llama.cpp Server Error ({response.status_code}): {response.text}"
        except requests.exceptions.ConnectionError:
            return "\n[Execution Alert] Could not connect to llama.cpp on port 8080! Ensure your binary server is running."


# --- RUNTIME EXECUTION ---
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Query RAG and invoke SRE Agent")
    parser.add_argument("--query", type=str, required=True, help="The query string to search for")
    args = parser.parse_args()

    agent = OpenShiftSREAgent()
    
    final_solution = agent.invoke_sre_agent(args.query)
    print("\n" + "="*70)
    print("FINAL CONTEXT-GROUNDED SRE REMEDIATION INSTRUCTION:")
    print("="*70)
    print(final_solution)