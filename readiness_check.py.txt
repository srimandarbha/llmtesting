import os
import psycopg2
import urllib.request
import logging
from typing import Dict, Any

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def check_postgres(db_config: Dict[str, Any]) -> bool:
    try:
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()
        
        # Check pgvector extension and table
        cur.execute("SELECT extname FROM pg_extension WHERE extname = 'vector';")
        ext = cur.fetchone()
        if ext:
            logging.info("PostgreSQL: pgvector extension is installed.")
        else:
            logging.warning("PostgreSQL: pgvector extension NOT found.")
            
        cur.execute("SELECT count(*) FROM rhokp_cve_knowledge;")
        count = cur.fetchone()[0]
        logging.info(f"PostgreSQL: Connected successfully. rhokp_cve_knowledge has {count} rows.")
        
        cur.close()
        conn.close()
        return True
    except Exception as e:
        logging.error(f"PostgreSQL: Connection failed - {e}")
        return False

def check_api(url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{url}/health", timeout=3) as response:
            if response.status == 200:
                logging.info("FastAPI: Health check passed.")
                return True
            else:
                logging.warning(f"FastAPI: Returned status {response.status}")
                return False
    except Exception as e:
        logging.error(f"FastAPI: Connection failed - {e}")
        return False

if __name__ == "__main__":
    logging.info("Running System Readiness Check...")
    
    # 1. Create Test Directories if they don't exist
    for d in ["tests/api", "tests/worker", "tests/evals"]:
        os.makedirs(d, exist_ok=True)
        init_file = os.path.join(d, "__init__.py")
        if not os.path.exists(init_file):
            with open(init_file, "w") as f:
                pass
    logging.info("Test directories created: tests/api, tests/worker, tests/evals")
    
    # 2. Check Database
    db_config = {
        "dbname": "rhokp",
        "user": "postgres",
        "password": "postgres",
        "host": "localhost",
        "port": "5432"
    }
    db_ok = check_postgres(db_config)
    
    # 3. Check API
    api_ok = check_api("http://localhost:8000")
    
    if db_ok and api_ok:
        logging.info("System is READY for tests.")
    else:
        logging.warning("System is NOT fully ready.")
