import os
import sys
import logging
import requests
import psycopg2
import zipfile
import io
import shutil
import argparse
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

    def ensure_local_repo(self, repo_path="runbooks_repo"):
        """Ensures that the runbooks repository exists locally. Clones it if missing."""
        if os.path.exists(repo_path) and os.path.isdir(os.path.join(repo_path, "alerts")):
            print(f"Using existing local repository at '{repo_path}'")
            return repo_path

        print(f"Repository alerts directory not found at '{repo_path}'. Cloning from upstream...")
        import subprocess
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", "https://github.com/openshift/runbooks.git", repo_path],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print(f"Successfully cloned upstream repository to '{repo_path}'")
            return repo_path
        except Exception as git_err:
            print(f"Git clone failed: {git_err}. Attempting fallback via zip download...")
            try:
                zip_url = "https://github.com/openshift/runbooks/archive/refs/heads/master.zip"
                response = requests.get(zip_url)
                response.raise_for_status()
                with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
                    # Extracts to folder runbooks-master/
                    zip_ref.extractall(".")
                # Rename to repo_path if it doesn't conflict
                if os.path.exists("runbooks-master"):
                    if os.path.exists(repo_path):
                        shutil.rmtree(repo_path)
                    os.rename("runbooks-master", repo_path)
                    print(f"Successfully downloaded and extracted repository to '{repo_path}'")
                    return repo_path
            except Exception as zip_err:
                raise RuntimeError(
                    f"Failed to retrieve runbooks repository.\n"
                    f"Git clone error: {git_err}\n"
                    f"Zip download error: {zip_err}"
                )

    def find_alert_files(self, repo_path):
        """Scans the repository alerts/ directory recursively for all .md files."""
        alerts_dir = os.path.join(repo_path, "alerts")
        md_files = []
        for root, dirs, files in os.walk(alerts_dir):
            for file in files:
                if file.endswith(".md"):
                    full_path = os.path.join(root, file)
                    # Get operator folder name relative to alerts
                    rel_dir = os.path.relpath(root, alerts_dir)
                    operator_name = rel_dir if rel_dir != "." else "root"
                    alert_name = os.path.splitext(file)[0]
                    md_files.append({
                        "filepath": full_path,
                        "alert_name": alert_name,
                        "operator_name": operator_name
                    })
        return md_files

    def chunk_runbook_content(self, raw_md):
        """Segments the document by structural KCS boundaries: MEANING, DIAGNOSIS, MITIGATION."""
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
                namespace VARCHAR(100),      -- Operator/Namespace label
                section_type VARCHAR(30),    -- 'meaning', 'diagnosis', 'mitigation'
                raw_text TEXT,               
                embedding vector(384),
                model_name VARCHAR(255) DEFAULT 'all-MiniLM-L6-v2',
                model_version VARCHAR(50) DEFAULT '1.0'
            );

        """)
        # Ensure unique constraint exists for upsert capability
        cur.execute("""
            SELECT count(*) FROM pg_constraint WHERE conname = 'unique_alert_section_namespace';
        """)
        if cur.fetchone()[0] == 0:
            # Delete duplicates first to avoid errors when creating constraint
            cur.execute("""
                DELETE FROM rhokp_knowledge a 
                USING rhokp_knowledge b 
                WHERE a.id < b.id 
                  AND a.rhokp_id = b.rhokp_id 
                  AND a.section_type = b.section_type 
                  AND a.namespace = b.namespace;
            """)
            cur.execute("""
                ALTER TABLE rhokp_knowledge 
                ADD CONSTRAINT unique_alert_section_namespace UNIQUE (rhokp_id, section_type, namespace, model_name, model_version);
            """)
            
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_rhokp_knowledge_model 
            ON rhokp_knowledge(model_name, model_version);
        """)

            
        cur.execute("""
            CREATE INDEX IF NOT EXISTS rhokp_knowledge_hnsw_idx 
            ON rhokp_knowledge USING hnsw (embedding vector_l2_ops) 
            WITH (m = 16, ef_construction = 64);
        """)
        conn.commit()
        cur.close()
        conn.close()

    def ingest_alert_runbook(self, alert_name, repo_path="runbooks_repo"):
        """Executes full extraction, formatting, and database storage workflow for a single alert"""
        self.init_database_schema()
        self.ensure_local_repo(repo_path)
        
        # Find the alert file locally
        alert_files = self.find_alert_files(repo_path)
        matching_files = [f for f in alert_files if f["alert_name"].lower() == alert_name.lower()]
        
        if not matching_files:
            print(f"[Ingestion Error] Runbook for alert '{alert_name}' not found locally in '{repo_path}'.")
            return False

        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()

        for file_info in matching_files:
            filepath = file_info["filepath"]
            operator_name = file_info["operator_name"]
            print(f"Ingesting runbook from '{filepath}'...")
            
            with open(filepath, "r", encoding="utf-8") as f:
                raw_md = f.read()
                
            chunks = self.chunk_runbook_content(raw_md)
            
            print(f"Generating embeddings and syncing vector graph blocks for {alert_name} (Operator: {operator_name})...")
            for section_name, section_content in chunks.items():
                if not section_content:
                    continue
                
                # Context Prepend: Injects clear object tracking headers into individual text vectors
                enriched_chunk_text = (
                    f"AlertName: {alert_name} | "
                    f"Operator/Directory: {operator_name} | "
                    f"Runbook Section: {section_name.upper()} | "
                    f"Content: {section_content}"
                )
                
                # Create local vector embedding
                vector_coord = self.embed_model.encode(enriched_chunk_text).tolist()
                
                # Write row out into pgvector with UPSERT
                cur.execute("""
                    INSERT INTO rhokp_knowledge (rhokp_id, namespace, section_type, raw_text, embedding, model_name, model_version)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (rhokp_id, section_type, namespace, model_name, model_version)
                    DO UPDATE SET raw_text = EXCLUDED.raw_text, embedding = EXCLUDED.embedding;
                """, (alert_name, operator_name, section_name, enriched_chunk_text, vector_coord, 'all-MiniLM-L6-v2', '1.0'))


        conn.commit()
        cur.close()
        conn.close()
        print(f"[Success] {alert_name} runbook data layers processed into HNSW space.\n")
        return True

    def sync_all_runbooks(self, repo_path="runbooks_repo", clear_table=True):
        """Finds all alert runbook markdown files and ingests them into the RAG database."""
        self.init_database_schema()
        self.ensure_local_repo(repo_path)
        
        alert_files = self.find_alert_files(repo_path)
        if not alert_files:
            print("No alert runbook markdown files found.")
            return False
            
        print(f"Found {len(alert_files)} alert runbooks to sync.")
        
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        
        if clear_table:
            print("Clearing existing rhokp_knowledge table for clean sync...")
            cur.execute("TRUNCATE TABLE rhokp_knowledge;")
            conn.commit()
            
        success_count = 0
        for idx, file_info in enumerate(alert_files, 1):
            filepath = file_info["filepath"]
            alert_name = file_info["alert_name"]
            operator_name = file_info["operator_name"]
            
            # Avoid processing files like OWNERS or files without content
            if alert_name.upper() in ("OWNERS", "README"):
                continue
                
            print(f"[{idx}/{len(alert_files)}] Processing alert '{alert_name}' (Operator: {operator_name})...")
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    raw_md = f.read()
                    
                chunks = self.chunk_runbook_content(raw_md)
                
                for section_name, section_content in chunks.items():
                    if not section_content:
                        continue
                        
                    enriched_chunk_text = (
                        f"AlertName: {alert_name} | "
                        f"Operator/Directory: {operator_name} | "
                        f"Runbook Section: {section_name.upper()} | "
                        f"Content: {section_content}"
                    )
                    
                    vector_coord = self.embed_model.encode(enriched_chunk_text).tolist()
                    
                    # Write row out into pgvector with UPSERT
                    cur.execute("""
                        INSERT INTO rhokp_knowledge (rhokp_id, namespace, section_type, raw_text, embedding, model_name, model_version)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (rhokp_id, section_type, namespace, model_name, model_version)
                        DO UPDATE SET raw_text = EXCLUDED.raw_text, embedding = EXCLUDED.embedding;
                    """, (alert_name, operator_name, section_name, enriched_chunk_text, vector_coord, 'all-MiniLM-L6-v2', '1.0'))

                
                # Commit periodically (e.g. every 10 files) or at the end
                if idx % 10 == 0:
                    conn.commit()
                success_count += 1
            except Exception as e:
                print(f"[Warning] Failed to ingest {alert_name} from {filepath}: {e}")
                
        conn.commit()
        cur.close()
        conn.close()
        print(f"\n[Success] Ingested {success_count} alert runbooks into RAG pipeline.")
        return True


