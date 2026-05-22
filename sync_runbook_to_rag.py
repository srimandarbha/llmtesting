import os
import sys
import logging
import requests
import psycopg2
from sentence_transformers import SentenceTransformer

# Silence Hugging Face diagnostics completely
os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)


class OpenShiftRunbookIngestionEngine:
    def __init__(self, db_config):
        self.db_config = db_config
        print("Initializing local semantic embedding layers (all-MiniLM-L6-v2)...")
        self.embed_model = SentenceTransformer('all-MiniLM-L6-v2') # 384 dimensions

    def clean_markdown_to_text(self, md_content):
        """Strips clean prose lines out of typical runbook markdown blocks"""
        import re
        # Remove bold accents, inline backticks, and lists
        text = md_content.replace("**", "").replace("`", "").replace(" - ", " ")
        # Strip structural link identifiers [text](url)
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        return "\n".join([line.strip() for line in text.splitlines() if line.strip()])

    def fetch_and_chunk_runbook(self, alert_name):
        """
        Connects directly to the upstream raw GitHub source for OpenShift Virtualization Runbooks.
        Segments the document by structural KCS boundaries: MEANING, DIAGNOSIS, MITIGATION.
        """
        # Formulate direct raw path to the targeted runbook file
        github_raw_url = (
            f"https://raw.githubusercontent.com/openshift/runbooks/master/"
            f"alerts/openshift-virtualization-operator/{alert_name}.md"
        )
        
        print(f"Connecting to raw repository context for alert: {alert_name}...")
        response = requests.get(github_raw_url)
        
        if response.status_code != 200:
            raise FileNotFoundError(
                f"Runbook for alert '{alert_name}' not found on upstream master branch.\n"
                f"Checked URL: {github_raw_url}\n"
                f"Verify that the alert name exactly matches the markdown file filename."
            )

        raw_md = response.text
        
        # Segment definitions using landmarks native to the openshift/runbooks structure
        sections = {"meaning": "", "diagnosis": "", "mitigation": ""}
        
        # Parse text boundaries based on prominent markdown headers
        lines = raw_md.splitlines()
        current_section = None
        section_accumulator = []

        for line in lines:
            line_upper = line.upper()
            if line.startswith("#"):
                # Save previous tracking block before hopping boundaries
                if current_section and section_accumulator:
                    sections[current_section] = "\n".join(section_accumulator).strip()
                    section_accumulator = []
                
                # Identify incoming structural region
                if "MEANING" in line_upper:
                    current_section = "meaning"
                elif "DIAGNOSIS" in line_upper:
                    current_section = "diagnosis"
                elif "MITIGATION" in line_upper or "REMEDIAL" in line_upper:
                    current_section = "mitigation"
                else:
                    current_section = None
            elif current_section:
                section_accumulator.append(line)

        # Catch remaining buffer chunk
        if current_section and section_accumulator:
            sections[current_section] = "\n".join(section_accumulator).strip()

        # Sanity check: if the runbook doesn't have standard headers, drop the full cleaned text into diagnosis
        if not any(sections.values()):
            sections["diagnosis"] = raw_md

        # Clean markdown characters out of each gathered segment
        for key in sections:
            sections[key] = self.clean_markdown_to_text(sections[key])

        return sections

    def init_database_schema(self):
        """Initializes database layers, structural targets, and the HNSW graph index"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rhokp_knowledge (
                id SERIAL PRIMARY KEY,
                rhokp_id VARCHAR(100),       -- Holds the dynamic Alert Name string
                title TEXT,                  -- Human-friendly runbook label
                section_type VARCHAR(30),    -- 'meaning', 'diagnosis', 'mitigation'
                raw_text TEXT,               
                embedding vector(384)
            );
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS rhokp_knowledge_hnsw_idx 
            ON rhokp_knowledge USING hnsw (embedding vector_l2_ops) 
            WITH (m = 16, ef_construction = 64);
        """)
        conn.commit()
        cur.close()
        conn.close()

    def ingest_alert_runbook(self, alert_name):
        """Executes full extraction, formatting, and database storage workflow"""
        self.init_database_schema()
        
        try:
            chunks = self.fetch_and_chunk_runbook(alert_name)
        except Exception as e:
            print(f"[Ingestion Error] Pipeline execution halted: {e}")
            return False

        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()

        # Clear any existing chunks for this runbook to prevent duplicate entries on re-runs
        cur.execute("DELETE FROM rhokp_knowledge WHERE rhokp_id = %s;", (alert_name,))

        print(f"Generating embeddings and syncing vector graph blocks for {alert_name}...")
        for section_name, section_content in chunks.items():
            if not section_content:
                continue
            
            # Context Prepend: Injects clear object tracking headers into individual text vectors
            enriched_chunk_text = (
                f"AlertName: {alert_name} | "
                f"Runbook Section: {section_name.upper()} | "
                f"Content: {section_content}"
            )
            
            # Create local vector embedding
            vector_coord = self.embed_model.encode(enriched_chunk_text).tolist()
            
            # Write row out into pgvector
            cur.execute("""
                INSERT INTO rhokp_knowledge (rhokp_id, title, section_type, raw_text, embedding)
                VALUES (%s, %s, %s, %s, %s);
            """, (alert_name, f"{alert_name} Runbook Documentation", section_name, enriched_chunk_text, vector_coord))

        conn.commit()
        cur.close()
        conn.close()
        print(f"[Success] {alert_name} runbook data layers processed into HNSW space.\n")
        return True


# --- RUNTIME ENTRYPOINT ---
if __name__ == "__main__":
    DATABASE_TARGET = {
        "dbname": "rhokp",
        "user": "postgres",
        "password": "postgres",
        "host": "localhost",
        "port": "5432"
    }

    # Input parameter tracking from external orchestration triggers
    # Try common OpenShift Virtualization alerting scenarios like:
    # 'KubeVirtNoAvailableNodesToRunVMs' or 'VirtualMachineStuckInUnhealthyState'
    TARGET_ALERT = "KubeVirtNoAvailableNodesToRunVMs"

    engine = OpenShiftRunbookIngestionEngine(db_config=DATABASE_TARGET)
    engine.ingest_alert_runbook(alert_name=TARGET_ALERT)