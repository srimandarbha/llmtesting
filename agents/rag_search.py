import os
import re
import sys
import logging
import argparse
import psycopg2
from sentence_transformers import SentenceTransformer

# Silence diagnostics
os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)


class RAGQueryClient:
    def __init__(self):
        self.db_config = {
            "dbname": "rhokp",
            "user": "postgres",
            "password": "postgres",
            "host": "localhost",
            "port": "5432"
        }
        print("Loading local semantic embedding layers (all-MiniLM-L6-v2)...", file=sys.stderr)
        self.embed_model = SentenceTransformer('all-MiniLM-L6-v2')

    def fetch_kb_context(self, user_input):
        """
        Dual-mode selection engine. Resolves direct keys instantly, extracts matching
        tokens out of complex questions, or shifts globally to HNSW for natural language.
        """
        cleaned_input = user_input.strip()
        if not cleaned_input:
            return "Empty input received."
        
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
        except Exception as e:
            return f"Database Connection Error: {e}"

        # Mode 1: Exact Alert Key Match Check
        cur.execute("SELECT COUNT(*) FROM rhokp_knowledge WHERE rhokp_id = %s;", (cleaned_input,))
        if cur.fetchone()[0] > 0:
            print(f"\n[Mode: Direct Key Lookup] Exact alert matched for: '{cleaned_input}'", file=sys.stderr)
            cur.execute("""
                SELECT section_type, raw_text FROM rhokp_knowledge 
                WHERE rhokp_id = %s 
                ORDER BY CASE WHEN section_type = 'mitigation' THEN 1 ELSE 2 END;
            """, (cleaned_input,))
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return "\n\n".join([row[1] for row in rows])

        # Mode 2: Hybrid Query Parsing (Extract alert names out of natural sentences)
        alert_tokens = re.findall(r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b', cleaned_input)
        if alert_tokens:
            target_alert = alert_tokens[0]
            cur.execute("SELECT COUNT(*) FROM rhokp_knowledge WHERE rhokp_id = %s;", (target_alert,))
            if cur.fetchone()[0] > 0:
                print(f"\n[Mode: Hybrid Targeted Search] Isolated alert context for '{target_alert}' inside question.", file=sys.stderr)
                query_vector = self.embed_model.encode(cleaned_input).tolist()
                cur.execute("""
                    SELECT section_type, raw_text, (embedding <-> %s::vector) AS distance
                    FROM rhokp_knowledge
                    WHERE rhokp_id = %s
                    ORDER BY embedding <-> %s::vector
                    LIMIT 2;
                """, (query_vector, target_alert, query_vector))
                rows = cur.fetchall()
                cur.close()
                conn.close()
                return "\n\n".join([row[1] for row in rows])

        # Mode 3: Fallback Vector Semantic HNSW Search
        print(f"\n[Mode: Global HNSW Semantic Search] Traversing vector index for query: '{cleaned_input}'", file=sys.stderr)
        query_vector = self.embed_model.encode(cleaned_input).tolist()
        
        cur.execute("""
            SELECT rhokp_id, section_type, raw_text, (embedding <-> %s::vector) AS distance
            FROM rhokp_knowledge
            ORDER BY embedding <-> %s::vector
            LIMIT 2;
        """, (query_vector, query_vector))
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        if rows:
            nearest_distance = rows[0][3]
            print(f" -> Nearest HNSW match: KCS-{rows[0][0]} (Distance: {nearest_distance:.4f})", file=sys.stderr)
            if nearest_distance > 1.1:
                return (
                    "No relevant details found in the RAG database for this query.\n"
                    "I don't know the solution steps for this alert. Please reach out to Red Hat support."
                )
            return "\n\n".join([row[2] for row in rows])
        
        return "No relevant documentation or runbook snippets found inside the index."


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RHOKP pgvector RAG CLI Query Client Tool")
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("-a", "--alertname", type=str, default="CollectorNodeDown", help="Target alertname token to search")
    group.add_argument("-i", "--interactive", action="store_true", help="Launch interactive REPL shell")

    args = parser.parse_args()
    client = RAGQueryClient()

    if args.interactive:
        print("\n" + "="*60)
        print("RHOKP RAG Interactive Shell Initialized.")
        print("Enter any AlertName or ask a question. Type 'exit' to close.")
        print("="*60)
        while True:
            try:
                user_prompt = input("\nrag-shell> ")
                if user_prompt.strip().lower() in ["exit", "quit"]:
                    break
                if not user_prompt.strip():
                    continue
                print("\n--- Context Results ---")
                print(client.fetch_kb_context(user_prompt))
                print("-" * 23)
            except KeyboardInterrupt:
                break
    else:
        result = client.fetch_kb_context(args.alertname)
        print("\n" + "="*60 + "\nRETRIEVED RAG CONTEXT\n" + "="*60)
        print(result)