# --- RUNTIME ENTRYPOINT ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync OpenShift runbooks into RAG database (pgvector)")
    parser.add_argument("--sync-all", action="store_true", help="Sync all alerts recursively from local/cloned repository")
    parser.add_argument("--alert", type=str, help="Sync a single alert by name")
    parser.add_argument("--repo-path", type=str, default="runbooks_repo", help="Path to local openshift/runbooks repository")
    parser.add_argument("--no-clear", action="store_true", help="Do not truncate table before syncing all (ignored if not syncing all)")
    
    args = parser.parse_args()

    DATABASE_TARGET = {
        "dbname": os.environ.get("DB_NAME", "rhokp"),
        "user": os.environ.get("DB_USER", "postgres"),
        "password": os.environ.get("DB_PASSWORD", "postgres"),
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": os.environ.get("DB_PORT", "5432")
    }

    engine = OpenShiftRunbookIngestionEngine(db_config=DATABASE_TARGET)
    
    if args.sync_all:
        engine.sync_all_runbooks(repo_path=args.repo_path, clear_table=not args.no_clear)
    elif args.alert:
        engine.ingest_alert_runbook(alert_name=args.alert, repo_path=args.repo_path)
    else:
        # Default behavior: run complete sync without clearing the table (upserting)
        print("No sync action specified. Defaulting to complete sync (upserting existing entries)...")
        engine.sync_all_runbooks(repo_path=args.repo_path, clear_table=False)