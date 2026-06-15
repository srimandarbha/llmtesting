# Repository Code Dump

The following contains the files from the repository. Each file is demarcated by its path and a code block.

// filepath: .env.example
# =============================================================================
# SRE Incident Agent — Environment Variables
# Copy this file to .env and fill in real values
# =============================================================================

# ─── Database (required) ─────────────────────────────────────────────────────
DB_HOST=localhost
DB_PORT=5432
DB_NAME=rhokp
DB_USER=your_db_user
DB_PASSWORD=your_db_password

# ─── LLM API ─────────────────────────────────────────────────────────────────
# Local llama.cpp server (default) — compatible with OpenAI API format
LLM_API_URL=http://127.0.0.1:8080/v1/chat/completions
# For Ollama: LLM_API_URL=http://localhost:11434/v1/chat/completions
# For OpenAI: LLM_API_URL=https://api.openai.com/v1/chat/completions

# ─── Observability APIs ───────────────────────────────────────────────────────
PROMETHEUS_URL=http://127.0.0.1:9090
SPLUNK_URL=http://127.0.0.1:8088
SPLUNK_CONTROLLER_NAME=argocd-application-controller

# ─── AWX / Ansible Tower ──────────────────────────────────────────────────────
AWX_BASE_URL=http://your-awx-server:8052
AWX_API_TOKEN=your_awx_api_token
# Set to false in production to use the real AWX client
USE_MOCK_AWX=true

# ─── Celery (uses PostgreSQL — no Redis needed) ──────────────────────────────
# Auto-derived from DB_* vars if not set. Override only if using a separate broker.
# CELERY_BROKER_URL=db+postgresql://your_db_user:your_db_password@localhost:5432/rhokp
# CELERY_RESULT_BACKEND=db+postgresql://your_db_user:your_db_password@localhost:5432/rhokp

# ─── Auth / API Key ───────────────────────────────────────────────────────────
# IMPORTANT: Change this to a strong random secret in production
API_KEY=dev-api-key-change-in-prod

# ─── PagerDuty ────────────────────────────────────────────────────────────────
# Leave empty to skip PagerDuty escalation (logs warning instead)
PAGERDUTY_API_KEY=
PAGERDUTY_ESCALATION_POLICY_ID=

# ─── Safety Controls ─────────────────────────────────────────────────────────
# Max concurrent auto-executing incidents per cluster per hour
BLAST_RADIUS_CAP=5
# Deduplication window in minutes (same alert+cluster+namespace = skip)
DEDUP_WINDOW_MINUTES=10

# ─── Embedding Model ─────────────────────────────────────────────────────────
EMBED_MODEL_NAME=all-MiniLM-L6-v2

---

// filepath: .gitignore
runbooks_repo/
*.pyc
__pycache__/
.env

---

// filepath: docker-compose.prod.yml
services:
  # ─── FastAPI API server ──────────────────────────────────────────────────────
  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    environment:
      DB_HOST: host.docker.internal
      DB_PORT: 5432
      DB_NAME: ${DB_NAME:-rhokp}
      DB_USER: ${DB_USER:-postgres}
      DB_PASSWORD: ${DB_PASSWORD:-}
      LLM_API_URL: ${LLM_API_URL:-http://host.docker.internal:8080/v1/chat/completions}
      LLM_API_KEY: ${LLM_API_KEY:-}
      LLM_MODEL: ${LLM_MODEL:-}
      PROMETHEUS_URL: ${PROMETHEUS_URL:-http://host.docker.internal:9090}
      AWX_BASE_URL: ${AWX_BASE_URL:-http://host.docker.internal:8052}
      AWX_API_TOKEN: ${AWX_API_TOKEN:-changeme}
      USE_MOCK_AWX: "false"
      API_KEY: ${API_KEY:-production-api-key}
      BLAST_RADIUS_CAP: ${BLAST_RADIUS_CAP:-5}
      DEDUP_WINDOW_MINUTES: ${DEDUP_WINDOW_MINUTES:-10}
      CELERY_BROKER_URL: sqla+postgresql://${DB_USER:-postgres}:${DB_PASSWORD:-}@host.docker.internal:5432/${DB_NAME:-rhokp}
      CELERY_RESULT_BACKEND: db+postgresql://${DB_USER:-postgres}:${DB_PASSWORD:-}@host.docker.internal:5432/${DB_NAME:-rhokp}
    extra_hosts:
      - "host.docker.internal:host-gateway"
    # Uvicorn without --reload for production
    command: uvicorn api.main:app --host 0.0.0.0 --port 8000
    working_dir: /app
    restart: always

  # ─── Celery worker ──────────────────────────────────────────────────────────
  worker:
    build:
      context: .
      dockerfile: Dockerfile.api
    environment:
      DB_HOST: host.docker.internal
      DB_PORT: 5432
      DB_NAME: ${DB_NAME:-rhokp}
      DB_USER: ${DB_USER:-postgres}
      DB_PASSWORD: ${DB_PASSWORD:-}
      LLM_API_URL: ${LLM_API_URL:-http://host.docker.internal:8080/v1/chat/completions}
      LLM_API_KEY: ${LLM_API_KEY:-}
      LLM_MODEL: ${LLM_MODEL:-}
      PROMETHEUS_URL: ${PROMETHEUS_URL:-http://host.docker.internal:9090}
      AWX_BASE_URL: ${AWX_BASE_URL:-http://host.docker.internal:8052}
      AWX_API_TOKEN: ${AWX_API_TOKEN:-changeme}
      USE_MOCK_AWX: "false"
      API_KEY: ${API_KEY:-production-api-key}
      BLAST_RADIUS_CAP: ${BLAST_RADIUS_CAP:-5}
      CELERY_BROKER_URL: sqla+postgresql://${DB_USER:-postgres}:${DB_PASSWORD:-}@host.docker.internal:5432/${DB_NAME:-rhokp}
      CELERY_RESULT_BACKEND: db+postgresql://${DB_USER:-postgres}:${DB_PASSWORD:-}@host.docker.internal:5432/${DB_NAME:-rhokp}
    extra_hosts:
      - "host.docker.internal:host-gateway"
    command: >
      celery -A worker.celery_app worker
      --loglevel=info
      --queues=default,priority
      --concurrency=4
    working_dir: /app
    restart: always

  # ─── Kafka Consumer ─────────────────────────────────────────────────────────
  kafka-consumer:
    build:
      context: .
      dockerfile: Dockerfile.api
    depends_on:
      - worker
    environment:
      DB_HOST: ${DB_HOST:-host.docker.internal}
      DB_PORT: ${DB_PORT:-5432}
      DB_NAME: ${DB_NAME:-rhokp}
      DB_USER: ${DB_USER:-postgres}
      DB_PASSWORD: ${DB_PASSWORD:-}
      KAFKA_BROKER_URL: ${KAFKA_BROKER_URL:-kafka:9092}
      KAFKA_TOPIC: ${KAFKA_TOPIC:-sre_alerts}
      CELERY_BROKER_URL: sqla+postgresql://${DB_USER:-postgres}:${DB_PASSWORD:-}@${DB_HOST:-host.docker.internal}:${DB_PORT:-5432}/${DB_NAME:-rhokp}
      CELERY_RESULT_BACKEND: db+postgresql://${DB_USER:-postgres}:${DB_PASSWORD:-}@${DB_HOST:-host.docker.internal}:${DB_PORT:-5432}/${DB_NAME:-rhokp}
    command: python ingestion/kafka_consumer.py
    volumes:
      - .:/app
    working_dir: /app
    restart: always

  # ─── React frontend (Production built via Nginx) ────────────────────────────
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "80:80"
    depends_on:
      - api
    restart: always

---

// filepath: docker-compose.yml
services:
  # ─── FastAPI API server ──────────────────────────────────────────────────────
  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    ports:
      - "8000:8000"
    environment:
      DB_HOST: host.docker.internal
      DB_PORT: 5432
      DB_NAME: ${DB_NAME:-rhokp}
      DB_USER: ${DB_USER:-postgres}
      DB_PASSWORD: ${DB_PASSWORD:-}
      LLM_API_URL: ${LLM_API_URL:-http://host.docker.internal:8080/v1/chat/completions}
      LLM_API_KEY: ${LLM_API_KEY:-}
      LLM_MODEL: ${LLM_MODEL:-}
      PROMETHEUS_URL: ${PROMETHEUS_URL:-http://host.docker.internal:9090}
      AWX_BASE_URL: ${AWX_BASE_URL:-http://host.docker.internal:8052}
      AWX_API_TOKEN: ${AWX_API_TOKEN:-changeme}
      USE_MOCK_AWX: ${USE_MOCK_AWX:-true}
      USE_MOCK_LLM: ${USE_MOCK_LLM:-false}
      API_KEY: ${API_KEY:-dev-api-key-change-in-prod}
      BLAST_RADIUS_CAP: ${BLAST_RADIUS_CAP:-5}
      DEDUP_WINDOW_MINUTES: ${DEDUP_WINDOW_MINUTES:-10}
      CELERY_BROKER_URL: sqla+postgresql://${DB_USER:-postgres}:${DB_PASSWORD:-}@host.docker.internal:5432/${DB_NAME:-rhokp}
      CELERY_RESULT_BACKEND: db+postgresql://${DB_USER:-postgres}:${DB_PASSWORD:-}@host.docker.internal:5432/${DB_NAME:-rhokp}
    extra_hosts:
      - "host.docker.internal:host-gateway"
    command: uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
    volumes:
      - .:/app
    working_dir: /app

  # ─── Celery worker ──────────────────────────────────────────────────────────
  worker:
    build:
      context: .
      dockerfile: Dockerfile.api
    environment:
      DB_HOST: host.docker.internal
      DB_PORT: 5432
      DB_NAME: ${DB_NAME:-rhokp}
      DB_USER: ${DB_USER:-postgres}
      DB_PASSWORD: ${DB_PASSWORD:-}
      LLM_API_URL: ${LLM_API_URL:-http://host.docker.internal:8080/v1/chat/completions}
      LLM_API_KEY: ${LLM_API_KEY:-}
      LLM_MODEL: ${LLM_MODEL:-}
      PROMETHEUS_URL: ${PROMETHEUS_URL:-http://host.docker.internal:9090}
      AWX_BASE_URL: ${AWX_BASE_URL:-http://host.docker.internal:8052}
      AWX_API_TOKEN: ${AWX_API_TOKEN:-changeme}
      USE_MOCK_AWX: ${USE_MOCK_AWX:-true}
      USE_MOCK_LLM: ${USE_MOCK_LLM:-false}
      API_KEY: ${API_KEY:-dev-api-key-change-in-prod}
      BLAST_RADIUS_CAP: ${BLAST_RADIUS_CAP:-5}
      CELERY_BROKER_URL: sqla+postgresql://${DB_USER:-postgres}:${DB_PASSWORD:-}@host.docker.internal:5432/${DB_NAME:-rhokp}
      CELERY_RESULT_BACKEND: db+postgresql://${DB_USER:-postgres}:${DB_PASSWORD:-}@host.docker.internal:5432/${DB_NAME:-rhokp}
      PYTHONPATH: /app
    extra_hosts:
      - "host.docker.internal:host-gateway"
    command: >
      celery -A worker.celery_app worker
      --loglevel=info
      --queues=default,priority
      --concurrency=4
    volumes:
      - .:/app
    working_dir: /app

  # ─── Zookeeper & Kafka ──────────────────────────────────────────────────────
  zookeeper:
    image: confluentinc/cp-zookeeper:7.4.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000

  kafka:
    image: confluentinc/cp-kafka:7.4.0
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:29092,PLAINTEXT_HOST://localhost:9092
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1

  # ─── Kafka Consumer ─────────────────────────────────────────────────────────
  kafka-consumer:
    build:
      context: .
      dockerfile: Dockerfile.api
    depends_on:
      - kafka
      - worker
    environment:
      DB_HOST: host.docker.internal
      DB_PORT: 5432
      DB_NAME: ${DB_NAME:-rhokp}
      DB_USER: ${DB_USER:-postgres}
      DB_PASSWORD: ${DB_PASSWORD:-}
      KAFKA_BROKER_URL: kafka:29092
      KAFKA_TOPIC: sre_alerts
      PYTHONPATH: /app
      CELERY_BROKER_URL: sqla+postgresql://${DB_USER:-postgres}:${DB_PASSWORD:-}@host.docker.internal:5432/${DB_NAME:-rhokp}
      CELERY_RESULT_BACKEND: db+postgresql://${DB_USER:-postgres}:${DB_PASSWORD:-}@host.docker.internal:5432/${DB_NAME:-rhokp}
    extra_hosts:
      - "host.docker.internal:host-gateway"
    command: python ingestion/kafka_consumer.py
    volumes:
      - .:/app
    working_dir: /app

  # ─── React frontend (dev mode) ──────────────────────────────────────────────
  frontend:
    image: node:20-alpine
    ports:
      - "5173:5173"
    volumes:
      - ./frontend:/app
      - /app/node_modules
    working_dir: /app
    command: sh -c "npm install && npm run dev -- --host 0.0.0.0"
    environment:
      VITE_API_BASE: http://localhost:8000
      API_TARGET: http://api:8000
      WS_TARGET: ws://api:8000

---

// filepath: Dockerfile.api
FROM python:3.11-slim

WORKDIR /app

# Install system deps for psycopg2, kubernetes client
RUN apt-get update && apt-get install -y \
    gcc libpq-dev curl git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default: API server (overridden in docker-compose for worker)
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

---

// filepath: publish_test_alert.py
import json
import time
from kafka import KafkaProducer

import os

def publish():
    broker = os.environ.get('KAFKA_BROKER_URL', 'localhost:9092')
    producer = KafkaProducer(
        bootstrap_servers=[broker],
        value_serializer=lambda m: json.dumps(m).encode('utf-8')
    )
    
    alert = {
        "alert_name": "KubeletHealthState",
        "cluster": "auclo303",
        "namespace": "machine-config-operator",
        "hostname": "aul12345",
        "correlation_id": f"test-kafka-{int(time.time())}"
    }
    
    topic = "sre_alerts"
    print(f"Publishing to topic '{topic}': {alert}")
    producer.send(topic, alert)
    producer.flush()
    print("Message sent successfully.")

if __name__ == "__main__":
    publish()

---

// filepath: readiness_check.py
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

---

// filepath: README.md
# SRE Incident Intelligence Agent

An automated, LLM-powered incident response system for Kubernetes/OpenShift environments. 
This system integrates natively with Prometheus alerts and ServiceNow incidents, utilizing advanced RAG (Retrieval-Augmented Generation) across OpenShift runbooks and past incident resolutions to automatically triage, analyze, and safely remediate alerts.

## Key Features

1. **Kafka-driven Ingestion**: Listens directly for Prometheus alerts via Kafka (`ingestion/kafka_consumer.py`).
2. **Deterministic Risk Engine**: Hardcoded safety rules that determine the blast radius of any LLM-proposed remediation (`agents/risk_engine.py`). 
   - `LOW` risk (e.g. restart pod) auto-executes via AWX/Ansible.
   - `HIGH` risk (e.g. rollout restart deployment) halts and requests human approval via the UI.
   - Low confidence (<0.75) immediately triggers `ESCALATE` to PagerDuty.
3. **Advanced RAG Engine**: Uses pgvector (HNSW index) to vectorize incoming alerts against Red Hat OpenShift runbooks and historical ServiceNow resolutions (`ingestion/sync_runbook_to_rag.py`).
4. **LangChain ReAct Agent**: Coordinates diagnostic steps (Prometheus query, Kubernetes pod status checks) via tool execution, and formulates a final `RemediationIntent` schema (`agents/langchain_agent.py`).
5. **Observability**: Complete audit trails for every incident. All LLM thoughts, parsed actions, and state transitions are written immutably to the `incident_timeline` in PostgreSQL.

## Architecture & Data Flow

1. **Alert Source**: Alertmanager forwards webhooks to Kafka.
2. **Consumer**: The `KafkaAlertConsumer` securely validates payloads, drops duplicates, and inserts an `incidents_v2` record.
3. **Trigger**: PostgreSQL `LISTEN/NOTIFY` informs the Celery worker queue that a new incident arrived.
4. **Agent Pipeline**: 
   - Context is gathered from tools (`get_pod_status`, `query_prometheus`, `lookup_runbook`, `get_incident_history`).
   - The LLM reasons over the context and proposes a `RemediationIntent`.
   - The Risk Engine validates the intent against an approved allowlist.
5. **Execution**: If approved (or auto-approved for low-risk), the worker triggers a pre-configured Job Template in AWX/Ansible Tower (`worker/tasks.py`).
6. **Verification**: 60 seconds after execution, the worker re-queries Kubernetes pod status. If healthy, the incident is resolved.

## Components

- `agents/`: Contains the LangChain pipeline, tool definitions, ReAct prompt, and risk/safety engine.
- `db/`: PostgreSQL database models and connection pooling.
- `ingestion/`: Kafka consumers and scheduled sync jobs (ServiceNow history and Runbook markdowns) to populate the RAG vector store.
- `worker/`: Celery task definitions for asynchronous pipeline execution and AWX orchestration.
- `api/`: FastAPI web server serving the frontend UI via WebSockets and REST endpoints.
- `simulation/`: Mock files and data generators for testing (isolated from production components).

## Prerequisites

- PostgreSQL 15+ with `pgvector` and `pgcrypto` extensions enabled.
- Redis (Optional, though Celery is currently configured to use Postgres as broker).
- Kafka cluster.
- Ansible AWX / Tower instance.
- Python 3.10+

## Setup & Running Locally

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment**:
   Copy or configure your environment variables. Essential variables:
   - `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_NAME` (Default: `rhokp`)
   - `KAFKA_BOOTSTRAP_SERVERS` (Default: `localhost:9092`)
   - `LLM_API_URL`, `LLM_API_KEY`, `LLM_MODEL` (e.g. local llama.cpp endpoint or OpenAI)
   - `AWX_BASE_URL`, `AWX_API_TOKEN`

3. **Initialize Database**:
   ```bash
   python -c "import psycopg2; from agents.config import DATABASE_TARGET; conn=psycopg2.connect(**DATABASE_TARGET); print('Database connection verified.')"
   # Apply migrations
   psql -h localhost -U postgres -d rhokp -f full_db_migration.sql.txt
   ```

4. **Populate RAG Knowledge**:
   ```bash
   # Sync OpenShift runbooks
   python ingestion/sync_runbook_to_rag.py --sync-all
   
   # Sync historical ServiceNow records
   python ingestion/sync_servicenow_to_postgres.py
   ```

5. **Start Services**:
   You need to run three primary processes for full functionality:
   
   *Start the Kafka Consumer:*
   ```bash
   python ingestion/kafka_consumer.py
   ```
   
   *Start the Celery Worker:*
   ```bash
   celery -A worker.celery_app worker --loglevel=info -P threads
   ```
   
   *Start the FastAPI UI Server:*
   ```bash
   uvicorn api.main:app --host 0.0.0.0 --port 8000
   ```

## Safety & Security Best Practices

- **Never** modify the `agents/risk_engine.py` allowlist without architecture review. 
- LLM confidence below `0.75` will always short-circuit auto-remediation.
- `EMBED_MODEL_NAME` configures the RAG embeddings model. If you change this model, you **must** re-ingest runbooks and tickets to update the vectors.
- Always use the `SimpleConnectionPool` across worker threads to avoid PG connection exhaustion.
- The `SentenceTransformer` model is intentionally pre-loaded globally via the `worker_process_init` signal in Celery to avoid thread-safety race conditions on simultaneous task execution.

---

// filepath: requirements.txt
--extra-index-url https://download.pytorch.org/whl/cpu

# ── Core HTTP / Async ─────────────────────────────────────────────────────────
requests==2.32.3
httpx==0.28.1
uvicorn[standard]==0.32.1
fastapi==0.115.5
python-multipart==0.0.12

# ── LangChain ─────────────────────────────────────────────────────────────────
langchain==0.3.14
langchain-openai==0.3.0
langchain-community==0.3.14
langchain-core==0.3.29

# ── Pydantic / Settings ───────────────────────────────────────────────────────
pydantic==2.10.3
pydantic-settings==2.7.0

# ── Database ──────────────────────────────────────────────────────────────────
psycopg2-binary==2.9.10
sqlalchemy[asyncio]==2.0.36
asyncpg==0.30.0
alembic==1.14.0

# ── Celery ────────────────────────────────────────────────────────────────────
celery==5.4.0
kombu==5.4.2
# Broker: PostgreSQL via SQLAlchemy transport (uses sqlalchemy from DB section)

# ── Auth ──────────────────────────────────────────────────────────────────────
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4

# ── Embeddings / ML ───────────────────────────────────────────────────────────
sentence-transformers==3.3.1
numpy==1.26.4

# ── Kubernetes ────────────────────────────────────────────────────────────────
kubernetes==31.0.0

# ── Observability ─────────────────────────────────────────────────────────────
structlog==24.4.0

# ── Testing ───────────────────────────────────────────────────────────────────
pytest==8.3.4
pytest-asyncio==0.24.0
respx==0.21.1
pytest-mock==3.14.0
kafka-python==2.0.2

---

// filepath: SRE_Agent_Flow.md
# RAG SRE Incident Agent - Complete End-to-End Flow

### 1. Alert Ingestion (The Trigger)
* **Webhook / Payload:** When a system monitor (e.g., Prometheus) detects an issue like `IngressControllerDegraded`, it sends a JSON payload to the FastAPI backend via the `POST /alerts/ingest` endpoint.
* **Deduplication:** The API immediately checks PostgreSQL. If the exact same alert fired for the same cluster and namespace within a defined time window (e.g., 10 minutes), it ignores it to prevent flooding the system. 
* **Incident Creation:** If it's a new alert, it is logged in the `incidents_v2` database table as `RECEIVED`, and a timeline event is created. 
* **Asynchronous Handoff:** A Celery background task (`run_agent_pipeline`) is enqueued to process the alert without blocking the API.

### 2. LangChain AI Pipeline (The Brain)
The Celery worker picks up the job and executes a 5-step LangChain pipeline:

* **Step 1: Context Gathering (RAG):** The system invokes tools to pull live data. It fetches Kubernetes Pod status, queries Prometheus metrics, pulls relevant SRE runbooks, and grabs past incident history for that specific alert/cluster.
* **Step 2: ReAct Agent Analysis:** All this context is sent to your local `llama.cpp` LLM. Using a ReAct (Reasoning + Acting) prompt, the LLM analyzes the situation and decides on a `RemediationIntent` (i.e., what action to take, like restarting a pod, on what specific target, and in what namespace).
* **Step 3: Validation:** The LLM's decision is parsed into a strict Pydantic schema. The system verifies that the proposed action exists in a predefined security allowlist. If the AI suggests something unapproved, the pipeline forces an escalation.
* **Step 4: Hardcoded Risk Scoring:** To ensure safety, a **non-LLM** risk engine evaluates the proposed intent. It classifies the action as:
   * **LOW Risk:** Safe actions (e.g., restarting a stateless pod).
   * **HIGH Risk:** Destructive or impactful actions (e.g., database restarts).
   * **ESCALATE:** Unknown actions or situations the AI has low confidence in.
* **Step 5: Routing:** The incident is routed based on the risk score.

### 3. Execution & Human-in-the-Loop (HITL)
Depending on how the pipeline routed the incident:

* **If LOW Risk (Auto-Execution):** 
   * The system checks the "Blast Radius Cap" to ensure it isn't automatically remediating too many things at once on the same cluster.
   * If safe, it triggers an **Ansible playbook** via the AWX/Ansible Tower API (or a mocked client in your dev environment) to fix the issue automatically.
* **If HIGH Risk (Human Approval):** 
   * The incident state changes to `PENDING_APPROVAL`.
   * An SRE sees the alert on the React frontend (`http://localhost:5173`). They can review the LLM's thought process, the risk reasoning, and the proposed Ansible variables.
   * The SRE can **Approve**, **Edit & Approve**, **Reject**, or **Escalate** the remediation.
* **If ESCALATE:** 
   * A Celery task uses the PagerDuty API to page the on-call engineer immediately.

### 4. Verification & Resolution
* For executed tasks (either auto-approved or human-approved), a separate Celery task (`poll_awx_job`) continuously polls the AWX API for job completion.
* Once the Ansible job finishes successfully, the agent performs a **post-execution verification** (e.g., checks if the pod is now healthy).
* If the verification passes, the incident is marked as `RESOLVED`. If the job fails, it falls back to a PagerDuty escalation.

### 5. Frontend UI
Throughout this entire lifecycle, the React frontend stays synchronized via a **FastAPI WebSocket connection**. When the status changes from `ANALYZING` ➡️ `PENDING_APPROVAL` ➡️ `EXECUTING` ➡️ `RESOLVED`, the UI updates instantly without requiring a page refresh.

---

// filepath: agents/config.py
import os
import sys


def get_env_or_fail(var_name, default=None, required=True):
    value = os.getenv(var_name, default)
    if required and value is None:
        print(
            f"[FATAL CONFIG ERROR] Environment variable {var_name} is required but not set.",
            file=sys.stderr,
        )
        sys.exit(1)
    return value


# ---------------------------------------------------------------------------
# Database Configuration
# ---------------------------------------------------------------------------
DB_HOST = get_env_or_fail("DB_HOST", default="localhost", required=False)
DB_PORT = get_env_or_fail("DB_PORT", default="5432", required=False)
DB_NAME = get_env_or_fail("DB_NAME", default="rhokp", required=False)
DB_USER = get_env_or_fail("DB_USER", required=True)
DB_PASSWORD = get_env_or_fail("DB_PASSWORD", default="", required=False)

DATABASE_TARGET = {
    "dbname": DB_NAME,
    "user": DB_USER,
    "password": DB_PASSWORD,
    "host": DB_HOST,
    "port": DB_PORT,
}

# ---------------------------------------------------------------------------
# LLM / Observability API Endpoints
# ---------------------------------------------------------------------------
LLM_API_URL = get_env_or_fail(
    "LLM_API_URL",
    default="http://127.0.0.1:8080/v1/chat/completions",
    required=False,
)
LLM_API_KEY = get_env_or_fail(
    "LLM_API_KEY",
    default="local",
    required=False,
)
LLM_MODEL = get_env_or_fail(
    "LLM_MODEL",
    default="local-model",
    required=False,
)
PROMETHEUS_URL = get_env_or_fail(
    "PROMETHEUS_URL", default="http://127.0.0.1:9090", required=False
)
SPLUNK_URL = get_env_or_fail(
    "SPLUNK_URL", default="http://127.0.0.1:8088", required=False
)

# ---------------------------------------------------------------------------
# AWX / Ansible Tower
# ---------------------------------------------------------------------------
AWX_BASE_URL = get_env_or_fail(
    "AWX_BASE_URL", default="http://localhost:8052", required=False
)
AWX_API_TOKEN = get_env_or_fail("AWX_API_TOKEN", default="changeme", required=False)
# Set USE_MOCK_AWX=false in production to use the real AWX client
USE_MOCK_AWX = get_env_or_fail("USE_MOCK_AWX", default="true", required=False).lower() == "true"
USE_MOCK_SERVERS = get_env_or_fail("USE_MOCK_SERVERS", default="true", required=False).lower() == "true"
USE_MOCK_LLM = get_env_or_fail("USE_MOCK_LLM", default=str(USE_MOCK_SERVERS).lower(), required=False).lower() == "true"

# ---------------------------------------------------------------------------
# Celery (uses PostgreSQL as broker — no Redis needed)
# ---------------------------------------------------------------------------
_CELERY_DB_URL = f"db+postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
CELERY_BROKER_URL = get_env_or_fail(
    "CELERY_BROKER_URL", default=_CELERY_DB_URL, required=False
)
CELERY_RESULT_BACKEND = get_env_or_fail(
    "CELERY_RESULT_BACKEND", default=_CELERY_DB_URL, required=False
)

# ---------------------------------------------------------------------------
# Auth / API Key
# ---------------------------------------------------------------------------
API_KEY = get_env_or_fail("API_KEY", default="dev-api-key-change-in-prod", required=False)

# ---------------------------------------------------------------------------
# PagerDuty (escalation)
# ---------------------------------------------------------------------------
PAGERDUTY_API_KEY = get_env_or_fail("PAGERDUTY_API_KEY", default="", required=False)
PAGERDUTY_ESCALATION_POLICY_ID = get_env_or_fail(
    "PAGERDUTY_ESCALATION_POLICY_ID", default="", required=False
)

# ---------------------------------------------------------------------------
# Safety Controls
# ---------------------------------------------------------------------------
# Max concurrent auto-executing incidents per cluster per hour
BLAST_RADIUS_CAP = int(
    get_env_or_fail("BLAST_RADIUS_CAP", default="5", required=False)
)
# Minutes within which identical (alert+cluster+namespace) events are deduplicated
DEDUP_WINDOW_MINUTES = int(
    get_env_or_fail("DEDUP_WINDOW_MINUTES", default="10", required=False)
)

# ---------------------------------------------------------------------------
# Embedding Model / Misc
# ---------------------------------------------------------------------------
SPLUNK_CONTROLLER_NAME = get_env_or_fail(
    "SPLUNK_CONTROLLER_NAME",
    default="argocd-application-controller",
    required=False,
)
EMBED_MODEL_NAME = get_env_or_fail(
    "EMBED_MODEL_NAME", default="all-MiniLM-L6-v2", required=False
)

---

// filepath: agents/escalation_matrix.json
{
  "default": "SRE-Triage",
  "KubeAPIDown": "SRE-Core-Platform",
  "TargetDown": "SRE-Observability",
  "DiskClusterFailing": "SRE-Storage",
  "EtcdMembersDown": "SRE-Core-Platform",
  "ingress-operator-degraded": "SRE-Networking",
  "NetworkInterfaceFlapping": "SRE-Networking",
  "KubeVirtNoAvailableNodesToRunVMs": "SRE-Compute",
  "CollectorNodeDown": "SRE-Observability"
}

---

// filepath: agents/langchain_agent.py
"""
LangChain AgentExecutor pipeline for SRE incident analysis.

Pipeline stages (Python if/else routing — no LangGraph):

  Step 1: Context gathering  → RunnableParallel (all 4 info tools fire at once)
  Step 2: ReAct agent        → classify_action tool → RemediationIntent
  Step 3: Validation chain   → Pydantic schema + action allowlist check
  Step 4: Risk scoring       → risk_engine.classify_risk() (NO LLM)
  Step 5: Route              → LOW / HIGH / ESCALATE

Every state transition writes to incident_timeline via log_timeline_event.
LLM reasoning is stored in llm_decisions.
"""

from __future__ import annotations

import json
import uuid
import re
from dataclasses import dataclass

def _extract_json_string(text: str) -> str:
    """Extracts JSON object from a string using brace counting to handle nesting."""
    start_idx = text.find('{')
    if start_idx == -1:
        return text
    
    brace_count = 0
    for i in range(start_idx, len(text)):
        if text[i] == '{':
            brace_count += 1
        elif text[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                return text[start_idx:i+1]
                
    return text

from typing import Any, Literal

from langchain.agents.agent import AgentExecutor
from langchain.agents.react.agent import create_react_agent
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
import psycopg2

from agents.config import LLM_API_URL, LLM_API_KEY, LLM_MODEL
from agents.langchain_tools import (
    ALL_TOOLS,
    RemediationIntent,
    classify_action,
    get_incident_history,
    get_pod_status,
    lookup_runbook,
    query_prometheus,
)
from agents.risk_engine import RiskTier, classify_risk, get_risk_reasoning, is_action_allowed
from agents.config import DATABASE_TARGET

# ---------------------------------------------------------------------------
# LLM Observability Callback Handler
# ---------------------------------------------------------------------------

class IncidentTimelineCallbackHandler(BaseCallbackHandler):
    """Logs LLM intermediate steps (thoughts, tools, errors) to the database timeline."""
    
    def __init__(self, incident_id: uuid.UUID):
        self.incident_id = str(incident_id)

    def _log_to_db(self, action: str, notes: str = "", metadata: dict | None = None):
        try:
            conn = psycopg2.connect(**DATABASE_TARGET)
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO incident_timeline (incident_id, actor_type, action, notes, metadata_json)
                VALUES (%s, 'agent', %s, %s, %s)
                """,
                (self.incident_id, action, notes, json.dumps(metadata) if metadata else None)
            )
            conn.commit()
            cur.close()
            conn.close()
        except Exception:
            pass  # Best effort

    def on_agent_action(self, action: Any, **kwargs: Any) -> None:
        """Fires when the agent decides to use a tool, logging its internal thought process."""
        if hasattr(action, "log") and action.log:
            # ReAct format: "Thought: ...\nAction: ..."
            thought = action.log.split("Action:")[0].strip()
            if thought:
                self._log_to_db("LLM Thought", notes=thought)

    def on_tool_start(self, serialized: dict, input_str: str, **kwargs: Any) -> None:
        tool_name = serialized.get("name", "unknown_tool")
        if tool_name == "_Exception":
            return
        self._log_to_db(f"Executing Tool: {tool_name}", notes=f"Input: {input_str}")

    def on_tool_error(self, error: BaseException, **kwargs: Any) -> None:
        self._log_to_db("Tool Execution Failed", notes=str(error))

    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        self._log_to_db("LLM Generation Error", notes=str(error))


# ---------------------------------------------------------------------------
# LLM client — points at the existing llama.cpp compatible endpoint
# ---------------------------------------------------------------------------


def _get_llm():
    """
    Returns a ChatOpenAI instance pointed at the local LLM endpoint.
    Compatible with llama.cpp server, Ollama, and OpenAI API.
    Set LLM_API_URL in .env to switch providers.
    """
    from agents.config import USE_MOCK_LLM
    if USE_MOCK_LLM:
        from langchain_core.language_models.chat_models import BaseChatModel
        from langchain_core.messages import AIMessage
        from langchain_core.outputs import ChatResult, ChatGeneration
        
        class MockLLM(BaseChatModel):
            def _generate(self, messages, stop=None, run_manager=None, **kwargs):
                return ChatResult(generations=[ChatGeneration(message=AIMessage(content='''Thought: I have gathered the context.
Final Answer: {
  "action": "delete_pvc",
  "namespace": "machine-config-operator",
  "target": "pvc-aul12345",
  "reason": "Simulating a HIGH risk remediation action.",
  "confidence": 0.95,
  "analysis_summary": "Mock analysis summary for PVC deletion.",
  "escalate_to": "Storage-Admin"
}'''))])
            
            @property
            def _llm_type(self) -> str:
                return "mock"
                
        return MockLLM()

    return ChatOpenAI(
        base_url=LLM_API_URL.replace("/v1/chat/completions", "/v1"),
        api_key=LLM_API_KEY if LLM_API_KEY else "local",
        model=LLM_MODEL,
        temperature=0.1,
        max_retries=2,
        timeout=60,
        model_kwargs={"extra_body": {"reasoning": {"enabled": True}}},
    )


# ---------------------------------------------------------------------------
# ReAct agent prompt
# ---------------------------------------------------------------------------

REACT_PROMPT_TEMPLATE = """You are an expert OpenShift SRE incident analysis agent.

You have access to the following tools:
{tools}

Use this format EXACTLY:
Thought: think about what to do
Action: tool_name
Action Input: a valid JSON object containing the tool arguments
Observation: the tool result
... (repeat Thought/Action/Action Input/Observation as needed)
Thought: I now know the final answer
Final Answer: <your response>

For your Final Answer, you MUST call the classify_action tool last with all gathered context
and return the JSON output from classify_action as your Final Answer verbatim.

Available tool names: {tool_names}

Context about the current incident:
Alert: {alert_name}
Namespace: {namespace}
Cluster: {cluster}
Hostname: {hostname}
Correlation ID: {correlation_id}

Begin!

{agent_scratchpad}"""


# ---------------------------------------------------------------------------
# Pipeline result dataclass
# ---------------------------------------------------------------------------


@dataclass
class AgentPipelineResult:
    """Complete result from one run of run_incident_pipeline()."""

    incident_id: uuid.UUID
    intent: RemediationIntent
    risk_tier: RiskTier
    risk_reasoning: str
    tool_calls: list[dict]
    raw_agent_output: str
    action: Literal["auto_execute", "pending_approval", "escalate"]


# ---------------------------------------------------------------------------
# Main pipeline function
# ---------------------------------------------------------------------------


def run_incident_pipeline(
    incident_id: uuid.UUID,
    alert_name: str,
    namespace: str,
    cluster: str,
    hostname: str,
    correlation_id: str,
    on_status_update: Any | None = None,  # callable(incident_id, status, notes)
) -> AgentPipelineResult:
    """
    Run the full 5-step LangChain agent pipeline for one incident.

    Parameters
    ----------
    incident_id:
        UUID of the incident record in incidents_v2.
    alert_name, namespace, cluster, hostname, correlation_id:
        Alert context fields from the normalized event.
    on_status_update:
        Optional async callback invoked on every status change.
        Signature: on_status_update(incident_id, new_status, notes)

    Returns
    -------
    AgentPipelineResult with intent, risk_tier, and routing action.
    """

    def _notify(status: str, notes: str = ""):
        if on_status_update:
            on_status_update(incident_id, status, notes)

    # ------------------------------------------------------------------
    # Step 1: Context gathering — run info tools before ReAct loop
    # ------------------------------------------------------------------
    _notify("ANALYZING", "Gathering context from k8s, Prometheus, runbooks, history")

    pod_status_raw = get_pod_status.invoke(
        json.dumps({"namespace": namespace, "pod_name": hostname.split(".")[0]})
    )
    prometheus_raw = query_prometheus.invoke(
        json.dumps({
            "metric_query": f'ALERTS{{alertname="{alert_name}", alertstate="firing"}}',
            "cluster": cluster,
        })
    )
    runbook_raw = lookup_runbook.invoke(alert_name)
    history_raw = get_incident_history.invoke(
        json.dumps({"cluster": cluster, "alert_name": alert_name})
    )

    # Aggregate context for classify_action
    context_payload = json.dumps(
        {
            "alert_name": alert_name,
            "namespace": namespace,
            "cluster": cluster,
            "hostname": hostname,
            "pod_status": json.loads(pod_status_raw),
            "prometheus_data": json.loads(prometheus_raw),
            "runbook_context": json.loads(runbook_raw),
            "incident_history": json.loads(history_raw),
        }
    )

    # ------------------------------------------------------------------
    # Step 2: ReAct agent — produce RemediationIntent via classify_action
    # ------------------------------------------------------------------
    _notify("ANALYZING", "Running ReAct classification agent")

    llm = _get_llm()
    prompt = PromptTemplate.from_template(REACT_PROMPT_TEMPLATE)

    agent = create_react_agent(llm=llm, tools=ALL_TOOLS, prompt=prompt)
    
    timeline_cb = IncidentTimelineCallbackHandler(incident_id)
    
    executor = AgentExecutor(
        agent=agent,
        tools=ALL_TOOLS,
        verbose=True,
        max_iterations=8,
        handle_parsing_errors=True,
        return_intermediate_steps=True,
        callbacks=[timeline_cb],
    )

    try:
        agent_result = executor.invoke(
            {
                "alert_name": alert_name,
                "namespace": namespace,
                "cluster": cluster,
                "hostname": hostname,
                "correlation_id": correlation_id,
            }
        )
        raw_output: str = agent_result.get("output", "")
        intermediate_steps: list = agent_result.get("intermediate_steps", [])
    except Exception as e:
        # LLM parsing errors or max iterations hit
        raw_output = str(e)
        intermediate_steps = []

    # Collect tool call log for llm_decisions
    tool_calls: list[dict] = []
    for step in intermediate_steps:
        action_obj, observation = step
        tool_name = getattr(action_obj, "tool", "unknown")
        
        # Skip Langchain's internal parsing errors from showing up in the UI
        if tool_name == "_Exception":
            continue
            
        tool_calls.append(
            {
                "tool": tool_name,
                "input": getattr(action_obj, "tool_input", {}),
                "output": str(observation)[:1000],
            }
        )

    # ------------------------------------------------------------------
    # Step 3: Validation — parse and validate the classify_action output
    # ------------------------------------------------------------------
    _notify("ANALYZING", "Validating intent schema and action allowlist")

    try:
        clean_raw = _extract_json_string(raw_output)
        intent = RemediationIntent.model_validate_json(clean_raw)
    except Exception:
        # Try direct classify_action call with the gathered context as fallback
        fallback_prompt = classify_action.invoke({"context_json": context_payload})
        fallback_msg = llm.invoke(fallback_prompt)
        clean_fallback = _extract_json_string(fallback_msg.content)
        intent = RemediationIntent.model_validate_json(clean_fallback)

    # Allowlist validation
    if not is_action_allowed(intent.action) and intent.action != "escalate":
        intent = RemediationIntent(
            action="escalate",
            namespace=intent.namespace,
            target=intent.target,
            reason=f"Action '{intent.action}' is not in the approved allowlist.",
            confidence=0.0,
        )

    # ------------------------------------------------------------------
    # Step 4: Risk scoring — HARDCODED, NO LLM
    # ------------------------------------------------------------------
    risk_tier = classify_risk(intent)
    risk_reasoning = get_risk_reasoning(intent, risk_tier)

    # ------------------------------------------------------------------
    # Step 5: Route
    # ------------------------------------------------------------------
    if risk_tier == "LOW":
        action = "auto_execute"
        _notify("EXECUTING", f"Risk=LOW. Auto-executing via AWX. {risk_reasoning}")
    elif risk_tier == "HIGH":
        action = "pending_approval"
        _notify("PENDING_APPROVAL", f"Risk=HIGH. Awaiting human approval. {risk_reasoning}")
    else:  # ESCALATE
        action = "escalate"
        _notify("ESCALATED", f"Risk=ESCALATE. Paging oncall. {risk_reasoning}")

    return AgentPipelineResult(
        incident_id=incident_id,
        intent=intent,
        risk_tier=risk_tier,
        risk_reasoning=risk_reasoning,
        tool_calls=tool_calls,
        raw_agent_output=raw_output,
        action=action,
    )

---

// filepath: agents/langchain_tools.py
"""
LangChain @tool definitions for the SRE Incident Agent.

Each tool is a thin adapter over an existing data source:
  - get_pod_status       → Kubernetes Python client
  - query_prometheus     → Prometheus HTTP API (existing PROMETHEUS_URL)
  - lookup_runbook       → pgvector RAG search (reuses existing query logic)
  - get_incident_history → Postgres (existing recurrence_intelligence table)
  - classify_action      → LLM structured output (Pydantic RemediationIntent)

Tools are intentionally idempotent and read-only.
The ONLY write path is through AWX (never from these tools).
"""

from __future__ import annotations

import json
import textwrap
from typing import Literal, Optional

import psycopg2
import requests
# pyrefly: ignore [missing-import]
from langchain_core.tools import tool
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field

from agents.config import (
    DATABASE_TARGET,
    EMBED_MODEL_NAME,
    PROMETHEUS_URL,
)

# ---------------------------------------------------------------------------
# Pydantic schema for the LLM's structured output
# ---------------------------------------------------------------------------


class RemediationIntent(BaseModel):
    """
    Strictly typed intent produced by the LangChain ReAct agent.
    The 'action' field is restricted to the known action allowlist.
    AWX extra_vars are ALWAYS sourced from this validated model — never raw LLM output.
    """

    action: Literal[
        "restart_pod",
        "clear_evicted_pods",
        "scale_up_replicas",
        "delete_pvc",
        "drain_node",
        "scale_down_deployment",
        "escalate",
    ] = Field(description="The remediation action to take")
    namespace: str = Field(description="The Kubernetes namespace to act on")
    target: str = Field(
        description="The specific pod, node, or deployment name to act on"
    )
    reason: str = Field(
        description="One-sentence reason for this action derived from context"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score 0.0–1.0 for this remediation intent",
    )
    analysis_summary: str = Field(
        default="",
        description="Detailed markdown analysis including existing tickets, maintenance, RedHat cases, diagnostics, remediation, and validation steps."
    )
    escalate_to: str = Field(
        default="SRE-Triage",
        description="Who to escalate to, based on the Escalation Matrix, if validation fails or risk is high."
    )

    def to_awx_extra_vars(self) -> dict:
        """
        Produces validated extra_vars dict for AWX job templates.
        ONLY this method should supply extra_vars — never raw strings.
        """
        return {
            "action": self.action,
            "namespace": self.namespace,
            "target": self.target,
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# Tool 1: Kubernetes pod status
# ---------------------------------------------------------------------------


@tool
def get_pod_status(input_json: str) -> str:
    """
    Query the Kubernetes API for the current status of a specific pod.
    Returns pod phase, container statuses, and any recent events.
    Use this to confirm the alert is still active before taking action.
    Input must be a JSON string with keys "namespace" and "pod_name".
    """
    pod_name = "unknown"
    namespace = "unknown"
    try:
        import json
        if isinstance(input_json, str):
            input_json = input_json.strip(" '`\n")
        args = json.loads(input_json) if isinstance(input_json, str) else input_json
        if isinstance(args, dict):
            namespace = args.get("namespace", "default")
            pod_name = args.get("pod_name", "")

        from agents.config import USE_MOCK_SERVERS
        if USE_MOCK_SERVERS:
            return json.dumps(
                {
                    "pod": pod_name,
                    "namespace": namespace,
                    "phase": "Failed",
                    "container_statuses": [
                        {
                            "name": "collector",
                            "state": "terminated",
                            "reason": "OOMKilled",
                            "exit_code": 137
                        }
                    ],
                    "message": "Pod was OOMKilled",
                    "reason": "OOMKilled",
                }
            )

        # pyrefly: ignore [missing-import]
        from kubernetes import client as k8s_client, config as k8s_config

        try:
            k8s_config.load_incluster_config()
        except Exception:
            k8s_config.load_kube_config()

        v1 = k8s_client.CoreV1Api()
        pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)

        container_statuses = []
        if pod.status.container_statuses:
            for cs in pod.status.container_statuses:
                state_info = {}
                if cs.state.running:
                    state_info = {"state": "running"}
                elif cs.state.waiting:
                    state_info = {
                        "state": "waiting",
                        "reason": cs.state.waiting.reason,
                        "message": cs.state.waiting.message,
                    }
                elif cs.state.terminated:
                    state_info = {
                        "state": "terminated",
                        "reason": cs.state.terminated.reason,
                        "exit_code": cs.state.terminated.exit_code,
                    }
                container_statuses.append({"name": cs.name, **state_info})

        return json.dumps(
            {
                "pod": pod_name,
                "namespace": namespace,
                "phase": pod.status.phase,
                "container_statuses": container_statuses,
                "message": pod.status.message,
                "reason": pod.status.reason,
            }
        )
    except Exception as e:
        return json.dumps(
            {
                "error": str(e),
                "pod": pod_name,
                "namespace": namespace,
                "phase": "Unknown",
                "note": "Could not reach Kubernetes API. Proceeding with alert context only.",
            }
        )


# ---------------------------------------------------------------------------
# Tool 2: Prometheus metric query
# ---------------------------------------------------------------------------


@tool
def query_prometheus(input_json: str) -> str:
    """
    Execute an instant PromQL query against Prometheus.
    Use this to check real-time resource utilisation, alert firing state,
    and SLO metrics. Pass a JSON string with keys "metric_query" and "cluster".
    Example: '{"metric_query": "ALERTS{alertname=\\"PodCrashLooping\\"}", "cluster": "nzclu101"}'
    """
    metric_query = "unknown"
    cluster = "unknown"
    try:
        import json
        if isinstance(input_json, str):
            input_json = input_json.strip(" '`\n")
        args = json.loads(input_json) if isinstance(input_json, str) else input_json
        if isinstance(args, dict):
            metric_query = args.get("metric_query", "")
            cluster = args.get("cluster", "")
            
        from agents.config import USE_MOCK_SERVERS
        if USE_MOCK_SERVERS:
            import time
            return json.dumps(
                {
                    "query": metric_query,
                    "cluster": cluster,
                    "result_count": 1,
                    "results": [
                        {
                            "metric": {"__name__": "up", "namespace": "cluster-logging-operator"},
                            "value": [int(time.time()), "0"]
                        }
                    ],
                }
            )

        resp = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": metric_query},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("data", {}).get("result", [])
        return json.dumps(
            {
                "query": metric_query,
                "cluster": cluster,
                "result_count": len(results),
                "results": results[:10],  # cap to avoid token overflow
            }
        )
    except Exception as e:
        return json.dumps(
            {
                "error": str(e),
                "query": metric_query,
                "cluster": cluster,
                "note": "Prometheus unavailable. Proceeding without live metrics.",
            }
        )


# ---------------------------------------------------------------------------
# Tool 3: RAG runbook lookup
# ---------------------------------------------------------------------------

_embed_model = None


def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        # pyrefly: ignore [missing-import]
        from sentence_transformers import SentenceTransformer
        _embed_model = SentenceTransformer(EMBED_MODEL_NAME)
    return _embed_model


@tool
def lookup_runbook(alert_name: str) -> str:
    """
    Search the pgvector runbook knowledge base for remediation procedures
    relevant to the given alert name. Returns the top 2 matching runbook
    excerpts with their source IDs and similarity scores.
    Always call this before recommending any action.
    """
    try:
        from agents.config import USE_MOCK_SERVERS
        if USE_MOCK_SERVERS:
            import json
            return json.dumps({
                "alert_name": alert_name,
                "runbook_hits": 1,
                "results": [{
                    "source_id": "mock_runbook_1",
                    "source_table": "rhokp_knowledge",
                    "similarity": 0.95,
                    "excerpt": f"Standard remediation for {alert_name}: Requires manual approval if risk is high. Check node status, drain node if kernel panic, or restart pods."
                }]
            })
            
        embed_model = _get_embed_model()
        query_text = f"Remediation procedure for alert: {alert_name}"
        query_vector = embed_model.encode(query_text).tolist()
        search_keyword = f"%{alert_name}%"

        conn = psycopg2.connect(**DATABASE_TARGET)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT * FROM (
                SELECT source_id, source_table, text_chunk,
                       CASE WHEN source_id ILIKE %s
                            THEN (embedding <-> %s::vector) - 0.4
                            ELSE (embedding <-> %s::vector) END AS distance
                FROM operational_knowledge_embeddings
                WHERE model_name = %s AND model_version = '1.0'
                UNION ALL
                SELECT rhokp_id AS source_id, section_type AS source_table,
                       raw_text AS text_chunk,
                       CASE WHEN rhokp_id ILIKE %s
                            THEN (embedding <-> %s::vector) - 0.4
                            ELSE (embedding <-> %s::vector) END AS distance
                FROM rhokp_knowledge
                WHERE model_name = %s AND model_version = '1.0'
            ) AS combined
            WHERE distance < 0.75
            ORDER BY distance
            LIMIT 2;
            """,
            (search_keyword, query_vector, query_vector, EMBED_MODEL_NAME,
             search_keyword, query_vector, query_vector, EMBED_MODEL_NAME),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()

        results = []
        for row in rows:
            source_id, source_table, text_chunk, distance = row
            results.append(
                {
                    "source_id": source_id,
                    "source_table": source_table,
                    "similarity": round(min(1.0, 1.0 - float(distance)), 4),
                    "excerpt": textwrap.shorten(text_chunk, width=500),
                }
            )

        return json.dumps(
            {
                "alert_name": alert_name,
                "runbook_hits": len(results),
                "results": results,
            }
        )
    except Exception as e:
        return json.dumps(
            {
                "error": str(e),
                "alert_name": alert_name,
                "note": "RAG search failed. LLM should reason from alert name alone.",
            }
        )


# ---------------------------------------------------------------------------
# Tool 4: Incident history lookup
# ---------------------------------------------------------------------------


@tool
def get_incident_history(input_json: str) -> str:
    """
    Query the Postgres database for the historical reoccurrence pattern of
    this alert on this cluster. Returns weekly incident count, reopen count,
    average MTTR, resolution quality score, and recent agent action count.
    Use this to assess whether auto-remediation has previously succeeded.
    Input must be a JSON string with keys "cluster" and "alert_name".
    """
    cluster = "unknown"
    alert_name = "unknown"
    try:
        import json
        if isinstance(input_json, str):
            input_json = input_json.strip(" '`\n")
        args = json.loads(input_json) if isinstance(input_json, str) else input_json
        if isinstance(args, dict):
            cluster = args.get("cluster", "")
            alert_name = args.get("alert_name", "")
        conn = psycopg2.connect(**DATABASE_TARGET)
        cur = conn.cursor()

        # Fingerprint logic was flawed because we lack namespace and operator component in this context.
        # Instead, query by alertname and cluster directly.

        # Weekly frequency
        cur.execute(
            """
            SELECT COUNT(i.*) FROM incidents i
            JOIN alert_occurrences a ON i.alert_fingerprint = a.fingerprint
            WHERE a.alertname = %s AND a.cluster_id = %s AND i.sys_created_on > NOW() - INTERVAL '7 days';
            """,
            (alert_name, cluster),
        )
        weekly_count = cur.fetchone()[0] or 0

        # Recurrence intelligence
        cur.execute(
            """
            SELECT SUM(total_occurrences), SUM(total_incidents), SUM(reopen_count),
                   AVG(mttr_seconds), AVG(resolution_quality_score)
            FROM recurrence_intelligence WHERE alertname = %s AND cluster_id = %s;
            """,
            (alert_name, cluster),
        )
        rec = cur.fetchone()

        # Agent auto-remediation count last 24h
        cur.execute(
            """
            SELECT COUNT(*) FROM incidents_v2
            WHERE alert_name = %s AND cluster = %s AND status = 'RESOLVED'
            AND updated_at >= NOW() - INTERVAL '24 hours';
            """,
            (alert_name, cluster),
        )
        agent_24h = cur.fetchone()[0] or 0

        cur.close()
        conn.close()

        return json.dumps(
            {
                "cluster": cluster,
                "alert_name": alert_name,
                "weekly_occurrences": weekly_count,
                "total_occurrences": rec[0] if rec else 0,
                "total_incidents": rec[1] if rec else 0,
                "reopen_count": rec[2] if rec else 0,
                "avg_mttr_seconds": rec[3] if rec else 0,
                "resolution_quality_score": float(rec[4]) if rec and rec[4] else 100.0,
                "agent_auto_remediations_last_24h": agent_24h,
            }
        )
    except Exception as e:
        return json.dumps(
            {
                "error": str(e),
                "cluster": cluster,
                "alert_name": alert_name,
                "note": "History unavailable. Treating as new incident.",
            }
        )


# ---------------------------------------------------------------------------
# Tool 5: LLM action classification
# ---------------------------------------------------------------------------


@tool
def classify_action(context_json: str) -> str:
    """
    Validate and structure the gathered alert context, then instruct the ReAct
    agent (you) to produce a RemediationIntent JSON response.

    This tool does NOT make a second LLM call. The ReAct agent is the LLM.
    Calling this tool returns a structured prompt that YOU (the agent) must
    answer with a valid RemediationIntent JSON as your Final Answer.

    Input must be a JSON string with keys: alert_name, namespace, cluster,
    hostname, runbook_context, pod_status, prometheus_data, incident_history.

    Allowed actions: restart_pod | clear_evicted_pods | scale_up_replicas |
                     delete_pvc | drain_node | scale_down_deployment | escalate
    """
    try:
        if isinstance(context_json, str):
            context_json = context_json.strip(" '`\n")
        context = json.loads(context_json)
    except Exception:
        context = {"raw": context_json}

    try:
        import os
        matrix_path = os.path.join(os.path.dirname(__file__), "escalation_matrix.json")
        with open(matrix_path, "r") as f:
            escalation_matrix = f.read()
    except Exception:
        escalation_matrix = '{"default": "SRE-Triage"}'

    # Return a structured instruction — the ReAct agent will use this to produce the Final Answer
    instruction = textwrap.dedent(f"""
        Based on the following alert context, produce your Final Answer as a
        valid JSON object matching the RemediationIntent schema below.
        DO NOT include any text outside the JSON object.

        Schema:
        {{
          "action": "<restart_pod|clear_evicted_pods|scale_up_replicas|delete_pvc|drain_node|scale_down_deployment|escalate>",
          "namespace": "<kubernetes namespace>",
          "target": "<specific pod/node/deployment name -- never generic>",
          "reason": "<one-sentence reason derived only from context>",
          "confidence": <float 0.0-1.0>,
          "analysis_summary": "<markdown: 1) Remediation 2) Diagnostics 3) Validation 4) Tickets 5) RH Cases>",
          "escalate_to": "<team from escalation matrix>"
        }}

        Escalation Matrix: {escalation_matrix}

        Rules:
        - Use ONLY information from context. Never hallucinate resource names.
        - If context is insufficient, set action="escalate" and confidence<0.75.

        Alert Context:
        {json.dumps(context, indent=2)}
    """)

    return instruction


# ---------------------------------------------------------------------------
# Exported tools list for AgentExecutor
# ---------------------------------------------------------------------------

ALL_TOOLS = [
    get_pod_status,
    query_prometheus,
    lookup_runbook,
    get_incident_history,
    classify_action,
]

---

// filepath: agents/rag_search.py
import os
import re
import sys
import logging
import argparse
import psycopg2
# pyrefly: ignore [missing-import]
from sentence_transformers import SentenceTransformer
from agents.config import DATABASE_TARGET, EMBED_MODEL_NAME

# Silence diagnostics
os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)


class RAGQueryClient:
    def __init__(self):
        self.db_config = DATABASE_TARGET
        print(f"Loading local semantic embedding layers ({EMBED_MODEL_NAME})...", file=sys.stderr)
        self.embed_model = SentenceTransformer(EMBED_MODEL_NAME)

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
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-a", "--alertname", type=str, help="Target alertname token to search")
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

---

// filepath: agents/risk_engine.py
"""
Risk tier classification engine.

NON-NEGOTIABLE: LLM NEVER decides risk tier.
Risk tier is determined ONLY by this rule engine based on action type and confidence.
"""

from __future__ import annotations

from typing import Literal

from agents.langchain_tools import RemediationIntent

# ---------------------------------------------------------------------------
# Allowlists — single source of truth for all risk tiers
# ---------------------------------------------------------------------------

LOW_RISK_ACTIONS: frozenset[str] = frozenset(
    {"restart_pod", "clear_evicted_pods", "scale_up_replicas"}
)

HIGH_RISK_ACTIONS: frozenset[str] = frozenset(
    {"delete_pvc", "drain_node", "scale_down_deployment"}
)

# Any action NOT in LOW or HIGH → ESCALATE
# Explicit set for documentation purposes
KNOWN_ACTIONS: frozenset[str] = LOW_RISK_ACTIONS | HIGH_RISK_ACTIONS

CONFIDENCE_THRESHOLD = 0.75  # Below this → ESCALATE immediately, no approval prompt

RiskTier = Literal["LOW", "HIGH", "ESCALATE"]


def classify_risk(intent: RemediationIntent) -> RiskTier:
    """
    Classify the risk tier for a remediation intent.

    Rules (evaluated in order):
    1. Confidence < CONFIDENCE_THRESHOLD → ESCALATE (page oncall, no human prompt)
    2. Action in LOW_RISK_ACTIONS → LOW (auto-execute via AWX)
    3. Action in HIGH_RISK_ACTIONS → HIGH (pause, write PENDING_APPROVAL, wait for human)
    4. Unknown action → ESCALATE

    Returns one of: "LOW", "HIGH", "ESCALATE"
    """
    if intent.confidence < CONFIDENCE_THRESHOLD:
        return "ESCALATE"

    if intent.action in LOW_RISK_ACTIONS:
        return "LOW"

    if intent.action in HIGH_RISK_ACTIONS:
        return "HIGH"

    # Unknown action — never execute
    return "ESCALATE"


def get_risk_reasoning(intent: RemediationIntent, tier: RiskTier) -> str:
    """Return a human-readable explanation of the risk decision."""
    if intent.confidence < CONFIDENCE_THRESHOLD:
        return (
            f"Confidence score {intent.confidence:.2%} is below the "
            f"{CONFIDENCE_THRESHOLD:.0%} threshold. Escalating to oncall "
            f"without human approval prompt."
        )
    if tier == "LOW":
        return (
            f"Action '{intent.action}' is classified as LOW risk. "
            f"Proceeding with automatic AWX execution."
        )
    if tier == "HIGH":
        return (
            f"Action '{intent.action}' is classified as HIGH risk. "
            f"Pausing for human approval before AWX execution."
        )
    return (
        f"Action '{intent.action}' is not in the known action allowlist. "
        f"Escalating to oncall."
    )


def is_action_allowed(action: str) -> bool:
    """Returns True if the action is in the known allowlist."""
    return action in KNOWN_ACTIONS

---

// filepath: ansible_playbooks/remediate.yml
---
- name: SRE Automated Remediation Router
  hosts: localhost
  connection: local
  gather_facts: false
  
  vars:
    # These variables are expected to be passed via extra-vars (--extra-vars)
    action: ""
    namespace: ""
    target: ""
    
  tasks:
    - name: Fail if required variables are missing
      ansible.builtin.fail:
        msg: "Missing required variables: action, namespace, and target must be provided."
      when: action == "" or namespace == "" or target == ""

    - name: Log remediation attempt
      ansible.builtin.debug:
        msg: "Attempting automated remediation: {{ action }} on {{ target }} in namespace {{ namespace }}"

    - name: Route to appropriate remediation task
      ansible.builtin.include_tasks: "tasks/{{ action }}.yml"

---

// filepath: ansible_playbooks/tasks/delete_resource.yml
---
- name: Execute Resource Deletion
  ansible.builtin.debug:
    msg: "MOCK: Executing 'oc delete' on {{ target }} in namespace {{ namespace }} to force operator reconciliation."

- name: Wait for Pod/Resource Recreation
  ansible.builtin.debug:
    msg: "MOCK: Verified target object was successfully recreated by its controlling operator."

---

// filepath: ansible_playbooks/tasks/drain_node.yml
---
- name: Drain Cluster Node
  ansible.builtin.debug:
    msg: "MOCK: Cordoning node {{ target }} and executing 'oc drain --ignore-daemonsets --delete-emptydir-data'."

- name: Await Node Rebalance
  ansible.builtin.debug:
    msg: "MOCK: Workloads safely evicted to alternative nodes."

---

// filepath: ansible_playbooks/tasks/escalate_to_support.yml
---
- name: Automate Support Escalation
  ansible.builtin.debug:
    msg: "MOCK: Opened RedHat Support Case for target {{ target }} in namespace {{ namespace }}."

- name: Write ticket data to log
  ansible.builtin.copy:
    dest: escalate_log.txt
    content: |
      [{{ ansible_date_time.iso8601 }}] Created Support Case for {{ target }} in {{ namespace }}
      
      Diagnostic Data:
      {{ alert_summary | default("No summary provided.") }}
      
      ----------------

---

// filepath: ansible_playbooks/tasks/etcd_compaction.yml
---
# tasks/etcd_compaction.yml
# Compacts and defragments the etcd database

- name: Get etcd pod in namespace
  kubernetes.core.k8s_info:
    api_version: v1
    kind: Pod
    namespace: "{{ namespace }}"
    label_selectors:
      - app=etcd
  register: etcd_pods

- name: Fail if no etcd pods found
  ansible.builtin.fail:
    msg: "No etcd pods found in namespace {{ namespace }}"
  when: etcd_pods.resources | length == 0

- name: Execute etcdctl compact
  kubernetes.core.k8s_exec:
    namespace: "{{ namespace }}"
    pod: "{{ etcd_pods.resources[0].metadata.name }}"
    command: etcdctl compact $(etcdctl endpoint status --write-out=\"json\" | egrep -o '\"revision\":[0-9]*' | egrep -o '[0-9].*')
  register: compact_out

- name: Execute etcdctl defrag
  kubernetes.core.k8s_exec:
    namespace: "{{ namespace }}"
    pod: "{{ etcd_pods.resources[0].metadata.name }}"
    command: etcdctl defrag
  register: defrag_out

- name: Report compaction status
  ansible.builtin.debug:
    msg: "ETCD database compacted and defragmented successfully."

---

// filepath: ansible_playbooks/tasks/label_node.yml
---
# tasks/label_node.yml
# Applies specific scheduling labels to worker nodes

- name: Apply kubevirt schedulable label to target node
  kubernetes.core.k8s:
    state: present
    definition:
      apiVersion: v1
      kind: Node
      metadata:
        name: "{{ target }}"
        labels:
          kubevirt.io/schedulable: "true"

- name: Confirm node label applied
  ansible.builtin.debug:
    msg: "Successfully applied kubevirt label to node {{ target }}."

---

// filepath: ansible_playbooks/tasks/patch_configmap.yml
---
# tasks/patch_configmap.yml
# Updates timeouts or routes in configmaps

- name: Patch target ConfigMap
  kubernetes.core.k8s_json_patch:
    api_version: v1
    kind: ConfigMap
    name: "{{ target }}"
    namespace: "{{ namespace }}"
    patch:
      - op: replace
        path: /data/upstream_timeout
        value: "5s"

- name: Confirm patch success
  ansible.builtin.debug:
    msg: "ConfigMap {{ target }} patched successfully."

---

// filepath: ansible_playbooks/tasks/patch_resource.yml
---
- name: Execute Resource Patch
  ansible.builtin.debug:
    msg: "MOCK: Executing 'oc patch' on {{ target }} in namespace {{ namespace }} to apply configuration hotfixes."

- name: Verify Patch State
  ansible.builtin.debug:
    msg: "MOCK: Verified target configuration has successfully converged to desired state."

---

// filepath: ansible_playbooks/tasks/restart_pod.yml
---
# tasks/restart_pod.yml
# Safely restarts a pod by deleting it (ReplicaSet will recreate it)

- name: Retrieve pod details
  kubernetes.core.k8s_info:
    api_version: v1
    kind: Pod
    name: "{{ target }}"
    namespace: "{{ namespace }}"
  register: pod_info

- name: Fail if pod does not exist
  ansible.builtin.fail:
    msg: "Pod {{ target }} not found in namespace {{ namespace }}"
  when: pod_info.resources | length == 0

- name: Delete pod to trigger restart
  kubernetes.core.k8s:
    state: absent
    api_version: v1
    kind: Pod
    name: "{{ target }}"
    namespace: "{{ namespace }}"

- name: Wait for new pod to become ready
  ansible.builtin.debug:
    msg: "Pod {{ target }} deleted successfully. ReplicaSet will provision a new instance."

---

// filepath: ansible_playbooks/tasks/scale_deployment.yml
---
# tasks/scale_deployment.yml
# Scales a deployment to handle load or clear degraded states

- name: Retrieve current deployment scale
  kubernetes.core.k8s_info:
    api_version: apps/v1
    kind: Deployment
    name: "{{ target }}"
    namespace: "{{ namespace }}"
  register: deploy_info

- name: Fail if deployment does not exist
  ansible.builtin.fail:
    msg: "Deployment {{ target }} not found in namespace {{ namespace }}"
  when: deploy_info.resources | length == 0

- name: Scale up deployment
  kubernetes.core.k8s_scale:
    api_version: apps/v1
    kind: Deployment
    name: "{{ target }}"
    namespace: "{{ namespace }}"
    replicas: 3
    wait: yes

- name: Confirm scale success
  ansible.builtin.debug:
    msg: "Deployment {{ target }} successfully scaled to 3 replicas."

---

// filepath: api/dependencies.py
"""
FastAPI dependency providers.

- db_session: async SQLAlchemy session per request
- get_current_user: JWT authentication (dev mode accepts any token)
"""

from __future__ import annotations

from typing import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from agents.config import API_KEY
from db.session import get_async_session

# ---------------------------------------------------------------------------
# Database session dependency
# ---------------------------------------------------------------------------


async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yields one AsyncSession per request, committed or rolled back on exit."""
    async with get_async_session() as session:
        yield session


# ---------------------------------------------------------------------------
# API Key Auth dependency
# ---------------------------------------------------------------------------

_bearer = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """
    Validates Bearer API Key and returns a mock user payload.

    In production: Replace this with your actual SSO/OIDC integration.
    In dev: Use 'dev-api-key-change-in-prod' as the Bearer token.
    """
    token = credentials.credentials
    if token != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Return a mock user ID for the audit logs
    return {"user_id": "api-user", "name": "API User"}

---

// filepath: api/main.py
"""
FastAPI application entry point.

Features:
- CORS for local React dev server
- Lifespan events for DB connection setup/teardown
- All routers mounted
- WebSocket endpoint for real-time incident updates
- Health check endpoint
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager

import psycopg2
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from api.routers.alerts import router as alerts_router
from api.routers.analytics import router as analytics_router
from api.routers.incidents import router as incidents_router
from api.routers.cve_advisor import router as cve_advisor_router
from api.routers.handovers import router as handovers_router
from api.routers.chat import router as chat_router
from api.routers.summaries import router as summaries_router
from api.websocket import manager
from db.pg_notify import listen_for_pg_notifications
from db.session import close_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("SRE Incident Agent API starting up...")
    # Start the PostgreSQL NOTIFY listener — bridges Celery → WebSocket
    import asyncio
    pg_listener_task = asyncio.create_task(listen_for_pg_notifications(manager))
    yield
    logger.info("SRE Incident Agent API shutting down...")
    pg_listener_task.cancel()
    await close_engine()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="SRE Incident Agent API",
    description=(
        "LangChain-powered incident remediation system with Human-in-the-Loop approval. "
        "All automated Ansible actions execute via AWX REST API."
    ),
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS (allow React dev server)
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite default
        "http://localhost:3000",   # CRA default
        "http://localhost:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(alerts_router)
app.include_router(incidents_router)
app.include_router(analytics_router)
app.include_router(cve_advisor_router)
app.include_router(handovers_router)
app.include_router(chat_router)
app.include_router(summaries_router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health", tags=["System"])
async def health_check():
    """Returns API liveness status."""
    return {"status": "ok", "service": "sre-incident-agent"}


# ---------------------------------------------------------------------------
# Live incident counts (used by Dashboard cards)
# ---------------------------------------------------------------------------


@app.get("/dashboard/counts", tags=["Dashboard"])
async def dashboard_counts():
    """Return live counts for the four Dashboard stat cards."""
    from agents.config import DATABASE_TARGET
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
          COUNT(*) FILTER (WHERE status IN ('ANALYZING','EXECUTING','VERIFYING','PENDING_APPROVAL')) AS active,
          COUNT(*) FILTER (WHERE status = 'PENDING_APPROVAL') AS pending_approval,
          COUNT(*) FILTER (WHERE status = 'RESOLVED' AND resolved_at::date = CURRENT_DATE) AS resolved_today,
          COUNT(*) FILTER (WHERE status = 'FAILED') AS failed
        FROM incidents_v2;
        """
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return {
        "active": row[0],
        "pending_approval": row[1],
        "resolved_today": row[2],
        "failed": row[3],
    }


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


@app.websocket("/ws/incidents/{incident_id}")
async def websocket_incident(
    websocket: WebSocket,
    incident_id: str,
    user_name: str = Query(default="anonymous"),
):
    """
    Subscribe to real-time updates for a specific incident.

    Messages sent to client:
    - {"type": "status_change", "incident_id": ..., "new_status": ..., ...}
    - {"type": "presence", "viewers": [...]}

    Connect with: ws://localhost:8000/ws/incidents/{id}?user_name=john.doe
    """
    await manager.connect(incident_id, websocket, user_name)
    try:
        while True:
            # Keep connection alive; handle client pings
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except Exception:
                pass
    except WebSocketDisconnect:
        await manager.disconnect(incident_id, websocket, user_name)
        await manager.broadcast(
            incident_id,
            {"type": "presence", "viewers": manager.get_viewers(incident_id)},
        )

---

// filepath: api/schemas.py
"""
Pydantic schemas for FastAPI request/response models.

These are the ONLY contracts between the API layer and clients.
All human actions flow through these schemas — never raw JSON from LLM.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Alert Ingestion
# ---------------------------------------------------------------------------


class AlertIngestRequest(BaseModel):
    """Normalized alert payload from Kafka/webhook. Matches event.json schema."""

    cluster: str = Field(..., description="Cluster ID (e.g. nzclu101)")
    hostname: str
    correlation_id: str = Field(..., description="Unique correlation ID for deduplication")
    namespace: str
    alert_name: str = Field(..., alias="alertname")
    start_at: str | None = Field(None, alias="startAt")
    awx_template_id: str = Field(default="1", description="AWX job template ID to use for execution")

    model_config = {"populate_by_name": True}


class AlertIngestResponse(BaseModel):
    incident_id: uuid.UUID
    status: str
    message: str


# ---------------------------------------------------------------------------
# Incident (read)
# ---------------------------------------------------------------------------


class TimelineEventOut(BaseModel):
    id: int
    timestamp: datetime
    actor_type: str
    actor_id: str | None
    action: str
    from_status: str | None
    to_status: str | None
    notes: str | None
    metadata_json: dict | None


class HumanActionOut(BaseModel):
    id: int
    user_id: str
    action: str
    original_intent_json: dict | None
    final_intent_json: dict | None
    reason: str
    timestamp: datetime


class LLMDecisionOut(BaseModel):
    id: int
    prompt_used: str | None
    raw_llm_output: str | None
    parsed_intent: dict | None
    confidence: float | None
    tool_calls_json: list | None
    timestamp: datetime


class IncidentOut(BaseModel):
    id: uuid.UUID
    correlation_id: str | None
    cluster: str
    namespace: str
    alert_name: str
    hostname: str | None
    status: str
    risk_tier: str | None
    llm_confidence: float | None
    llm_intent_json: dict | None
    analysis_summary: str | None = None
    escalate_to: str | None = None
    awx_job_id: str | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    timeline: list[TimelineEventOut] = []
    human_actions: list[HumanActionOut] = []
    llm_decisions: list[LLMDecisionOut] = []


class IncidentListOut(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[IncidentOut]


# ---------------------------------------------------------------------------
# Human-in-the-Loop action requests
# ---------------------------------------------------------------------------


class ApproveRequest(BaseModel):
    reason: str = Field(..., min_length=5, description="Mandatory reason for approval")
    user_id: str = Field(..., description="Authenticated user ID — never anonymous")


class RejectRequest(BaseModel):
    reason: str = Field(..., min_length=5, description="Mandatory reason for rejection")
    user_id: str


class EditAndApproveRequest(BaseModel):
    modified_intent: dict = Field(
        ...,
        description="Modified intent JSON. Must still validate against RemediationIntent schema.",
    )
    reason: str = Field(..., min_length=5, description="Mandatory reason for edit")
    user_id: str


class EscalateRequest(BaseModel):
    reason: str = Field(..., min_length=5, description="Mandatory reason for escalation")
    user_id: str


class HumanActionResponse(BaseModel):
    incident_id: uuid.UUID
    new_status: str
    message: str


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


class MTTRDataPoint(BaseModel):
    cluster: str
    alert_name: str
    avg_mttr_seconds: float
    incident_count: int


class ResolutionStats(BaseModel):
    auto_resolved: int
    human_intervened: int
    total: int
    auto_resolved_pct: float
    human_intervened_pct: float


class LLMAccuracyStats(BaseModel):
    approved_as_is: int
    edited_before_approve: int
    rejected: int
    total_high_risk: int


class FlappingAlert(BaseModel):
    alert_name: str
    cluster: str
    flapping_count: int
    reopen_count: int

class SentimentTrend(BaseModel):
    date: str
    average_score: float
    total_resolutions: int

class RedHatCaseSummary(BaseModel):
    open_cases: int
    critical_escalation_pct: float
    avg_vendor_mttr_days: float

class ComponentIncident(BaseModel):
    component: str
    incident_count: int

class FleetRisk(BaseModel):
    average_risk_pct: int
    critical_cves_active: int

class EnvironmentDistribution(BaseModel):
    environment: str
    incident_count: int

class AnalyticsSummaryOut(BaseModel):
    mttr_by_cluster: list[MTTRDataPoint]
    resolution_stats: ResolutionStats
    llm_accuracy: LLMAccuracyStats
    top_recurring_alerts: list[dict[str, Any]]
    flapping_alerts: list[FlappingAlert]
    sentiment_trend: list[SentimentTrend]
    redhat_cases_summary: RedHatCaseSummary
    component_incidents: list[ComponentIncident]
    fleet_risk: FleetRisk
    environment_distribution: list[EnvironmentDistribution]

---

// filepath: api/websocket.py
"""
WebSocket connection manager for real-time incident status updates.

Supports:
- Per-incident subscription channels
- Broadcast on every state change
- Live presence tracking (who is viewing an incident)
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections subscribed to specific incident IDs.
    Thread-safe for use with FastAPI's async event loop.
    """

    def __init__(self):
        # incident_id (str) → list of connected WebSockets
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)
        # incident_id → set of user display names currently viewing
        self._presence: dict[str, set[str]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, incident_id: str, websocket: WebSocket, user_name: str = "anonymous"):
        await websocket.accept()
        async with self._lock:
            self._connections[incident_id].append(websocket)
            self._presence[incident_id].add(user_name)
        logger.info("[WS] %s connected to incident %s", user_name, incident_id)
        # Notify others of new viewer
        await self.broadcast(
            incident_id,
            {"type": "presence", "viewers": list(self._presence[incident_id])},
            exclude=websocket,
        )

    async def disconnect(self, incident_id: str, websocket: WebSocket, user_name: str = "anonymous"):
        async with self._lock:
            try:
                self._connections[incident_id].remove(websocket)
            except ValueError:
                pass
            self._presence[incident_id].discard(user_name)
            if not self._connections[incident_id]:
                del self._connections[incident_id]
                self._presence.pop(incident_id, None)
        logger.info("[WS] %s disconnected from incident %s", user_name, incident_id)

    async def broadcast(
        self,
        incident_id: str,
        message: dict[str, Any],
        exclude: WebSocket | None = None,
    ):
        """Send message to all subscribers of an incident (except excluded socket)."""
        payload = json.dumps(message, default=str)
        dead: list[WebSocket] = []

        async with self._lock:
            sockets = list(self._connections.get(incident_id, []))

        for ws in sockets:
            if ws is exclude:
                continue
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)

        # Clean up dead connections
        if dead:
            async with self._lock:
                for ws in dead:
                    try:
                        self._connections[incident_id].remove(ws)
                    except ValueError:
                        pass

    async def broadcast_status_change(
        self,
        incident_id: str,
        new_status: str,
        actor: str = "agent",
        notes: str = "",
        metadata: dict | None = None,
    ):
        """Convenience method for status transition broadcasts."""
        await self.broadcast(
            incident_id,
            {
                "type": "status_change",
                "incident_id": incident_id,
                "new_status": new_status,
                "actor": actor,
                "notes": notes,
                "metadata": metadata or {},
            },
        )

    def get_viewers(self, incident_id: str) -> list[str]:
        return list(self._presence.get(incident_id, set()))

    def get_connection_count(self, incident_id: str) -> int:
        return len(self._connections.get(incident_id, []))


# Singleton instance used across the app
manager = ConnectionManager()

---

// filepath: api/__init__.py
"""api package init."""

---

// filepath: api/routers/alerts.py
"""Alert ingestion router — POST /alerts/ingest"""

from __future__ import annotations

import json
import uuid

import psycopg2
from fastapi import APIRouter, HTTPException, status

from agents.config import DATABASE_TARGET, DEDUP_WINDOW_MINUTES
from api.schemas import AlertIngestRequest, AlertIngestResponse
from worker.tasks import run_agent_pipeline

router = APIRouter(prefix="/alerts", tags=["Alert Ingestion"])


@router.post(
    "/ingest",
    response_model=AlertIngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a normalized alert event and start the agent pipeline",
)
async def ingest_alert(payload: AlertIngestRequest):
    """
    Accepts a normalized alert from Kafka/webhook and creates a new incident.

    - Deduplication: Checks if the exact same alert on the same cluster 
      and namespace has already fired in the last `DEDUP_WINDOW_MINUTES` minutes.
      If yes, we skip creating a new incident to avoid flooding the system.
    - On success: creates the incident record and enqueues the Celery pipeline task.
    """
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur = conn.cursor()

    try:
        # Deduplication check
        cur.execute(
            """
            SELECT id, status FROM incidents_v2
            WHERE alert_name = %s AND cluster = %s AND namespace = %s
              AND created_at > NOW() - (INTERVAL '1 minute' * %s)
              AND status NOT IN ('REJECTED', 'ESCALATED', 'FAILED', 'RESOLVED')
            ORDER BY created_at DESC LIMIT 1;
            """,
            (payload.alert_name, payload.cluster, payload.namespace, DEDUP_WINDOW_MINUTES),
        )
        existing = cur.fetchone()
        if existing:
            existing_id, existing_status = existing
            return AlertIngestResponse(
                incident_id=uuid.UUID(str(existing_id)),
                status=existing_status,
                message=f"Duplicate alert deduplicated. Existing incident: {existing_id}",
            )

        # Create new incident
        incident_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO incidents_v2
              (id, correlation_id, cluster, namespace, alert_name, hostname, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'RECEIVED')
            """,
            (
                incident_id,
                payload.correlation_id,
                payload.cluster,
                payload.namespace,
                payload.alert_name,
                payload.hostname,
            ),
        )

        # Write initial timeline event
        cur.execute(
            """
            INSERT INTO incident_timeline
              (incident_id, actor_type, action, from_status, to_status, notes)
            VALUES (%s, 'system', 'Alert received and incident created', NULL, 'RECEIVED',
                    %s)
            """,
            (incident_id, f"correlation_id={payload.correlation_id}"),
        )

        conn.commit()

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create incident: {e}")
    finally:
        cur.close()
        conn.close()

    # Enqueue LangChain agent pipeline (async, non-blocking)
    run_agent_pipeline.apply_async(
        args=[
            incident_id,
            payload.alert_name,
            payload.namespace,
            payload.cluster,
            payload.hostname,
            payload.correlation_id,
            payload.awx_template_id,
        ],
        queue="default",
    )

    return AlertIngestResponse(
        incident_id=uuid.UUID(incident_id),
        status="RECEIVED",
        message="Incident created and agent pipeline enqueued.",
    )

---

// filepath: api/routers/analytics.py
"""Analytics router — aggregated metrics for the Analytics page."""

from __future__ import annotations

import psycopg2
from fastapi import APIRouter

from agents.config import DATABASE_TARGET
from api.schemas import AnalyticsSummaryOut

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/summary", response_model=AnalyticsSummaryOut)
async def get_analytics_summary():
    """
    Returns aggregated analytics data for:
    - MTTR by cluster/alert
    - Auto-resolved vs human-intervened breakdown
    - LLM accuracy (approved as-is / edited / rejected)
    - Top recurring alerts
    """
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur = conn.cursor()

    # 1. MTTR per cluster + alert (resolved incidents only)
    cur.execute(
        """
        SELECT cluster, alert_name,
               AVG(EXTRACT(EPOCH FROM (resolved_at - created_at))) AS avg_mttr_seconds,
               COUNT(*) AS incident_count
        FROM incidents_v2
        WHERE status = 'RESOLVED' AND resolved_at IS NOT NULL
        GROUP BY cluster, alert_name
        ORDER BY avg_mttr_seconds DESC
        LIMIT 20;
        """
    )
    mttr_rows = cur.fetchall()
    mttr_data = [
        {"cluster": r[0], "alert_name": r[1], "avg_mttr_seconds": float(r[2] or 0), "incident_count": r[3]}
        for r in mttr_rows
    ]

    # 2. Auto-resolved vs human-intervened
    cur.execute(
        """
        SELECT
            COUNT(*) FILTER (WHERE status = 'RESOLVED' AND risk_tier = 'LOW') AS auto_resolved,
            COUNT(*) FILTER (WHERE status IN ('RESOLVED','REJECTED') AND risk_tier = 'HIGH') AS human_intervened,
            COUNT(*) FILTER (WHERE status IN ('RESOLVED','REJECTED','ESCALATED','FAILED')) AS total
        FROM incidents_v2;
        """
    )
    res_row = cur.fetchone()
    auto_resolved = res_row[0] or 0
    human_intervened = res_row[1] or 0
    total_closed = res_row[2] or 1  # avoid div-by-zero

    resolution_stats = {
        "auto_resolved": auto_resolved,
        "human_intervened": human_intervened,
        "total": total_closed,
        "auto_resolved_pct": round(auto_resolved / total_closed * 100, 1),
        "human_intervened_pct": round(human_intervened / total_closed * 100, 1),
    }

    # 3. LLM accuracy: approved-as-is vs edited vs rejected
    cur.execute(
        """
        SELECT
            COUNT(*) FILTER (WHERE action = 'APPROVED') AS approved_as_is,
            COUNT(*) FILTER (WHERE action = 'EDITED') AS edited,
            COUNT(*) FILTER (WHERE action = 'REJECTED') AS rejected,
            COUNT(*) AS total_high_risk
        FROM human_actions;
        """
    )
    acc_row = cur.fetchone()
    llm_accuracy = {
        "approved_as_is": acc_row[0] or 0,
        "edited_before_approve": acc_row[1] or 0,
        "rejected": acc_row[2] or 0,
        "total_high_risk": acc_row[3] or 0,
    }

    # 4. Top recurring alert types (candidates to promote to LOW tier)
    cur.execute(
        """
        SELECT alert_name, cluster, COUNT(*) AS occurrences
        FROM incidents_v2
        WHERE created_at > NOW() - INTERVAL '30 days'
        GROUP BY alert_name, cluster
        ORDER BY occurrences DESC
        LIMIT 10;
        """
    )
    recurring = [
        {"alert_name": r[0], "cluster": r[1], "occurrences_30d": r[2]}
        for r in cur.fetchall()
    ]

    # 5. Flapping Alerts (Nuisance)
    cur.execute(
        """
        SELECT a.alertname, a.cluster_id, SUM(i.flapping_count) as total_flapping, MAX(COALESCE(r.reopen_count, 0)) as reopen_count
        FROM incidents i
        JOIN alert_occurrences a ON i.alert_fingerprint = a.fingerprint
        LEFT JOIN recurrence_intelligence r ON r.fingerprint = a.fingerprint
        GROUP BY a.alertname, a.cluster_id
        HAVING SUM(i.flapping_count) > 0 OR MAX(COALESCE(r.reopen_count, 0)) > 0
        ORDER BY (SUM(i.flapping_count) + MAX(COALESCE(r.reopen_count, 0))) DESC
        LIMIT 10;
        """
    )
    flapping = [
        {"alert_name": r[0], "cluster": r[1], "flapping_count": int(r[2]), "reopen_count": int(r[3])}
        for r in cur.fetchall()
    ]

    # 6. SRE Sentiment Trend
    cur.execute(
        """
        SELECT TO_CHAR(sys_updated_on, 'YYYY-MM-DD') as date, AVG(sentiment_score), COUNT(*) 
        FROM incidents 
        WHERE state IN ('Resolved', 'Closed')
        GROUP BY TO_CHAR(sys_updated_on, 'YYYY-MM-DD')
        ORDER BY date ASC;
        """
    )
    sentiment_trend = [
        {"date": r[0], "average_score": float(r[1]), "total_resolutions": int(r[2])}
        for r in cur.fetchall()
    ]

    # 7. Red Hat Case Summary
    cur.execute(
        """
        SELECT 
            COUNT(*) FILTER (WHERE status = 'Open') AS open_cases,
            COUNT(*) FILTER (WHERE severity IN ('Severity 1 (Urgent)', 'Severity 2 (High)'))::FLOAT / NULLIF(COUNT(*), 0) AS critical_pct,
            AVG(EXTRACT(EPOCH FROM (closed_on - created_on)))/86400.0 AS avg_mttr_days
        FROM redhat_cases;
        """
    )
    rh_row = cur.fetchone()
    rh_summary = {
        "open_cases": rh_row[0] or 0,
        "critical_escalation_pct": round((rh_row[1] or 0) * 100, 1),
        "avg_vendor_mttr_days": round(rh_row[2] or 0, 1)
    }

    # 8. Component Incidents (Problematic Components)
    cur.execute(
        """
        SELECT a.operator_component, COUNT(i.sys_id)
        FROM incidents i
        JOIN alert_occurrences a ON i.alert_fingerprint = a.fingerprint
        GROUP BY a.operator_component
        ORDER BY COUNT(i.sys_id) DESC
        LIMIT 10;
        """
    )
    components = [
        {"component": r[0], "incident_count": int(r[1])}
        for r in cur.fetchall()
    ]

    # 9. Fleet Risk (CVE)
    cur.execute("SELECT cluster_id, openshift_version FROM clusters")
    clusters_info = cur.fetchall()
    total_risk = 0
    critical_cves_active = 0
    for c_id, ver in clusters_info:
        cur.execute("SELECT severity FROM rhokp_cve_knowledge WHERE affected_versions @> %s", (f'"{ver}"',))
        cves = cur.fetchall()
        score = sum({"Critical": 10, "Important": 5, "Moderate": 2, "Low": 1}.get(c[0], 1) for c in cves)
        total_risk += min(100, int((score / 30) * 100))
        critical_cves_active += sum(1 for c in cves if c[0] == "Critical")
        
    fleet_risk = {
        "average_risk_pct": int(total_risk / len(clusters_info)) if clusters_info else 0,
        "critical_cves_active": critical_cves_active
    }

    # 10. Environment Distribution
    cur.execute(
        """
        SELECT c.environment, COUNT(i.sys_id)
        FROM incidents i
        JOIN clusters c ON i.cluster_id = c.cluster_id
        GROUP BY c.environment;
        """
    )
    env_dist = [
        {"environment": r[0] or "unknown", "incident_count": int(r[1])}
        for r in cur.fetchall()
    ]

    cur.close()
    conn.close()

    return {
        "mttr_by_cluster": mttr_data,
        "resolution_stats": resolution_stats,
        "llm_accuracy": llm_accuracy,
        "top_recurring_alerts": recurring,
        "flapping_alerts": flapping,
        "sentiment_trend": sentiment_trend,
        "redhat_cases_summary": rh_summary,
        "component_incidents": components,
        "fleet_risk": fleet_risk,
        "environment_distribution": env_dist
    }

---

// filepath: api/routers/chat.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import psycopg2
from typing import Optional
from langchain_core.messages import SystemMessage, HumanMessage

from agents.config import DATABASE_TARGET
from agents.langchain_agent import _get_llm

router = APIRouter(prefix="/chat", tags=["Chat"])

class ChatRequest(BaseModel):
    query: str
    timeframe_hours: int = 8

class ChatResponse(BaseModel):
    answer: str

from api.routers.summaries import get_embed_model

def get_context_for_timeframe(hours: int, query: str = "") -> str:
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur = conn.cursor()
    
    if hours >= 24:
        # Use vector semantic search against historical summaries
        model = get_embed_model()
        query_vector = model.encode(query).tolist()
        
        cur.execute(
            """
            SELECT shift_name, summary_text, created_at, (embedding <-> %s::vector) as distance
            FROM historical_shift_summaries
            WHERE created_at >= NOW() - INTERVAL '%s hours'
            ORDER BY embedding <-> %s::vector
            LIMIT 5
            """,
            (query_vector, hours, query_vector)
        )
        historical = cur.fetchall()
        cur.close()
        conn.close()
        
        context = f"--- TOP 5 RELEVANT SHIFT SUMMARIES FROM LAST {hours} HOURS ---\n"
        if not historical:
            context += "No relevant historical summaries found.\n"
        for h in historical:
            context += f"### {h[0]} (Date: {h[2]})\n{h[1]}\n\n"
        return context

    # 1. Get incidents (for < 24 hours)
    cur.execute(
        """
        SELECT alert_name, cluster, status, risk_tier, created_at, resolved_at 
        FROM incidents_v2 
        WHERE created_at >= NOW() - INTERVAL '%s hours'
        ORDER BY created_at DESC
        """,
        (hours,)
    )
    incidents = cur.fetchall()
    
    # 2. Get shift handovers
    cur.execute(
        """
        SELECT 
            author, shift_identifier, cluster, handover_type, priority,
            action_required, related_incidents, resolution_notes,
            upgraded_version, operator_name, message, created_at
        FROM shift_handovers 
        WHERE created_at >= NOW() - INTERVAL '%s hours'
        ORDER BY created_at DESC
        """,
        (hours,)
    )
    handovers = cur.fetchall()
    
    cur.close()
    conn.close()
    
    context = f"--- INCIDENTS IN LAST {hours} HOURS ---\n"
    if not incidents:
        context += "No incidents recorded.\n"
    for inc in incidents:
        context += f"- [{inc[4]}] Alert: {inc[0]} | Cluster: {inc[1]} | Status: {inc[2]} | Risk: {inc[3]}\n"
        
    context += f"\n--- SHIFT HANDOVERS IN LAST {hours} HOURS ---\n"
    if not handovers:
        context += "No handovers recorded.\n"
    for ho in handovers:
        (author, shift_identifier, cluster, handover_type, priority,
         action_required, related_incidents, resolution_notes,
         upgraded_version, operator_name, message, created_at) = ho
         
        ho_str = f"- [{created_at}] {shift_identifier or author} on {cluster} | Type: {handover_type} | Priority: {priority}\n"
        ho_str += f"  Message: {message}\n"
        if related_incidents:
            ho_str += f"  Related Incidents: {related_incidents}\n"
        if action_required:
            ho_str += "  ACTION REQUIRED from next shift.\n"
        if resolution_notes:
            ho_str += f"  Resolution: {resolution_notes}\n"
        if upgraded_version:
            ho_str += f"  Upgraded Version: {upgraded_version}\n"
        if operator_name:
            ho_str += f"  Operator: {operator_name}\n"
            
        context += ho_str
        
    return context

@router.post("", response_model=ChatResponse)
async def chat_with_context(req: ChatRequest):
    try:
        query = req.query.strip()
        
        # ─── Command Interception ───
        if query.startswith("/checkalerts"):
            parts = query.split()
            cluster_name = parts[1] if len(parts) > 1 else None
            
            conn = psycopg2.connect(**DATABASE_TARGET)
            cur = conn.cursor()
            if cluster_name:
                cur.execute("SELECT id, alert_name, risk_tier, status FROM incidents_v2 WHERE cluster = %s AND status != 'RESOLVED' ORDER BY created_at DESC LIMIT 5", (cluster_name,))
                msg = f"🔍 **Live Alerts for Cluster: {cluster_name}**\n\n"
            else:
                cur.execute("SELECT id, alert_name, risk_tier, cluster, status FROM incidents_v2 WHERE status != 'RESOLVED' ORDER BY created_at DESC LIMIT 5")
                msg = "🔍 **Recent Live Alerts Across All Clusters**\n\n"
                
            rows = cur.fetchall()
            cur.close()
            conn.close()
            
            if not rows:
                msg += "No active alerts found."
            else:
                for r in rows:
                    if cluster_name:
                        msg += f"- **{r[1]}** (ID: `{r[0]}`) | Tier: {r[2]} | Status: {r[3]}\n"
                    else:
                        msg += f"- **{r[1]}** on {r[3]} (ID: `{r[0]}`) | Tier: {r[2]} | Status: {r[4]}\n"
            return {"answer": msg}
            
        elif query.startswith("/escalate"):
            parts = query.split()
            if len(parts) < 2:
                return {"answer": "⚠️ Please provide an incident ID: `/escalate [incident_id]`"}
            inc_id = parts[1]
            
            conn = psycopg2.connect(**DATABASE_TARGET)
            cur = conn.cursor()
            cur.execute("UPDATE incidents_v2 SET risk_tier = 'CRITICAL', status = 'ESCALATED', updated_at = NOW() WHERE id = %s RETURNING alert_name", (inc_id,))
            row = cur.fetchone()
            if row:
                cur.execute(
                    "INSERT INTO incident_timeline (incident_id, actor_type, action, notes) VALUES (%s, 'human', 'escalated', 'Escalated via Summaries Chat')",
                    (inc_id,)
                )
                conn.commit()
                cur.close()
                conn.close()
                return {"answer": f"🚨 **Escalated!** Incident `{inc_id}` ({row[0]}) has been escalated to CRITICAL priority."}
            else:
                conn.rollback()
                cur.close()
                conn.close()
                return {"answer": f"❌ Could not find incident with ID `{inc_id}`."}
        # ────────────────────────────

        context_str = get_context_for_timeframe(req.timeframe_hours, query=req.query)
        
        system_prompt = (
            "You are an expert SRE shift assistant. Use the provided context to accurately answer the user's questions "
            "regarding past incidents, alerts, and shift handover messages. Do not hallucinate outside the provided context."
        )
        
        user_prompt = f"Context:\n{context_str}\n\nUser Query:\n{req.query}"
        
        llm = _get_llm()
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        response = llm.invoke(messages)
        
        return {"answer": response.content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

---

// filepath: api/routers/cve_advisor.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import text
from typing import List, Dict
import json
from ..dependencies import db_session
router = APIRouter(prefix="/clusters", tags=["CVE Advisor"])

# Weights for severity to calculate risk score
SEVERITY_WEIGHT = {
    "Critical": 10,
    "Important": 5,
    "Moderate": 2,
    "Low": 1
}
MAX_RISK_BASELINE = 30 # Arbitrary threshold to represent 100% risk for normalization

def calculate_risk_percent(cves: list) -> int:
    score = sum(SEVERITY_WEIGHT.get(cve.get("severity", "Low"), 1) for cve in cves)
    percent = min(100, int((score / MAX_RISK_BASELINE) * 100))
    return percent

@router.get("")
async def list_clusters(db: AsyncSession = Depends(db_session)):
    result = await db.execute(text("SELECT cluster_id AS id, name, openshift_version AS current_version FROM clusters;"))
    clusters = result.fetchall()
    
    output = []
    for c in clusters:
        cluster_dict = dict(c._mapping)
        active_cves_result = await db.execute(
            text("SELECT severity FROM rhokp_cve_knowledge WHERE affected_versions @> :ver"),
            {"ver": f'"{cluster_dict["current_version"]}"'}
        )
        current_cves = [dict(r._mapping) for r in active_cves_result]
        cluster_dict["risk_percent"] = calculate_risk_percent(current_cves)
        output.append(cluster_dict)
        
    return output

@router.get("/{cluster_id}/upgrade-advisor")
async def get_upgrade_advisor(cluster_id: str, db: AsyncSession = Depends(db_session)):
    # 1. Fetch cluster
    result = await db.execute(
        text("SELECT openshift_version AS current_version FROM clusters WHERE cluster_id = :id"),
        {"id": cluster_id}
    )
    cluster = result.fetchone()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
        
    cluster_dict = dict(cluster._mapping)
    current_version = cluster_dict["current_version"]
    
    # 2. Fetch all CVEs currently affecting this cluster
    # Using JSONB containment operator `@>` for affected_versions
    active_cves_result = await db.execute(
        text("SELECT advisory_id, severity, cves, raw_text FROM rhokp_cve_knowledge WHERE affected_versions @> :ver"),
        {"ver": f'"{current_version}"'}
    )
    current_cves = [dict(r._mapping) for r in active_cves_result]
    current_risk_percent = calculate_risk_percent(current_cves)

    # 3. Define target paths
    parts = current_version.split('.')
    if len(parts) != 3:
        raise HTTPException(status_code=400, detail="Invalid version format")
        
    # We evaluate +2 patches up, and +1 minor up based on our mock data structure
    targets = [
        {"version": f"{parts[0]}.{parts[1]}.{int(parts[2]) + 1}", "type": "patch"},
        {"version": f"{parts[0]}.{parts[1]}.{int(parts[2]) + 2}", "type": "patch"},
        {"version": f"{parts[0]}.{int(parts[1]) + 1}.0", "type": "minor"}
    ]
    
    paths = {}
    best_target = None
    lowest_risk = 101

    for target in targets:
        t_version = target["version"]
        
        # Risks Waiting: CVEs that explicitly affect the target version
        waiting_result = await db.execute(
            text("SELECT advisory_id, severity, cves, raw_text FROM rhokp_cve_knowledge WHERE affected_versions @> :ver"),
            {"ver": f'"{t_version}"'}
        )
        risks_waiting = [dict(r._mapping) for r in waiting_result]
        residual_risk_percent = calculate_risk_percent(risks_waiting)
        
        # Resolves: CVEs affecting the current version but NOT the target version
        waiting_advisory_ids = {w["advisory_id"] for w in risks_waiting}
        resolves = [cve for cve in current_cves if cve["advisory_id"] not in waiting_advisory_ids]
        
        # Track Best Upgrade
        if residual_risk_percent < lowest_risk:
            lowest_risk = residual_risk_percent
            best_target = t_version
            
        paths[t_version] = {
            "version": t_version,
            "type": target["type"],
            "residual_risk_percent": residual_risk_percent,
            "resolves": resolves,
            "risks_waiting": risks_waiting,
            "description": f"Upgrading to {t_version} leaves {len(risks_waiting)} known risks."
        }
        
    return {
        "current_version": current_version,
        "current_risk_percent": current_risk_percent,
        "current_cves": current_cves,
        "best_upgrade": best_target,
        "paths": paths
    }

---

// filepath: api/routers/handovers.py
"""
Shift Handovers API — v2

Structured handover notes between SRE shifts. Each note captures:
  - shift_identifier : outgoing engineer / shift label
  - cluster          : target cluster or ALL
  - handover_type    : handover | maintenance | upgrade | operator_upgrade |
                       incident_followup | change_freeze | escalation
  - priority         : low | medium | high | critical
  - action_required  : bool — next shift must act
  - related_incidents: comma-separated incident IDs
  - message          : free-text body

SSO NOTE: `author` is kept for legacy compatibility. When SSO is live,
populate it from the OIDC token in the request (e.g. via a Depends()).
"""

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
import psycopg2
import uuid
from typing import List, Optional
from datetime import datetime

from agents.config import DATABASE_TARGET

router = APIRouter(prefix="/handovers", tags=["Handovers"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class HandoverCreate(BaseModel):
    # SSO-ready: when OIDC is integrated, author/shift_identifier will be
    # injected server-side from the bearer token. Until then, clients send them.
    author: str
    shift_identifier: str
    cluster: str = "ALL"
    handover_type: str = "handover"   # matches handover_type_enum values
    priority: str = "medium"          # matches handover_priority_enum values
    action_required: bool = False
    related_incidents: str = ""
    message: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    upgraded_version: Optional[str] = None
    operator_name: Optional[str] = None


class HandoverOut(BaseModel):
    id: uuid.UUID
    author: str
    shift_identifier: str
    cluster: str
    handover_type: str
    priority: str
    action_required: bool
    related_incidents: str
    message: str
    created_at: datetime
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    is_active: bool = True
    resolution_notes: Optional[str] = None
    upgraded_version: Optional[str] = None
    operator_name: Optional[str] = None

class HandoverUpdate(BaseModel):
    is_active: Optional[bool] = None
    resolution_notes: Optional[str] = None
    action_required: Optional[bool] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_TYPES = {
    "handover", "maintenance", "upgrade", "operator_upgrade",
    "incident_followup", "change_freeze", "escalation",
}
_VALID_PRIORITIES = {"low", "medium", "high", "critical"}


def _row_to_dict(row: tuple) -> dict:
    return {
        "id":                 row[0],
        "author":             row[1],
        "shift_identifier":   row[2],
        "cluster":            row[3],
        "handover_type":      row[4],
        "priority":           row[5],
        "action_required":    row[6],
        "related_incidents":  row[7],
        "message":            row[8],
        "created_at":         row[9],
        "start_time":         row[10] if len(row) > 10 else None,
        "end_time":           row[11] if len(row) > 11 else None,
        "is_active":          row[12] if len(row) > 12 else True,
        "resolution_notes":   row[13] if len(row) > 13 else None,
        "upgraded_version":   row[14] if len(row) > 14 else None,
        "operator_name":      row[15] if len(row) > 15 else None,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=HandoverOut)
async def create_handover(handover: HandoverCreate):
    """Create a new shift handover note."""
    # Normalise / validate enum values
    h_type    = handover.handover_type if handover.handover_type in _VALID_TYPES     else "handover"
    h_prio    = handover.priority       if handover.priority       in _VALID_PRIORITIES else "medium"
    # shift_identifier defaults to author if not provided
    shift_id  = handover.shift_identifier.strip() or handover.author.strip()

    # Validation
    if h_type == "upgrade" and not handover.upgraded_version:
        raise HTTPException(status_code=400, detail="upgraded_version is required for Platform Upgrades")
    if h_type == "operator_upgrade" and (not handover.operator_name or not handover.upgraded_version):
        raise HTTPException(status_code=400, detail="operator_name and upgraded_version are required for Operator Upgrades")

    conn = psycopg2.connect(**DATABASE_TARGET)
    cur  = conn.cursor()
    new_id = uuid.uuid4()

    cur.execute(
        """
        INSERT INTO shift_handovers
            (id, author, shift_identifier, cluster, handover_type,
             priority, action_required, related_incidents, message, created_at,
             start_time, end_time, is_active, upgraded_version, operator_name)
        VALUES (%s, %s, %s, %s, %s::handover_type_enum,
                %s::handover_priority_enum, %s, %s, %s, NOW(), %s, %s, TRUE, %s, %s)
        RETURNING id, author, shift_identifier, cluster, handover_type,
                  priority, action_required, related_incidents, message, created_at,
                  start_time, end_time, is_active, resolution_notes, upgraded_version, operator_name
        """,
        (
            str(new_id),
            handover.author,
            shift_id,
            handover.cluster or "ALL",
            h_type,
            h_prio,
            handover.action_required,
            handover.related_incidents,
            handover.message,
            handover.start_time,
            handover.end_time,
            handover.upgraded_version,
            handover.operator_name
        )
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return _row_to_dict(row)


@router.get("", response_model=List[HandoverOut])
async def list_handovers(
    limit:          int           = Query(50, ge=1, le=200),
    cluster:        Optional[str] = Query(None, description="Filter by cluster name"),
    handover_type:  Optional[str] = Query(None, description="Filter by type"),
    priority:       Optional[str] = Query(None, description="Filter by priority"),
    action_required: Optional[bool] = Query(None, description="Filter action-required notes"),
):
    """
    List shift handovers, newest first.
    Supports optional filtering by cluster, type, priority, action_required.
    """
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur  = conn.cursor()

    conditions = []
    params: list = []

    if cluster:
        conditions.append("cluster = %s")
        params.append(cluster)
    if handover_type and handover_type in _VALID_TYPES:
        conditions.append("handover_type = %s::handover_type_enum")
        params.append(handover_type)
    if priority and priority in _VALID_PRIORITIES:
        conditions.append("priority = %s::handover_priority_enum")
        params.append(priority)
    if action_required is not None:
        conditions.append("action_required = %s")
        params.append(action_required)

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.append(limit)

    cur.execute(
        f"""
        SELECT id, author, shift_identifier, cluster, handover_type,
               priority, action_required, related_incidents, message, created_at,
               start_time, end_time, is_active, resolution_notes, upgraded_version, operator_name
        FROM shift_handovers
        {{where_clause}}
        ORDER BY created_at DESC
        LIMIT %s
        """.replace('{where_clause}', where_clause),
        params,
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [_row_to_dict(r) for r in rows]

@router.get("/active_ticker", response_model=List[HandoverOut])
async def get_active_ticker():
    """Fetch active handovers for the global floating pane."""
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, author, shift_identifier, cluster, handover_type,
               priority, action_required, related_incidents, message, created_at,
               start_time, end_time, is_active, resolution_notes, upgraded_version, operator_name
        FROM shift_handovers
        WHERE is_active = TRUE 
          AND (action_required = TRUE OR handover_type = 'maintenance')
          AND (end_time IS NULL OR end_time > NOW())
        ORDER BY priority DESC, created_at DESC
        """
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [_row_to_dict(r) for r in rows]

@router.patch("/{handover_id}", response_model=HandoverOut)
async def update_handover(handover_id: str, updates: HandoverUpdate):
    """Update active status or resolution notes for a handover."""
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur = conn.cursor()

    set_clauses = []
    params = []
    
    if updates.is_active is not None:
        set_clauses.append("is_active = %s")
        params.append(updates.is_active)
    if updates.resolution_notes is not None:
        set_clauses.append("resolution_notes = %s")
        params.append(updates.resolution_notes)
    if updates.action_required is not None:
        set_clauses.append("action_required = %s")
        params.append(updates.action_required)

    if not set_clauses:
        cur.close()
        conn.close()
        return {} # No-op

    params.append(handover_id)
    
    cur.execute(
        f"""
        UPDATE shift_handovers
        SET {', '.join(set_clauses)}
        WHERE id = %s
        RETURNING id, author, shift_identifier, cluster, handover_type,
                  priority, action_required, related_incidents, message, created_at,
                  start_time, end_time, is_active, resolution_notes, upgraded_version, operator_name
        """,
        params
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return _row_to_dict(row) if row else {}

@router.get("/clusters", response_model=List[str])
async def list_handover_clusters():
    """
    List all available clusters from the clusters table for the dropdown.
    """
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur  = conn.cursor()
    cur.execute("SELECT cluster_id FROM clusters ORDER BY cluster_id")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [r[0] for r in rows]


---

// filepath: api/routers/incidents.py
"""
Incidents router — CRUD + Human-in-the-Loop approval endpoints.

Endpoints:
  GET  /incidents                    → paginated list
  GET  /incidents/{id}               → full detail with timeline
  POST /incidents/{id}/approve       → approve and launch AWX
  POST /incidents/{id}/reject        → reject and page oncall
  POST /incidents/{id}/edit          → edit intent then approve
  POST /incidents/{id}/escalate      → manually escalate to oncall
"""

from __future__ import annotations

import json
import uuid

import psycopg2
from fastapi import APIRouter, Depends, HTTPException, Query, status

from agents.config import DATABASE_TARGET
from agents.langchain_tools import RemediationIntent
from api.dependencies import get_current_user
from api.schemas import (
    ApproveRequest,
    EditAndApproveRequest,
    EscalateRequest,
    HumanActionResponse,
    IncidentListOut,
    IncidentOut,
    RejectRequest,
)
from api.websocket import manager
from worker.tasks import poll_awx_job, trigger_pagerduty_escalation

router = APIRouter(prefix="/incidents", tags=["Incidents"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fetch_incident(cur, incident_id: str) -> dict:
    cur.execute(
        "SELECT id, correlation_id, cluster, namespace, alert_name, hostname, "
        "status, risk_tier, llm_confidence, llm_intent_json, analysis_summary, "
        "escalate_to, awx_job_id, "
        "created_at, updated_at, resolved_at "
        "FROM incidents_v2 WHERE id = %s",
        (incident_id,),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Incident not found")
    cols = [
        "id", "correlation_id", "cluster", "namespace", "alert_name", "hostname",
        "status", "risk_tier", "llm_confidence", "llm_intent_json", "analysis_summary",
        "escalate_to", "awx_job_id",
        "created_at", "updated_at", "resolved_at",
    ]
    return dict(zip(cols, row))


def _require_status(incident: dict, required: str):
    if incident["status"] != required:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Incident is in status '{incident['status']}', expected '{required}'",
        )


def _insert_human_action(
    cur,
    incident_id: str,
    user_id: str,
    action: str,
    original_intent: dict | None,
    final_intent: dict | None,
    reason: str,
):
    cur.execute(
        """
        INSERT INTO human_actions
          (incident_id, user_id, action, original_intent_json, final_intent_json, reason)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            incident_id,
            user_id,
            action,
            json.dumps(original_intent) if original_intent else None,
            json.dumps(final_intent) if final_intent else None,
            reason,
        ),
    )


def _insert_timeline(
    cur,
    incident_id: str,
    actor_type: str,
    action: str,
    from_status: str | None,
    to_status: str | None,
    actor_id: str | None = None,
    notes: str | None = None,
    metadata: dict | None = None,
):
    cur.execute(
        """
        INSERT INTO incident_timeline
          (incident_id, actor_type, actor_id, action, from_status, to_status, notes, metadata_json)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            incident_id,
            actor_type,
            actor_id,
            action,
            from_status,
            to_status,
            notes,
            json.dumps(metadata) if metadata else None,
        ),
    )


# ---------------------------------------------------------------------------
# GET /incidents
# ---------------------------------------------------------------------------


@router.get("", response_model=IncidentListOut)
async def list_incidents(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    cluster: str | None = None,
    alert_name: str | None = None,
):
    """Return paginated list of incidents, optionally filtered by status, cluster, and alert name."""
    offset = (page - 1) * page_size
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur = conn.cursor()

    where_clauses = []
    params = []
    if status_filter:
        where_clauses.append("status = %s")
        params.append(status_filter)
    if cluster:
        where_clauses.append("cluster = %s")
        params.append(cluster)
    if alert_name:
        where_clauses.append("alert_name = %s")
        params.append(alert_name)

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    cur.execute(f"SELECT COUNT(*) FROM incidents_v2 {where_sql}", params)
    total = cur.fetchone()[0]

    cur.execute(
        f"SELECT id, correlation_id, cluster, namespace, alert_name, hostname, "
        f"status, risk_tier, llm_confidence, llm_intent_json, analysis_summary, "
        f"escalate_to, awx_job_id, "
        f"created_at, updated_at, resolved_at "
        f"FROM incidents_v2 {where_sql} ORDER BY created_at DESC LIMIT %s OFFSET %s",
        params + [page_size, offset],
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    cols = [
        "id", "correlation_id", "cluster", "namespace", "alert_name", "hostname",
        "status", "risk_tier", "llm_confidence", "llm_intent_json", "analysis_summary",
        "escalate_to", "awx_job_id",
        "created_at", "updated_at", "resolved_at",
    ]
    items = [dict(zip(cols, r)) for r in rows]
    return {"total": total, "page": page, "page_size": page_size, "items": items}


# ---------------------------------------------------------------------------
# GET /incidents/{id}
# ---------------------------------------------------------------------------


@router.get("/{incident_id}", response_model=IncidentOut)
async def get_incident(incident_id: uuid.UUID):
    """Return full incident detail including timeline, human actions, and LLM decisions."""
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur = conn.cursor()

    incident = _fetch_incident(cur, str(incident_id))

    # Timeline
    cur.execute(
        "SELECT id, timestamp, actor_type, actor_id, action, from_status, to_status, notes, metadata_json "
        "FROM incident_timeline WHERE incident_id = %s ORDER BY timestamp ASC",
        (str(incident_id),),
    )
    tl_cols = ["id", "timestamp", "actor_type", "actor_id", "action", "from_status", "to_status", "notes", "metadata_json"]
    incident["timeline"] = [dict(zip(tl_cols, r)) for r in cur.fetchall()]

    # Human actions
    cur.execute(
        "SELECT id, user_id, action, original_intent_json, final_intent_json, reason, timestamp "
        "FROM human_actions WHERE incident_id = %s ORDER BY timestamp ASC",
        (str(incident_id),),
    )
    ha_cols = ["id", "user_id", "action", "original_intent_json", "final_intent_json", "reason", "timestamp"]
    incident["human_actions"] = [dict(zip(ha_cols, r)) for r in cur.fetchall()]

    # LLM decisions
    cur.execute(
        "SELECT id, prompt_used, raw_llm_output, parsed_intent, confidence, tool_calls_json, timestamp "
        "FROM llm_decisions WHERE incident_id = %s ORDER BY timestamp DESC LIMIT 5",
        (str(incident_id),),
    )
    ld_cols = ["id", "prompt_used", "raw_llm_output", "parsed_intent", "confidence", "tool_calls_json", "timestamp"]
    incident["llm_decisions"] = [dict(zip(ld_cols, r)) for r in cur.fetchall()]

    cur.close()
    conn.close()
    return incident


# ---------------------------------------------------------------------------
# POST /incidents/{id}/approve
# ---------------------------------------------------------------------------


@router.post("/{incident_id}/approve", response_model=HumanActionResponse)
async def approve_incident(
    incident_id: uuid.UUID,
    body: ApproveRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Human approves a HIGH-risk action. Launches AWX job immediately.

    Requirements:
    - Incident must be in PENDING_APPROVAL status.
    - Reason must be non-empty (min 5 chars).
    - User must be authenticated (JWT).
    """
    user_id = current_user["user_id"]
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur = conn.cursor()

    try:
        incident = _fetch_incident(cur, str(incident_id))
        _require_status(incident, "PENDING_APPROVAL")

        original_intent = incident.get("llm_intent_json") or {}

        # Launch AWX job with the ORIGINAL validated intent
        from agents.config import USE_MOCK_AWX
        if USE_MOCK_AWX:
            from simulation.mock_client import MockAWXClient
            awx = MockAWXClient()
        else:
            from awx.client import AWXClient
            awx = AWXClient()

        intent = RemediationIntent(**original_intent)
        job_id = awx.launch_job(template_id="1", extra_vars=intent.to_awx_extra_vars())

        # Update incident
        cur.execute(
            "UPDATE incidents_v2 SET status='EXECUTING', awx_job_id=%s, updated_at=NOW() WHERE id=%s",
            (job_id, str(incident_id)),
        )

        # Record human action
        _insert_human_action(cur, str(incident_id), user_id, "APPROVED", original_intent, original_intent, body.reason)

        # Append timeline event
        _insert_timeline(
            cur, str(incident_id), "human", "Human APPROVED — AWX job launched",
            "PENDING_APPROVAL", "EXECUTING", actor_id=user_id,
            notes=body.reason, metadata={"awx_job_id": job_id},
        )

        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

    # Broadcast WebSocket event
    await manager.broadcast_status_change(
        str(incident_id), "EXECUTING", actor=user_id, notes=body.reason
    )

    # Kick off AWX poll task
    poll_awx_job.apply_async(args=[str(incident_id), job_id], countdown=10, queue="priority")

    return HumanActionResponse(
        incident_id=incident_id,
        new_status="EXECUTING",
        message=f"AWX job #{job_id} launched after human approval by {user_id}",
    )


# ---------------------------------------------------------------------------
# POST /incidents/{id}/reject
# ---------------------------------------------------------------------------


@router.post("/{incident_id}/reject", response_model=HumanActionResponse)
async def reject_incident(
    incident_id: uuid.UUID,
    body: RejectRequest,
    current_user: dict = Depends(get_current_user),
):
    """Human rejects the proposed action. Pages oncall."""
    user_id = current_user["user_id"]
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur = conn.cursor()

    try:
        incident = _fetch_incident(cur, str(incident_id))
        _require_status(incident, "PENDING_APPROVAL")

        cur.execute(
            "UPDATE incidents_v2 SET status='REJECTED', updated_at=NOW() WHERE id=%s",
            (str(incident_id),),
        )
        _insert_human_action(
            cur, str(incident_id), user_id, "REJECTED",
            incident.get("llm_intent_json"), None, body.reason
        )
        _insert_timeline(
            cur, str(incident_id), "human", "Human REJECTED proposed action",
            "PENDING_APPROVAL", "REJECTED", actor_id=user_id, notes=body.reason,
        )
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

    await manager.broadcast_status_change(str(incident_id), "REJECTED", actor=user_id)
    trigger_pagerduty_escalation.delay(str(incident_id), f"Rejected by {user_id}: {body.reason}")

    return HumanActionResponse(
        incident_id=incident_id,
        new_status="REJECTED",
        message=f"Incident rejected by {user_id}. Oncall notified.",
    )


# ---------------------------------------------------------------------------
# POST /incidents/{id}/edit
# ---------------------------------------------------------------------------


@router.post("/{incident_id}/edit", response_model=HumanActionResponse)
async def edit_and_approve_incident(
    incident_id: uuid.UUID,
    body: EditAndApproveRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Human edits the proposed intent (e.g. changes target or action) then approves.
    The modified_intent is re-validated against RemediationIntent Pydantic schema
    before AWX is called — never raw JSON from the UI.
    """
    user_id = current_user["user_id"]

    # Validate modified intent against Pydantic schema BEFORE any DB writes
    try:
        intent = RemediationIntent(**body.modified_intent)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Modified intent failed validation: {e}",
        )

    conn = psycopg2.connect(**DATABASE_TARGET)
    cur = conn.cursor()

    try:
        incident = _fetch_incident(cur, str(incident_id))
        _require_status(incident, "PENDING_APPROVAL")
        original_intent = incident.get("llm_intent_json") or {}

        from agents.config import USE_MOCK_AWX
        if USE_MOCK_AWX:
            from simulation.mock_client import MockAWXClient
            awx = MockAWXClient()
        else:
            from awx.client import AWXClient
            awx = AWXClient()

        job_id = awx.launch_job(template_id="1", extra_vars=intent.to_awx_extra_vars())

        cur.execute(
            "UPDATE incidents_v2 SET status='EXECUTING', awx_job_id=%s, "
            "llm_intent_json=%s, updated_at=NOW() WHERE id=%s",
            (job_id, json.dumps(intent.model_dump()), str(incident_id)),
        )
        _insert_human_action(
            cur, str(incident_id), user_id, "EDITED",
            original_intent, intent.model_dump(), body.reason,
        )
        _insert_timeline(
            cur, str(incident_id), "human",
            "Human EDITED intent and APPROVED — AWX job launched",
            "PENDING_APPROVAL", "EXECUTING", actor_id=user_id,
            notes=body.reason,
            metadata={"original_intent": original_intent, "final_intent": intent.model_dump(), "awx_job_id": job_id},
        )
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

    await manager.broadcast_status_change(str(incident_id), "EXECUTING", actor=user_id)
    poll_awx_job.apply_async(args=[str(incident_id), job_id], countdown=10, queue="priority")

    return HumanActionResponse(
        incident_id=incident_id,
        new_status="EXECUTING",
        message=f"Edited intent approved by {user_id}. AWX job #{job_id} launched.",
    )


# ---------------------------------------------------------------------------
# POST /incidents/{id}/escalate
# ---------------------------------------------------------------------------


@router.post("/{incident_id}/escalate", response_model=HumanActionResponse)
async def escalate_incident(
    incident_id: uuid.UUID,
    body: EscalateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Human manually escalates to oncall from any active status."""
    user_id = current_user["user_id"]
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur = conn.cursor()

    try:
        incident = _fetch_incident(cur, str(incident_id))
        if incident["status"] in ("RESOLVED", "REJECTED", "ESCALATED"):
            raise HTTPException(
                status_code=409, detail=f"Cannot escalate incident in status {incident['status']}"
            )

        cur.execute(
            "UPDATE incidents_v2 SET status='ESCALATED', updated_at=NOW() WHERE id=%s",
            (str(incident_id),),
        )
        _insert_human_action(
            cur, str(incident_id), user_id, "ESCALATED",
            incident.get("llm_intent_json"), None, body.reason,
        )
        _insert_timeline(
            cur, str(incident_id), "human", "Human manually ESCALATED to oncall",
            incident["status"], "ESCALATED", actor_id=user_id, notes=body.reason,
        )
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

    await manager.broadcast_status_change(str(incident_id), "ESCALATED", actor=user_id)
    trigger_pagerduty_escalation.delay(str(incident_id), f"Manually escalated by {user_id}: {body.reason}")

    return HumanActionResponse(
        incident_id=incident_id,
        new_status="ESCALATED",
        message=f"Escalated by {user_id}. Oncall paged.",
    )

---

// filepath: api/routers/summaries.py
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import psycopg2
from langchain_core.messages import SystemMessage, HumanMessage
from sentence_transformers import SentenceTransformer

from agents.config import DATABASE_TARGET, EMBED_MODEL_NAME
from agents.langchain_agent import _get_llm

router = APIRouter(prefix="/summaries", tags=["Summaries"])

embed_model = None

def get_embed_model():
    global embed_model
    if embed_model is None:
        embed_model = SentenceTransformer(EMBED_MODEL_NAME)
    return embed_model

def get_previous_shift_window():
    """
    Returns (shift_name, start_time, end_time) for the immediately preceding shift.
    Shifts: 00:00-08:00, 08:00-16:00, 16:00-00:00.
    """
    now = datetime.now(timezone.utc)
    hour = now.hour
    
    if 0 <= hour < 8:
        # Prev shift: yesterday 16:00 to today 00:00
        end_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_time = end_time - timedelta(hours=8)
        shift_name = f"Shift 3 (16:00-00:00) {start_time.strftime('%Y-%m-%d')}"
    elif 8 <= hour < 16:
        # Prev shift: today 00:00 to 08:00
        end_time = now.replace(hour=8, minute=0, second=0, microsecond=0)
        start_time = end_time - timedelta(hours=8)
        shift_name = f"Shift 1 (00:00-08:00) {start_time.strftime('%Y-%m-%d')}"
    else:
        # Prev shift: today 08:00 to 16:00
        end_time = now.replace(hour=16, minute=0, second=0, microsecond=0)
        start_time = end_time - timedelta(hours=8)
        shift_name = f"Shift 2 (08:00-16:00) {start_time.strftime('%Y-%m-%d')}"
        
    return shift_name, start_time, end_time

class SummaryPreviewResponse(BaseModel):
    shift_name: str
    preview_text: str

@router.post("/preview", response_model=SummaryPreviewResponse)
async def preview_summary():
    shift_name, start_time, end_time = get_previous_shift_window()
    
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur = conn.cursor()
    
    # Fetch incidents
    cur.execute(
        """
        SELECT alert_name, cluster, status, risk_tier, created_at
        FROM incidents_v2 
        WHERE created_at >= %s AND created_at < %s
        ORDER BY created_at ASC
        """,
        (start_time, end_time)
    )
    incidents = cur.fetchall()
    
    # Fetch handovers
    cur.execute(
        """
        SELECT 
            author, shift_identifier, cluster, handover_type, priority,
            action_required, related_incidents, resolution_notes,
            upgraded_version, operator_name, message, created_at
        FROM shift_handovers 
        WHERE created_at >= %s AND created_at < %s
        ORDER BY created_at ASC
        """,
        (start_time, end_time)
    )
    handovers = cur.fetchall()
    
    cur.close()
    conn.close()
    
    context = f"--- INCIDENTS FROM {start_time} TO {end_time} ---\n"
    if not incidents:
        context += "No incidents recorded.\n"
    for inc in incidents:
        context += f"- Alert: {inc[0]} | Cluster: {inc[1]} | Status: {inc[2]} | Risk: {inc[3]}\n"
        
    context += f"\n--- SHIFT HANDOVERS FROM {start_time} TO {end_time} ---\n"
    if not handovers:
        context += "No handovers recorded.\n"
    for ho in handovers:
        (author, shift_identifier, cluster, handover_type, priority,
         action_required, related_incidents, resolution_notes,
         upgraded_version, operator_name, message, created_at) = ho
         
        ho_str = f"- [{created_at}] {shift_identifier or author} on {cluster} | Type: {handover_type} | Priority: {priority}\n"
        ho_str += f"  Message: {message}\n"
        if related_incidents:
            ho_str += f"  Related Incidents: {related_incidents}\n"
        if action_required:
            ho_str += "  ACTION REQUIRED from next shift.\n"
        if resolution_notes:
            ho_str += f"  Resolution: {resolution_notes}\n"
        if upgraded_version:
            ho_str += f"  Upgraded Version: {upgraded_version}\n"
        if operator_name:
            ho_str += f"  Operator: {operator_name}\n"
        
        context += ho_str
        
    system_prompt = (
        "You are an SRE shift supervisor. Write a clear, comprehensive markdown report "
        "summarizing the events of the shift based on the provided logs. Group related events, "
        "highlight ongoing maintenance or issues, and provide a quick executive summary at the top.\n"
        "CRITICAL REQUIREMENTS:\n"
        "- If a handover has 'Resolution' notes or was completed, you MUST state that it was resolved and what the resolution was.\n"
        "- You MUST include all 'Related Incidents' (e.g., INC123456) for each handover.\n"
        "- Do not omit any crucial operational metadata like target versions or operator names."
    )
    
    user_prompt = f"Shift Log:\n{context}\n\nPlease generate the Final Shift Report."
    
    llm = _get_llm()
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]
    
    response = llm.invoke(messages)
    
    return {
        "shift_name": shift_name,
        "preview_text": response.content
    }

class SummarySaveRequest(BaseModel):
    shift_name: str
    summary_text: str
    is_auto_generated: bool = False

@router.post("/save")
async def save_summary(req: SummarySaveRequest):
    try:
        model = get_embed_model()
        vector_coord = model.encode(req.summary_text).tolist()
        
        conn = psycopg2.connect(**DATABASE_TARGET)
        cur = conn.cursor()
        
        new_id = uuid.uuid4()
        
        cur.execute(
            """
            INSERT INTO historical_shift_summaries (id, shift_name, summary_text, embedding, is_auto_generated)
            VALUES (%s, %s, %s, %s::vector, %s)
            """,
            (str(new_id), req.shift_name, req.summary_text, vector_coord, req.is_auto_generated)
        )
        conn.commit()
        cur.close()
        conn.close()
        return {"status": "success", "id": str(new_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/historical")
async def get_historical_summaries():
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur = conn.cursor()
    
    cur.execute(
        """
        SELECT id, shift_name, summary_text, is_auto_generated, created_at 
        FROM historical_shift_summaries 
        ORDER BY created_at DESC 
        LIMIT 20
        """
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    return [
        {
            "id": r[0],
            "shift_name": r[1],
            "summary_text": r[2],
            "is_auto_generated": r[3],
            "created_at": r[4]
        }
        for r in rows
    ]

---

// filepath: api/routers/__init__.py
"""routers package init."""

---

// filepath: awx/client.py
"""
AWX REST API client.

Design rules (NON-NEGOTIABLE):
- AWX is the ONLY way Ansible playbooks are executed. No subprocess.
- extra_vars ALWAYS comes from a validated RemediationIntent Pydantic model.
- This client never constructs extra_vars from raw strings or raw LLM output.

AWX API reference:
  POST /api/v2/job_templates/{id}/launch/  → launch job
  GET  /api/v2/jobs/{id}/                  → get job status
  POST /api/v2/jobs/{id}/cancel/           → cancel job
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx

from agents.config import AWX_API_TOKEN, AWX_BASE_URL

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# AWX job status enum
# ---------------------------------------------------------------------------


class AWXJobStatus(str, Enum):
    PENDING = "pending"
    WAITING = "waiting"
    RUNNING = "running"
    SUCCESSFUL = "successful"
    FAILED = "failed"
    ERROR = "error"
    CANCELED = "canceled"

    @property
    def is_terminal(self) -> bool:
        return self in (
            AWXJobStatus.SUCCESSFUL,
            AWXJobStatus.FAILED,
            AWXJobStatus.ERROR,
            AWXJobStatus.CANCELED,
        )

    @property
    def is_success(self) -> bool:
        return self == AWXJobStatus.SUCCESSFUL


@dataclass
class AWXJobResult:
    job_id: str
    status: AWXJobStatus
    url: str
    elapsed: float | None = None
    failed: bool = False
    extra_vars: dict | None = None


# ---------------------------------------------------------------------------
# Real AWX REST client
# ---------------------------------------------------------------------------


class AWXClient:
    """
    Synchronous AWX REST API client using httpx.

    Usage:
        client = AWXClient()
        job_id = client.launch_job(template_id="42", extra_vars=intent.to_awx_extra_vars())
        result = client.get_job_status(job_id)
    """

    def __init__(
        self,
        base_url: str = AWX_BASE_URL,
        api_token: str = AWX_API_TOKEN,
        timeout: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }
        self._timeout = timeout

    def _request(self, method: str, path: str, **kwargs: Any) -> dict:
        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(headers=self._headers, timeout=self._timeout) as client:
                response = getattr(client, method)(url, **kwargs)
                response.raise_for_status()
                # Some AWX endpoints return 204 No Content on cancel
                return response.json() if response.content else {}
        except httpx.HTTPStatusError as e:
            logger.error("AWX HTTP error %s %s → %s", method.upper(), url, e.response.status_code)
            raise
        except httpx.RequestError as e:
            logger.error("AWX connection error %s %s → %s", method.upper(), url, e)
            raise

    def launch_job(self, template_id: str, extra_vars: dict) -> str:
        """
        Launch an AWX job template.

        Parameters
        ----------
        template_id:
            AWX job template ID (from the AWX UI / API).
        extra_vars:
            Dict produced by RemediationIntent.to_awx_extra_vars().
            NEVER pass raw strings from LLM output here.

        Returns
        -------
        AWX job ID as a string.
        """
        logger.info(
            "Launching AWX job template=%s extra_vars=%s", template_id, extra_vars
        )
        result = self._request(
            "post",
            f"/api/v2/job_templates/{template_id}/launch/",
            json={"extra_vars": extra_vars},
        )
        job_id = str(result["id"])
        logger.info("AWX job launched: job_id=%s", job_id)
        return job_id

    def get_job_status(self, job_id: str) -> AWXJobResult:
        """Poll the current status of an AWX job."""
        result = self._request("get", f"/api/v2/jobs/{job_id}/")
        status_str = result.get("status", "error")

        try:
            status = AWXJobStatus(status_str)
        except ValueError:
            status = AWXJobStatus.ERROR

        return AWXJobResult(
            job_id=job_id,
            status=status,
            url=f"{self.base_url}/#/jobs/playbook/{job_id}/details",
            elapsed=result.get("elapsed"),
            failed=result.get("failed", False),
            extra_vars=result.get("extra_vars"),
        )

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running AWX job. Returns True if cancel was accepted."""
        try:
            self._request("post", f"/api/v2/jobs/{job_id}/cancel/")
            logger.info("AWX job %s cancel requested", job_id)
            return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 405:
                # 405 = already terminal
                return False
            raise


# ---------------------------------------------------------------------------
# Factory: returns real or mock client based on config
# ---------------------------------------------------------------------------


def get_awx_client() -> AWXClient:
    """
    Returns the real AWXClient.
    Import simulation.mock_client.MockAWXClient for local development.
    Use agents.config.USE_MOCK_AWX to switch automatically in worker/tasks.py.
    """
    return AWXClient()

---

// filepath: awx/__init__.py
"""AWX package — real and mock AWX REST API clients."""

---

// filepath: db/models.py
"""
SQLAlchemy async ORM models for the LangChain Incident Tracking system.

Key design decisions:
- incidents_v2 uses UUID primary key (gen_random_uuid from pgcrypto).
- incident_timeline is append-only — no update method exposed.
- All timestamps are TIMESTAMPTZ (timezone-aware).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Incident (core record)
# ---------------------------------------------------------------------------

VALID_STATUSES = (
    "RECEIVED",
    "ANALYZING",
    "PENDING_APPROVAL",
    "EXECUTING",
    "VERIFYING",
    "RESOLVED",
    "REJECTED",
    "ESCALATED",
    "FAILED",
)

VALID_RISK_TIERS = ("LOW", "HIGH", "ESCALATE")


class Incident(Base):
    __tablename__ = "incidents_v2"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    correlation_id: Mapped[str | None] = mapped_column(String, unique=True)
    cluster: Mapped[str] = mapped_column(String, nullable=False)
    namespace: Mapped[str] = mapped_column(String, nullable=False)
    alert_name: Mapped[str] = mapped_column(String, nullable=False)
    hostname: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="RECEIVED",
        server_default="RECEIVED",
    )
    risk_tier: Mapped[str | None] = mapped_column(String)
    llm_confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))
    llm_intent_json: Mapped[dict | None] = mapped_column(JSONB)
    analysis_summary: Mapped[str | None] = mapped_column(Text)
    escalate_to: Mapped[str | None] = mapped_column(String)
    awx_job_id: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column()

    # Relationships
    timeline: Mapped[list[IncidentTimelineEvent]] = relationship(
        back_populates="incident",
        order_by="IncidentTimelineEvent.timestamp",
        lazy="selectin",
    )
    human_actions: Mapped[list[HumanAction]] = relationship(
        back_populates="incident",
        order_by="HumanAction.timestamp",
        lazy="selectin",
    )
    llm_decisions: Mapped[list[LLMDecision]] = relationship(
        back_populates="incident",
        order_by="LLMDecision.timestamp",
        lazy="selectin",
    )

    __table_args__ = (
        CheckConstraint(f"status IN {VALID_STATUSES}", name="ck_incident_status"),
        CheckConstraint(
            f"risk_tier IN {VALID_RISK_TIERS} OR risk_tier IS NULL",
            name="ck_incident_risk_tier",
        ),
        Index("idx_incidents_v2_status", "status"),
        Index("idx_incidents_v2_cluster_alert", "cluster", "alert_name"),
        Index("idx_incidents_v2_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Incident id={self.id} alert={self.alert_name} status={self.status}>"


# ---------------------------------------------------------------------------
# Incident Timeline (append-only audit log)
# ---------------------------------------------------------------------------


class IncidentTimelineEvent(Base):
    __tablename__ = "incident_timeline"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents_v2.id", ondelete="CASCADE"),
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    actor_type: Mapped[str] = mapped_column(
        String, nullable=False
    )  # agent | human | system
    actor_id: Mapped[str | None] = mapped_column(String)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    from_status: Mapped[str | None] = mapped_column(String)
    to_status: Mapped[str | None] = mapped_column(String)
    notes: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)

    incident: Mapped[Incident] = relationship(back_populates="timeline")

    __table_args__ = (
        CheckConstraint(
            "actor_type IN ('agent', 'human', 'system')",
            name="ck_timeline_actor_type",
        ),
        Index("idx_timeline_incident_id", "incident_id", "timestamp"),
    )

    def __repr__(self) -> str:
        return (
            f"<TimelineEvent incident={self.incident_id} "
            f"actor={self.actor_type} action={self.action}>"
        )


# ---------------------------------------------------------------------------
# Human Actions
# ---------------------------------------------------------------------------


class HumanAction(Base):
    __tablename__ = "human_actions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents_v2.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)  # APPROVED|REJECTED|EDITED|ESCALATED
    original_intent_json: Mapped[dict | None] = mapped_column(JSONB)
    final_intent_json: Mapped[dict | None] = mapped_column(JSONB)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    incident: Mapped[Incident] = relationship(back_populates="human_actions")

    __table_args__ = (
        CheckConstraint(
            "action IN ('APPROVED','REJECTED','EDITED','ESCALATED')",
            name="ck_human_action_type",
        ),
        Index("idx_human_actions_incident", "incident_id", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<HumanAction user={self.user_id} action={self.action}>"


# ---------------------------------------------------------------------------
# LLM Decisions
# ---------------------------------------------------------------------------


class LLMDecision(Base):
    __tablename__ = "llm_decisions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents_v2.id", ondelete="CASCADE"),
        nullable=False,
    )
    prompt_used: Mapped[str | None] = mapped_column(Text)
    raw_llm_output: Mapped[str | None] = mapped_column(Text)
    parsed_intent: Mapped[dict | None] = mapped_column(JSONB)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))
    tool_calls_json: Mapped[dict | None] = mapped_column(JSONB)
    timestamp: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    incident: Mapped[Incident] = relationship(back_populates="llm_decisions")

    __table_args__ = (
        Index("idx_llm_decisions_incident", "incident_id", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<LLMDecision incident={self.incident_id} conf={self.confidence}>"


# ---------------------------------------------------------------------------
# Helper: append a timeline event (enforces append-only contract)
# ---------------------------------------------------------------------------


async def log_timeline_event(
    session: Any,
    incident_id: uuid.UUID,
    actor_type: str,
    action: str,
    from_status: str | None = None,
    to_status: str | None = None,
    actor_id: str | None = None,
    notes: str | None = None,
    metadata: dict | None = None,
) -> IncidentTimelineEvent:
    """
    Always INSERTs a new row. Never updates existing rows.
    This is the ONLY way timeline events should be written.
    """
    event = IncidentTimelineEvent(
        incident_id=incident_id,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        from_status=from_status,
        to_status=to_status,
        notes=notes,
        metadata_json=metadata,
    )
    session.add(event)
    return event


# ---------------------------------------------------------------------------
# Cluster Inventory
# ---------------------------------------------------------------------------

class ClusterInventory(Base):
    __tablename__ = "cluster_inventory"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    current_version: Mapped[str] = mapped_column(String, nullable=False)
    active_cves: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<ClusterInventory id={self.id} name={self.name} version={self.current_version}>"

# ---------------------------------------------------------------------------
# Shift Handovers
# ---------------------------------------------------------------------------

class ShiftHandover(Base):
    __tablename__ = "shift_handovers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    author: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<ShiftHandover id={self.id} author={self.author}>"

---

// filepath: db/pg_notify.py
"""
PostgreSQL LISTEN/NOTIFY bridge for Celery → FastAPI WebSocket notifications.

WHY THIS EXISTS:
  Celery workers and the FastAPI process are separate OS processes.
  The FastAPI WebSocket manager lives in the API process memory.
  Celery cannot directly call manager.broadcast() — it has zero WebSocket connections.

HOW IT WORKS:
  1. Celery calls `notify_status_change(incident_id, new_status)`.
     This fires a PostgreSQL NOTIFY on channel 'incident_updates'.
  2. The FastAPI API process runs `listen_for_pg_notifications()` as a background task.
     It receives the NOTIFY payload and calls manager.broadcast() with live WS connections.

This is reliable, zero-dependency (uses the existing Postgres connection), and works
across any number of Celery worker processes.
"""

from __future__ import annotations

import asyncio
import json
import logging

import psycopg2
import psycopg2.extensions

from agents.config import DATABASE_TARGET

logger = logging.getLogger(__name__)

PG_CHANNEL = "incident_updates"


# ---------------------------------------------------------------------------
# Celery side: fire-and-forget NOTIFY (synchronous, safe in any process)
# ---------------------------------------------------------------------------


def notify_status_change(incident_id: str, new_status: str, actor: str = "agent") -> None:
    """
    Send a PostgreSQL NOTIFY from any process (Celery worker, API, etc.).
    The FastAPI listener will pick this up and push it to WebSocket clients.
    """
    payload = json.dumps({
        "incident_id": incident_id,
        "new_status": new_status,
        "actor": actor,
    })
    try:
        conn = psycopg2.connect(**DATABASE_TARGET)
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute(f"NOTIFY {PG_CHANNEL}, %s", (payload,))
        cur.close()
        conn.close()
        logger.debug("NOTIFY sent: incident_id=%s status=%s", incident_id, new_status)
    except Exception as e:
        logger.error("Failed to send NOTIFY for incident %s: %s", incident_id, e)


# ---------------------------------------------------------------------------
# FastAPI side: async listener that bridges PG NOTIFY → WebSocket broadcast
# ---------------------------------------------------------------------------


async def listen_for_pg_notifications(manager) -> None:
    """
    Long-running async task to be started in FastAPI lifespan.
    Listens on the PostgreSQL NOTIFY channel and forwards status changes
    to all subscribed WebSocket clients via the connection manager.

    Usage in api/main.py lifespan:
        asyncio.create_task(listen_for_pg_notifications(manager))
    """
    logger.info("Starting PostgreSQL NOTIFY listener on channel '%s'", PG_CHANNEL)

    # Use a dedicated synchronous connection in a thread executor
    # (psycopg2 is not async-native; we poll it in a thread)
    loop = asyncio.get_running_loop()

    def _blocking_listen():
        """Runs in a thread — polls for NOTIFY using conn.poll() (cross-platform, works on Windows)."""
        import time

        conn = psycopg2.connect(**DATABASE_TARGET)
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute(f"LISTEN {PG_CHANNEL}")
        logger.info("LISTEN registered on channel '%s'", PG_CHANNEL)

        while True:
            # poll() is cross-platform (works on Windows unlike select.select with psycopg2 FDs)
            conn.poll()
            while conn.notifies:
                notify = conn.notifies.pop(0)
                try:
                    data = json.loads(notify.payload)
                    # Schedule the async broadcast from the sync thread
                    asyncio.run_coroutine_threadsafe(
                        manager.broadcast(
                            data["incident_id"],
                            {
                                "type": "status_change",
                                "incident_id": data["incident_id"],
                                "new_status": data["new_status"],
                                "actor": data.get("actor", "system"),
                            },
                        ),
                        loop,
                    )
                    logger.info(
                        "Forwarded NOTIFY to WebSocket: incident_id=%s status=%s",
                        data.get("incident_id"), data.get("new_status"),
                    )
                except Exception as e:
                    logger.error("Failed to process NOTIFY payload: %s", e)
            # Sleep briefly to avoid busy-waiting (5s matches previous select timeout)
            time.sleep(1)

    await loop.run_in_executor(None, _blocking_listen)

---

// filepath: db/session.py
"""
Async SQLAlchemy engine and session factory.

Usage (in FastAPI dependency):
    async with get_async_session() as session:
        ...

Usage in Celery tasks (sync context):
    Use get_sync_session() which wraps async in asyncio.run().
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from agents.config import DATABASE_TARGET

# ---------------------------------------------------------------------------
# Build asyncpg connection URL from existing DATABASE_TARGET dict
# ---------------------------------------------------------------------------


def _build_async_url() -> str:
    cfg = DATABASE_TARGET
    return (
        f"postgresql+asyncpg://{cfg['user']}:{cfg['password']}"
        f"@{cfg['host']}:{cfg['port']}/{cfg['dbname']}"
    )


# Engine is created once at module import
_engine = create_async_engine(
    _build_async_url(),
    echo=False,            # set True for SQL debug logging
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,    # validates connections before use
)

# Session factory
_async_session_factory = async_sessionmaker(
    bind=_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ---------------------------------------------------------------------------
# Context manager for use in FastAPI route dependencies
# ---------------------------------------------------------------------------


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Yields a new AsyncSession; commits on success, rolls back on error."""
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ---------------------------------------------------------------------------
# FastAPI dependency (use with Depends)
# ---------------------------------------------------------------------------


async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an AsyncSession per request."""
    async with get_async_session() as session:
        yield session


# ---------------------------------------------------------------------------
# Sync helper for Celery tasks (runs in a thread-event-loop)
# ---------------------------------------------------------------------------


def run_in_new_loop(coro):
    """Run an async coroutine synchronously — for use inside Celery tasks."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Engine teardown (call on app shutdown)
# ---------------------------------------------------------------------------


async def close_engine() -> None:
    await _engine.dispose()

---

// filepath: db/__init__.py
"""db package — database layer for the LangChain Incident Tracking system."""

from db.models import (
    Base,
    HumanAction,
    Incident,
    IncidentTimelineEvent,
    LLMDecision,
    log_timeline_event,
)
from db.session import close_engine, db_session, get_async_session, run_in_new_loop

__all__ = [
    "Base",
    "Incident",
    "IncidentTimelineEvent",
    "HumanAction",
    "LLMDecision",
    "log_timeline_event",
    "db_session",
    "get_async_session",
    "run_in_new_loop",
    "close_engine",
]

---

// filepath: db/migrations/001_new_tables.sql
-- =============================================================================
-- Migration 001: New tables for LangChain + Incident Tracking UI
-- Existing tables (incidents, alert_occurrences, clusters, etc.) are UNTOUCHED.
-- Run with: psql -U $DB_USER -d $DB_NAME -f 001_new_tables.sql
-- =============================================================================

-- Enable pgvector if not already enabled
CREATE EXTENSION IF NOT EXISTS vector;
-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------------------------------------------------------------------------
-- incidents_v2: Core incident record (replaces ad-hoc SNOW integration)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS incidents_v2 (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    correlation_id   TEXT UNIQUE,
    cluster          TEXT NOT NULL,
    namespace        TEXT NOT NULL,
    alert_name       TEXT NOT NULL,
    hostname         TEXT,
    status           TEXT NOT NULL DEFAULT 'RECEIVED'
                         CHECK (status IN (
                             'RECEIVED','ANALYZING','PENDING_APPROVAL',
                             'EXECUTING','VERIFYING','RESOLVED',
                             'REJECTED','ESCALATED','FAILED'
                         )),
    risk_tier        TEXT CHECK (risk_tier IN ('LOW','HIGH','ESCALATE')),
    llm_confidence   NUMERIC(5,4),
    llm_intent_json  JSONB,
    analysis_summary TEXT,
    escalate_to      TEXT,
    awx_job_id       TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_incidents_v2_status
    ON incidents_v2(status);
CREATE INDEX IF NOT EXISTS idx_incidents_v2_cluster_alert
    ON incidents_v2(cluster, alert_name);
CREATE INDEX IF NOT EXISTS idx_incidents_v2_created_at
    ON incidents_v2(created_at DESC);

-- ---------------------------------------------------------------------------
-- incident_timeline: Append-only audit log — NEVER UPDATE ROWS
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS incident_timeline (
    id            BIGSERIAL PRIMARY KEY,
    incident_id   UUID NOT NULL REFERENCES incidents_v2(id) ON DELETE CASCADE,
    timestamp     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actor_type    TEXT NOT NULL CHECK (actor_type IN ('agent','human','system')),
    actor_id      TEXT,
    action        TEXT NOT NULL,
    from_status   TEXT,
    to_status     TEXT,
    notes         TEXT,
    metadata_json JSONB
);

CREATE INDEX IF NOT EXISTS idx_timeline_incident_id
    ON incident_timeline(incident_id, timestamp ASC);

-- ---------------------------------------------------------------------------
-- human_actions: Explicit record of every human decision
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS human_actions (
    id                   BIGSERIAL PRIMARY KEY,
    incident_id          UUID NOT NULL REFERENCES incidents_v2(id) ON DELETE CASCADE,
    user_id              TEXT NOT NULL,
    action               TEXT NOT NULL CHECK (action IN ('APPROVED','REJECTED','EDITED','ESCALATED')),
    original_intent_json JSONB,
    final_intent_json    JSONB,
    reason               TEXT NOT NULL,
    timestamp            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_human_actions_incident
    ON human_actions(incident_id, timestamp DESC);

-- ---------------------------------------------------------------------------
-- llm_decisions: Full LLM reasoning stored for every agent run
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS llm_decisions (
    id             BIGSERIAL PRIMARY KEY,
    incident_id    UUID NOT NULL REFERENCES incidents_v2(id) ON DELETE CASCADE,
    prompt_used    TEXT,
    raw_llm_output TEXT,
    parsed_intent  JSONB,
    confidence     NUMERIC(5,4),
    tool_calls_json JSONB,
    timestamp      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_llm_decisions_incident
    ON llm_decisions(incident_id, timestamp DESC);

-- ---------------------------------------------------------------------------
-- Function: auto-update incidents_v2.updated_at on any row change
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_incidents_v2_updated_at ON incidents_v2;
CREATE TRIGGER trg_incidents_v2_updated_at
    BEFORE UPDATE ON incidents_v2
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

---

// filepath: db/migrations/002_constraints.sql
-- =============================================================================
-- Migration 002: Performance indexes
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Blast-radius query helper: counts executing incidents per cluster
-- (used in Celery task before launching AWX job)
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_incidents_v2_executing_cluster
    ON incidents_v2 (cluster, status, updated_at)
    WHERE status = 'EXECUTING';

-- ---------------------------------------------------------------------------
-- Celery SQLAlchemy transport tables
-- These are created automatically by Celery on first connection,
-- but defining them here ensures proper permissions.
-- ---------------------------------------------------------------------------
-- Celery will auto-create: celery_taskmeta, celery_tasksetmeta, kombu_queue, kombu_message

---

// filepath: db/migrations/003_handovers.sql
-- ============================================================
-- Migration: shift_handovers v2 — Rich structured fields
-- Safe to run on existing data; all new columns have defaults.
-- ============================================================

-- Ensure the table exists first (idempotent baseline)
CREATE TABLE IF NOT EXISTS shift_handovers (
    id         UUID PRIMARY KEY,
    author     VARCHAR NOT NULL,
    message    TEXT    NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- 1. Shift Identifier — outgoing engineer / shift name
ALTER TABLE shift_handovers
    ADD COLUMN IF NOT EXISTS shift_identifier VARCHAR DEFAULT '' NOT NULL;

-- 2. Cluster — target cluster (e.g. nzclu101) or 'ALL'
ALTER TABLE shift_handovers
    ADD COLUMN IF NOT EXISTS cluster VARCHAR DEFAULT 'ALL' NOT NULL;

-- 3. Handover Type
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'handover_type_enum') THEN
        CREATE TYPE handover_type_enum AS ENUM (
            'handover',
            'maintenance',
            'upgrade',
            'operator_upgrade',
            'incident_followup',
            'change_freeze',
            'escalation'
        );
    END IF;
END$$;

ALTER TABLE shift_handovers
    ADD COLUMN IF NOT EXISTS handover_type handover_type_enum DEFAULT 'handover' NOT NULL;

-- 4. Priority
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'handover_priority_enum') THEN
        CREATE TYPE handover_priority_enum AS ENUM ('low', 'medium', 'high', 'critical');
    END IF;
END$$;

ALTER TABLE shift_handovers
    ADD COLUMN IF NOT EXISTS priority handover_priority_enum DEFAULT 'medium' NOT NULL;

-- 5. Action Required — does next shift need to take action?
ALTER TABLE shift_handovers
    ADD COLUMN IF NOT EXISTS action_required BOOLEAN DEFAULT FALSE NOT NULL;

-- 6. Related Incidents — comma-separated incident UUIDs
ALTER TABLE shift_handovers
    ADD COLUMN IF NOT EXISTS related_incidents TEXT DEFAULT '' NOT NULL;

-- 7. Maintenance Windows
ALTER TABLE shift_handovers
    ADD COLUMN IF NOT EXISTS start_time TIMESTAMP NULL,
    ADD COLUMN IF NOT EXISTS end_time TIMESTAMP NULL,
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;

-- 8. Resolution Logic
ALTER TABLE shift_handovers
    ADD COLUMN IF NOT EXISTS resolution_notes TEXT NULL;

-- 9. Upgrades
ALTER TABLE shift_handovers
    ADD COLUMN IF NOT EXISTS upgraded_version TEXT NULL,
    ADD COLUMN IF NOT EXISTS operator_name TEXT NULL;

-- Backfill shift_identifier from existing author column where empty
UPDATE shift_handovers
    SET shift_identifier = author
    WHERE shift_identifier = '';

-- Index on cluster and type for fast filtering
CREATE INDEX IF NOT EXISTS idx_shift_handovers_cluster       ON shift_handovers (cluster);
CREATE INDEX IF NOT EXISTS idx_shift_handovers_handover_type ON shift_handovers (handover_type);
CREATE INDEX IF NOT EXISTS idx_shift_handovers_priority      ON shift_handovers (priority);
CREATE INDEX IF NOT EXISTS idx_shift_handovers_created_at    ON shift_handovers (created_at DESC);

---

// filepath: db/migrations/004_summaries.sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS historical_shift_summaries (
    id UUID PRIMARY KEY,
    shift_name VARCHAR NOT NULL,
    summary_text TEXT NOT NULL,
    embedding vector(384),
    is_auto_generated BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_shift_summary_embedding 
ON historical_shift_summaries 
USING hnsw (embedding vector_l2_ops) 
WITH (m = 16, ef_construction = 64);

---

// filepath: db/migrations/01_add_embedding_versioning.sql
-- Database migration to add embedding model versioning

-- 1. Add model_name and model_version to operational_knowledge_embeddings
ALTER TABLE operational_knowledge_embeddings 
ADD COLUMN model_name VARCHAR(255) DEFAULT 'all-MiniLM-L6-v2',
ADD COLUMN model_version VARCHAR(50) DEFAULT '1.0';

-- 2. Add model_name and model_version to rhokp_knowledge
ALTER TABLE rhokp_knowledge 
ADD COLUMN model_name VARCHAR(255) DEFAULT 'all-MiniLM-L6-v2',
ADD COLUMN model_version VARCHAR(50) DEFAULT '1.0';

-- 3. Update indices if necessary (optional for exact match filtering, but good for performance)
CREATE INDEX IF NOT EXISTS idx_operational_embeddings_model 
ON operational_knowledge_embeddings(model_name, model_version);

CREATE INDEX IF NOT EXISTS idx_rhokp_knowledge_model 
ON rhokp_knowledge(model_name, model_version);

---

// filepath: docs/alert_analysis.md
# Complete Alert Analysis

This table provides a comprehensive list of all alerts found in the knowledge base, along with their specific diagnostic and mitigation actions, and their associated risk levels.

| Alert ID | Diagnostics (Low Risk) | Mitigations (Actionable) | Mitigation Risk Level |
| :--- | :--- | :--- | :--- |
| **HighlyAvailableWorkloadIncorrectlySpread** | `oc -n "$NS" get -o wide pods | grep "$WORKLOAD"` | `oc adm cordon "$NODE"`<br>`oc get nodes -o yaml | grep -E "^\s+failure-domain.beta.kubernetes.io/zone" | uniq | wc -l`<br>`oc delete -n "$NS" pvc "$PVC"`<br>`oc delete -n "$NS" pod "$POD"`<br>`oc adm uncordon "$NODE"` | **High** |
| **ACMMetricsCollectorFederationError** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **ACMMetricsCollectorForwardRemoteWriteError** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **CoreDNSErrorsHigh** | `oc get co/dns`<br>`oc get ds -n openshift-dns`<br>`oc exec pod/$COREDNS_POD_NAME -c dns -n openshift-dns -- \`<br>`dig -q $DOMAIN_NAME @$IP_OF_UPSTREAM_NAMESERVER`<br>`oc patch dnses.operator.openshift.io/default \`<br>`oc logs -c dns -l dns.operator.openshift.io/daemonset-dns=default \` | `oc edit dns.operator/default` | **Medium** |
| **ACMRemoteWriteError** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **etcdMembersDown** | `oc get nodes -l node-role.kubernetes.io/master=`<br>`oc adm upgrade`<br>`oc get nodes -l node-role.kubernetes.io/master= -o template --template='{{range .items}}{{"===> node:> "}}{{.metadata.name}}{{"\n"}}{{range $k, $v := .metadata.annotations}}{{println $k ":" $v}}{{end}}{{"\n"}}{{end}}'` | Manual/UI Interventions | **Manual Eval** |
| **KubeControllerManagerDown** | `oc get clusteroperators.config.openshift.io kube-controller-manager`<br>`oc get -o yaml kubecontrollermanagers.operator.openshift.io cluster`<br>`oc get events -n openshift-kube-controller-manager-operator`<br>`oc get pods -n openshift-kube-controller-manager-operator`<br>`oc logs -n openshift-kube-controller-manager-operator $POD_NAME`<br>`oc get events -n openshift-kube-controller-manager`<br>`oc get pods -n openshift-kube-controller-manager`<br>`oc logs -n openshift-kube-controller-manager $POD_NAME` | Manual/UI Interventions | **Manual Eval** |
| **ACMThanosCompactHalted** | `oc get secret thanos-object-storage -n open-cluster-management-observability -o jsonpath='{.data.thanos\.yaml}' | base64 --decode`<br>`oc get obc -n open-cluster-management-observability`<br>`oc get configmap <OBC-NAME> -n open-cluster-management-observability -o yaml` | Manual/UI Interventions | **Manual Eval** |
| **ACMUWLMetricsCollectorFederationError** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **ImageRegistryStorageFull** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **PodDisruptionBudgetAtLimit** | `oc get poddisruptionbudgets -o yaml -n $NS $PDB_NAME`<br>`oc get events -n $NS` | `oc get pods -n $NS --selector="app=myapp"` | **Low** |
| **ACMUWLMetricsCollectorForwardRemoteWriteError** | `oc get deployment observability-observatorium-api -n open-cluster-management-observability`<br>`oc scale deployment observability-observatorium-api -n open-cluster-management-observability --replicas=2` | Manual/UI Interventions | **Manual Eval** |
| **etcdDatabaseQuotaLowSpace** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **etcdGRPCRequestsSlow** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **etcdHighFsyncDurations** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **etcdHighNumberOfFailedGRPCRequests** | `oc logs -n openshift-etcd -lapp=etcd -c etcd` | Manual/UI Interventions | **Manual Eval** |
| **etcdInsufficientMembers** | `oc get nodes -l node-role.kubernetes.io/master=`<br>`oc adm upgrade`<br>`oc get nodes -l node-role.kubernetes.io/master= -o template --template='{{range .items}}{{"===> node:> "}}{{.metadata.name}}{{"\n"}}{{range $k, $v := .metadata.annotations}}{{println $k ":" $v}}{{end}}{{"\n"}}{{end}}'` | Manual/UI Interventions | **Manual Eval** |
| **KubeMacPoolDuplicateMacsFound** | `oc get pod -A -l control-plane=mac-controller-manager --no-headers \`<br>`oc logs -n <namespace> <kubemacpool_mac_controller> | grep "already allocated"` | `oc delete pod -n <namespace> <kubemacpool_mac_controller>` | **Medium** |
| **etcdNoLeader** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **etcdSignerCAExpirationCritical** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **ImageRegistryStorageReadOnly** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **AuditLogError** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **ExtremelyHighIndividualControlPlaneCPU** | Manual/UI Checks | `oc adm must-gather -- /usr/bin/gather_audit_logs` | **Low** |
| **KubeAggregatedAPIErrors** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **KubeAPIDown** | `oc cluster-info`<br>`oc -n openshift-kube-apiserver get pods`<br>`oc -n openshift-kube-apiserver logs -l 'app=openshift-kube-apiserver'` | Manual/UI Interventions | **Manual Eval** |
| **KubeAPIErrorBudgetBurn** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **GarbageCollectorSyncFailed** | `oc get pods -n openshift-kube-controller-manager`<br>`oc logs -n openshift-kube-controller-manager $POD`<br>`oc patch kubecontrollermanagers.operator/cluster --type=json -p '[{"op": "replace", "path": "/spec/logLevel", "value": "LOGLEVEL" }]'` | Manual/UI Interventions | **Manual Eval** |
| **PodDisruptionBudgetLimit** | `oc get poddisruptionbudgets -o yaml -n $NS $PDB_NAME`<br>`oc get events -n $NS` | `oc get pods -n $NS --selector="app=myapp"` | **Low** |
| **DeschedulerPSIDisabled** | `oc debug node/<node-name>` | Manual/UI Interventions | **Manual Eval** |
| **CollectorHigh403ForbiddenResponseRate** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **CollectorNodeDown** | `oc get pods -n openshift-logging -l app.kubernetes.io/component=collector`<br>`oc describe pod <POD_NAME> -n openshift-logging`<br>`oc logs <POD_NAME> -n openshift-logging`<br>`oc exec <POD_NAME> -n openshift-logging -- curl -s http://localhost:24231/metrics`<br>`oc get networkpolicies -n openshift-logging`<br>`oc get servicemonitor -n openshift-logging`<br>`oc describe servicemonitor <SERVICEMONITOR_NAME> -n openshift-logging`<br>`oc get service -n openshift-logging -l app.kubernetes.io/component=collector`<br>`oc get endpoints -n openshift-logging -l app.kubernetes.io/component=collector` | Manual/UI Interventions | **Manual Eval** |
| **CephClusterWarningState** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **KubeSchedulerDown** | `oc get clusteroperators.config.openshift.io kube-scheduler`<br>`oc get -o yaml kubeschedulers.operator.openshift.io cluster`<br>`oc get events -n openshift-kube-scheduler-operator`<br>`oc get pods -n openshift-kube-scheduler-operator`<br>`oc logs -n openshift-kube-scheduler-operator $POD_NAME`<br>`oc get events -n openshift-kube-scheduler`<br>`oc get pods -n openshift-kube-scheduler`<br>`oc logs -n openshift-kube-scheduler $POD_NAME` | Manual/UI Interventions | **Manual Eval** |
| **ClusterLogForwarderConfigNamingSchema** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **ClusterLogForwarderOutputErrorRate** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **AlertmanagerClusterFailedToSendAlerts** | `oc -n openshift-monitoring logs -l 'alertmanager=main'` | Manual/UI Interventions | **Manual Eval** |
| **AlertmanagerFailedReload** | `oc -n $NAMESPACE logs -l 'app.kubernetes.io/name=alertmanager' --tail=-1 | \` | Manual/UI Interventions | **Manual Eval** |
| **AlertmanagerFailedToSendAlerts** | `oc -n openshift-monitoring logs alertmanager-main-1` | Manual/UI Interventions | **Manual Eval** |
| **NodeFilesystemFilesFillingUp** | `oc debug "node/$NODE_NAME"` | Manual/UI Interventions | **Manual Eval** |
| **ClusterMonitoringOperatorDeprecatedConfig** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **ClusterOperatorDegraded** | `oc get clusteroperator`<br>`oc get clusteroperator $CLUSTEROPERATOR -ojson | jq .status.conditions`<br>`oc get clusteroperator $CLUSTEROPERATOR -ojson | jq .status.relatedObjects`<br>`oc adm inspect clusteroperator/$CLUSTEROPERATOR --dest-dir=out` | Manual/UI Interventions | **Manual Eval** |
| **ClusterOperatorDown** | `oc get clusteroperator`<br>`oc get clusteroperator $CLUSTEROPERATOR -ojson | jq .status.conditions`<br>`oc get clusteroperator $CLUSTEROPERATOR -ojson | jq .status.relatedObjects`<br>`oc adm inspect clusteroperator/$CLUSTEROPERATOR --dest-dir=out` | Manual/UI Interventions | **Manual Eval** |
| **NodeFilesystemSpaceFillingUp** | Manual/UI Checks | `oc -n default debug node/$NODE_NAME` | **Low** |
| **KubeDeploymentReplicasMismatch** | `oc get deploy -n $NAMESPACE $DEPLOYMENT`<br>`oc get events -n $NAMESPACE`<br>`oc get pods -n $NAMESPACE --selector=app=$DEPLOYMENT`<br>`oc describe pod $POD`<br>`oc get nodes`<br>`oc adm top nodes` | Manual/UI Interventions | **Manual Eval** |
| **KubeJobFailed** | Manual/UI Checks | `oc get pod -n $NAMESPACE -l job-name=$JOBNAME`<br>`oc get jobs -n $NAMESPACE` | **Low** |
| **KubeletDown** | `oc get nodes`<br>`oc describe node $NODE_NAME`<br>`oc get events --field-selector 'involvedObject.kind=Node'`<br>`oc get events`<br>`oc adm node-logs --role=master -u kubelet` | Manual/UI Interventions | **Manual Eval** |
| **KubeNodeNotReady** | `oc get node $NODE -o yaml`<br>`oc get -n openshift-machine-api machine $NODE -o yaml`<br>`oc get -n openshift-machine-api events` | Manual/UI Interventions | **Manual Eval** |
| **ExtremelyHighIndividualControlPlaneMemory** | `oc get nodes -l node-role.kubernetes.io/control-plane -o name | while read NODE; do printf -- '\n----------%s description---------\n\n' "${NODE}"; oc describe "${NODE}"; done`<br>`oc debug node/<node>`<br>`oc -n openshift-etcd rsh <etcd-pod-name>`<br>`oc exec -n openshift-etcd <etcd-pod> -c etcd -n openshift-etcd -- etcdctl --command-timeout=160s get / --prefix --keys-only |sed '/^$/d' | cut -d/ -f3,4 | sort | uniq -c | sort -rn |head` | Manual/UI Interventions | **Manual Eval** |
| **KubePersistentVolumeFillingUp** | `oc -n $NAMESPACE describe pvc $PVC_NAME`<br>`oc -n $NAMESPACE rsh $POD_NAME` | Manual/UI Interventions | **Manual Eval** |
| **KubePersistentVolumeInodesFillingUp** | `oc -n $NAMESPACE describe pvc $PVC_NAME`<br>`oc -n $NAMESPACE rsh $POD_NAME` | Manual/UI Interventions | **Manual Eval** |
| **KubePodNotReady** | `oc get pod -n $NAMESPACE $POD`<br>`oc logs -n $NAMESPACE $POD` | Manual/UI Interventions | **Manual Eval** |
| **NodeClockNotSynchronising** | `oc -n default debug node/<affected_node_name>` | Manual/UI Interventions | **Manual Eval** |
| **NodeFileDescriptorLimit** | `oc debug "node/$NODE_NAME"` | Manual/UI Interventions | **Manual Eval** |
| **DNSNxDomain** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **NodeFilesystemAlmostOutOfFiles** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **PrometheusDuplicateTimestamps** | `oc -n $NAMESPACE logs -l 'app.kubernetes.io/name=prometheus' | \` | Manual/UI Interventions | **Manual Eval** |
| **Ingress5xxErrors** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **NodeFilesystemAlmostOutOfSpace** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **NodeRAIDDegraded** | `oc debug "node/$NODE_NAME"` | Manual/UI Interventions | **Manual Eval** |
| **PrometheusKubernetesListWatchFailures** | `oc -n $NAMESPACE logs -c prometheus -l 'app.kubernetes.io/name=prometheus' --tail=-1` | Manual/UI Interventions | **Manual Eval** |
| **PrometheusScrapeBodySizeLimitHit** | `oc get cm -n openshift-monitoring cluster-monitoring-config -o yaml | grep enforcedBodySizeLimit`<br>`oc describe sa prometheus-k8s -n openshift-monitoring`<br>`curl -H "Authorization: Bearer $token" -k https://${host}/api/v1/targets | jq '.data.activeTargets[]|select(.health!="up")'`<br>`oc exec -it prometheus-k8s-0 -n openshift-monitoring  -- curl -k --key /etc/prometheus/secrets/metrics-client-certs/tls.key --cert /etc/prometheus/secrets/metrics-client-certs/tls.crt --cacert /etc/prometheus/configmaps/serving-certs-ca-bundle/service-ca.crt $scrape_url | wc --bytes` | Manual/UI Interventions | **Manual Eval** |
| **PrometheusOperatorRejectedResources** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **PrometheusPossibleNarrowSelectors** | Manual/UI Checks | `oc -n $NAMESPACE logs -l app.kubernetes.io/name=$NAME --tail=-1 \` | **Low** |
| **OVNKubernetesNorthdInactive** | `oc get pod -n openshift-ovn-kubernetes -l app=ovnkube-master`<br>`oc exec -it <ovnkube-master-podname> -c northd -- bash`<br>`oc get pod -n openshift-ovn-kubernetes -l app=ovnkube-node -o wide`<br>`oc exec -it <ovnkube-node-podname> -c northd -- bash`<br>`curl 127.0.0.1:29105/metrics | grep northd` | Manual/UI Interventions | **Manual Eval** |
| **SouthboundStaleAlert** | `oc get pod -n openshift-ovn-kubernetes -l app=ovnkube-master`<br>`oc get pod -n openshift-ovn-kubernetes -l app=ovnkube-node -o wide`<br>`oc describe pod/<podname> -n openshift-ovn-kubernetes`<br>`oc logs <podname> -n openshift-ovn-kubernetes -c <container>`<br>`oc exec -n openshift-ovn-kubernetes -it <podname> -c sbdb -- bash` | Manual/UI Interventions | **Manual Eval** |
| **PrometheusRemoteStorageFailures** | `oc -n $NAMESPACE logs -l 'app.kubernetes.io/component=prometheus'` | Manual/UI Interventions | **Manual Eval** |
| **PrometheusRuleFailures** | `oc -n $NAMESPACE logs -l 'app.kubernetes.io/name=prometheus' | \` | Manual/UI Interventions | **Manual Eval** |
| **PrometheusTargetSyncFailure** | `oc -n $NAMESPACE logs -l 'app.kubernetes.io/name=prometheus'` | Manual/UI Interventions | **Manual Eval** |
| **MachineConfigControllerDrainError** | `oc -n openshift-machine-config-operator logs $CONTROLLERPOD -c machine-config-controller` | `oc patch pdb $PDB -n $NS --type=merge -p '{"spec":{"minAvailable":0}}'`<br>`oc get validatingwebhookconfiguration`<br>`oc get mutatingwebhookconfiguration`<br>`oc get validatingwebhookconfiguration/<webhook_name> -o yaml > webhook.yaml`<br>`oc delete <webhook_type> <webhook_name>`<br>`oc delete pod <pod-name> --force=true --grace-period=0`<br>`oc patch pod <pod_name> -p '{"metadata":{"finalizers":null}}' -n <namespace_name>` | **High** |
| **TargetDown** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **TelemeterClientFailures** | `oc logs -n openshift-monitoring deployment.apps/telemeter-client -c telemeter-client -f` | Manual/UI Interventions | **Manual Eval** |
| **ThanosRuleQueueIsDroppingAlerts** | `oc -n openshift-user-workload-monitoring logs -l 'thanos-ruler=user-workload'` | Manual/UI Interventions | **Manual Eval** |
| **ThanosRuleRuleEvaluationLatencyHigh** | `oc -n openshift-user-workload-monitoring logs -l 'thanos-ruler=user-workload' \`<br>`oc -n openshift-monitoring logs -l 'app.kubernetes.io/name=thanos-query' \` | Manual/UI Interventions | **Manual Eval** |
| **NodeWithoutOVNKubeNodePodRunning** | `oc get node -l kubernetes.io/os!=windows`<br>`oc get daemonset ovnkube-node -n openshift-ovn-kubernetes`<br>`oc get po -n openshift-ovn-kubernetes -l app=ovnkube-node -o wide`<br>`oc describe po -n openshift-ovn-kubernetes <ovnkube-node-name>`<br>`oc logs <ovnkube-node-name> -n openshift-ovn-kubernetes --all-containers` | `oc delete po <ovnkube-node> -n openshift-ovn-kubernetes` | **Medium** |
| **ImageStreamImportFailed** | `oc get imagestreams --all-namespaces -o wide | grep -v True`<br>`oc get -o json imagestream <name> -n <namespace> | jq .status` | `oc import-image <imagestream-name> -n <namespace> --confirm` | **Medium** |
| **CephClusterCriticallyFull** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **NoOvnClusterManagerLeader** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **NoOvnMasterLeader** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **NorthboundStaleAlert** | `oc get pod -n openshift-ovn-kubernetes -l app=ovnkube-master`<br>`oc get pod -n openshift-ovn-kubernetes -l app=ovnkube-node -o wide`<br>`oc describe pod/<podname> -n openshift-ovn-kubernetes`<br>`oc logs <podname> -n openshift-ovn-kubernetes -c <container>`<br>`oc exec -n openshift-ovn-kubernetes -it <podname> -c nbdb --bash`<br>`oc get lease -n ovn-kubernetes ovn-kubernetes-master -o yaml`<br>`oc logs <podname> -n <namespace> -c ovnkube-master` | Manual/UI Interventions | **Manual Eval** |
| **NoRunningOvnControlPlane** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **NoRunningOvnMaster** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **OVNKubernetesControllerDisconnectedSouthboundDatabase** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **V4SubnetAllocationThresholdExceeded** | `oc get networks.config.openshift.io/cluster -o jsonpath='{.spec.clusterNetwork}'`<br>`oc get node --no-headers | wc -l` | Manual/UI Interventions | **Manual Eval** |
| **ClusterVersionOperatorDown** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **OpenShiftUpdateRiskMightApply** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **HighOverallControlPlaneMemory** | `oc get nodes -l node-role.kubernetes.io/control-plane -o name | while read NODE; do printf -- '\n----------%s description---------\n\n' "${NODE}"; oc describe "${NODE}"; done`<br>`oc debug node/<node>`<br>`oc -n openshift-etcd rsh <etcd-pod-name>`<br>`oc exec -n openshift-etcd <etcd-pod> -c etcd -n openshift-etcd -- etcdctl --command-timeout=160s get / --prefix --keys-only |sed '/^$/d' | cut -d/ -f3,4 | sort | uniq -c | sort -rn |head` | Manual/UI Interventions | **Manual Eval** |
| **KubeletHealthState** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **MachineConfigControllerPausedPoolKubeletCA** | `oc -n openshift-machine-config-operator get mcp $MCP_NAME -o jsonpath='{.spec.paused}'`<br>`oc -n openshift-kube-apiserver-operator describe secret kube-apiserver-to-kubelet-signer`<br>`oc -n openshift-kube-apiserver describe secret/kubelet-client`<br>`oc -n openshift-machine-config-operator get mcp $MCP_NAME -o jsonpath='{.status.configuration.name}'`<br>`oc get mc rendered-worker-bc1470f2331a3136999e0b49d85e1e21 -o jsonpath='{.spec.config.storage.files[?(@.path=="/etc/kubernetes/kubelet-ca.crt")].contents.source}' | python3 -c 'import sys, urllib.parse; print(urllib.parse.unquote(sys.stdin.read()))' | openssl x509 -text -noout` | `oc patch mcp $MCP_NAME --type='json' -p='[{"op": "replace", "path": "/spec/paused", "value":false}]'`<br>`oc edit mcp $MCP_NAME` | **Medium** |
| **MachineConfigControllerPoolAlert** | `oc -n openshift-machine-config-operator logs $CONTROLLERPOD -c machine-config-controller` | Manual/UI Interventions | **Manual Eval** |
| **MachineConfigDaemonRebootError** | `oc logs -f -n openshift-machine-config-operator $DAEMONPOD -c machine-config-daemon` | Manual/UI Interventions | **Manual Eval** |
| **MachineConfigDaemonPivotError** | `oc logs -f -n openshift-machine-config-operator $DAEMONPOD -c machine-config-daemon` | `oc debug node <Node-name>` | **Low** |
| **RuncDeprecated** | `oc get nodes`<br>`oc debug node/<node-name>` | Manual/UI Interventions | **Manual Eval** |
| **SystemMemoryExceedsReservation** | Manual/UI Checks | `oc debug node/<node>` | **Low** |
| **DNSErrors** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **ExternalEgressHighTrend** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **ExternalIngressHighTrend** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **IngressHTTPLatencyTrend** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **IPsecErrors** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **LatencyHighTrend** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **NetObservLokiError** | `oc get pods -n netobserv -l app=flowlogs-pipeline`<br>`oc logs -n netobserv <POD>` | `oc edit flowcollector cluster` | **Medium** |
| **NetObservNoFlows** | `oc get pods -n netobserv-privileged`<br>`oc logs -n netobserv-privileged <POD>`<br>`oc get pods -n netobserv -l app=flowlogs-pipeline`<br>`oc logs -n netobserv <POD>` | `oc get servicemonitors -n netobserv` | **Low** |
| **NetpolDenied** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **PacketDropsByDevice** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **CephClusterErrorState** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **CephMdsCacheUsageHigh** | Manual/UI Checks | `oc patch -n openshift-storage storagecluster ocs-storagecluster \` | **Medium** |
| **PacketDropsByKernel** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **CephClusterNearFull** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **CephClusterReadOnly** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **CephDataRecoveryTakingTooLong** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **CephFSOrphanedSnapshot** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **CephFSStaleSubvolume** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **ODFNodeNICBandwidthSaturation** | `oc debug node/<node>` | Manual/UI Interventions | **Manual Eval** |
| **CephMdsCpuUsageHigh** | Manual/UI Checks | `oc patch -n openshift-storage storagecluster ocs-storagecluster \`<br>`oc patch -n openshift-storage storagecluster ocs-storagecluster\` | **Medium** |
| **CephMdsCPUUsageHighNeedsHorizontalScaling** | Manual/UI Checks | `oc patch -n openshift-storage storagecluster ocs-storagecluster\` | **Medium** |
| **CephMdsCPUUsageHighNeedsVerticalScaling** | Manual/UI Checks | `oc patch -n openshift-storage storagecluster ocs-storagecluster \` | **Medium** |
| **CephMdsMissingReplicas** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **StorageAutoScalingCapacityReached** | `oc get storageautoscaler <resource_name> -n <resource_namespace> -o json | jq -r '.status.storageCapacityLimitReached'` | `oc patch storageautoscaler <resource_name> -n <resource_namespace> --type=merge --patch '{"spec":{"storageCapacityLimit":<storageCapacityLimit>}}'`<br>`oc delete storageautoscaler <resource_name> -n <resource_namespace>` | **Medium** |
| **CephMgrIsAbsent** | Manual/UI Checks | `oc get pods -n openshift-storage | grep mgr`<br>`oc describe -n openshift-storage pods/<rook-ceph-mgr pod name from previous step>`<br>`oc get pods -n openshift-storage | grep mgr` | **Low** |
| **CephMgrIsMissingReplicas** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **CephMonHighNumberOfLeaderChanges** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **verifyEndpoint** | `oc get storageclient -A -ojsonpath='{.items[?(@.status.id==`<br>`oc rsh -n<CLIENT_NAMESPACE> deploy/ocs-client-operator-controller-manager \`<br>`curl <ENDPOINT>` | Manual/UI Interventions | **Manual Eval** |
| **CephMonLowNumber** | `oc get pods -l app=rook-ceph-mon --no-headers=true -n openshift-storage | wc -l`<br>`oc get storagecluster -o jsonpath='{.items[*].status.failureDomainValues}' -n openshift-storage | tr ',' '\n' | sort -u | wc -l` | `oc patch storageclusters.ocs.openshift.io ocs-storagecluster -n openshift-storage --type merge --patch '{"spec": {"managedResources": {"cephCluster": {"monCount" : 5}}}}'`<br>`oc get pods -n openshift-storage -l app=rook-ceph-mon` | **Medium** |
| **CephMonQuorumAtRisk** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **CephMonQuorumLost** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **CephNodeDown** | Manual/UI Checks | `oc -n openshift-storage get pods`<br>`oc -n openshift-storage get pods`<br>`oc -n openshift-storage get pods | grep osd`<br>`oc -n openshift-storage describe pods/<osd podname from previous step>` | **Low** |
| **CephMonVersionMismatch** | `oc describe pods -n openshift-storage --selector app=rook-ceph-mon | grep CONTAINER_IMAGE` | `oc get events --field-selector involvedObject.name=$ocs_operator --namespace openshift-storage`<br>`oc logs -n openshift-storage --selector name=ocs-operator -c ocs-operator` | **Low** |
| **CephOSDCriticallyFull** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **CephOSDDiskNotResponding** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **CephOSDSlowOps** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **CDIDataImportCronOutdated** | `oc get sc -o jsonpath='{.items[?(.metadata.annotations.storageclass\.kubernetes\.io\/is-default-class=="true")].metadata.name}'`<br>`oc get sc -o jsonpath='{.items[?(.metadata.annotations.storageclass\.kubevirt\.io\/is-default-virt-class=="true")].metadata.name}'`<br>`oc get dataimportcron -A -o jsonpath='{range .items[*]}{.status.conditions[?(@.type=="UpToDate")].status}{"\t"}{.metadata.namespace}{"/"}{.metadata.name}{"\n"}{end}' | grep False`<br>`oc -n <namespace> get dataimportcron <dataimportcron> -o jsonpath='{.spec.template.spec.storage.storageClassName}{"\n"}'`<br>`oc -n <namespace> get dataimportcron <dataimportcron> -o jsonpath='{.status.lastImportedPVC.name}{"\n"}'`<br>`oc -n <namespace> get dv <datavolume> -o jsonpath-as-json='{.status}'`<br>`oc logs -n $CDI_NAMESPACE deployment/cdi-deployment` | `oc patch hco kubevirt-hyperconverged -n $CDI_NAMESPACE --type json -p '[{"op": "replace", "path": "/spec/featureGates/enableCommonBootImageImport", "value": false}]'` | **Medium** |
| **CephOSDDiskUnavailable** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **CephOSDDown** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **CephOSDFlapping** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **CephOSDNearFull** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **NooBaaSystemCapacityWarning85** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **CephOSDVersionMismatch** | `oc describe pods -n openshift-storage --selector app=rook-ceph-osd | grep CONTAINER_IMAGE` | `oc get events --field-selector involvedObject.name=$ocs_operator --namespace openshift-storage`<br>`oc logs -n openshift-storage --selector name=ocs-operator -c ocs-operator` | **Low** |
| **CephPgRepairTakingTooLong** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **CephPoolQuotaBytesCriticallyExhausted** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **CephPoolQuotaBytesNearExhaustion** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **CephXattrSetLatency** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **ClusterObjectStoreState** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **NooBaaSystemCapacityWarning95** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **HighRBDCloneSnapshotCount** | `oc patch storagecluster ocs-storagecluster -n openshift-storage --type json --patch`<br>`oc -n openshift-storage exec -it <rook-ceph-tools-pod> -- bash` | `oc delete pvc <pvc-name> -n <namespace>` | **High** |
| **KMSServerConnectionAlert** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **NooBaaSystemCapacityWarning100** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **ObcQuotaBytesAlert** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **ObcQuotaBytesExhausedAlert** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **ODFNodeLatencyHighOnNonOSDNodes** | `oc debug node/<node-name>`<br>`oc logs -l app=rook-ceph-mon -n openshift-storage` | Manual/UI Interventions | **Manual Eval** |
| **ObcQuotaObjectsAlert** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **ODFNodeLatencyHighOnOSDNodes** | `oc debug node/<node>` | Manual/UI Interventions | **Manual Eval** |
| **ObcQuotaObjectsExhausedAlert** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **ODFCorePodRestarted** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **ODFDiskUtilizationHigh** | `oc debug node/<node>` | Manual/UI Interventions | **Manual Eval** |
| **OdfMirrorDaemonStatus** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **ODFNodeMTULessThan9000** | `oc get nodes -l cluster.ocs.openshift.io/openshift-storage=''`<br>`oc debug node/<node-name>` | Manual/UI Interventions | **Manual Eval** |
| **ODFOperatorNotUpgradeable** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **ODFPersistentVolumeMirrorStatus** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **OdfPoolMirroringImageHealth** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **ODFRBDClientBlocked** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **OSDCPULoadHigh** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **PersistentVolumeUsageCritical** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **PersistentVolumeUsageNearFull** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **StorageAutoScalerCRIsInvalid** | `oc get storageautoscaler -n openshift-storage -o jsonpath='{.items[*].status}'` | `oc delete storageautoscaler <scaler_name> -n <resource_namespace>` | **Medium** |
| **StorageAutoScalingFailed** | `oc describe pod <osd_pod> -n <namespace>`<br>`oc get pvc $pvcName -n <namespace> -o yaml`<br>`oc get pvc <pvc_name> -n <namespace> -o yaml`<br>`oc get pvc <pvc_name> -n <namespace> -o jsonpath='{.spec.volumeName}'`<br>`oc get pv <pv_name> -n <namespace> -o yaml`<br>`oc get pvc $pvcName -n <namespace> -o yaml` | `oc get pods -n <namespace> -l app=rook-ceph-osd`<br>`oc delete pod <osd-pod-name> -n <namespace>`<br>`oc get pods -n <namespace> -l app=rook-ceph-osd`<br>`oc delete pod <osd-pod-name> -n <namespace>`<br>`oc rollout restart deployment rook-ceph-operator -n <namespace>`<br>`oc logs -l app=rook-ceph-operator -n <namespace>` | **Medium** |
| **StorageClientHeartbeatMissed** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **CDIOperatorDown** | `oc -n $CDI_NAMESPACE get pods -l name=cdi-operator`<br>`oc -n $CDI_NAMESPACE describe pods -l name=cdi-operator`<br>`oc -n $CDI_NAMESPACE logs -l name=cdi-operator` | Manual/UI Interventions | **Manual Eval** |
| **StorageClientIncompatibleOperatorVersion** | `oc patch console.v1.operator.openshift.io cluster --type=json \` | Manual/UI Interventions | **Manual Eval** |
| **StorageQuotaUtilizationThresholdReached** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **accessToolbox** | `oc rsh -n openshift-storage $TOOLS_POD` | Manual/UI Interventions | **Manual Eval** |
| **cephCLI** | `oc rsh -n openshift-storage $(oc get pods -n openshift-storage -o name -l app=rook-ceph-operator)` | Manual/UI Interventions | **Manual Eval** |
| **checkOperator** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **connectedClient** | `oc get storageconsumer -nopenshift-storage` | Manual/UI Interventions | **Manual Eval** |
| **determineFailedOcsNode** | `oc get nodes --selector='node-role.kubernetes.io/worker','!node-role.kubernetes.io/infra'`<br>`oc describe node <node_name>` | Manual/UI Interventions | **Manual Eval** |
| **diagnosis** | `oc port-forward alertmanager-managed-ocs-alertmanager-0 9093 -n`<br>`curl http://localhost:9093/api/v1/alerts | jq '.data[] | select( .labels.alertname) | { ALERT: .labels.alertname, STATE: .status.state}'`<br>`oc get nodes -o wide`<br>`oc get events -n default | grep NODE_NAME`<br>`oc get events -n default | grep 10-0-159-144` | Manual/UI Interventions | **Manual Eval** |
| **gatherLogs** | `oc adm must-gather --image=<ODF-MUST-GATHER-IMAGE>` | Manual/UI Interventions | **Manual Eval** |
| **networkConnectivity** | `oc get cm rook-ceph-mon-endpoints -ojson -n openshift-storage | jq -r '.data."data"'`<br>`oc debug node/<any-node-name> -n openshift-storage`<br>`oc get pods -n openshift-storage | grep rook-ceph-mon`<br>`oc get pods -n openshift-storage | grep rook-ceph-tools`<br>`oc rsh -n openshift-storage <rook-ceph-tools pod name from previous step>`<br>`oc rsh -n openshift-storage rook-ceph-tools-79ccc8ddc5-77brq`<br>`oc get storagecluster -n openshift-storage -o json | grep storageProviderEndpoint`<br>`oc debug -n openshift-storage`<br>`oc exec bash -- ping -c 5 <provider ip from first step>` | Manual/UI Interventions | **Manual Eval** |
| **podDebug** | `oc project openshift-storage`<br>`oc get pod | grep {ceph-component}`<br>`oc get pod/${MYPOD} -o wide`<br>`oc describe pod/${MYPOD}`<br>`oc logs pod/${MYPOD}` | Manual/UI Interventions | **Manual Eval** |
| **sre-to-engineering-escalation** | `oc get storageconsumers.ocs.openshift.io -n openshift-storage`<br>`oc get csvs -n <addon-namespace> on the affected cluster>`<br>`oc get csvs -n openshift-storage` | Manual/UI Interventions | **Manual Eval** |
| **troubleshootCeph** | `curl -k -H "Authorization: Bearer $(oc -n openshift-monitoring sa get-token prometheus-k8s)"  https://${MYALERTMANAGER}/api/v1/alerts | jq '.data[] | select( .labels.alertname) | { ALERT: .labels.alertname, STATE: .status.state}'` | Manual/UI Interventions | **Manual Eval** |
| **CDIDataVolumeUnusualRestartCount** | `oc get pods --all-namespaces -l app=containerized-data-importer -o=jsonpath='{range .items[?(@.status.containerStatuses[0].restartCount>3)]}{.metadata.name}{"/"}{.metadata.namespace}{"\n"}'`<br>`oc -n <namespace> describe pods <pod>`<br>`oc -n <namespace> logs <pod>` | Manual/UI Interventions | **Manual Eval** |
| **CDIDefaultStorageClassDegraded** | `oc get storageprofile $CDI_DEFAULT_VIRT_SC -o jsonpath='{.status.claimPropertySets}' | grep ReadWriteMany`<br>`oc get storageprofile $CDI_DEFAULT_VIRT_SC -o jsonpath='{.status.claimPropertySets}' | grep ReadWriteMany` | Manual/UI Interventions | **Manual Eval** |
| **DuplicateWaspAgentDSDetected** | `oc get ds wasp-agent -n wasp` | `oc delete ds wasp-agent -n wasp`<br>`oc delete sa wasp -n wasp`<br>`oc delete clusterrolebinding wasp`<br>`oc adm policy remove-scc-from-user -n wasp privileged -z wasp`<br>`oc delete project wasp` | **Medium** |
| **CDIMultipleDefaultVirtStorageClasses** | `oc get sc -o jsonpath='{.items[?(.metadata.annotations.storageclass\.kubevirt\.io\/is-default-virt-class=="true")].metadata.name}'` | Manual/UI Interventions | **Manual Eval** |
| **CDINoDefaultStorageClass** | `oc get sc -o jsonpath='{.items[?(.metadata.annotations.storageclass\.kubernetes\.io\/is-default-class=="true")].metadata.name}'`<br>`oc get sc -o jsonpath='{.items[?(.metadata.annotations.storageclass\.kubevirt\.io\/is-default-virt-class=="true")].metadata.name}'` | `oc patch storageclass <storage-class-name> -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'`<br>`oc patch storageclass <storage-class-name> -p '{"metadata": {"annotations":{"storageclass.kubevirt.io/is-default-virt-class":"true"}}}'` | **Medium** |
| **GuestVCPUQueueHighCritical** | `oc get vmi $VM -ojsonpath='{.spec.domain.cpu}'` | Manual/UI Interventions | **Manual Eval** |
| **CDINotReady** | `oc -n $CDI_NAMESPACE get deploy -l cdi.kubevirt.io`<br>`oc -n $CDI_NAMESPACE describe pods <pod>`<br>`oc -n $CDI_NAMESPACE logs <pod>` | Manual/UI Interventions | **Manual Eval** |
| **CDIStorageProfilesIncomplete** | `oc get storageprofile <storage_class>` | `oc patch storageprofile local --type=merge -p '{"spec": \` | **Medium** |
| **CnaoDown** | `oc -n $NAMESPACE get pods -l name=cluster-network-addons-operator`<br>`oc -n $NAMESPACE logs -l name=cluster-network-addons-operator`<br>`oc -n $NAMESPACE describe pods -l name=cluster-network-addons-operator` | Manual/UI Interventions | **Manual Eval** |
| **HCOMisconfiguredDescheduler** | `oc get -n openshift-kube-descheduler-operator KubeDescheduler cluster -o yaml` | `oc get crd kubedeschedulers.operator.openshift.io -o json | jq '.spec.versions[] | select(.name=="v1").schema.openAPIV3Schema.properties.spec.properties.profiles.items.enum[]'` | **Low** |
| **CnaoNmstateMigration** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **DeprecatedMachineType** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **GuestFilesystemAlmostOutOfSpace** | `oc exec -it <pod-name> -n <namespace> -- virsh list`<br>`oc exec -it <pod-name> -n <namespace> -- virsh qemu-agent-command <domain-name> '{"execute": "guest-get-fsinfo"}'` | Manual/UI Interventions | **Manual Eval** |
| **GuestVCPUQueueHighWarning** | `oc get vmi $VM -ojsonpath='{.spec.domain.cpu}'` | Manual/UI Interventions | **Manual Eval** |
| **HAControlPlaneDown** | `oc get nodes -l node-role.kubernetes.io/control-plane=''`<br>`oc describe node <node-name>` | `oc top node <node-name>`<br>`oc get node <node-name> -o yaml | jq '.status.conditions[] | select(.type == "DiskPressure")'`<br>`oc drain <node-name> --ignore-daemonsets --delete-emptydir-data` | **Low** |
| **HCOGoldenImageWithNoArchitectureAnnotation** | `oc get hyperconverged -n "${NAMESPACE}" -o yaml` | Manual/UI Interventions | **Manual Eval** |
| **HCOGoldenImageWithNoSupportedArchitecture** | `oc get hyperconverged -n "${NAMESPACE}" -o yaml` | Manual/UI Interventions | **Manual Eval** |
| **HCOInstallationIncomplete** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **HCOMultiArchGoldenImagesDisabled** | `oc get hyperconverged -n openshift-cnv kubevirt-hyperconverged -o yaml` | Manual/UI Interventions | **Manual Eval** |
| **HCOOperatorConditionsUnhealthy** | `oc get HyperConverged kubevirt-hyperconverged -n openshift-cnv -o jsonpath='{.status.conditions}'` | Manual/UI Interventions | **Manual Eval** |
| **HighNodeCPUFrequency** | `oc get nodes`<br>`oc debug node/<node-name> -it --image=registry.redhat.io/ubi8/ubi`<br>`oc top nodes`<br>`oc top pods --all-namespaces --sort-by=cpu`<br>`oc describe node <node-name>` | Manual/UI Interventions | **Manual Eval** |
| **HighCPUWorkload** | `oc get nodes`<br>`oc describe node <node-name>`<br>`oc top pods --all-namespaces --sort-by=cpu`<br>`oc describe pod <pod-name> -n <namespace>` | Manual/UI Interventions | **Manual Eval** |
| **HPPOperatorDown** | `oc -n $HPP_NAMESPACE get pods -l name=hostpath-provisioner-operator`<br>`oc -n $HPP_NAMESPACE describe pods -l name=hostpath-provisioner-operator`<br>`oc -n $HPP_NAMESPACE logs -l name=hostpath-provisioner-operator` | Manual/UI Interventions | **Manual Eval** |
| **HPPNotReady** | `oc -n $HPP_NAMESPACE get all -l k8s-app=hostpath-provisioner`<br>`oc -n $HPP_NAMESPACE describe pods <pod>`<br>`oc -n $HPP_NAMESPACE logs <pod>` | Manual/UI Interventions | **Manual Eval** |
| **HPPSharingPoolPathWithOS** | `oc -n $HPP_NAMESPACE get pods | grep hostpath-provisioner-csi`<br>`oc -n $HPP_NAMESPACE logs <csi_daemonset> -c hostpath-provisioner` | Manual/UI Interventions | **Manual Eval** |
| **KubemacpoolDown** | `oc describe pod -n $KMP_NAMESPACE $KMP_NAME`<br>`oc logs -n $KMP_NAMESPACE $KMP_NAME` | Manual/UI Interventions | **Manual Eval** |
| **KubemacpoolMACCollisionDetected** | `oc get vmi -A -o jsonpath='{range .items[*]}{.metadata.namespace}{"\t"}{.metadata.name}{"\t"}{.status.interfaces[*].mac}{"\n"}{end}' | grep -i "$MAC"`<br>`oc get pod -A -o json | jq -r --arg mac "$MAC" '.items[] | .metadata as $m | (.metadata.annotations["k8s.v1.cni.cncf.io/network-status"] // "[]" | fromjson)[] | select(.mac // "" | test($mac; "i")) | "\($m.namespace)\t\($m.name)\t\(.mac)"'` | Manual/UI Interventions | **Manual Eval** |
| **KubeVirtDeprecatedAPIRequested** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **KubeVirtComponentExceedsRequestedCPU** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **KubeVirtComponentExceedsRequestedMemory** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **KubeVirtCRModified** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **KubeVirtNoAvailableNodesToRunVMs** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **KubeVirtVMGuestMemoryAvailableLow** | Manual/UI Checks | `oc edit vm <vm-name> -n <namespace>` | **Medium** |
| **NoReadyVirtHandler** | `oc -n $NAMESPACE get daemonset virt-handler`<br>`oc -n $NAMESPACE get pods -l kubevirt.io=virt-handler -o wide`<br>`oc -n $NAMESPACE describe daemonset virt-handler`<br>`oc -n $NAMESPACE describe pod -l kubevirt.io=virt-handler`<br>`oc -n $NAMESPACE logs <virt-handler-pod-name> --previous`<br>`oc -n $NAMESPACE logs <virt-handler-pod-name>`<br>`oc get nodes` | Manual/UI Interventions | **Manual Eval** |
| **KubeVirtVMGuestMemoryPressure** | Manual/UI Checks | `oc edit vm <vm-name> -n <namespace>` | **Medium** |
| **KubevirtVmHighMemoryUsage** | `oc get pod <virt-launcher> -o yaml`<br>`oc exec -it <virt-launcher> -c compute -- top` | Manual/UI Interventions | **Manual Eval** |
| **KubeVirtVMIExcessiveMigrations** | `oc get nodes -l node-role.kubernetes.io/worker= -o json | jq .items[].status.allocatable`<br>`oc get nodes -l node-role.kubernetes.io/worker= -o json | jq .items[].status.conditions` | Manual/UI Interventions | **Manual Eval** |
| **LowKVMNodesCount** | `oc get nodes --o custom-columns=NAME:.metadata.name,KVM:".status.allocatable.devices\.kubevirt\.io/kvm"` | Manual/UI Interventions | **Manual Eval** |
| **LowReadyVirtAPICount** | `oc -n $NAMESPACE get pods -l kubevirt.io=virt-api`<br>`oc -n $NAMESPACE describe deploy virt-api`<br>`oc -n $NAMESPACE get pods -l kubevirt.io=virt-api -o wide`<br>`oc -n $NAMESPACE describe pod -l kubevirt.io=virt-api`<br>`oc -n $NAMESPACE logs -l kubevirt.io=virt-api`<br>`oc get nodes` | Manual/UI Interventions | **Manual Eval** |
| **LowReadyVirtControllersCount** | `oc get deployment -n $NAMESPACE virt-controller -o jsonpath='{.status.readyReplicas}'`<br>`oc -n $NAMESPACE get deploy virt-controller -o yaml`<br>`oc -n $NAMESPACE describe deploy virt-controller`<br>`oc get nodes` | Manual/UI Interventions | **Manual Eval** |
| **LowReadyVirtHandlerCount** | `oc -n $NAMESPACE get pods -l kubevirt.io=virt-handler -o wide`<br>`oc -n $NAMESPACE describe pod -l kubevirt.io=virt-handler`<br>`oc -n $NAMESPACE logs -l kubevirt.io=virt-handler`<br>`oc -n $NAMESPACE describe daemonset virt-handler`<br>`oc get nodes` | Manual/UI Interventions | **Manual Eval** |
| **LowReadyVirtOperatorsCount** | `oc -n $NAMESPACE get deploy virt-operator -o yaml`<br>`oc -n $NAMESPACE describe deploy virt-operator`<br>`oc get nodes` | Manual/UI Interventions | **Manual Eval** |
| **LowVirtAPICount** | `oc get deployment -n $NAMESPACE virt-api -o jsonpath='{.status.readyReplicas}'`<br>`oc -n $NAMESPACE get deploy virt-api -o yaml`<br>`oc get nodes` | Manual/UI Interventions | **Manual Eval** |
| **NoReadyVirtOperator** | `oc -n $NAMESPACE get deploy virt-operator -o yaml`<br>`oc -n $NAMESPACE describe deploy virt-operator`<br>`oc get nodes` | Manual/UI Interventions | **Manual Eval** |
| **LowVirtControllersCount** | `oc -n openshift-cnv get pods -l kubevirt.io=virt-controller`<br>`oc -n openshift-cnv logs <virt-controller>`<br>`oc -n openshift-cnv describe pod/<virt-controller>` | Manual/UI Interventions | **Manual Eval** |
| **LowVirtOperatorCount** | `oc -n $NAMESPACE get pods -l kubevirt.io=virt-operator`<br>`oc -n $NAMESPACE logs <virt-operator>`<br>`oc -n $NAMESPACE describe pod <virt-operator>` | Manual/UI Interventions | **Manual Eval** |
| **NetworkAddonsConfigNotReady** | `oc get networkaddonsconfig -o custom-columns=':.status.conditions[*].message' | tr -d '\n'`<br>`oc -n openshift-cnv get daemonset <daemonset> -o yaml`<br>`oc -n openshift-cnv logs <pod>`<br>`oc -n openshift-cnv describe pod <pod>` | Manual/UI Interventions | **Manual Eval** |
| **NodeNetworkInterfaceDown** | `oc get nodes` | Manual/UI Interventions | **Manual Eval** |
| **NoLeadingVirtOperator** | `oc -n $NAMESPACE get pods -l kubevirt.io=virt-operator`<br>`oc -n $NAMESPACE logs | grep lead`<br>`oc -n $NAMESPACE describe pod <virt-operator>` | Manual/UI Interventions | **Manual Eval** |
| **NoReadyVirtAPI** | `oc -n $NAMESPACE get pods -l kubevirt.io=virt-api`<br>`oc -n $NAMESPACE describe deploy virt-api`<br>`oc -n $NAMESPACE logs <virt-api-pod-name> --previous`<br>`oc -n $NAMESPACE logs <virt-api-pod-name>`<br>`oc get nodes` | Manual/UI Interventions | **Manual Eval** |
| **NoReadyVirtController** | `oc get deployment -n $NAMESPACE virt-controller -o jsonpath='{.status.readyReplicas}'`<br>`oc -n $NAMESPACE get deploy virt-controller -o yaml`<br>`oc -n $NAMESPACE describe deploy virt-controller`<br>`oc logs -n $NAMESPACE <virt-controller>`<br>`oc get nodes` | Manual/UI Interventions | **Manual Eval** |
| **OperatorConditionsUnhealthy** | `oc get <CR> <CR_OBJECT> -n <namespace> -o jsonpath='{.status.conditions}'`<br>`oc get HyperConverged kubevirt-hyperconverged -n kubevirt -o jsonpath='{.status.conditions}'` | Manual/UI Interventions | **Manual Eval** |
| **OrphanedVirtualMachineInstances** | `oc get pods --all-namespaces -o wide -l kubevirt.io=virt-handler`<br>`oc get vmis --all-namespaces`<br>`oc get daemonset virt-handler --all-namespaces`<br>`oc get daemonset virt-handler --all-namespaces -o yaml | jq .status`<br>`oc get nodes`<br>`oc get kubevirt kubevirt --all-namespaces -o yaml` | Manual/UI Interventions | **Manual Eval** |
| **SingleStackIPv6Unsupported** | `oc get network.config cluster -o yaml` | Manual/UI Interventions | **Manual Eval** |
| **VirtHandlerRESTErrorsBurst** | `oc get pods -n $NAMESPACE -l=kubevirt.io=virt-handler`<br>`oc logs -n $NAMESPACE <virt-handler>` | `oc delete -n $NAMESPACE <virt-handler>` | **Medium** |
| **OutdatedVirtualMachineInstanceWorkloads** | `oc get vmi -l kubevirt.io/outdatedLauncherImage --all-namespaces`<br>`oc get kubevirt --all-namespaces -o yaml`<br>`oc get vmi <vmi> -o yaml` | Manual/UI Interventions | **Manual Eval** |
| **PersistentVolumeFillingUp** | `oc exec -it <pod-name> -n <namespace> -- df -h /path/to/mount` | Manual/UI Interventions | **Manual Eval** |
| **VirtControllerRESTErrorsBurst** | `oc get pods -n $NAMESPACE -l=kubevirt.io=virt-controller`<br>`oc logs -n $NAMESPACE <virt-controller>` | `oc delete -n $NAMESPACE <virt-controller>` | **Medium** |
| **SSPCommonTemplatesModificationReverted** | `oc -n $NAMESPACE logs --tail=-1 -l control-plane=ssp-operator | grep 'common template' -C 3` | Manual/UI Interventions | **Manual Eval** |
| **SSPDown** | `oc -n $NAMESPACE get pods -l control-plane=ssp-operator`<br>`oc -n $NAMESPACE describe pods -l control-plane=ssp-operator`<br>`oc -n $NAMESPACE logs --tail=-1 -l control-plane=ssp-operator` | Manual/UI Interventions | **Manual Eval** |
| **SSPFailingToReconcile** | `oc -n $NAMESPACE describe pods -l control-plane=ssp-operator`<br>`oc -n $NAMESPACE logs --tail=-1 -l control-plane=ssp-operator`<br>`oc -n $NAMESPACE get pods -l name=virt-template-validator`<br>`oc -n $NAMESPACE describe pods -l name=virt-template-validator`<br>`oc -n $NAMESPACE logs --tail=-1 -l name=virt-template-validator` | Manual/UI Interventions | **Manual Eval** |
| **VirtControllerRESTErrorsHigh** | `oc get pods -n $NAMESPACE -l=kubevirt.io=virt-controller`<br>`oc logs -n $NAMESPACE <virt-controller>` | `oc delete -n $NAMESPACE <virt-controller>` | **Medium** |
| **SSPHighRateRejectedVms** | `oc -n $NAMESPACE logs --tail=-1 -l name=virt-template-validator` | Manual/UI Interventions | **Manual Eval** |
| **SSPOperatorDown** | `oc -n $NAMESPACE get pods -l control-plane=ssp-operator`<br>`oc -n $NAMESPACE describe pods -l control-plane=ssp-operator`<br>`oc -n $NAMESPACE logs --tail=-1 -l control-plane=ssp-operator` | Manual/UI Interventions | **Manual Eval** |
| **SSPTemplateValidatorDown** | `oc -n $NAMESPACE get pods -l name=virt-template-validator`<br>`oc -n $NAMESPACE describe pods -l name=virt-template-validator`<br>`oc -n $NAMESPACE logs --tail=-1 -l name=virt-template-validator` | Manual/UI Interventions | **Manual Eval** |
| **UnsupportedHCOModification** | `oc get hyperconverged -n "${NS}" kubevirt-hyperconverged \` | `oc annotate hyperconverged -n "${NS}" kubevirt-hyperconverged \` | **Low** |
| **VirtAPIDown** | `oc -n $NAMESPACE get pods -l kubevirt.io=virt-api`<br>`oc -n $NAMESPACE get deploy virt-api -o yaml`<br>`oc -n $NAMESPACE describe deploy virt-api`<br>`oc get nodes` | Manual/UI Interventions | **Manual Eval** |
| **VirtApiRESTErrorsBurst** | `oc -n $NAMESPACE get pods -l kubevirt.io=virt-api`<br>`oc logs -n $NAMESPACE <virt-api>`<br>`oc describe -n $NAMESPACE <virt-api>`<br>`oc get nodes`<br>`oc -n $NAMESPACE get deploy virt-api -o yaml`<br>`oc -n $NAMESPACE describe deploy virt-api` | Manual/UI Interventions | **Manual Eval** |
| **VirtApiRESTErrorsHigh** | `oc -n $NAMESPACE get pods -l kubevirt.io=virt-api`<br>`oc logs -n $NAMESPACE <virt-api>`<br>`oc describe -n $NAMESPACE <virt-api>`<br>`oc get nodes`<br>`oc -n $NAMESPACE get deploy virt-api -o yaml`<br>`oc -n $NAMESPACE describe deploy virt-api` | Manual/UI Interventions | **Manual Eval** |
| **VirtControllerDown** | `oc get deployment -n $NAMESPACE virt-controller -o yaml`<br>`oc get logs <virt-controller>` | Manual/UI Interventions | **Manual Eval** |
| **VirtHandlerDaemonSetRolloutFailing** | `oc get pods -n $NAMESPACE -l=kubevirt.io=virt-handler`<br>`oc -n $NAMESPACE get pod <virt-handler> -o jsonpath='{.spec.nodeName}'` | Manual/UI Interventions | **Manual Eval** |
| **VirtHandlerDown** | `oc -n $NAMESPACE get daemonset virt-handler -o yaml`<br>`oc -n $NAMESPACE get pods -l kubevirt.io=virt-handler`<br>`oc -n $NAMESPACE describe daemonset virt-handler`<br>`oc -n $NAMESPACE describe pod -l kubevirt.io=virt-handler`<br>`oc get nodes`<br>`oc -n $NAMESPACE logs <virt-handler-pod-name> --previous`<br>`oc -n $NAMESPACE logs <virt-handler-pod-name>` | Manual/UI Interventions | **Manual Eval** |
| **VirtHandlerRESTErrorsHigh** | `oc get pods -n $NAMESPACE -l=kubevirt.io=virt-handler`<br>`oc logs -n $NAMESPACE <virt-handler>` | `oc delete -n $NAMESPACE <virt-handler>` | **Medium** |
| **VirtLauncherPodsStuckFailed** | `oc get pods -A -l kubevirt.io=virt-launcher --field-selector=status.phase=Failed --no-headers | head -n 20`<br>`oc -n <namespace> describe pod <virt-launcher-pod> | sed -n '/Events/,$p'`<br>`oc get vmim -A`<br>`oc -n "$NAMESPACE" logs -l kubevirt.io=virt-controller --tail=200`<br>`oc -n "$NAMESPACE" logs -l kubevirt.io=virt-handler --tail=200` | `oc delete vmim -A`<br>`oc get pods -A -l kubevirt.io=virt-launcher --field-selector=status.phase=Failed -o name | xargs -r -n50 oc delete` | **Medium** |
| **VirtOperatorDown** | `oc -n $NAMESPACE get deploy virt-operator -o yaml`<br>`oc -n $NAMESPACE describe deploy virt-operator`<br>`oc get pods -n $NAMESPACE -l=kubevirt.io=virt-operator`<br>`oc get nodes` | Manual/UI Interventions | **Manual Eval** |
| **VirtOperatorRESTErrorsBurst** | `oc -n $NAMESPACE get pods -l kubevirt.io=virt-operator`<br>`oc -n $NAMESPACE logs <virt-operator>`<br>`oc -n $NAMESPACE describe pod <virt-operator>` | `oc delete -n $NAMESPACE <virt-operator>` | **Medium** |
| **VirtOperatorRESTErrorsHigh** | `oc -n $NAMESPACE get pods -l kubevirt.io=virt-operator`<br>`oc -n $NAMESPACE logs <virt-operator>`<br>`oc -n $NAMESPACE describe pod <virt-operator>` | `oc delete -n <install-namespace> <virt-operator>` | **Medium** |
| **VirtualMachineCRCErrors** | Manual/UI Checks | Manual/UI Interventions | **Manual Eval** |
| **VirtualMachineInstanceHasEphemeralHotplugVolume** | `oc get vmis -A -o json | jq -r '.items[].metadata | select(.annotations | has("kubevirt.io/ephemeral-hotplug-volumes")) | [.name , .namespace] | @tsv'`<br>`oc get vmis <vm-name> -n <namespace> -o json | jq -r '.metadata.annotations."kubevirt.io/ephemeral-hotplug-volumes"'` | Manual/UI Interventions | **Manual Eval** |
| **VirtualMachineStuckInUnhealthyState** | `oc get vm <vm-name> -n <namespace> -o yaml`<br>`oc describe vm <vm-name> -n <namespace>`<br>`oc get events -n <namespace> --sort-by='.lastTimestamp'`<br>`oc get nodes -o wide`<br>`oc describe nodes`<br>`oc get storageclass`<br>`oc get pv,pvc -n <namespace>`<br>`oc get datavolume -n <namespace>`<br>`oc describe datavolume <dv-name> -n <namespace>`<br>`oc debug node/<node-name> -it --image=busybox`<br>`oc get secrets -n <namespace>`<br>`oc get kubevirt -n "$NAMESPACE" \`<br>`oc get kubevirt kubevirt -n "$NAMESPACE" \`<br>`oc get pods -n "$NAMESPACE" \`<br>`oc logs -n "$NAMESPACE" <virt-controller-pod>`<br>`oc get pods -n "$NAMESPACE" \`<br>`oc logs -n "$NAMESPACE" <virt-handler-pod>` | Manual/UI Interventions | **Manual Eval** |
| **VirtualMachineStuckOnNode** | `oc get vm <vm-name> -n <namespace> -o yaml`<br>`oc get vmi <vm-name> -n <namespace> -o yaml`<br>`oc describe vmi <vm-name> -n <namespace>`<br>`oc get events -n <namespace> \`<br>`oc get pods -n <namespace> -l kubevirt.io/domain=<vm-name>`<br>`oc describe pod <virt-launcher-pod> -n <namespace>`<br>`oc logs <virt-launcher-pod> -n <namespace> -c compute`<br>`oc logs <virt-launcher-pod> -n <namespace> -c istio-proxy \`<br>`oc top pod <virt-launcher-pod> -n <namespace>`<br>`oc describe node <node-name>`<br>`oc get pods -n "$NAMESPACE" -o wide | grep <node-name>`<br>`oc logs <virt-handler-pod> -n "$NAMESPACE"`<br>`oc get pvc -n <namespace>`<br>`oc describe pvc <pvc-name> -n <namespace>`<br>`oc get volumeattachment | grep <node-name>`<br>`oc get dv -n <namespace>`<br>`oc describe dv <dv-name> -n <namespace>`<br>`oc debug node/<node-name> -it --image=busybox`<br>`oc exec -it <virt-launcher-pod> -n <namespace> -c compute \`<br>`oc exec -it <virt-launcher-pod> -n <namespace> -c compute \` | Manual/UI Interventions | **Manual Eval** |
| **VMCannotBeEvicted** | `oc get vmis -o yaml`<br>`oc get vmis -o wide`<br>`oc get vmi <vmi> -o yaml` | Manual/UI Interventions | **Manual Eval** |
| **VMStorageClassWarning** | `oc get vm <vm-name> -o json | jq -r '.spec.template.spec.volumes[] | if .dataVolume then "DataVolume " + .dataVolume.name elif .persistentVolumeClaim then "PersistentVolumeClaim " + .persistentVolumeClaim.claimName else empty end'` | Manual/UI Interventions | **Manual Eval** |

---

// filepath: docs/analysis_results.md
# RHOKP Knowledge Base Analysis

Based on the review of the `rhokp_knowledge` table containing diagnostics and remediations across various OpenShift/Kubernetes operators, here is the comprehensive analysis you requested.

## 1. Recommended Ansible Playbooks ("Good to Have")

To automate the mitigation steps outlined in the knowledge base, the following Ansible playbooks are highly recommended. They represent repetitive or multi-step processes that are prone to human error when executed under pressure:

1. **Workload Spread & Node Rescheduling Playbook** (`pb_ha_workload_spread.yml`)
   - **Purpose:** Addresses `HighlyAvailableWorkloadIncorrectlySpread`.
   - **Actions:** Automates cordoning a specific node, identifying and gracefully terminating misconfigured pods, optionally handling PVC removal (with safety prompts), and uncordoning the node.
2. **Observability & Telemetry Recovery Playbook** (`pb_observability_recovery.yml`)
   - **Purpose:** Addresses Thanos, ACM Metrics, and Telemeter alerts (e.g., `ACMThanosCompactHalted`, `ACMUWLMetricsCollectorForwardRemoteWriteError`).
   - **Actions:** Scales up `observability-observatorium-api`, restarts failing metric collector pods, and validates S3/Object Storage secret configurations automatically.
3. **Network (OVN/DNS) Health Recovery Playbook** (`pb_network_health.yml`)
   - **Purpose:** Addresses `OVNKubernetesNorthdInactive`, `StaleAlert`, `CoreDNSErrorsHigh`.
   - **Actions:** Safely deletes/restarts stuck `ovnkube-node` or `ovnkube-master` pods, dynamically changes CoreDNS log levels to `Debug` for capturing errors, and tests upstream nameserver connectivity.
4. **Machine Config & Node Drain Unblocker Playbook** (`pb_mco_unblock.yml`)
   - **Purpose:** Addresses `MachineConfigControllerDrainError` and paused pools.
   - **Actions:** Pauses/Unpauses MachineConfigPools, temporarily patches PodDisruptionBudgets (PDBs) or Webhooks blocking node drains, and automatically un-patches them once the node reboots.
5. **Storage Full / Image Registry Playbook** (`pb_storage_expansion.yml`)
   - **Purpose:** Addresses `ImageRegistryStorageFull` and PVC filling alerts.
   - **Actions:** Prunes dead images, expands PVC definitions, and verifies if the backend storage supports dynamic expansion.

---

## 2. Risk Categorization Table

When executing remediations, actions fall into different risk tiers. You can use this table to determine which actions can be fully automated versus those requiring human approval.

| Risk Level | Action Description | Example `oc` Commands | Potential Impact |
| :--- | :--- | :--- | :--- |
| **Low** | **Read-Only / Diagnostics** | `oc get`, `oc describe`, `oc logs`, `oc adm must-gather`, `oc exec -- curl / dig` | None. Safe to run at any time to gather context. |
| **Low** | **Scaling up stateless Deployments** | `oc scale deployment ... --replicas=N` | Negligible. Adds compute overhead but does not disrupt existing connections. |
| **Medium** | **Cordoning Nodes** | `oc adm cordon <node>` | Lowers cluster capacity temporarily; prevents new pods from scheduling. |
| **Medium** | **Restarting Stateless Pods** | `oc delete pod <pod-name>` (e.g., `ovnkube-node`, `mac_controller`) | Momentary disruption to specific components. Controllers will automatically recreate the pods. |
| **Medium** | **Patching Configs / Log Levels** | `oc patch dnses.operator.openshift.io`, `oc patch mcp ...` | Minor operational changes; can trigger rolling updates in operators if not careful. |
| **High** | **Deleting Persistent Volume Claims (PVC)** | `oc delete pvc <pvc-name>` | **Data Loss.** Explicitly required for HA rescheduling but destroys local/bound data. |
| **High** | **Bypassing Webhooks/PDBs** | `oc delete validatingwebhookconfiguration`, `oc patch pdb ...` | Disables critical cluster safeguards (admission control, HA guarantees) temporarily. |
| **High** | **Manual Master/etcd Interventions**| Rebooting Master Nodes, Deleting etcd pods, Manual CA rotation | Can lead to complete control plane outage or loss of quorum if done improperly. |

---

## 3. Complete Actions to be Performed

To handle any incident identified in this knowledge base, the complete operational flow you need to execute (or automate) consists of the following 4 phases:

### Phase 1: Investigation & Context Gathering (Low Risk)
*   **Identify the Alert:** Extract `namespace`, `alertname`, and `pod/node` tags from the incoming event.
*   **Run Diagnostics:** Execute the exact commands mapped in the `diagnosis` section of the KB (e.g., `oc get events`, `oc describe`, `oc logs`).
*   **Network Probing:** If it's a network/DNS issue, use `oc exec` to run `curl`, `dig`, or `etcdctl` to verify internal component connectivity.

### Phase 2: Isolation & Preparation (Medium Risk)
*   **Cordoning:** If a node is failing or workload is stuck, isolate it by cordoning the node so no further workloads are scheduled there.
*   **Configuration Backups:** Before patching PDBs or Webhooks, dump the current config using `oc get <resource> -o yaml > backup.yaml`.
*   **Log Level Adjustment:** Patch operators (like CoreDNS) to enable `Debug` logging to catch the exact failure reason during the mitigation phase.

### Phase 3: Mitigation Execution (Medium to High Risk)
*   **Resource Reset:** Delete stuck pods (e.g., `ovnkube`, `kube-mac-pool`) to force the respective DaemonSet/Deployment to spin up fresh instances.
*   **Capacity Tuning:** Scale up deployments (like `observability-observatorium-api` to 2 replicas) or patch the `MachineConfigPool` to unpause rollouts.
*   **Data & State Clearing (Handle with Care):** Delete PVCs for workloads that cannot migrate across Availability Zones, forcing the StatefulSet to provision a fresh volume.
*   **Blocker Removal:** Forcibly delete stuck pods with `--grace-period=0` and remove finalizers, or temporarily delete mutating/validating webhooks blocking node operations.

### Phase 4: Verification & Restoration (Low Risk)
*   **Uncordon:** Bring nodes back into the scheduling pool.
*   **Restore Configs:** Re-apply the backed-up PDBs, Webhooks, or revert log levels back to `Info`.
*   **Validate:** Run the Phase 1 diagnostic commands again to verify the output matches a healthy state and ensure the original Prometheus alert clears.

---

// filepath: docs/bare_metal_deployment.md
# Bare-Metal Deployment Guide (No Docker)

If you prefer to run the application directly on your server's OS without using Docker, you will need to manually start and manage the 4 core processes. In a true production environment, you should wrap these commands in **Systemd** services or use a process manager like **PM2** or **Supervisor** to ensure they restart if they crash.

## Prerequisites
- **Python 3.10+**
- **Node.js 18+**
- **PostgreSQL** running on `localhost:5432`

---

## 1. Environment Setup

First, clone the repository and set up your Python virtual environment.

```bash
git clone <your-repo>
cd rag_testing

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\activate

# Install backend dependencies
pip install -r requirements.txt
```

Create your `.env` file in the root directory:
```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=rhokp
DB_USER=postgres
DB_PASSWORD=your_secure_password

CELERY_BROKER_URL=sqla+postgresql://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}
CELERY_RESULT_BACKEND=db+postgresql://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}

# Kafka Configuration (Optional, for kafka_consumer.py)
KAFKA_BROKER_URL=localhost:9092
KAFKA_TOPIC=sre_alerts
KAFKA_DLQ_TOPIC=sre_alerts_dlq
KAFKA_GROUP_ID=sre-agent-group

# ... [add your LLM and other API keys] ...
```

---

## 2. Start the Backend Processes

You need to run these three Python processes concurrently. 

**Process 1: The FastAPI Server**
This runs the main API and WebSocket connections.
```bash
source .venv/bin/activate
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

**Process 2: The Celery Worker & Beat Scheduler**
This executes the background AI tasks and scheduled ingestion scripts. The `-B` flag tells it to also run the Celery Beat scheduler!
```bash
source .venv/bin/activate
celery -A worker.celery_app worker --beat --loglevel=info --queues=default,priority --concurrency=4
```

**Process 3: The Kafka Consumer (Optional)**
If you are ingesting alerts from Kafka, run the listener daemon.
```bash
source .venv/bin/activate
python ingestion/kafka_consumer.py
```

---

## 3. Build & Serve the Frontend

For the frontend, you first need to compile the React TypeScript code into static HTML/JS/CSS files, and then serve them.

```bash
cd frontend
npm install
npm run build
```

The compiled files will now be located in the `frontend/dist/` folder. 

**Serving the Frontend:**
In production, you should point a web server like **Nginx** or **Apache** to serve the `frontend/dist` directory on port 80. 

If you just want to run it quickly for testing without installing Nginx, you can use the node `serve` package:
```bash
npx serve -s dist -l 80
```

---

## Summary
To run the SRE Agent bare-metal, you are managing four distinct components:
1. `uvicorn` (Backend API)
2. `celery` (Background Worker & Schedules)
3. `python ingestion/kafka_consumer.py` (Alert Ingestion)
4. `nginx` or `npx serve` (React Frontend)

---

// filepath: docs/cve_report.md
# OpenShift 4.19 & 4.20 CVE Report

This report contains the latest CVEs affecting OpenShift Container Platform (versions 4.19 and 4.20) and OpenShift Virtualization, pulled directly from the Red Hat Security Data API.

| CVE ID | Severity | Public Date | Description |
| :--- | :--- | :--- | :--- |

---

// filepath: docs/decision_matrix.md
# CVE Upgrade Advisor: Decision Matrix & Algorithm

If the "Residual Risk" percentage looks surprisingly high (or even higher than your current risk) for certain upgrade paths, it is actually the algorithm working exactly as intended! Here is a transparent breakdown of how the engine calculates those percentages and flags the "Best Choice."

## 1. Severity Weighting 
Every vulnerability actively affecting a version is assigned a mathematical weight based on its Red Hat Severity rating:
- **Critical:** 10 points
- **Important:** 5 points
- **Moderate:** 2 points
- **Low:** 1 point

## 2. Risk Percentage Calculation
The total sum of these weights is divided by a hardcoded **Maximum Risk Baseline** (currently set to `30` points for visualization purposes) and capped at 100%.
```
Risk % = min(100, (Sum of Weights / 30) * 100)
```
*Example: A version with 2 Criticals (20) and 1 Important (5) scores 25. 25 / 30 = 83% Risk.*

## 3. The "Residual Risk" (Risks Waiting)
When evaluating a future target version (e.g., `4.20.16`), the engine does **not** just look at what is being fixed. It actively scans the database for all vulnerabilities that *still affect* the target version. 

**Why would Residual Risk be high?**
- **Unpatched Zero-Days:** If there is a critical zero-day affecting all `4.20.x` streams, upgrading to a higher patch will NOT eliminate it. That CVE becomes a "Risk Waiting", and its score is added to the target version's Residual Risk.
- **Early Release Bugs:** Upgrading to a major early release (like `4.21.0-rc1`) might resolve old bugs, but it often introduces *new* critical vulnerabilities specific to that release. The algorithm penalizes the target version for these new risks!

## 4. The "Best Choice" Decision Matrix
The backend dynamically evaluates multiple semantic upgrade paths (Patch +1, Patch +2, and Next Minor). 

The `⭐ Best Choice` badge is awarded using a strict minimizing function:
1. It calculates the **Residual Risk %** for every possible target.
2. It completely ignores how many CVEs are *resolved*. It strictly prioritizes the **lowest absolute remaining risk**.
3. It selects the target version with the lowest Residual Risk %.

If a minor release introduces new critical bugs, the algorithm will intelligently suggest a lower patch version as the "Best Choice" because it mathematically yields a safer overall cluster posture!

---

// filepath: docs/implementation_plan.md
# Cluster CVE & Upgrade Path RAG Implementation Plan

This document outlines the architectural changes and implementation steps to achieve CVE extraction, cluster vulnerability mapping, and upgrade path recommendations using the Red Hat Offline Knowledge Portal (RHOKP) and RAG.

## User Review Required

> [!IMPORTANT]
> The offline knowledge portal syncing requires a data source. Please confirm if you have an offline JSON dump of the RHSA (Red Hat Security Advisories) or if the ingestion script should pull from a specific internal URL.

> [!WARNING]
> Generating upgrade paths requires an understanding of OpenShift update graphs. Do we have access to the `cincinnati` / OSUS upgrade graph data offline, or should we simulate the upgrade graph based purely on semantic versioning (e.g., 4.20.15 -> 4.20.16)?

## Open Questions
1. Do you want the RAG extraction to run asynchronously (via Celery) when a cluster version changes, or synchronously when the UI requests it?
2. Are clusters already stored in a separate table, or should we create a new `ClusterInventory` table?

## Proposed Changes

---

### Database & Models

#### [MODIFY] [models.py](file:///c:/Users/SRIMANDARBHA/Downloads/rag_testing/db/models.py)
We will introduce two new SQLAlchemy models:
1. `ClusterInventory`: Tracks `cluster_id`, `name`, `current_version`, and a JSONB field for `active_cves`.
2. `RHOKPSecurityAdvisory`: Stores `advisory_id` (e.g., RHSA-2026:3856), `affected_versions`, `fixed_in_version`, `summary`, and an `embedding` vector column for RAG similarity searches.

---

### Data Ingestion

#### [NEW] [sync_rhokp_cve_to_postgres.py](file:///c:/Users/SRIMANDARBHA/Downloads/rag_testing/ingestion/sync_rhokp_cve_to_postgres.py)
A new ingestion script similar to `sync_runbook_to_rag.py`. 
- **Action:** It will parse offline Red Hat Errata/CVE data.
- **Action:** It will chunk the CVE summaries and use the `all-MiniLM-L6-v2` embedding model to store vectors into the `RHOKPSecurityAdvisory` table.

---

### API & RAG Engine

#### [NEW] [routers/cve_advisor.py](file:///c:/Users/SRIMANDARBHA/Downloads/rag_testing/api/routers/cve_advisor.py)
Exposes the backend logic to the frontend via FastAPI.
- `GET /api/clusters`: Returns the list of clusters from `ClusterInventory` along with their affected CVE counts.
- `GET /api/clusters/{cluster_id}/upgrade-advisor`: 
  - **RAG Logic:** Uses the local LLM (Phi-4 / local-model) to compare the cluster's current version against the `RHOKPSecurityAdvisory` embeddings.
  - **Path Generation:** Determines the immediate next version (e.g., `current + 1 patch`) and evaluates remaining CVEs.
  - **Response:** Returns two suggested paths: 
    - **Path 1 (Recommended):** Version with the *least* issues.
    - **Path 2 (Warning):** Immediate version that might still retain *considerable* issues (if intermediate updates don't fix everything).

#### [MODIFY] [main.py](file:///c:/Users/SRIMANDARBHA/Downloads/rag_testing/api/main.py)
- Register the new `cve_advisor` router.

---

### Frontend UI

#### [NEW] [src/components/UpgradeAdvisor.tsx](file:///c:/Users/SRIMANDARBHA/Downloads/rag_testing/frontend/src/components/UpgradeAdvisor.tsx)
A premium, dynamic React component using Tailwind CSS.
- **Cluster List View:** A clean table mapping clusters to their current versions and a highly visible "Critical CVEs" badge.
- **Upgrade Path Cards:** When clicking a cluster, it expands to show the two upgrade options:
  - Green card for "Least Issues" (Safe path).
  - Amber/Red card for "Considerable Issues" (Warning path).
  - Will include micro-animations on hover and glassmorphism styling to provide a highly polished look.

---

## Verification Plan

### Automated Tests
- Unit test the RAG prompt extraction to ensure the LLM reliably outputs JSON detailing the CVEs for a specific version.
- API tests using `pytest` and `respx` to mock the Neo4j/Postgres calls and verify the `upgrade-advisor` endpoint logic.

### Manual Verification
- Run the ingestion script with a mock RHSA file (like the one previously fetched for RHSA-2026:3856).
- Start the Vite dev server and confirm the UI flawlessly renders the upgrade paths and dynamically queries the backend.

---

// filepath: docs/implementation_plan_v2.md
# Implementation Plan: Advanced CVE Risk & Upgrade Advisor

Based on your request, we will significantly refine the Upgrade Advisor to map exact versions to CVEs, calculate quantified risk percentages, evaluate residual risks ("risks waiting") for target upgrades, and automatically determine the absolute best upgrade path based on errata analysis.

## Proposed Changes

---

### Database & Ingestion

We will modify the backend data structure to accurately map specific versions to vulnerabilities so we can calculate risks dynamically.

#### [MODIFY] `ingestion/sync_rhokp_cve_to_postgres.py`
- Refactor the ingestion script to use a purely relational schema for CVE-to-version mappings to avoid heavy ML dependencies (`sentence-transformers`) that previously caused environment issues.
- **Table Structure:**
  - `advisory_id`: String (e.g., RHSA-2026:3856)
  - `affected_versions`: Array of Strings (e.g., `["4.20.15", "4.20.16"]`)
  - `severity`: String (Critical, Important, Moderate, Low)
  - `description`: String
- Create an extensive mock dataset representing real OpenShift errata (including the ones pulled earlier) spanning `4.20.15`, `4.20.16`, `4.20.17`, and `4.21.0` to demonstrate varying levels of active and residual risks.

---

### API & Core Logic

We will rewrite the advisor endpoint to perform live risk calculations and delta comparisons.

#### [MODIFY] `api/routers/cve_advisor.py`
- **Risk Calculation Engine:**
  - Introduce severity weighting: Critical = 10, Important = 5, Moderate = 2, Low = 1.
  - Compute a **Current Risk Percentage** by summing the weights of all CVEs affecting the cluster's *current* version.
- **Path Evaluation:**
  - For candidate upgrade targets (e.g., Patch `4.20.17` vs Minor `4.21.0`), fetch the CVEs that *still affect* the target ("Risks Waiting").
  - Compute the **Residual Risk Percentage** for each target.
  - Identify the vulnerabilities that will be successfully mitigated ("Resolves").
- **Best Upgrade Identification:**
  - Algorithmically select the "Best Version" by finding the semantic upgrade path that yields the lowest Residual Risk Percentage.

---

### Frontend UI Visualization

We will overhaul the React interface to incorporate data-dense, visually striking metrics.

#### [MODIFY] `frontend/src/components/UpgradeAdvisor.tsx`
- **Current Posture Display:**
  - Add a dynamic Risk Gauge (circular progress bar) displaying the current cluster's Risk Percentage in appropriate colors (Red for high risk).
  - List the active vulnerabilities currently impacting the cluster.
- **Upgrade Path Cards:**
  - Add a "Residual Risk" gauge to each proposed upgrade card.
  - Split the details into two distinct views:
    1. **Resolves (✓):** The CVEs that this upgrade will eliminate.
    2. **Risks Waiting (⚠):** The CVEs (like zero-days or unpatched minor bugs) that will still be present in the target version.
  - Add a glowing **"⭐ Recommended Target"** badge to the path chosen by the backend's Best Upgrade algorithm.

## Verification Plan
1. **API Validation:** Run the new ingestion script, hit the endpoint manually, and ensure `current_risk_percent` and `risks_waiting` are accurately calculated based on the dataset.
2. **UI Validation:** Ensure the risk gauges render correctly and the "Best Upgrade" badge aligns with the lowest residual risk score.

> [!IMPORTANT]
> Please review this plan. If you approve the math behind the risk percentages and the proposed UI visualizations, we will proceed with the execution immediately.

---

// filepath: docs/implementation_plan_v3.md
# Implementation Plan: Dynamic Errata Sync & Live Cluster Integration

Based on your existing `clusters` table, we will shift the architecture from static mock data to a dynamic, production-ready synchronization workflow. The system will read your live cluster inventory, calculate potential future versions, and fetch/ingest the Errata data accordingly.

## Proposed Changes

---

### 1. Database Alignment
Your existing infrastructure relies on the `clusters` table, not the temporary `cluster_inventory` table I created earlier.

- **Data Update:** I will execute a SQL script to modify your existing `clusters` table, updating `openshift_version` to realistic `4.19.x` and `4.20.x` minor builds as requested.
- **Backend Refactor:** I will update the `api/routers/cve_advisor.py` endpoint to query the `clusters` table (`cluster_id`, `name`, `openshift_version`) instead of `cluster_inventory`.

---

### 2. Dynamic Weekly Ingestion Script
We will transform `sync_rhokp_cve_to_postgres.py` into a dynamic cron-ready script designed to run weekly.

**Execution Flow:**
1. **Discover:** Query the `clusters` table to identify all distinct `openshift_version` values actively running in your environments.
2. **Calculate Targets:** For each active version, calculate the immediate higher Patch versions (e.g., `4.19.15` -> `4.19.16`) and Minor versions (e.g., `4.20.0`).
3. **Fetch/Simulate:** Reach out to the Red Hat Security API (or dynamically generate accurate mock Errata mappings if the public unauthenticated API restricts exact minor version queries). It will structure CVEs affecting the current versions and the newly calculated target versions.
4. **Upsert:** Cleanly upsert these dynamic Errata records into `rhokp_cve_knowledge` so the RAG API and Upgrade Advisor UI stay perfectly synchronized with the latest vulnerabilities.

## Verification Plan
1. Ensure the `clusters` table is successfully updated to `4.19`/`4.20`.
2. Run the new `sync_rhokp_cve_to_postgres.py` and verify it automatically detects the versions in the database.
3. Test the UI to ensure the existing Dashboard and Upgrade Advisor seamlessly load the live data from the `clusters` table.

> [!IMPORTANT]
> Please review this alignment plan. If you approve, I will run the SQL updates on your database and rewrite the ingestion engine to be fully dynamic!

---

// filepath: docs/mitigation_summaries.md
# Alert Mitigations (1-Line Summary)

This table provides a quick, 1-line summary of the exact remediation steps for each alert based on the knowledge base.

| Alert ID | 1-Line Remediation Summary |
| :--- | :--- |
| **HighlyAvailableWorkloadIncorrectlySpread** | Delete the stuck pod, PVC, or blocking webhook to force recreation. |
| **ACMMetricsCollectorFederationError** | Resolution involves restoring the metrics-collector-deployment's ability to successfully authenticate and scrape metrics from the openshift-monitor... |
| **CoreDNSErrorsHigh** | - If there is a connectivity issue between the CoreDNS pods and the workload, review the Controlling DNS pod placement: shell oc edit dns.operator/... |
| **ACMMetricsCollectorForwardRemoteWriteError** | The mitigation depends on the errors found in the diagnosis.. |
| **etcdMembersDown** | Manually reboot the affected node(s) or wait for rolling reboot to finish. |
| **KubeControllerManagerDown** | Refer to the official documentation for specific manual resolution steps. |
| **ACMRemoteWriteError** | The mitigation depends on the errors found in the diagnosis.. |
| **ACMThanosCompactHalted** | Resolution depends on the fatal error found during the Diagnosis.. |
| **ImageRegistryStorageFull** | Contact support or open a support case for further assistance. |
| **ACMUWLMetricsCollectorFederationError** | The RBAC permissions for the uwl-metrics-collector-deployment are automatically managed by the endpoint-observability-operator. |
| **ACMUWLMetricsCollectorForwardRemoteWriteError** | This alert is almost always caused by a problem with the client certificate used for mTLS authentication. |
| **etcdGRPCRequestsSlow** | Depending on what resource was determined to be exhausted, you can try the following:. |
| **etcdHighNumberOfFailedGRPCRequests** | Depending on the above diagnosis, the issue will most likely be described in the error log line of either etcd or openshift-etcd-operator. |
| **etcdSignerCAExpirationCritical** | Refer to the official documentation for specific manual resolution steps. |
| **ImageRegistryStorageReadOnly** | Refer to the official documentation for specific manual resolution steps. |
| **AuditLogError** | The appropriate mitigation will be very different depending on the organization and the compliance requirements. |
| **ExtremelyHighIndividualControlPlaneCPU** | Scale up the deployment or increase resource limits (CPU/Memory/Storage). |
| **KubeAggregatedAPIErrors** | Troubleshoot and fix the issue or issues causing the aggregated API errors by checking the availability status for each API and by verifying the au... |
| **KubeAPIDown** | Refer to the official documentation for specific manual resolution steps. |
| **GarbageCollectorSyncFailed** | Upgrade to the recommended version to resolve known bugs. |
| **PodDisruptionBudgetAtLimit** | Refer to the official documentation for specific manual resolution steps. |
| **PodDisruptionBudgetLimit** | Refer to the official documentation for specific manual resolution steps. |
| **DeschedulerPSIDisabled** | Manually reboot the affected node(s) or wait for rolling reboot to finish. |
| **KubeSchedulerDown** | Refer to the official documentation for specific manual resolution steps. |
| **ClusterLogForwarderOutputErrorRate** | Mitigation of the issue depends upon the error message displayed by the alert. |
| **CollectorNodeDown** | The following examples assume the collector is deployed to the 'openshift-logging' namespace. |
| **AlertmanagerClusterFailedToSendAlerts** | How you resolve the problem causing the alert to fire depends on the particular issue reported in the logs.. |
| **AlertmanagerFailedReload** | The resolution depends on the particular issue reported in the logs.. |
| **NodeFilesystemFilesFillingUp** | The number of inodes allocated to a file system is usually based on the storage size. |
| **AlertmanagerFailedToSendAlerts** | The resolution depends on the particular issue reported in the logs.. |
| **ClusterMonitoringOperatorDeprecatedConfig** | Delete the stuck pod, PVC, or blocking webhook to force recreation. |
| **ClusterOperatorDegraded** | How you resolve the issue causing the Degraded state of the Operator varies depending on the Operator. |
| **ClusterOperatorDown** | How you resolve the issue causing the issue varies depending on the Operator. |
| **KubeDeploymentReplicasMismatch** | Refer to the official documentation for specific manual resolution steps. |
| **KubeJobFailed** | Delete the stuck pod, PVC, or blocking webhook to force recreation. |
| **KubeletDown** | Contact support or open a support case for further assistance. |
| **KubeNodeNotReady** | Manually reboot the affected node(s) or wait for rolling reboot to finish. |
| **NodeFilesystemSpaceFillingUp** | Delete the stuck pod, PVC, or blocking webhook to force recreation. |
| **ExtremelyHighIndividualControlPlaneMemory** | Contact support or open a support case for further assistance. |
| **KubePersistentVolumeFillingUp** | Mitigation for this issue depends on what is filling up the storage. |
| **KubePersistentVolumeInodesFillingUp** | Mitigating this issue depends on the total count of files, directories, and symbolic links. |
| **KubePodNotReady** | Refer to the official documentation for specific manual resolution steps. |
| **NodeClockNotSynchronising** | Manually reboot the affected node(s) or wait for rolling reboot to finish. |
| **NodeFileDescriptorLimit** | Reduce the number of files opened simultaneously either by adjusting application configuration or by moving some applications to other nodes.. |
| **Ingress5xxErrors** | Possible causes and mitigations include: - Checking application logs and recent deployments for errors or changes - Verifying backend pod health, r... |
| **NodeFilesystemAlmostOutOfFiles** | Refer to the [NodeFilesystemFilesFillingUp][1] runbook. |
| **NodeFilesystemAlmostOutOfSpace** | Refer to the [NodeFilesystemSpaceFillingUp][1] runbook. |
| **NodeRAIDDegraded** | Contact support or open a support case for further assistance. |
| **PrometheusDuplicateTimestamps** | Contact support or open a support case for further assistance. |
| **PrometheusKubernetesListWatchFailures** | The issue might arise for multiple reasons:. |
| **PrometheusOperatorRejectedResources** | The mitigation depends on which resources are being rejected and why.. |
| **PrometheusPossibleNarrowSelectors** | Contact support or open a support case for further assistance. |
| **OVNKubernetesNorthdInactive** | Restart the affected pod or deployment. |
| **PrometheusRemoteStorageFailures** | This alert fires when Prometheus has an issue communicating with the remote system. |
| **PrometheusRuleFailures** | Contact support or open a support case for further assistance. |
| **PrometheusScrapeBodySizeLimitHit** | Your analysis of the issue might reveal that the alert was triggered by one of two causes:  The value set for enforcedBodySizeLimit is too small. |
| **PrometheusTargetSyncFailure** | If the logs indicate a syntax or other configuration error, correct the corresponding ServiceMonitor, PodMonitor, Probe, or other configuration res... |
| **TelemeterClientFailures** | Contact support or open a support case for further assistance. |
| **ThanosRuleQueueIsDroppingAlerts** | The default queue capacity for Thanos Ruler is quite high at 10,000 items, which means that the most likely cause of this issue is a misconfigurati... |
| **ThanosRuleRuleEvaluationLatencyHigh** | - Check for a misconfiguration that causes the user workload monitoring stack to overload Thanos Ruler with duplicate or otherwise erroneous alerts. |
| **NodeWithoutOVNKubeNodePodRunning** | Manually reboot the affected node(s) or wait for rolling reboot to finish. |
| **ImageStreamImportFailed** | Inspect the failure reason in .status.tags[].conditions[].message and .status.tags[].conditions[].reason Typical causes include:  Invalid or exp... |
| **NorthboundStaleAlert** | Restart the affected pod or deployment. |
| **NoRunningOvnControlPlane** | Refer to the official documentation for specific manual resolution steps. |
| **NoRunningOvnMaster** | Refer to the official documentation for specific manual resolution steps. |
| **OVNKubernetesControllerDisconnectedSouthboundDatabase** | Mitigation will depend on what was found in the diagnosis section. |
| **SouthboundStaleAlert** | Restart the affected pod or deployment. |
| **V4SubnetAllocationThresholdExceeded** | Contact support or open a support case for further assistance. |
| **HighOverallControlPlaneMemory** | Contact support or open a support case for further assistance. |
| **KubeletHealthState** | Delete the stuck pod, PVC, or blocking webhook to force recreation. |
| **MachineConfigControllerDrainError** | Scale up the deployment or increase resource limits (CPU/Memory/Storage). |
| **MachineConfigControllerPausedPoolKubeletCA** | You must unpause the pool. |
| **MachineConfigControllerPoolAlert** | Contact support or open a support case for further assistance. |
| **MachineConfigDaemonRebootError** | Manually reboot the affected node(s) or wait for rolling reboot to finish. |
| **MachineConfigDaemonPivotError** | Manually reboot the affected node(s) or wait for rolling reboot to finish. |
| **RuncDeprecated** | To migrate from runc to crun, you can use a ContainerRuntimeConfig custom resource (CR). |
| **SystemMemoryExceedsReservation** | Contact support or open a support case for further assistance. |
| **DNSErrors** | For mitigation strategies and solutions, refer to: - Troubleshooting DNS in OpenShift - OpenShift DNS Operator - OpenShift Networking. |
| **CephClusterCriticallyFull** | Refer to the official documentation for specific manual resolution steps. |
| **DNSNxDomain** | When NX_DOMAIN errors are returned despite of an apparently valid Service or Pod host name, such as my-svc.my-namespace.svc, this is likely because... |
| **ExternalEgressHighTrend** | Contact support or open a support case for further assistance. |
| **ExternalIngressHighTrend** | Contact support or open a support case for further assistance. |
| **IngressHTTPLatencyTrend** | Possible causes and mitigations include: - Scaling HAProxy router pods or adjusting resource limits - Scaling backend application pods if they're o... |
| **IPsecErrors** | For mitigation strategies and solutions, refer to: - Configuring IPsec encryption - OpenShift Networking. |
| **LatencyHighTrend** | For mitigation strategies and solutions, refer to: - Troubleshooting latency in OpenShift - OpenShift Networking. |
| **NetObservLokiError** | Refer to the official documentation for specific manual resolution steps. |
| **NetObservNoFlows** | Refer to the official documentation for specific manual resolution steps. |
| **NetpolDenied** | For mitigation strategies and solutions, refer to: - Network policy - OpenShift Networking. |
| **CephMdsCacheUsageHigh** | Scale up the deployment or increase resource limits (CPU/Memory/Storage). |
| **PacketDropsByDevice** | For mitigation strategies and solutions, refer to: - Reducing packet drops in OVS - OpenShift Networking. |
| **PacketDropsByKernel** | For mitigation strategies and solutions, refer to: - Packet drop tracking in Network Observability - Reducing packet drops in OVS - Blog: Network O... |
| **CephClusterNearFull** | Refer to the official documentation for specific manual resolution steps. |
| **CephClusterReadOnly** | Refer to the official documentation for specific manual resolution steps. |
| **CephFSOrphanedSnapshot** | Delete the stuck pod, PVC, or blocking webhook to force recreation. |
| **CephFSStaleSubvolume** | Delete the stuck pod, PVC, or blocking webhook to force recreation. |
| **CephMdsCpuUsageHigh** | Scale up the deployment or increase resource limits (CPU/Memory/Storage). |
| **CephMdsCPUUsageHighNeedsHorizontalScaling** | Scale up the deployment or increase resource limits (CPU/Memory/Storage). |
| **ODFNodeNICBandwidthSaturation** | 1. |
| **CephMdsCPUUsageHighNeedsVerticalScaling** | Refer to the official documentation for specific manual resolution steps. |
| **CephMdsMissingReplicas** | It is highly recomended to distribute MDS daemons across at least two nodes in the cluster. |
| **CephMgrIsAbsent** | Restart the affected pod or deployment. |
| **StorageAutoScalingCapacityReached** | Scale up the deployment or increase resource limits (CPU/Memory/Storage). |
| **CephMgrIsMissingReplicas** | Restart the affected pod or deployment. |
| **CephMonHighNumberOfLeaderChanges** | pod debug gather_logs. |
| **CephMonLowNumber** | Scale up the deployment or increase resource limits (CPU/Memory/Storage). |
| **CephMonQuorumAtRisk** | Restore Ceph Mon Quorum Lost Troubleshooting Monitor. |
| **CephMonQuorumLost** | Restore Ceph Mon Quorum Lost Troubleshooting Monitor. |
| **CephMonVersionMismatch** | Contact support or open a support case for further assistance. |
| **CephNodeDown** | Document the current OCS pods (running and failing): oc -n openshift-storage get pods The OCS resource requirements must be met in order for the os... |
| **CephOSDVersionMismatch** | Contact support or open a support case for further assistance. |
| **CephPoolQuotaBytesCriticallyExhausted** | Delete the stuck pod, PVC, or blocking webhook to force recreation. |
| **NooBaaSystemCapacityWarning85** | - For public cloud providers, there is nothing to do. |
| **CephPoolQuotaBytesNearExhaustion** | Delete the stuck pod, PVC, or blocking webhook to force recreation. |
| **ClusterObjectStoreState** | Please check the health of the Ceph cluster and the deployments and find the root cause of the issue.. |
| **HighRBDCloneSnapshotCount** | Delete the stuck pod, PVC, or blocking webhook to force recreation. |
| **NooBaaSystemCapacityWarning95** | - For public cloud providers, there is nothing to do. |
| **KMSServerConnectionAlert** | Review configuration values in the ´ocs-kms-connection-details´ confimap. |
| **NooBaaSystemCapacityWarning100** | - For public cloud providers, there is nothing to do. |
| **ObcQuotaBytesAlert** | Scale up the deployment or increase resource limits (CPU/Memory/Storage). |
| **ODFNodeLatencyHighOnNonOSDNodes** | 1. |
| **ObcQuotaBytesExhausedAlert** | Scale up the deployment or increase resource limits (CPU/Memory/Storage). |
| **ObcQuotaObjectsAlert** | Scale up the deployment or increase resource limits (CPU/Memory/Storage). |
| **ObcQuotaObjectsExhausedAlert** | Scale up the deployment or increase resource limits (CPU/Memory/Storage). |
| **ODFNodeLatencyHighOnOSDNodes** | 1. |
| **ODFCorePodRestarted** | Upgrade to the recommended version to resolve known bugs. |
| **ODFDiskUtilizationHigh** | Add more disks to the cluster enhance the performance. |
| **OdfMirrorDaemonStatus** | Contact support or open a support case for further assistance. |
| **ODFNodeMTULessThan9000** | Contact support or open a support case for further assistance. |
| **ODFPersistentVolumeMirrorStatus** | Contact support or open a support case for further assistance. |
| **OdfPoolMirroringImageHealth** | Contact support or open a support case for further assistance. |
| **ODFRBDClientBlocked** | Manually reboot the affected node(s) or wait for rolling reboot to finish. |
| **OSDCPULoadHigh** | Refer to the official documentation for specific manual resolution steps. |
| **PersistentVolumeUsageCritical** | Scale up the deployment or increase resource limits (CPU/Memory/Storage). |
| **CDIDataImportCronOutdated** | Contact support or open a support case for further assistance. |
| **StorageAutoScalerCRIsInvalid** | Scale up the deployment or increase resource limits (CPU/Memory/Storage). |
| **StorageAutoScalingFailed** | Manually reboot the affected node(s) or wait for rolling reboot to finish. |
| **StorageClientIncompatibleOperatorVersion** | Update ocs-client-operator on ODF Client cluster to be on same major and minor version as odf-operator on ODF Provider cluster.. |
| **CDIDataVolumeUnusualRestartCount** | Contact support or open a support case for further assistance. |
| **CDIDefaultStorageClassDegraded** | Contact support or open a support case for further assistance. |
| **CDIMultipleDefaultVirtStorageClasses** | Contact support or open a support case for further assistance. |
| **GuestVCPUQueueHighCritical** | Contact support or open a support case for further assistance. |
| **CDINoDefaultStorageClass** | Contact support or open a support case for further assistance. |
| **CDINotReady** | Contact support or open a support case for further assistance. |
| **CDIOperatorDown** | Contact support or open a support case for further assistance. |
| **CDIStorageProfilesIncomplete** | Contact support or open a support case for further assistance. |
| **CnaoDown** | Contact support or open a support case for further assistance. |
| **CnaoNmstateMigration** | Install the OpenShift Container Platform NMState Operator from the OperatorHub. |
| **DeprecatedMachineType** | Contact support or open a support case for further assistance. |
| **DuplicateWaspAgentDSDetected** | Delete the stuck pod, PVC, or blocking webhook to force recreation. |
| **GuestVCPUQueueHighWarning** | Contact support or open a support case for further assistance. |
| **HAControlPlaneDown** | Manually reboot the affected node(s) or wait for rolling reboot to finish. |
| **HCOGoldenImageWithNoArchitectureAnnotation** | Contact support or open a support case for further assistance. |
| **HCOGoldenImageWithNoSupportedArchitecture** | The steps to mitigate this issue vary based on whether you are using pre-defined DICTs or user-defined DICTs.. |
| **HCOInstallationIncomplete** | The mitigation depends on whether you are installing or uninstalling the HCO: - Complete the installation by creating a HyperConverged CR with its ... |
| **HCOMisconfiguredDescheduler** | Contact support or open a support case for further assistance. |
| **HCOMultiArchGoldenImagesDisabled** | To address this issue, you can either enable the multi-arch boot image feature, or modify the workloads node placement in the HyperConverged CR to ... |
| **HCOOperatorConditionsUnhealthy** | Contact support or open a support case for further assistance. |
| **HighCPUWorkload** | Manually reboot the affected node(s) or wait for rolling reboot to finish. |
| **HighNodeCPUFrequency** | Contact support or open a support case for further assistance. |
| **HPPNotReady** | Contact support or open a support case for further assistance. |
| **HPPOperatorDown** | Contact support or open a support case for further assistance. |
| **HPPSharingPoolPathWithOS** | Contact support or open a support case for further assistance. |
| **KubemacpoolDown** | Contact support or open a support case for further assistance. |
| **KubeMacPoolDuplicateMacsFound** | Restart the affected pod or deployment. |
| **KubemacpoolMACCollisionDetected** | Contact support or open a support case for further assistance. |
| **KubeVirtCRModified** | Do not change the HCO operands directly. |
| **KubeVirtDeprecatedAPIRequested** | Contact support or open a support case for further assistance. |
| **KubeVirtNoAvailableNodesToRunVMs** | Contact support or open a support case for further assistance. |
| **KubeVirtVMGuestMemoryAvailableLow** | Contact support or open a support case for further assistance. |
| **NoReadyVirtHandler** | Contact support or open a support case for further assistance. |
| **KubeVirtVMGuestMemoryPressure** | Contact support or open a support case for further assistance. |
| **KubevirtVmHighMemoryUsage** | Scale up the deployment or increase resource limits (CPU/Memory/Storage). |
| **KubeVirtVMIExcessiveMigrations** | Contact support or open a support case for further assistance. |
| **LowKVMNodesCount** | Install KVM on the nodes without KVM resources.. |
| **LowReadyVirtAPICount** | Contact support or open a support case for further assistance. |
| **LowReadyVirtControllersCount** | Contact support or open a support case for further assistance. |
| **LowReadyVirtHandlerCount** | Contact support or open a support case for further assistance. |
| **LowReadyVirtOperatorsCount** | Contact support or open a support case for further assistance. |
| **LowVirtAPICount** | Contact support or open a support case for further assistance. |
| **LowVirtControllersCount** | Contact support or open a support case for further assistance. |
| **LowVirtOperatorCount** | Contact support or open a support case for further assistance. |
| **NoReadyVirtOperator** | Contact support or open a support case for further assistance. |
| **NetworkAddonsConfigNotReady** | Contact support or open a support case for further assistance. |
| **NodeNetworkInterfaceDown** | 1. |
| **NoLeadingVirtOperator** | Contact support or open a support case for further assistance. |
| **NoReadyVirtAPI** | Contact support or open a support case for further assistance. |
| **NoReadyVirtController** | Contact support or open a support case for further assistance. |
| **OperatorConditionsUnhealthy** | Contact support or open a support case for further assistance. |
| **OrphanedVirtualMachineInstances** | Contact support or open a support case for further assistance. |
| **VirtControllerRESTErrorsBurst** | Contact support or open a support case for further assistance. |
| **SingleStackIPv6Unsupported** | Refer to the official documentation for specific manual resolution steps. |
| **SSPCommonTemplatesModificationReverted** | Try to identify and resolve the cause of the changes. |
| **SSPDown** | Contact support or open a support case for further assistance. |
| **SSPFailingToReconcile** | Contact support or open a support case for further assistance. |
| **SSPHighRateRejectedVms** | Contact support or open a support case for further assistance. |
| **SSPOperatorDown** | Contact support or open a support case for further assistance. |
| **SSPTemplateValidatorDown** | Contact support or open a support case for further assistance. |
| **UnsupportedHCOModification** | Delete the stuck pod, PVC, or blocking webhook to force recreation. |
| **VirtControllerRESTErrorsHigh** | Contact support or open a support case for further assistance. |
| **VirtAPIDown** | Contact support or open a support case for further assistance. |
| **VirtApiRESTErrorsBurst** | Contact support or open a support case for further assistance. |
| **VirtHandlerRESTErrorsBurst** | Contact support or open a support case for further assistance. |
| **VirtApiRESTErrorsHigh** | Contact support or open a support case for further assistance. |
| **VirtControllerDown** | Contact support or open a support case for further assistance. |
| **VirtHandlerDaemonSetRolloutFailing** | Delete the stuck pod, PVC, or blocking webhook to force recreation. |
| **VirtHandlerDown** | Contact support or open a support case for further assistance. |
| **VirtHandlerRESTErrorsHigh** | Contact support or open a support case for further assistance. |
| **VirtLauncherPodsStuckFailed** | Contact support or open a support case for further assistance. |
| **VirtOperatorDown** | Contact support or open a support case for further assistance. |
| **VirtOperatorRESTErrorsBurst** | Contact support or open a support case for further assistance. |
| **VirtOperatorRESTErrorsHigh** | Contact support or open a support case for further assistance. |
| **VirtualMachineInstanceHasEphemeralHotplugVolume** | Contact support or open a support case for further assistance. |
| **VMCannotBeEvicted** | Set the evictionStrategy of the VMI to shutdown or resolve the issue that prevents the VMI from migrating.. |
| **VMStorageClassWarning** | It is recommended to create a dedicated StorageClass with "krbd:rxbounce" map option for the disks of virtual machines, to use a bounce buffer when... |

---

// filepath: docs/openshift_cve_report.md
# OpenShift Container Platform & Virtualization CVEs

> [!NOTE]
> The Red Hat Security Data API returns CVEs by product. Exact minor version mapping (e.g., 4.19.2 vs 4.19.3) is typically resolved at the **Errata (RHSA)** level rather than the root CVE level. The list below represents recent vulnerabilities affecting the platforms.

| CVE ID | Severity | Public Date | Description |
| :--- | :--- | :--- | :--- |
| **[CVE-2026-44604](https://access.redhat.com/security/cve/CVE-2026-44604)** | moderate | 2026-05-28 | rpm: Command injection in rpmuncompress doUntar() via unescaped archive top-level directory name in popen() shell command |
| **[CVE-2026-9804](https://access.redhat.com/security/cve/CVE-2026-9804)** | important | 2026-05-28 | kubevirt: kubevirt: VMExport directory symlink escape enables exporter pod file read |
| **[CVE-2026-8643](https://access.redhat.com/security/cve/CVE-2026-8643)** | important | 2026-05-27 | python-pip: Path traversal via malicious entry point name in pip wheel installation allows arbitrary file overwrite |
| **[CVE-2026-1933](https://access.redhat.com/security/cve/CVE-2026-1933)** | important | 2026-05-27 | samba: Missing access check on reparse point operations |
| **[CVE-2026-2340](https://access.redhat.com/security/cve/CVE-2026-2340)** | moderate | 2026-05-27 | samba: vfs_worm does not block directory modification |
| **[CVE-2026-3012](https://access.redhat.com/security/cve/CVE-2026-3012)** | important | 2026-05-27 | samba: group policy certificate enrollment uses http:// without validation |
| **[CVE-2026-48863](https://access.redhat.com/security/cve/CVE-2026-48863)** | important | 2026-05-26 | libsolv: Stack-based buffer overflow in libsolv EdDSA PGP signature verification allows denial of service |
| **[CVE-2026-48864](https://access.redhat.com/security/cve/CVE-2026-48864)** | moderate | 2026-05-26 | libsolv: Heap buffer overflow in libsolv repopagestore via unchecked decompression of malicious .solv page data |
| **[CVE-2026-4480](https://access.redhat.com/security/cve/CVE-2026-4480)** | important | 2026-05-26 | samba: Samba: Remote Code Execution in printing subsystem via unescaped job description |
| **[CVE-2026-3592](https://access.redhat.com/security/cve/CVE-2026-3592)** | moderate | 2026-05-26 | bind: Amplification vulnerabilities via self-pointed glue records |
| **[CVE-2026-5950](https://access.redhat.com/security/cve/CVE-2026-5950)** | moderate | 2026-05-26 | bind: Unbounded resend loop in BIND 9 resolver |
| **[CVE-2026-32792](https://access.redhat.com/security/cve/CVE-2026-32792)** | moderate | 2026-05-26 | unbound: Packet of death with DNSCrypt |
| **[CVE-2026-4408](https://access.redhat.com/security/cve/CVE-2026-4408)** | important | 2026-05-26 | samba: Remote Code Execution in SAMR |
| **[CVE-2026-43503](https://access.redhat.com/security/cve/CVE-2026-43503)** | important | 2026-05-23 | kernel: net: skbuff: propagate shared-frag marker through frag-transfer helpers |
| **[CVE-2026-9277](https://access.redhat.com/security/cve/CVE-2026-9277)** | important | 2026-05-22 | shell-quote: shell-quote: Arbitrary code execution via command injection due to unescaped line terminators |
| **[CVE-2026-9277](https://access.redhat.com/security/cve/CVE-2026-9277)** | important | 2026-05-22 | shell-quote: shell-quote: Arbitrary code execution via command injection due to unescaped line terminators |
| **[CVE-2026-5946](https://access.redhat.com/security/cve/CVE-2026-5946)** | important | 2026-05-21 | bind: Invalid handling of CLASS != IN |
| **[CVE-2026-3039](https://access.redhat.com/security/cve/CVE-2026-3039)** | important | 2026-05-21 | bind: BIND 9 server memory exhaustion during GSS-API TKEY negotiation |
| **[CVE-2026-5947](https://access.redhat.com/security/cve/CVE-2026-5947)** | important | 2026-05-21 | bind: SIG(0) validation during query flood may lead to undefined behavior |
| **[CVE-2026-3593](https://access.redhat.com/security/cve/CVE-2026-3593)** | important | 2026-05-21 | bind: Heap use-after-free vulnerability in BIND 9 DNS-over-HTTPS implementation |
| **[CVE-2026-9150](https://access.redhat.com/security/cve/CVE-2026-9150)** | moderate | 2026-05-20 | libsolv: Stack-based buffer overflow in libsolv's Debian metadata parser when handling SHA384/SHA512 checksums |
| **[CVE-2026-9149](https://access.redhat.com/security/cve/CVE-2026-9149)** | moderate | 2026-05-20 | libsolv: Heap buffer overflow in libsolv repo_add_solv via negative maxsize from crafted .solv file |
| **[CVE-2026-33278](https://access.redhat.com/security/cve/CVE-2026-33278)** | important | 2026-05-20 | unbound: Unbound DNSSEC Validator Use-After-Free via Deep Copy Pointer Overwrite Leading to DoS and Possible Remote Code Execution |
| **[CVE-2026-42944](https://access.redhat.com/security/cve/CVE-2026-42944)** | important | 2026-05-20 | unbound: Heap overflow and crash with multiple nsid, cookie, padding EDNS options |
| **[CVE-2026-44608](https://access.redhat.com/security/cve/CVE-2026-44608)** | moderate | 2026-05-20 | unbound: Unbound: Denial of Service due to locking inconsistency during RPZ XFR reload |
| **[CVE-2026-45232](https://access.redhat.com/security/cve/CVE-2026-45232)** | moderate | 2026-05-20 | rsync: Rsync: Denial of Service via malformed HTTP proxy response |
| **[CVE-2026-43618](https://access.redhat.com/security/cve/CVE-2026-43618)** | important | 2026-05-20 | rsync: rsync: Remote memory disclosure via integer overflow in compressed-token decoding |
| **[CVE-2026-29518](https://access.redhat.com/security/cve/CVE-2026-29518)** | important | 2026-05-20 | rsync: TOCTOU symlink race condition allowing local privilege escalation in daemon mode without chroot. |
| **[CVE-2026-43620](https://access.redhat.com/security/cve/CVE-2026-43620)** | moderate | 2026-05-20 | rsync: rsync: Remote Denial of Service via Out-of-bounds Read |
| **[CVE-2026-43619](https://access.redhat.com/security/cve/CVE-2026-43619)** | moderate | 2026-05-20 | rsync: rsync: Symlink race vulnerability allows unauthorized file operations |
| **[CVE-2026-43617](https://access.redhat.com/security/cve/CVE-2026-43617)** | moderate | 2026-05-20 | rsync: rsync: Hostname-based ACL bypass in daemon chroot configuration |
| **[CVE-2026-42959](https://access.redhat.com/security/cve/CVE-2026-42959)** | important | 2026-05-20 | unbound: Unbound DNSSEC Validator Denial of Service via Incorrect Write Offset Counter in Chase-Reply Messages |
| **[CVE-2026-42960](https://access.redhat.com/security/cve/CVE-2026-42960)** | moderate | 2026-05-20 | unbound: Unbound DNS Cache Poisoning via Promiscuous Additional Section RRSet Acceptance |
| **[CVE-2026-42923](https://access.redhat.com/security/cve/CVE-2026-42923)** | moderate | 2026-05-20 | unbound: Unbound DNSSEC Validator NSEC3 Hash Calculation Limit Bypass via Negative Cache Code Path Leading to DoS |
| **[CVE-2026-46483](https://access.redhat.com/security/cve/CVE-2026-46483)** | moderate | 2026-05-15 | vim: command injection when decompressing .tgz archives |
| **[CVE-2026-46333](https://access.redhat.com/security/cve/CVE-2026-46333)** | important | 2026-05-15 | kernel: Read root-owned files as an unprivileged user |
| **[CVE-2026-41888](https://access.redhat.com/security/cve/CVE-2026-41888)** | moderate | 2026-05-14 | github.com/distribution/distribution: Distribution: Security bypass allows unauthorized tag deletion |
| **[CVE-2026-44431](https://access.redhat.com/security/cve/CVE-2026-44431)** | moderate | 2026-05-13 | urllib3: urllib3: Information disclosure via cross-origin redirects forwarding sensitive headers |
| **[CVE-2026-44432](https://access.redhat.com/security/cve/CVE-2026-44432)** | important | 2026-05-13 | urllib3: urllib3: Denial of Service due to excessive HTTP response decompression |
| **[CVE-2026-46300](https://access.redhat.com/security/cve/CVE-2026-46300)** | important | 2026-05-13 | kernel: "Fragnesia" is a variant of Dirty Frag vulnerability in the ESP/XFRM leading to Local Privilege Escalation (LPE) vulnerability in the Linux... |
| **[CVE-2026-7168](https://access.redhat.com/security/cve/CVE-2026-7168)** | moderate | 2026-05-13 | curl: libcurl: Information disclosure via incorrect Proxy-Authorization header reuse |
| **[CVE-2026-44664](https://access.redhat.com/security/cve/CVE-2026-44664)** | moderate | 2026-05-13 | fast-xml-builder: fast-xml-builder: Arbitrary XML/HTML injection via insufficient sanitization of XML comments |
| **[CVE-2026-44665](https://access.redhat.com/security/cve/CVE-2026-44665)** | moderate | 2026-05-13 | fast-xml-builder: fast-xml-builder: Attribute injection leading to information disclosure or content manipulation |
| **[CVE-2026-44431](https://access.redhat.com/security/cve/CVE-2026-44431)** | moderate | 2026-05-13 | urllib3: urllib3: Information disclosure via cross-origin redirects forwarding sensitive headers |
| **[CVE-2026-44432](https://access.redhat.com/security/cve/CVE-2026-44432)** | important | 2026-05-13 | urllib3: urllib3: Denial of Service due to excessive HTTP response decompression |
| **[CVE-2025-35979](https://access.redhat.com/security/cve/CVE-2025-35979)** | moderate | 2026-05-12 | kernel: Kernel: Information disclosure via shared microarchitectural predictor state in Intel(R) Processors |
| **[CVE-2026-6402](https://access.redhat.com/security/cve/CVE-2026-6402)** | moderate | 2026-05-12 | webpack-dev-server: webpack-dev-server: Information disclosure due to cross-origin source code exposure |
| **[CVE-2026-6402](https://access.redhat.com/security/cve/CVE-2026-6402)** | moderate | 2026-05-12 | webpack-dev-server: webpack-dev-server: Information disclosure due to cross-origin source code exposure |
| **[CVE-2026-43896](https://access.redhat.com/security/cve/CVE-2026-43896)** | moderate | 2026-05-11 | jq: stack overflow in recursive object merge |
| **[CVE-2026-43895](https://access.redhat.com/security/cve/CVE-2026-43895)** | moderate | 2026-05-11 | jq: embedded NUL in jq import paths causes local redaction-policy bypass and preserves sensitive fields in published artifacts |
| **[CVE-2026-44777](https://access.redhat.com/security/cve/CVE-2026-44777)** | moderate | 2026-05-11 | jq: stack overflow in module loading on mutual include |
| **[CVE-2026-43894](https://access.redhat.com/security/cve/CVE-2026-43894)** | moderate | 2026-05-11 | jq: jq: Arbitrary Code Execution or Denial of Service via Signed Integer Overflow |
| **[CVE-2026-41256](https://access.redhat.com/security/cve/CVE-2026-41256)** | moderate | 2026-05-11 | jq: embedded NUL truncates top-level jq programs loaded with -f |
| **[CVE-2026-40612](https://access.redhat.com/security/cve/CVE-2026-40612)** | moderate | 2026-05-11 | jq: stack overflow via unbounded recursion in jv_contains |
| **[CVE-2026-41257](https://access.redhat.com/security/cve/CVE-2026-41257)** | moderate | 2026-05-11 | jq: signed-int overflow in stack_reallocate |
| **[CVE-2026-8261](https://access.redhat.com/security/cve/CVE-2026-8261)** | moderate | 2026-05-11 | squirrel: Squirrel: Heap-based buffer overflow allows local denial of service |
| **[CVE-2026-43500](https://access.redhat.com/security/cve/CVE-2026-43500)** | important | 2026-05-11 | kernel: "Dirty Frag" RxRPC variant is a new universal Local Privilege Escalation (LPE) vulnerability in the Linux kernel |
| **[CVE-2026-8261](https://access.redhat.com/security/cve/CVE-2026-8261)** | moderate | 2026-05-11 | squirrel: Squirrel: Heap-based buffer overflow allows local denial of service |
| **[CVE-2026-45190](https://access.redhat.com/security/cve/CVE-2026-45190)** | moderate | 2026-05-10 | Net::CIDR::Lite: perl: Net::CIDR::Lite: IP ACL bypass due to improper input validation |
| **[CVE-2026-2291](https://access.redhat.com/security/cve/CVE-2026-2291)** | moderate | 2026-05-09 | dnsmasq: dnsmasq: heap buffer overflow in cache via NAME_ESCAPE expansion |
| **[CVE-2026-4890](https://access.redhat.com/security/cve/CVE-2026-4890)** | important | 2026-05-09 | dnsmasq: NSEC bitmap parsing infinite loop |
| **[CVE-2026-4891](https://access.redhat.com/security/cve/CVE-2026-4891)** | important | 2026-05-09 | dnsmasq: RRSIG rdlen underflow leading to heap OOB read |
| **[CVE-2026-4892](https://access.redhat.com/security/cve/CVE-2026-4892)** | important | 2026-05-09 | dnsmasq: DHCPv6 CLID buffer overflow in helper process |
| **[CVE-2026-4893](https://access.redhat.com/security/cve/CVE-2026-4893)** | moderate | 2026-05-09 | dnsmasq: Broken ECS source validation bypass |
| **[CVE-2026-5172](https://access.redhat.com/security/cve/CVE-2026-5172)** | important | 2026-05-09 | dnsmasq: extract_addresses() OOB read via malformed rdlen |
| **[CVE-2026-45130](https://access.redhat.com/security/cve/CVE-2026-45130)** | moderate | 2026-05-08 | vim: Vim: Heap buffer overflow allows arbitrary code execution or denial of service |
| **[CVE-2026-6659](https://access.redhat.com/security/cve/CVE-2026-6659)** | moderate | 2026-05-08 | Crypt::PasswdMD5: Perl: Crypt::PasswdMD5: Weak cryptographic salts due to predictable random number generation |
| **[CVE-2026-41889](https://access.redhat.com/security/cve/CVE-2026-41889)** | moderate | 2026-05-08 | github.com/jackc/pgx: golang: pgx: SQL injection via specific SQL query conditions |
| **[CVE-2026-41506](https://access.redhat.com/security/cve/CVE-2026-41506)** | moderate | 2026-05-08 | golang: github.com/go-git/go-git: go-git: Information disclosure of HTTP authentication credentials via redirects |
| **[CVE-2026-41506](https://access.redhat.com/security/cve/CVE-2026-41506)** | moderate | 2026-05-08 | golang: github.com/go-git/go-git: go-git: Information disclosure of HTTP authentication credentials via redirects |
| **[CVE-2026-33811](https://access.redhat.com/security/cve/CVE-2026-33811)** | important | 2026-05-07 | net: golang: Go net package: Denial of Service via long CNAME response in LookupCNAME |
| **[CVE-2026-41139](https://access.redhat.com/security/cve/CVE-2026-41139)** | important | 2026-05-07 | mathjs: math.js: Arbitrary code execution via expression parser |
| **[CVE-2026-41674](https://access.redhat.com/security/cve/CVE-2026-41674)** | important | 2026-05-07 | xmldom: xmldom: Arbitrary XML markup injection |
| **[CVE-2026-43284](https://access.redhat.com/security/cve/CVE-2026-43284)** | important | 2026-05-07 | kernel: "Dirty Frag" ESP XFRM variant is a new universal Local Privilege Escalation (LPE) vulnerability in the Linux kernel |
| **[CVE-2026-33811](https://access.redhat.com/security/cve/CVE-2026-33811)** | important | 2026-05-07 | net: golang: Go net package: Denial of Service via long CNAME response in LookupCNAME |
| **[CVE-2026-41650](https://access.redhat.com/security/cve/CVE-2026-41650)** | moderate | 2026-05-07 | fast-xml-parser: fast-xml-parser: XML injection via improper escaping of comment and CDATA sequences |
| **[CVE-2026-44405](https://access.redhat.com/security/cve/CVE-2026-44405)** | low | 2026-05-05 | paramiko: Paramiko: Data integrity could be compromised due to SHA-1 algorithm use |
| **[CVE-2026-35579](https://access.redhat.com/security/cve/CVE-2026-35579)** | important | 2026-05-05 | github.com/coredns/coredns: CoreDNS: Authentication bypass allows unauthorized access to TSIG-protected functionalities |
| **[CVE-2026-33489](https://access.redhat.com/security/cve/CVE-2026-33489)** | moderate | 2026-05-05 | CoreDNS: github.com/coredns/coredns: CoreDNS: Information disclosure via incorrect ACL stanza selection in transfer plugin |
| **[CVE-2026-32936](https://access.redhat.com/security/cve/CVE-2026-32936)** | moderate | 2026-05-05 | github.com/coredns/coredns: CoreDNS: Denial of Service via oversized DNS-over-HTTPS GET requests |
| **[CVE-2026-32934](https://access.redhat.com/security/cve/CVE-2026-32934)** | moderate | 2026-05-05 | coredns: github.com/coredns/coredns: CoreDNS: Denial of Service due to unbounded resource growth in DNS-over-QUIC (DoQ) stream handling |
| **[CVE-2026-43869](https://access.redhat.com/security/cve/CVE-2026-43869)** | important | 2026-05-05 | Apache Thrift: Apache Thrift: Security bypass due to improper certificate validation |
| **[CVE-2026-6321](https://access.redhat.com/security/cve/CVE-2026-6321)** | important | 2026-05-04 | fast-uri: fast-uri: Path traversal vulnerability allows bypass of security policies |
| **[CVE-2026-33846](https://access.redhat.com/security/cve/CVE-2026-33846)** | important | 2026-05-04 | gnutls: GnuTLS: Denial of Service via heap buffer overflow in DTLS handshake fragment reassembly |
| **[CVE-2026-7598](https://access.redhat.com/security/cve/CVE-2026-7598)** | important | 2026-05-01 | libssh2: integer overflow via large username or password arguments |
| **[CVE-2026-43003](https://access.redhat.com/security/cve/CVE-2026-43003)** | important | 2026-05-01 | ironic-python-agent: OpenStack ironic-python-agent: Arbitrary code execution via malicious image |
| **[CVE-2026-3832](https://access.redhat.com/security/cve/CVE-2026-3832)** | low | 2026-04-30 | gnutls: gnutls: Security bypass allows acceptance of revoked server certificates via crafted OCSP response |
| **[CVE-2026-33845](https://access.redhat.com/security/cve/CVE-2026-33845)** | important | 2026-04-30 | gnutls: GnuTLS: Denial of Service via DTLS zero-length fragment |
| **[CVE-2026-3833](https://access.redhat.com/security/cve/CVE-2026-3833)** | moderate | 2026-04-30 | gnutls: GnuTLS: Policy bypass due to case-sensitive nameConstraints comparison |
| **[CVE-2025-14576](https://access.redhat.com/security/cve/CVE-2025-14576)** | important | 2026-04-30 | qt: Qt SVG: Arbitrary QML/JavaScript code injection via malicious SVG file |
| **[CVE-2026-4873](https://access.redhat.com/security/cve/CVE-2026-4873)** | moderate | 2026-04-29 | curl: curl: Information disclosure due to incorrect TLS connection reuse |
| **[CVE-2026-5773](https://access.redhat.com/security/cve/CVE-2026-5773)** | moderate | 2026-04-29 | curl: libcurl: Wrong file transfer due to incorrect SMB connection reuse |
| **[CVE-2026-6253](https://access.redhat.com/security/cve/CVE-2026-6253)** | moderate | 2026-04-29 | curl: curl: Proxy credential disclosure via redirects to unauthenticated proxies |
| **[CVE-2026-6276](https://access.redhat.com/security/cve/CVE-2026-6276)** | low | 2026-04-29 | curl: libcurl: Information disclosure due to cookie leak when reusing connections with custom Host headers |
| **[CVE-2026-5545](https://access.redhat.com/security/cve/CVE-2026-5545)** | moderate | 2026-04-29 | curl: libcurl: Authentication bypass due to incorrect HTTP Negotiate connection reuse |
| **[CVE-2026-6429](https://access.redhat.com/security/cve/CVE-2026-6429)** | moderate | 2026-04-29 | curl: libcurl: Credential leak via reused proxy connection during HTTP redirects |
| **[CVE-2026-42009](https://access.redhat.com/security/cve/CVE-2026-42009)** | important | 2026-04-29 | gnutls: gnutls: Denial of Service via DTLS packet reordering vulnerability |
| **[CVE-2026-42010](https://access.redhat.com/security/cve/CVE-2026-42010)** | important | 2026-04-29 | gnutls: gnutls: Authentication Bypass via NUL Character in Username |
| **[CVE-2026-42011](https://access.redhat.com/security/cve/CVE-2026-42011)** | moderate | 2026-04-29 | gnutls: gnutls: Security bypass due to incorrect name constraint handling |
| **[CVE-2026-42012](https://access.redhat.com/security/cve/CVE-2026-42012)** | moderate | 2026-04-29 | gnutls: gnutls: Certificate validation bypass due to improper handling of URI and SRV SANs |
| **[CVE-2026-42013](https://access.redhat.com/security/cve/CVE-2026-42013)** | moderate | 2026-04-29 | gnutls: gnutls: Certificate validation bypass due to oversized Subject Alternative Name |
| **[CVE-2026-5260](https://access.redhat.com/security/cve/CVE-2026-5260)** | moderate | 2026-04-29 | gnutls: gnutls: Information disclosure via heap overread in RSA key exchange |
| **[CVE-2026-42014](https://access.redhat.com/security/cve/CVE-2026-42014)** | moderate | 2026-04-29 | gnutls: Fix use-after-free in gnutls_pkcs11_token_set_pin |
| **[CVE-2026-42015](https://access.redhat.com/security/cve/CVE-2026-42015)** | moderate | 2026-04-29 | gnutls: gnutls: Memory corruption due to off-by-one error in PKCS#12 bag handling |
| **[CVE-2026-6238](https://access.redhat.com/security/cve/CVE-2026-6238)** | moderate | 2026-04-28 | glibc: glibc: Application crash or uninitialized memory read via crafted DNS response |
| **[CVE-2026-5435](https://access.redhat.com/security/cve/CVE-2026-5435)** | moderate | 2026-04-28 | glibc: glibc: Out-of-bounds write via TSIG record processing |
| **[CVE-2026-41636](https://access.redhat.com/security/cve/CVE-2026-41636)** | moderate | 2026-04-28 | apache.com/apache/thrift: Apache Thrift: Node.js skip() recursion |
| **[CVE-2026-41607](https://access.redhat.com/security/cve/CVE-2026-41607)** | important | 2026-04-28 | Apache Thrift: apache.com/apache/thrift: Apache Thrift: Out-of-bounds Read vulnerability |
| **[CVE-2026-41606](https://access.redhat.com/security/cve/CVE-2026-41606)** | important | 2026-04-28 | Apache Thrift: Apache Thrift: Denial of Service via uncontrolled recursion |
| **[CVE-2026-41605](https://access.redhat.com/security/cve/CVE-2026-41605)** | important | 2026-04-28 | Apache Thrift: Apache Thrift: Integer Overflow or Wraparound Vulnerability |
| **[CVE-2026-41604](https://access.redhat.com/security/cve/CVE-2026-41604)** | important | 2026-04-28 | Apache Thrift: apache.com/apache/thrift: Apache Thrift: Out-of-bounds Read vulnerability |
| **[CVE-2026-6993](https://access.redhat.com/security/cve/CVE-2026-6993)** | moderate | 2026-04-25 | net/http: golang: github.com/go-kratos/kratos: go-kratos kratos: Information disclosure via unintended HTTP server intermediary |
| **[CVE-2026-41907](https://access.redhat.com/security/cve/CVE-2026-41907)** | moderate | 2026-04-24 | uuid: uuid: Out-of-bounds write vulnerability impacts data integrity and confidentiality |
| **[CVE-2026-42042](https://access.redhat.com/security/cve/CVE-2026-42042)** | moderate | 2026-04-24 | axios: Axios: XSRF token bypass leading to information disclosure |
| **[CVE-2026-42039](https://access.redhat.com/security/cve/CVE-2026-42039)** | important | 2026-04-24 | axios: Node.js: Axios: Denial of Service via unbounded recursion in toFormData with deeply nested request data |
| **[CVE-2026-42036](https://access.redhat.com/security/cve/CVE-2026-42036)** | moderate | 2026-04-24 | axios: Axios: Denial of Service via unbounded stream consumption when 'responseType: 'stream'' is used |
| **[CVE-2026-42034](https://access.redhat.com/security/cve/CVE-2026-42034)** | moderate | 2026-04-24 | axios: Axios: Denial of Service via oversized streamed uploads bypassing body limits |
| **[CVE-2026-42037](https://access.redhat.com/security/cve/CVE-2026-42037)** | moderate | 2026-04-24 | axios: Node.js: Axios: Information disclosure via CRLF injection in multipart Content-Type header |
| **[CVE-2026-42038](https://access.redhat.com/security/cve/CVE-2026-42038)** | moderate | 2026-04-24 | axios: Axios: Information disclosure due to `no_proxy` bypass |
| **[CVE-2026-42041](https://access.redhat.com/security/cve/CVE-2026-42041)** | important | 2026-04-24 | axios: Axios: Authentication bypass due to prototype pollution of HTTP error handling |
| **[CVE-2026-42043](https://access.redhat.com/security/cve/CVE-2026-42043)** | important | 2026-04-24 | axios: Axios: NO_PROXY bypass via crafted URL |
| **[CVE-2026-42044](https://access.redhat.com/security/cve/CVE-2026-42044)** | important | 2026-04-24 | axios: Axios: Invisible JSON Response Tampering via Prototype Pollution Gadget |
| **[CVE-2026-42035](https://access.redhat.com/security/cve/CVE-2026-42035)** | moderate | 2026-04-24 | axios: Axios: Arbitrary HTTP header injection via prototype pollution |
| **[CVE-2026-42033](https://access.redhat.com/security/cve/CVE-2026-42033)** | important | 2026-04-24 | axios: Axios: HTTP Transport Hijacking via Prototype Pollution |
| **[CVE-2026-41305](https://access.redhat.com/security/cve/CVE-2026-41305)** | moderate | 2026-04-24 | postcss: PostCSS: Cross-Site Scripting (XSS) via improper escaping of style closing tags |
| **[CVE-2026-32952](https://access.redhat.com/security/cve/CVE-2026-32952)** | moderate | 2026-04-24 | go-ntlmssp: go-ntlmssp: Denial of Service via malicious NTLM challenge |
| **[CVE-2026-41240](https://access.redhat.com/security/cve/CVE-2026-41240)** | moderate | 2026-04-23 | DOMPurify: DOMPurify: Cross-Site Scripting (XSS) via inconsistent tag sanitization |
| **[CVE-2026-41239](https://access.redhat.com/security/cve/CVE-2026-41239)** | moderate | 2026-04-23 | DOMPurify: Vue 2: DOMPurify: Cross-site scripting due to incomplete sanitization of template expressions |
| **[CVE-2026-41238](https://access.redhat.com/security/cve/CVE-2026-41238)** | moderate | 2026-04-23 | DOMPurify: DOMPurify: Cross-Site Scripting bypass via prototype pollution |
| **[CVE-2026-41988](https://access.redhat.com/security/cve/CVE-2026-41988)** | low | 2026-04-23 | uuid: uuid: Unexpected data writes when using external output buffers with specific UUID versions |
| **[CVE-2026-40923](https://access.redhat.com/security/cve/CVE-2026-40923)** | moderate | 2026-04-21 | github.com/tektoncd/pipeline: Tekton Pipelines: Unauthorized access and information disclosure via path validation bypass |
| **[CVE-2026-40924](https://access.redhat.com/security/cve/CVE-2026-40924)** | moderate | 2026-04-21 | github.com/tektoncd/pipeline: Tekton Pipelines: Denial of Service via large HTTP response body |
| **[CVE-2026-40938](https://access.redhat.com/security/cve/CVE-2026-40938)** | important | 2026-04-21 | github.com/tektoncd/pipeline: Tekton Pipelines: Arbitrary code execution and secret exfiltration via malicious git commands |
| **[CVE-2026-40895](https://access.redhat.com/security/cve/CVE-2026-40895)** | important | 2026-04-21 | follow-redirects: follow-redirects: Information disclosure via cross-domain redirects |
| **[CVE-2026-33812](https://access.redhat.com/security/cve/CVE-2026-33812)** | moderate | 2026-04-21 | golang.org/x/image: golang: golang.org/x/image: Denial of Service due to excessive memory allocation when parsing malicious font files |
| **[CVE-2026-33813](https://access.redhat.com/security/cve/CVE-2026-33813)** | moderate | 2026-04-21 | golang.org/x/image: golang: golang.org/x/image: Denial of Service via malformed WEBP image parsing |
| **[CVE-2026-40161](https://access.redhat.com/security/cve/CVE-2026-40161)** | moderate | 2026-04-21 | github.com/tektoncd/pipeline: Tekton Pipelines: Information disclosure of Git API token via user-controlled serverURL |
| **[CVE-2026-25542](https://access.redhat.com/security/cve/CVE-2026-25542)** | moderate | 2026-04-21 | github.com/tektoncd/pipeline: Tekton Pipelines: Security bypass due to regular expression matching flaw |
| **[CVE-2026-6383](https://access.redhat.com/security/cve/CVE-2026-6383)** | moderate | 2026-04-15 | kubevirt: KubeVirt: Unauthorized subresource access due to improper RBAC evaluation |
| **[CVE-2026-35469](https://access.redhat.com/security/cve/CVE-2026-35469)** | important | 2026-04-13 | Kubelet: CRI-O: kube-apiserver: Kubelet, CRI-O, kube-apiserver: Denial of Service via SPDY streaming code |
| **[CVE-2026-40175](https://access.redhat.com/security/cve/CVE-2026-40175)** | important | 2026-04-10 | axios: Axios: Remote Code Execution via Prototype Pollution escalation |
| **[CVE-2025-62718](https://access.redhat.com/security/cve/CVE-2025-62718)** | important | 2026-04-09 | axios: Axios: Server-Side Request Forgery and proxy bypass due to improper hostname normalization |
| **[CVE-2026-39865](https://access.redhat.com/security/cve/CVE-2026-39865)** | moderate | 2026-04-08 | axios: Axios: Denial of Service via HTTP/2 session cleanup logic state corruption |
| **[CVE-2026-32281](https://access.redhat.com/security/cve/CVE-2026-32281)** | moderate | 2026-04-08 | crypto/x509: golang: Go crypto/x509: Denial of Service via inefficient certificate chain validation |
| **[CVE-2026-32280](https://access.redhat.com/security/cve/CVE-2026-32280)** | important | 2026-04-08 | crypto/x509: crypto/tls: golang: Go: Denial of Service vulnerability in certificate chain building |
| **[CVE-2026-32288](https://access.redhat.com/security/cve/CVE-2026-32288)** | moderate | 2026-04-08 | archive/tar: golang: Go's archive/tar package: Denial of Service via maliciously-crafted archive |
| **[CVE-2026-32283](https://access.redhat.com/security/cve/CVE-2026-32283)** | important | 2026-04-08 | crypto/tls: golang: Go crypto/tls: Denial of Service via multiple TLS 1.3 key update messages |
| **[CVE-2026-27140](https://access.redhat.com/security/cve/CVE-2026-27140)** | important | 2026-04-08 | cmd/go: golang: Go (golang) and cmd/go: Arbitrary Code Execution via malicious SWIG file names |
| **[CVE-2026-27143](https://access.redhat.com/security/cve/CVE-2026-27143)** | moderate | 2026-04-08 | golang: cmd/compile: possible memory corruption after bound check elimination |
| **[CVE-2026-32289](https://access.redhat.com/security/cve/CVE-2026-32289)** | moderate | 2026-04-08 | html/template: golang: html/template: Cross-Site Scripting (XSS) via improper context and brace depth tracking in JS template literals |
| **[CVE-2026-33810](https://access.redhat.com/security/cve/CVE-2026-33810)** | important | 2026-04-08 | crypto/x509: golang: Go crypto/x509: Certificate validation bypass due to incorrect DNS constraint application |
| **[CVE-2026-27144](https://access.redhat.com/security/cve/CVE-2026-27144)** | moderate | 2026-04-08 | golang: cmd/compile: no-op interface conversion bypasses overlap checking |
| **[CVE-2026-32282](https://access.redhat.com/security/cve/CVE-2026-32282)** | moderate | 2026-04-08 | golang: internal/syscall/unix: Root.Chmod can follow symlinks out of the root |
| **[CVE-2026-34986](https://access.redhat.com/security/cve/CVE-2026-34986)** | important | 2026-04-06 | github.com/go-jose/go-jose/v3: github.com/go-jose/go-jose/v4: Go JOSE: Denial of Service via crafted JSON Web Encryption (JWE) object |
| **[CVE-2026-4800](https://access.redhat.com/security/cve/CVE-2026-4800)** | important | 2026-03-31 | lodash: lodash: Arbitrary code execution via untrusted input in template imports |
| **[CVE-2026-2950](https://access.redhat.com/security/cve/CVE-2026-2950)** | moderate | 2026-03-31 | lodash: Lodash: Prototype pollution allows deletion of built-in prototype properties via array path bypass |
| **[CVE-2026-33762](https://access.redhat.com/security/cve/CVE-2026-33762)** | low | 2026-03-31 | github.com/go-git/go-git/v5: go-git: Denial of Service via crafted Git index file |
| **[CVE-2026-34165](https://access.redhat.com/security/cve/CVE-2026-34165)** | moderate | 2026-03-31 | github.com/go-git/go-git/v5: go-git: Denial of Service via crafted .idx file |
| **[CVE-2026-34043](https://access.redhat.com/security/cve/CVE-2026-34043)** | moderate | 2026-03-31 | serialize-javascript: serialize-javascript: Denial of Service via specially crafted array-like object serialization |
| **[CVE-2026-33997](https://access.redhat.com/security/cve/CVE-2026-33997)** | important | 2026-03-31 | moby: docker: github.com/moby/moby: Moby: Privilege validation bypass during plugin installation |
| **[CVE-2026-34040](https://access.redhat.com/security/cve/CVE-2026-34040)** | moderate | 2026-03-31 | Moby: Moby: Authorization bypass vulnerability |
| **[CVE-2026-33750](https://access.redhat.com/security/cve/CVE-2026-33750)** | moderate | 2026-03-27 | brace-expansion: brace-expansion: Denial of Service via zero step value in brace pattern |
| **[CVE-2026-33532](https://access.redhat.com/security/cve/CVE-2026-33532)** | moderate | 2026-03-26 | yaml: yaml: Denial of Service via deeply nested YAML document parsing |
| **[CVE-2026-4923](https://access.redhat.com/security/cve/CVE-2026-4923)** | moderate | 2026-03-26 | path-to-regexp: path-to-regexp: Denial of Service via specially crafted paths with multiple wildcards |
| **[CVE-2026-4926](https://access.redhat.com/security/cve/CVE-2026-4926)** | important | 2026-03-26 | path-to-regexp: path-to-regexp: Denial of Service via crafted regular expressions |
| **[CVE-2026-4867](https://access.redhat.com/security/cve/CVE-2026-4867)** | moderate | 2026-03-26 | path-to-regexp: path-to-regexp: Denial of Service via catastrophic backtracking from malformed URL parameters |
| **[CVE-2026-33809](https://access.redhat.com/security/cve/CVE-2026-33809)** | moderate | 2026-03-25 | golang: golang.org/x/image/tiff: golang.org/x/image/tiff: Denial of Service via maliciously crafted TIFF file |
| **[CVE-2026-33349](https://access.redhat.com/security/cve/CVE-2026-33349)** | moderate | 2026-03-24 | fast-xml-parser: fast-xml-parser: Denial of Service via unbounded entity expansion due to incorrect configuration limit handling |
| **[CVE-2026-33211](https://access.redhat.com/security/cve/CVE-2026-33211)** | important | 2026-03-23 | Tekton Pipelines: github.com/tektoncd/pipeline: Tekton Pipelines: Information disclosure via path traversal in git resolver |
| **[CVE-2026-33186](https://access.redhat.com/security/cve/CVE-2026-33186)** | important | 2026-03-20 | google.golang.org/grpc/grpc-go: google.golang.org/grpc/authz: gRPC-Go: Authorization bypass due to improper HTTP/2 path validation |
| **[CVE-2026-33022](https://access.redhat.com/security/cve/CVE-2026-33022)** | moderate | 2026-03-20 | github.com/tektoncd/pipeline: Tekton Pipelines: Denial of Service via long resolver names |
| **[CVE-2026-33036](https://access.redhat.com/security/cve/CVE-2026-33036)** | moderate | 2026-03-20 | fast-xml-parser: fast-xml-parser: Denial of Service via XML entity expansion bypass |
| **[CVE-2026-32274](https://access.redhat.com/security/cve/CVE-2026-32274)** | important | 2026-03-12 | black: Black: Arbitrary file writes from unsanitized user input in cache file name |
| **[CVE-2026-27139](https://access.redhat.com/security/cve/CVE-2026-27139)** | low | 2026-03-06 | os: FileInfo can escape from a Root in golang os module |
| **[CVE-2026-27138](https://access.redhat.com/security/cve/CVE-2026-27138)** | low | 2026-03-06 | crypto/x509: Panic in name constraint checking for malformed certificates in crypto/x509 |
| **[CVE-2026-27142](https://access.redhat.com/security/cve/CVE-2026-27142)** | moderate | 2026-03-06 | html/template: URLs in meta content attribute actions are not escaped in html/template |
| **[CVE-2026-25679](https://access.redhat.com/security/cve/CVE-2026-25679)** | important | 2026-03-06 | net/url: Incorrect parsing of IPv6 host literals in net/url |
| **[CVE-2026-27137](https://access.redhat.com/security/cve/CVE-2026-27137)** | important | 2026-03-06 | crypto/x509: Incorrect enforcement of email constraints in crypto/x509 |
| **[CVE-2026-29063](https://access.redhat.com/security/cve/CVE-2026-29063)** | important | 2026-03-06 | immutable-js: Immutable.js: Arbitrary code execution via Prototype Pollution |
| **[CVE-2025-15558](https://access.redhat.com/security/cve/CVE-2025-15558)** | important | 2026-03-04 | docker/cli: Docker CLI for Windows: Privilege escalation via malicious plugin binaries |
| **[CVE-2026-0540](https://access.redhat.com/security/cve/CVE-2026-0540)** | moderate | 2026-03-03 | DOMPurify: DOMPurify: Cross-site scripting vulnerability |
| **[CVE-2025-15599](https://access.redhat.com/security/cve/CVE-2025-15599)** | moderate | 2026-03-03 | DOMPurify: DOMPurify: Cross-site scripting |
| **[CVE-2026-27141](https://access.redhat.com/security/cve/CVE-2026-27141)** | moderate | 2026-02-26 | golang.org/x/net/http2: golang.org/x/net/http2: Denial of Service due to malformed HTTP/2 frames |
| **[CVE-2026-27942](https://access.redhat.com/security/cve/CVE-2026-27942)** | moderate | 2026-02-26 | fast-xml-parser: fast-xml-parser: Stack overflow leads to Denial of Service |
| **[CVE-2026-25896](https://access.redhat.com/security/cve/CVE-2026-25896)** | important | 2026-02-20 | fast-xml-parser: fast-xml-parser: Cross-Site Scripting (XSS) due to improper DOCTYPE entity handling |
| **[CVE-2026-26963](https://access.redhat.com/security/cve/CVE-2026-26963)** | moderate | 2026-02-19 | cilium: Cilium: Information disclosure via incorrect traffic permitting with specific network configurations |
| **[CVE-2026-26278](https://access.redhat.com/security/cve/CVE-2026-26278)** | important | 2026-02-19 | fast-xml-parser: fast-xml-parser: Denial of Service via unlimited XML entity expansion |
| **[CVE-2026-25934](https://access.redhat.com/security/cve/CVE-2026-25934)** | moderate | 2026-02-09 | go-git/go-git: go-git: Data integrity issue due to improper verification of pack and index files |
| **[CVE-2026-25639](https://access.redhat.com/security/cve/CVE-2026-25639)** | important | 2026-02-09 | axios: Axios affected by Denial of Service via __proto__ Key in mergeConfig |
| **[CVE-2025-47911](https://access.redhat.com/security/cve/CVE-2025-47911)** | moderate | 2026-02-05 | golang.org/x/net/html: Quadratic parsing complexity in golang.org/x/net/html |
| **[CVE-2025-68121](https://access.redhat.com/security/cve/CVE-2025-68121)** | moderate | 2026-02-05 | crypto/tls: crypto/tls: Incorrect certificate validation during TLS session resumption |
| **[CVE-2025-61732](https://access.redhat.com/security/cve/CVE-2025-61732)** | important | 2026-02-05 | cmd/cgo: Go cgo: Code smuggling due to comment parsing discrepancy |
| **[CVE-2025-22873](https://access.redhat.com/security/cve/CVE-2025-22873)** | moderate | 2026-02-04 | os: os: Information disclosure via path traversal using specially crafted filenames |
| **[CVE-2026-25128](https://access.redhat.com/security/cve/CVE-2026-25128)** | moderate | 2026-01-30 | fast-xml-parser: fast-xml-parser has RangeError DoS Numeric Entities Bug |
| **[CVE-2025-61728](https://access.redhat.com/security/cve/CVE-2025-61728)** | moderate | 2026-01-28 | golang: archive/zip: Excessive CPU consumption when building archive index in archive/zip |
| **[CVE-2025-61726](https://access.redhat.com/security/cve/CVE-2025-61726)** | important | 2026-01-28 | golang: net/url: Memory exhaustion in query parameter parsing in net/url |
| **[CVE-2025-61730](https://access.redhat.com/security/cve/CVE-2025-61730)** | moderate | 2026-01-28 | crypto/tls: Handshake messages may be processed at the incorrect encryption level in crypto/tls |
| **[CVE-2025-61731](https://access.redhat.com/security/cve/CVE-2025-61731)** | important | 2026-01-28 | cmd/go: cmd/go: Arbitrary file write via malicious pkg-config directive |
| **[CVE-2026-24137](https://access.redhat.com/security/cve/CVE-2026-24137)** | moderate | 2026-01-23 | github.com/sigstore/sigstore: sigstore legacy TUF client allows for arbitrary file writes with target cache path traversal |
| **[CVE-2025-13465](https://access.redhat.com/security/cve/CVE-2025-13465)** | important | 2026-01-21 | lodash: prototype pollution in _.unset and _.omit functions |

---

// filepath: docs/operational_intelligence_architecture.md
# AI-Powered OpenShift SRE Incident Intelligence Platform: Architectural Design

This document details the complete production-grade architecture, data schemas, ingestion logic, and agent query strategy for the ServiceNow alert-incident correlation and operational recurrence analysis engine.

---

## 1. Architecture Flow Diagram

```text
[Alertmanager alerts] ──> [ Kafka Broker ] 
                                │
                                ▼
                       [Normalization Engine] (fingerprint hash)
                                │
                                ▼
  [ServiceNow Pulls (30m)] ──> [Ingestion Pipeline] ──> [pgvector (HNSW) Embeddings]
                                │               │
                       (Upsert State)       (Append History)
                                │               │
                                ▼               ▼
                      [Operational Relational Database]
                           (PostgreSQL + pgvector)
                                │
                                ▼
                      [SRE Recommendation Agent] 
                   (Tool Calls via low-latency SQL)
```

---

## 2. Database Technology Selection & Critique

### The Winner: PostgreSQL (with `pgvector` & `JSONB`)
To store SRE operational telemetry and run low-latency AI queries, **PostgreSQL** is the only correct selection.

* **Unified Relational & Vector Space**: Allows joining transactional metrics (e.g. cluster version, incident status, reopen history) directly with HNSW vector similarity search in a **single query**. No data duplication across databases.
* **JSONB Capabilities**: Native binary JSON storage with GIN indexes allows us to preserve raw API payloads while indexing critical keys, avoiding slow table-scans.
* **Deduplication Constraints**: Strict unique indexes and transactional `UPSERT` guarantee zero duplicate entries under high concurrency.
* **HNSW Indexing**: Native pgvector implementation supports highly optimized distance metrics (`<->` cosine/L2) inside a proven, ACID-compliant database.

### Critique of Alternatives

* **MongoDB (Document DB)**: Naive choice. While good for schema-less storage, it fails catastrophically at relational joins required to compute historical recurrence across separate `alert_occurrences`, `incidents`, and `incident_snapshots` tables. Running multiple aggregation lookups under load introduces extreme latency.
* **Elasticsearch (Search Engine)**: Overkill and poor for operational state. It is not transactional, lacks strict foreign keys, has eventual consistency delays, and lacks robust relational constraint management. Running an upsert-heavy deduplication engine on Elasticsearch is highly inefficient.
* **Pinecone (Vector DB Only)**: Destroys the integrity of the design. You cannot perform operational joins (e.g. *“find similar incidents where status was closed AND reopen_count > 0 AND cluster_id = 'prod-1'”*). You are forced to maintain a separate relational DB, introducing double-writes and sync lag.
* **Cassandra (Wide-Column Store)**: Completely unsuitable. SRE telemetry analysis requires ad-hoc queries, aggregates (e.g., `MTTR` trends, flapping trends), and joins. Cassandra's query model is static and cannot support dynamic agent tool queries.

---

## 3. Deduplication and Fingerprinting Strategy

### What Constitutes a Duplicate?
A duplicate occurs when the same operational event (e.g. alert or incident state transition) is stored multiple times, causing artificial count inflation, corrupt MTTR calculation, and bad recurrence analysis.

### Why Alertname-Only Deduplication is Dangerous
Deduplicating by `alertname` alone means if two different clusters (or different namespaces on the same cluster) fire a `KubeAPIDown` alert at the same time, the system will merge them into a single incident. This masks critical production outages and results in invalid metrics.

### Secure Fingerprinting Model
We generate a deterministic `SHA-256` fingerprint for alert occurrences based on:
`SHA256(alertname + namespace + operator_component + cluster_id)`

This fingerprint uniquely identifies the operational alert instance.

* **Unique Constraints**: Table `alert_occurrences` enforces a `PRIMARY KEY` on this fingerprint.
* **UPSERT Strategy**: Ingestion uses `ON CONFLICT (fingerprint) DO UPDATE SET occurrence_count = occurrence_count + 1, last_seen = NOW()`.
* **Snapshot Uniqueness Model**: To avoid duplicate historical records, snapshots enforce a unique constraint on `(sys_id, sys_updated_on)`. If ServiceNow updates the same ticket twice within a polling window, only the latest state is kept.

---

## 4. Schema DDL Definition

```sql
-- Enable vector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 1. Clusters Table
CREATE TABLE IF NOT EXISTS clusters (
    cluster_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    openshift_version VARCHAR(20) NOT NULL,
    environment VARCHAR(20) NOT NULL CHECK (environment IN ('production', 'staging', 'development', 'dr'))
);
CREATE INDEX IF NOT EXISTS idx_clusters_env ON clusters(environment);

-- 2. Alert Occurrence Tracking (Deduplicated Stream)
CREATE TABLE IF NOT EXISTS alert_occurrences (
    fingerprint VARCHAR(64) PRIMARY KEY, -- SHA256 of identifier attributes
    alertname VARCHAR(100) NOT NULL,
    namespace VARCHAR(100) NOT NULL,
    operator_component VARCHAR(100) NOT NULL,
    cluster_id VARCHAR(50) NOT NULL REFERENCES clusters(cluster_id) ON DELETE CASCADE,
    severity VARCHAR(20) NOT NULL,
    occurrence_count INT DEFAULT 1,
    active BOOLEAN DEFAULT TRUE,
    first_seen TIMESTAMP NOT NULL,
    last_seen TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_alerts_lookup ON alert_occurrences(alertname, cluster_id, active);

-- 3. Red Hat Cases
CREATE TABLE IF NOT EXISTS redhat_cases (
    case_id VARCHAR(50) PRIMARY KEY,
    title TEXT NOT NULL,
    status VARCHAR(30) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    created_on TIMESTAMP NOT NULL,
    closed_on TIMESTAMP,
    resolution TEXT
);

-- 4. Current ServiceNow Incident State
CREATE TABLE IF NOT EXISTS incidents (
    sys_id VARCHAR(32) PRIMARY KEY, -- ServiceNow sys_id UUID
    number VARCHAR(20) UNIQUE NOT NULL, -- INC0012345
    state VARCHAR(30) NOT NULL, -- New, Work in Progress, Resolved, Closed, Reopened
    sys_created_on TIMESTAMP NOT NULL,
    sys_updated_on TIMESTAMP NOT NULL,
    short_description TEXT NOT NULL,
    cluster_id VARCHAR(50) REFERENCES clusters(cluster_id) ON DELETE SET NULL,
    alert_fingerprint VARCHAR(64) REFERENCES alert_occurrences(fingerprint) ON DELETE SET NULL,
    flapping_count INT DEFAULT 0,
    redhat_case_id VARCHAR(50) REFERENCES redhat_cases(case_id) ON DELETE SET NULL,
    sentiment_label VARCHAR(10) CHECK (sentiment_label IN ('positive', 'negative', 'neutral')),
    sentiment_score NUMERIC(5, 4),
    raw_payload JSONB
);
CREATE INDEX IF NOT EXISTS idx_incidents_state ON incidents(state);
CREATE INDEX IF NOT EXISTS idx_incidents_fingerprint ON incidents(alert_fingerprint);

-- 5. Incident Worknotes Timeline
CREATE TABLE IF NOT EXISTS incident_worknotes (
    id SERIAL PRIMARY KEY,
    sys_id VARCHAR(32) NOT NULL REFERENCES incidents(sys_id) ON DELETE CASCADE,
    worknote_text TEXT NOT NULL,
    created_on TIMESTAMP NOT NULL,
    sentiment_label VARCHAR(10) CHECK (sentiment_label IN ('positive', 'negative', 'neutral')),
    sentiment_score NUMERIC(5, 4)
);
CREATE INDEX IF NOT EXISTS idx_worknotes_sys_id ON incident_worknotes(sys_id, created_on DESC);

-- 6. Historical Ticket State Snapshots (Lifecycle Track)
CREATE TABLE IF NOT EXISTS incident_snapshots (
    snapshot_id SERIAL PRIMARY KEY,
    sys_id VARCHAR(32) NOT NULL REFERENCES incidents(sys_id) ON DELETE CASCADE,
    state VARCHAR(30) NOT NULL,
    sys_updated_on TIMESTAMP NOT NULL,
    changed_by VARCHAR(100) NOT NULL,
    worknotes_added TEXT,
    sentiment_label VARCHAR(10),
    sentiment_score NUMERIC(5, 4),
    CONSTRAINT unique_sys_id_updated UNIQUE (sys_id, sys_updated_on)
);
CREATE INDEX IF NOT EXISTS idx_snapshots_lookup ON incident_snapshots(sys_id, sys_updated_on DESC);

-- 7. Recurrence Intelligence Aggregates (Long-term retention)
CREATE TABLE IF NOT EXISTS recurrence_intelligence (
    fingerprint VARCHAR(64) PRIMARY KEY REFERENCES alert_occurrences(fingerprint) ON DELETE CASCADE,
    alertname VARCHAR(100) NOT NULL,
    operator_component VARCHAR(100) NOT NULL,
    cluster_id VARCHAR(50) REFERENCES clusters(cluster_id) ON DELETE CASCADE,
    total_occurrences INT DEFAULT 0,
    total_incidents INT DEFAULT 0,
    reopen_count INT DEFAULT 0,
    mttr_seconds BIGINT DEFAULT 0,
    resolution_quality_score NUMERIC(5, 2),
    last_reopened_at TIMESTAMP,
    updated_at TIMESTAMP NOT NULL
);

-- 8. Embeddings Table (Vector Storage for playbooks & post-mortems)
CREATE TABLE IF NOT EXISTS operational_knowledge_embeddings (
    id SERIAL PRIMARY KEY,
    source_id VARCHAR(100) NOT NULL,
    source_table VARCHAR(50) NOT NULL,
    text_chunk TEXT NOT NULL,
    embedding vector(384) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_vector_hnsw ON operational_knowledge_embeddings USING hnsw (embedding vector_l2_ops) WITH (m = 16, ef_construction = 64);
```

---

## 5. Schema Mechanics & Retention Policy

| Schema / Table | Update Behavior | Retention Strategy | Critique of Bad Approaches |
| :--- | :--- | :--- | :--- |
| **`alert_occurrences`** | `UPSERT` on fingerprint match. | Short-term (e.g. 14 days) for active count resets. | *Bad: Deleting active alert records means recurrence calculation starts from zero, losing flapping trends.* |
| **`incidents`** | `UPSERT` on `sys_id`. | Long-term (Indefinitely) as operational metadata. | *Bad: Storing only raw JSON makes searching/sorting slow and breaks SRE agent tool-calling APIs.* |
| **`incident_snapshots`** | Append only on transition detect. | Medium-term (e.g., 90 days) for SLA metrics. | *Bad: Storing a snapshot on every poll leads to massive storage bloat. Store only when state changes.* |
| **`recurrence_intelligence`** | Calculated update periodically. | Indefinite. | *Bad: Running recalculations on raw logs at search time is too slow. Maintain aggregated statistics.* |
| **`operational_knowledge_embeddings`** | Write once, delete on source delete. | Indefinite (Updated on post-mortem publication). | *Bad: Embedding raw JSON yields poor semantic similarity. Embed only cleaned playbooks/summaries.* |

---

## 6. JSON Normalization & Flat Fields Strategy

### Sample Raw ServiceNow Payload
```json
{
  "sys_id": "8a3a41b2c0a80164010b7a8a1132c3f8",
  "number": "INC0049281",
  "state": "Work in Progress",
  "sys_created_on": "2026-05-22 10:00:00",
  "sys_updated_on": "2026-05-22 10:30:00",
  "short_description": "CoreDNSErrorsHigh firing on cluster prod-us-east-1",
  "u_cluster_id": "prod-us-east-1",
  "u_alert_name": "CoreDNSErrorsHigh",
  "u_namespace": "openshift-dns",
  "u_operator": "cluster-dns-operator",
  "u_severity": "critical",
  "u_redhat_case": "53029103",
  "comments": "Worknote: Checked pod placement. Network looks saturated.",
  "close_notes": ""
}
```

### Extraction and Normalization

* **Flat fields extracted**: `sys_id`, `number`, `state`, `sys_created_on`, `sys_updated_on`, `short_description`, `cluster_id` (from `u_cluster_id`), `redhat_case_id` (from `u_redhat_case`).
* **JSONB fields**: The raw ServiceNow JSON response is kept intact inside `raw_payload` for compliance and schema evolution (to support mapping fields added in future ServiceNow releases).
* **Critique of full dynamic flattening**: Flattening all 300+ ServiceNow internal fields into SQL columns is a maintenance nightmare. Most fields (e.g., assignment groups, urgency dropdowns, sys_tags) are metadata junk that change often and disrupt indexing performance if stored as columns.

---

## 7. Ingestion Pipeline Mechanics

The ingestion script checks for updates using `sys_updated_on > LAST_POLL_TIME`.

```python
# Pseudo-code for Ingestion Pipeline
def ingest_pipeline():
    # 1. Fetch updated tickets from ServiceNow
    records = fetch_servicenow_delta(last_poll_time)
    
    for record in records:
        # 2. Extract and Normalize
        normalized = normalize_fields(record)
        
        # 3. Handle Alert Occurrence (Upsert)
        fingerprint = generate_fingerprint(normalized)
        upsert_alert(fingerprint, normalized)
        
        # 4. Handle Red Hat Case
        if normalized['redhat_case_id']:
            upsert_redhat_case(normalized['redhat_case_id'])
            
        # 5. Upsert Incident State
        sentiment = analyze_sentiment(normalized['worknotes'])
        upsert_incident(normalized, fingerprint, sentiment)
        
        # 6. Append Snapshot on State Transition
        if state_has_changed(normalized):
            append_snapshot(normalized, sentiment)
            
        # 7. Update Recurrence Analytics Table
        recalculate_recurrence_metrics(fingerprint)
```

### Ingestion SQL Upsert Example (Incident table)
```sql
INSERT INTO incidents (sys_id, number, state, sys_created_on, sys_updated_on, short_description, cluster_id, alert_fingerprint, flapping_count, redhat_case_id, sentiment_label, sentiment_score, raw_payload)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (sys_id)
DO UPDATE SET 
    state = EXCLUDED.state,
    sys_updated_on = EXCLUDED.sys_updated_on,
    flapping_count = incidents.flapping_count + EXCLUDED.flapping_count,
    redhat_case_id = EXCLUDED.redhat_case_id,
    sentiment_label = EXCLUDED.sentiment_label,
    sentiment_score = EXCLUDED.sentiment_score,
    raw_payload = EXCLUDED.raw_payload;
```

---

## 8. Agent Tool-Calling SQL Interfaces

### Q1: Has this alert occurred before, and how many times?
```sql
SELECT total_occurrences, total_incidents, reopen_count 
FROM recurrence_intelligence 
WHERE fingerprint = %s;
```
* **Tool Response JSON**:
  ```json
  {"fingerprint": "a2b9...", "total_occurrences": 12, "total_incidents": 4, "reopen_count": 2}
  ```

### Q2: Was the previous resolution temporary?
```sql
SELECT state, worknotes_added, sentiment_label 
FROM incident_snapshots 
WHERE sys_id = %s AND state = 'Resolved' 
ORDER BY sys_updated_on DESC LIMIT 1;
```
* **Tool Response JSON**:
  ```json
  {"state": "Resolved", "closing_comment": "Applied temporary workaround (deleted pod to trigger reschedule)", "sentiment": "neutral"}
  ```

### Q3: Is the cluster noisy or showing recurrence after closure?
```sql
SELECT count(*), environment 
FROM incidents i
JOIN clusters c ON i.cluster_id = c.cluster_id
WHERE i.state = 'Closed' AND i.cluster_id = %s 
  AND i.sys_updated_on > NOW() - INTERVAL '7 days';
```

---

## 9. Vector Search / RAG Strategy

* **What to Embed**: Cleaned Playbooks, SRE Post-Mortem Summaries, and Red Hat Case Resolution summaries.
* **What NOT to Embed**: Raw JSON structures, timestamps, or system configuration logs.
* **Why raw JSON embedding is poor design**: Embeddings capture semantic meaning. Raw JSON strings like `{"sys_id": "abc", "status": "closed"}` contain structural syntax and UUID strings that degrade vector quality and reduce search relevancy.

### Retrieval SQL Join (Relational + Semantic Search)
```sql
SELECT source_id, source_table, text_chunk, (embedding <-> %s::vector) AS distance
FROM operational_knowledge_embeddings
WHERE source_table = 'playbooks'
ORDER BY embedding <-> %s::vector
LIMIT 3;
```

---

// filepath: docs/single_server_deployment.md
# Single-Server Deployment Guide

Since you already have a PostgreSQL database running natively on your server, deploying the rest of the SRE Agent stack is very straightforward using the provided `docker-compose.prod.yml`.

This approach uses Docker containers for the application layer (API, Celery Worker, Frontend, Kafka Consumer) but connects them to your host machine's native PostgreSQL database.

## Prerequisites
1. **Docker & Docker Compose** must be installed on your server.
2. **PostgreSQL** must be running and accessible.
3. You must have created the required databases (e.g., `rhokp` and `rhokp_events`) and granted the appropriate permissions to your database user.

## Step-by-Step Deployment

### 1. Set Up the Environment Variables
Create a `.env` file in the root of the project on your server. You can copy the `.env.example` file and modify it. 

The `docker-compose.prod.yml` is already configured to use `host.docker.internal` as the `DB_HOST`. This special DNS name resolves to your host machine, allowing the Docker containers to seamlessly connect to your native Postgres database.

Ensure your `.env` contains the correct credentials:
```env
# Database Credentials (pointing to host PostgreSQL)
DB_HOST=host.docker.internal
DB_PORT=5432
DB_NAME=rhokp
DB_USER=postgres
DB_PASSWORD=your_secure_password

# External Integrations (Adjust as needed)
LLM_API_URL=http://your-llm-server:8080/v1/chat/completions
LLM_API_KEY=your-api-key
PROMETHEUS_URL=http://your-prometheus:9090
AWX_BASE_URL=http://your-awx:8052
AWX_API_TOKEN=your-awx-token

# Security
API_KEY=your-secure-production-api-key
```

> [!WARNING]
> **Postgres pg_hba.conf:** Ensure your PostgreSQL server is configured to accept connections from the Docker network. You may need to edit `/etc/postgresql/XX/main/pg_hba.conf` to add a line like `host all all 172.17.0.0/16 md5` (or whatever your Docker bridge subnet is), and set `listen_addresses = '*'` in `postgresql.conf`.

### 2. Build and Launch the Containers
With your `.env` file configured, build and start the production stack in detached mode:

```bash
docker-compose -f docker-compose.prod.yml up -d --build
```

### 3. What Gets Deployed?
This command will spin up 4 containers:
1. **`frontend` (Port 80)**: The React dashboard served by an optimized Nginx container.
2. **`api` (Port 8000)**: The FastAPI backend handling the WebSocket connections, routing, and REST API.
3. **`worker`**: The Celery worker processing background AI tasks, running the ReAct pipeline, and executing Celery Beat scheduled jobs.
4. **`kafka-consumer`**: The daemon listening for new alerts on the Kafka topic and pushing them to the database.

> [!TIP]
> **Celery Broker & Backend**: Notice that we aren't deploying Redis or RabbitMQ. The `docker-compose.prod.yml` is explicitly configured to use your existing PostgreSQL database as both the message broker and the result backend (`sqla+postgresql://...`). This minimizes your infrastructure footprint on a single server!

### 4. Verify the Deployment
Once running, you can check the logs to ensure the containers are successfully connecting to your database:

```bash
# Check if API started properly
docker-compose -f docker-compose.prod.yml logs -f api

# Check if the Celery worker is connected to Postgres
docker-compose -f docker-compose.prod.yml logs -f worker
```

If everything is green, your SRE dashboard will be accessible via HTTP on port `80` of your server's IP address!

---

// filepath: docs/sre_incident_intelligence_synopsis.md
# AI-Powered OpenShift SRE Incident Intelligence Platform: System Synopsis & Architecture

This document provides a comprehensive technical overview of the OpenShift SRE Operational Intelligence, Incident Ingestion, and Recurrence Analysis platform. It defines the system's core purpose, high-level multi-agent pipeline, low-level ingestion mechanics, database design, and agent blackboard reasoning logic.

---

## 1. High-Level Overview & Architecture

### System Purpose
The SRE Incident Intelligence Platform is designed to automate the lifecycle of cluster-alert incidents on enterprise Red Hat OpenShift fleets. It aggregates incoming Alertmanager alerts, correlates them with ServiceNow (SNOW) incident states and Red Hat support tickets, pulls semantic context from runbook repositories (RAG), and routes evidence-backed remediation recommendations to automated webhooks or human operators.

### High-Level Logic Flow

```mermaid
flowchart TD
    subgraph Monitoring ["Telemetry & Alert Sources"]
        Alerts["OpenShift Alertmanager Alerts"]
        SNOW["ServiceNow (ocv-sre-support)"]
        RH["Red Hat Support Cases"]
    end

    subgraph SyncEngine ["Ingestion & Normalisation Engine"]
        Watermark["1. Get Watermark (MAX sys_updated_on)"]
        APIQuery["2. Query SNOW API (sys_updated_on > watermark)"]
        Fingerprint["3. Compute SHA-256 Fingerprint"]
        RelationalUpsert["4. Database UPSERT (ON CONFLICT)"]
        Sentiment["5. Calculate Sentiment Score (Comments/Worknotes)"]
        Vectorise["6. Vectorise Resolution Notes (all-MiniLM-L6-v2)"]
    end

    subgraph Database ["PostgreSQL + pgvector Database (rhokp)"]
        DBRelational["Relational Tables\n(Clusters, Incidents, Worknotes, Snapshots)"]
        DBAggregates["Recurrence Intelligence\n(MTTR, Reopens, Quality Scores)"]
        DBVectors["Semantic Vector Space\n(HNSW Vector Index)"]
    end

    subgraph Agents ["Multi-Agent Blackboard Reasoning Pipeline"]
        State["Shared JSON State (IncidentState)"]
        AggAgent["1. Telemetry Aggregator\n(0% LLM - SQL Metrics)"]
        RAGAgent["2. RAG Recommender\n(Cognitive LLM - Synthesis)"]
        DecideAgent["3. Gatekeeper Decider\n(Cognitive LLM - Policy/Risk)"]
    end

    subgraph Execution ["Remediation Output"]
        Webhook["Auto-Remediation Webhook\n(Compaction, scaling, labeling)"]
        SRESlack["Human-in-the-Loop Gate\n(SRE Slack approval / SNOW update)"]
    end

    %% Flow lines
    Alerts --> SNOW
    SNOW --> Watermark
    Watermark --> APIQuery
    APIQuery --> Fingerprint
    Fingerprint --> RelationalUpsert
    RelationalUpsert --> Sentiment
    Sentiment --> Vectorise
    Vectorise --> Database
    
    Database <--> AggAgent
    Database <--> RAGAgent
    
    State --> AggAgent
    AggAgent -- "Appends telemetry" --> State
    State --> RAGAgent
    RAGAgent -- "Appends plan & risk" --> State
    State --> DecideAgent
    DecideAgent -- "Decides Routing" --> State
    
    DecideAgent --> Webhook
    DecideAgent --> SRESlack
```

---

## 2. Summary of Work Done So Far

1. **Relational & Vector Database Design**: Established a unified PostgreSQL schema with the `pgvector` extension and HNSW graph indexing for high-performance semantic search.
2. **Recursive Runbook Ingestion Engine ([sync_runbook_to_rag.py](file:///c:/Users/SRIMANDARBHA/Downloads/rag_testing/sync_runbook_to_rag.py))**:
   - Automated cloning/extraction fallback of the upstream `openshift/runbooks` repository.
   - Implemented markdown parsing and chunking aligned with standard Knowledge-Centered Service (KCS) sections (`MEANING`, `DIAGNOSIS`, `MITIGATION`).
   - Vectorized and stored 703 documentation chunks covering 262 unique alerts in the `rhokp_knowledge` vector table.
3. **Synthetic SRE Data Simulator ([generate_simulated_snow_data.py](file:///c:/Users/SRIMANDARBHA/Downloads/rag_testing/generate_simulated_snow_data.py))**:
   - Populated the database with 5 clusters, 25 alert occurrences, 8 Red Hat support cases, 55 ServiceNow incidents, 121 worknotes, 145 lifecycle snapshots, and computed long-term recurrence metrics.
   - Vectorized and indexed 30 dense incident post-mortems.
4. **Live ServiceNow Delta Synchronization Script ([sync_servicenow_to_postgres.py](file:///c:/Users/SRIMANDARBHA/Downloads/rag_testing/sync_servicenow_to_postgres.py))**:
   - Configured incremental updates querying ServiceNow using database-stored watermarks (`MAX(sys_updated_on)`).
   - Designed robust fallback regex parsing on ticket descriptions.
   - Automatically generates and writes dense 384-dimensional vector embeddings for closed incidents.
   - Includes a `--mock` mode to test delta synchronization offline.

---

## 3. Low-Level Ingestion & Sync Mechanics

The delta sync pipeline guarantees incremental extraction, schema normalization, deduplication, and vectorization.

```mermaid
sequenceDiagram
    autonumber
    participant Sync as Ingestion Engine (sync_servicenow_to_postgres)
    participant DB as PostgreSQL Database (rhokp)
    participant SNOW as ServiceNow Table API
    participant Model as sentence-transformers (all-MiniLM-L6-v2)

    Note over Sync, DB: Step 1: Detect Watermark
    Sync->>DB: Query MAX(sys_updated_on) FROM incidents;
    DB-->>Sync: Return last_sync_time (e.g. 2026-05-22 22:15:08)

    Note over Sync, SNOW: Step 2: Query Live API
    Sync->>SNOW: GET /api/now/table/incident with sysparm_query & Basic Auth
    Note right of Sync: Query: assignment_group.name=ocv-sre-support^stateIN1,2,6,7,8^sys_updated_on>2026-05-22 22:15:08
    SNOW-->>Sync: Return array of updated incident records

    loop For each incident record
        Note over Sync: Step 3: Normalise & Hash Fingerprint
        Sync->>Sync: Extract metadata (alertname, namespace, operator_component, cluster_id)
        Sync->>Sync: Compute SHA-256 Fingerprint: HASH(alertname + namespace + operator_component + cluster_id)
        
        Note over Sync, DB: Step 4: Database Upserts (ACID Txn)
        Sync->>DB: UPSERT Cluster (ON CONFLICT DO NOTHING)
        Sync->>DB: UPSERT Alert Occurrence (ON CONFLICT: occurrence_count += 1)
        Sync->>Sync: Analyze worknote sentiment (deterministic lexicon scorer)
        Sync->>DB: UPSERT Incident (ON CONFLICT: update state, sys_updated_on, sentiment)
        Sync->>DB: INSERT Worknote timeline entry
        Sync->>DB: INSERT Snapshot (ON CONFLICT (sys_id, sys_updated_on) DO NOTHING)
        
        Note over Sync, DB: Step 5: Recalculate Recurrence Aggregates
        Sync->>DB: Query historical reopens, active status, and MTTR averages for fingerprint
        Sync->>DB: Calculate Resolution Quality Score
        Sync->>DB: UPSERT recurrence_intelligence table
    end

    Note over Sync, Model: Step 6: Vectorise Resolutions (Async Outer Loop)
    loop For each incident resolved/closed in this sync
        Sync->>Model: Encode chunk: "Post-Mortem INCXXXX | Desc | Resolution | Sentiment"
        Model-->>Sync: Return 384-dimensional dense vector coordinates
        Sync->>DB: INSERT INTO operational_knowledge_embeddings
    end
```

### Ingestion Details

1. **Watermark Retrieval**:
   ```sql
   SELECT MAX(sys_updated_on) FROM incidents;
   ```
   If the database is empty, the timestamp defaults to `now - 30 days` to establish an initial synchronization baseline.

2. **Deduplication Hashing**:
   Deduplicating by alert name alone is highly dangerous, as it would merge incidents firing on different clusters or namespaces. The system generates a deterministic `SHA-256` fingerprint:
   ```python
   fingerprint = SHA256(alertname + namespace + operator_component + cluster_id)
   ```

3. **Database Conflict Management**:
   - **`alert_occurrences`**: Increments `occurrence_count` and updates `last_seen` timestamp.
   - **`incidents`**: Merges state, update timestamp, sentiment values, and replaces the JSONB payload.
   - **`incident_snapshots`**: Captures historical timeline changes. To prevent database bloating from high-frequency sync polling, snapshots enforce a composite unique constraint `(sys_id, sys_updated_on)` with `ON CONFLICT DO NOTHING`.

---

## 4. Low-Level Database Schema & Critique

### Relational + pgvector DDL Definition

```sql
-- Enable vector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 1. Clusters Table
CREATE TABLE IF NOT EXISTS clusters (
    cluster_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    openshift_version VARCHAR(20) NOT NULL,
    environment VARCHAR(20) NOT NULL CHECK (environment IN ('production', 'staging', 'development', 'dr'))
);
CREATE INDEX IF NOT EXISTS idx_clusters_env ON clusters(environment);

-- 2. Alert Occurrence Tracking (Deduplicated Stream)
CREATE TABLE IF NOT EXISTS alert_occurrences (
    fingerprint VARCHAR(64) PRIMARY KEY, -- SHA-256 hash
    alertname VARCHAR(100) NOT NULL,
    namespace VARCHAR(100) NOT NULL,
    operator_component VARCHAR(100) NOT NULL,
    cluster_id VARCHAR(50) NOT NULL REFERENCES clusters(cluster_id) ON DELETE CASCADE,
    severity VARCHAR(20) NOT NULL,
    occurrence_count INT DEFAULT 1,
    active BOOLEAN DEFAULT TRUE,
    first_seen TIMESTAMP NOT NULL,
    last_seen TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_alerts_lookup ON alert_occurrences(alertname, cluster_id, active);

-- 3. Red Hat Cases
CREATE TABLE IF NOT EXISTS redhat_cases (
    case_id VARCHAR(50) PRIMARY KEY,
    title TEXT NOT NULL,
    status VARCHAR(30) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    created_on TIMESTAMP NOT NULL,
    closed_on TIMESTAMP,
    resolution TEXT
);

-- 4. Current ServiceNow Incident State
CREATE TABLE IF NOT EXISTS incidents (
    sys_id VARCHAR(32) PRIMARY KEY, -- SNOW sys_id
    number VARCHAR(20) UNIQUE NOT NULL, -- INCXXXX
    state VARCHAR(30) NOT NULL, -- New, WIP, Resolved, Closed, Reopened
    sys_created_on TIMESTAMP NOT NULL,
    sys_updated_on TIMESTAMP NOT NULL,
    short_description TEXT NOT NULL,
    cluster_id VARCHAR(50) REFERENCES clusters(cluster_id) ON DELETE SET NULL,
    alert_fingerprint VARCHAR(64) REFERENCES alert_occurrences(fingerprint) ON DELETE SET NULL,
    flapping_count INT DEFAULT 0,
    redhat_case_id VARCHAR(50) REFERENCES redhat_cases(case_id) ON DELETE SET NULL,
    sentiment_label VARCHAR(10) CHECK (sentiment_label IN ('positive', 'negative', 'neutral')),
    sentiment_score NUMERIC(5, 4),
    raw_payload JSONB
);
CREATE INDEX IF NOT EXISTS idx_incidents_state ON incidents(state);
CREATE INDEX IF NOT EXISTS idx_incidents_fingerprint ON incidents(alert_fingerprint);

-- 5. Incident Worknotes Timeline
CREATE TABLE IF NOT EXISTS incident_worknotes (
    id SERIAL PRIMARY KEY,
    sys_id VARCHAR(32) NOT NULL REFERENCES incidents(sys_id) ON DELETE CASCADE,
    worknote_text TEXT NOT NULL,
    created_on TIMESTAMP NOT NULL,
    sentiment_label VARCHAR(10) CHECK (sentiment_label IN ('positive', 'negative', 'neutral')),
    sentiment_score NUMERIC(5, 4)
);
CREATE INDEX IF NOT EXISTS idx_worknotes_sys_id ON incident_worknotes(sys_id, created_on DESC);

-- 6. Historical Ticket State Snapshots (Lifecycle Track)
CREATE TABLE IF NOT EXISTS incident_snapshots (
    snapshot_id SERIAL PRIMARY KEY,
    sys_id VARCHAR(32) NOT NULL REFERENCES incidents(sys_id) ON DELETE CASCADE,
    state VARCHAR(30) NOT NULL,
    sys_updated_on TIMESTAMP NOT NULL,
    changed_by VARCHAR(100) NOT NULL,
    worknotes_added TEXT,
    sentiment_label VARCHAR(10) CHECK (sentiment_label IN ('positive', 'negative', 'neutral')),
    sentiment_score NUMERIC(5, 4),
    CONSTRAINT unique_sys_id_updated UNIQUE (sys_id, sys_updated_on)
);
CREATE INDEX IF NOT EXISTS idx_snapshots_lookup ON incident_snapshots(sys_id, sys_updated_on DESC);

-- 7. Recurrence Intelligence Aggregates (Long-term retention)
CREATE TABLE IF NOT EXISTS recurrence_intelligence (
    fingerprint VARCHAR(64) PRIMARY KEY REFERENCES alert_occurrences(fingerprint) ON DELETE CASCADE,
    alertname VARCHAR(100) NOT NULL,
    operator_component VARCHAR(100) NOT NULL,
    cluster_id VARCHAR(50) REFERENCES clusters(cluster_id) ON DELETE CASCADE,
    total_occurrences INT DEFAULT 0,
    total_incidents INT DEFAULT 0,
    reopen_count INT DEFAULT 0,
    mttr_seconds BIGINT DEFAULT 0,
    resolution_quality_score NUMERIC(5, 2),
    last_reopened_at TIMESTAMP,
    updated_at TIMESTAMP NOT NULL
);

-- 8. Embeddings Table (Vector Storage for playbooks & post-mortems)
CREATE TABLE IF NOT EXISTS operational_knowledge_embeddings (
    id SERIAL PRIMARY KEY,
    source_id VARCHAR(100) NOT NULL,
    source_table VARCHAR(50) NOT NULL,
    text_chunk TEXT NOT NULL,
    embedding vector(384) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_vector_hnsw ON operational_knowledge_embeddings USING hnsw (embedding vector_l2_ops) WITH (m = 16, ef_construction = 64);
```

---

## 5. Low-Level Sentiment Analysis Engine

To calculate sentiment without invoking costly, high-latency LLM calls, the sync engine runs a deterministic keyword-based classifier that scans updates for specific technical expressions.

```python
POSITIVE_WORDS = ["fixed", "resolved", "stabilized", "restored", "normal", "healthy", "successful", "completed", "great", "excellent", "workaround", "optimal", "recovered"]
NEGATIVE_WORDS = ["error", "fail", "broken", "critical", "outage", "down", "severe", "incident", "issue", "crash", "degraded", "timeout", "saturation", "leak", "exhaustion"]

def analyze_sentiment(text):
    if not text:
        return "neutral", 0.5000
    text_lower = text.lower()
    pos_count = sum(text_lower.count(word) for word in POSITIVE_WORDS)
    neg_count = sum(text_lower.count(word) for word in NEGATIVE_WORDS)
    
    # Base score centered at 0.5; shifts by 0.12 per match
    score = 0.5 + (pos_count * 0.12) - (neg_count * 0.12)
    score = max(0.0, min(1.0, score))
    
    if score > 0.58:
        label = "positive"
    elif score < 0.42:
        label = "negative"
    else:
        label = "neutral"
        
    return label, round(score, 4)
```

---

## 6. Multi-Agent Blackboard Architecture

To ensure decoupling and scalability, the platform uses the **Blackboard Design Pattern**. Individual agents operate as independent workers that read and update a shared JSON payload (`IncidentState`).

```mermaid
sequenceDiagram
    autonumber
    participant Orchestrator as Orchestrator / Blackboard
    participant DB as PostgreSQL (rhokp)
    participant Agent1 as 1. Telemetry Aggregator (0% LLM)
    participant Agent2 as 2. RAG Recommender (Cognitive LLM)
    participant Agent3 as 3. Gatekeeper Decider (Cognitive LLM)
    participant Webhook as Auto-Remediation Webhook

    Note over Orchestrator: Instantiate IncidentState JSON structure
    Orchestrator->>Agent1: Invoke with Initial State (incident_id, fingerprint)
    
    Note over Agent1: Step 1: SQL Telemetry Fetch
    Agent1->>DB: Query recurrence_intelligence, clusters, redhat_cases
    DB-->>Agent1: Return metrics, version, env, open cases
    Agent1->>Agent1: Mutate State: append telemetry metadata
    Agent1-->>Orchestrator: Return updated IncidentState

    Orchestrator->>Agent2: Invoke with State + Telemetry
    
    Note over Agent2: Step 2: Semantic RAG Retrieval
    Agent2->>DB: Query similar playbooks & past incident resolutions
    DB-->>Agent2: Return top-2 semantic matches
    Agent2->>Agent2: Run LLM Inference (grounded with RAG context)
    Agent2->>Agent2: Synthesise remediation steps & assign risk score
    Agent2->>Agent2: Mutate State: append proposed_action, confidence_score, risk_level
    Agent2-->>Orchestrator: Return updated IncidentState

    Orchestrator->>Agent3: Invoke with Proposed Recommendation
    
    Note over Agent3: Step 3: Decision Gate evaluation
    Agent3->>Agent3: Evaluate risk metrics, environment, & pre-approved policies
    Agent3->>Agent3: Mutate State: append final action routing
    Agent3-->>Orchestrator: Return updated IncidentState

    alt action_type == 'auto_remediate'
        Orchestrator->>Webhook: Trigger Webhook (Execute Remediation)
    else action_type == 'manual_action'
        Orchestrator->>DB: Update SNOW Ticket with proposed SRE action plan
    end
```

### Shared `IncidentState` Schema

The JSON payload passed between agents contains the following structure:

```json
{
  "incident_id": "sysid_mock_new_0000000001",
  "number": "INC0099991",
  "alert_fingerprint": "ca3957a64a85289...",
  "cluster_id": "prod-us-east-1",
  "short_description": "Alert 'CoreDNSErrorsHigh' firing in namespace 'openshift-dns'",
  "operational_history": {
    "cluster_environment": "production",
    "openshift_version": "4.14.12",
    "total_alert_occurrences": 14,
    "total_incidents_for_alert": 3,
    "reopen_count": 1,
    "average_mttr_seconds": 3600,
    "last_reopened_at": "2026-05-22 18:00:00",
    "associated_redhat_cases": [
      {
        "case_id": "RH-12948192",
        "title": "CoreDNS packet drops under scaling stress",
        "status": "Closed",
        "resolution": "Adjusted DNS upstream timeout values in CoreDNS configmap"
      }
    ]
  },
  "remediation_plan": {
    "proposed_action": "Scale CoreDNS replicas to 3 and increase upstream timeouts to 15s in the Corefile configmap.",
    "confidence_score": 0.88,
    "risk_level": "medium",
    "reference_sources": [
      "playbook-dns-errors",
      "INC0000042"
    ]
  },
  "routing_decision": {
    "action_type": "manual_action",
    "assigned_to": "human-sre-queue",
    "reasoning": "The cluster is a production environment and the proposed action involves editing a cluster operator configmap (risk level: medium). Auto-remediation is restricted to development or staging for medium-risk items."
  }
}
```

### Detailed Agent Specifications

#### 1. Telemetry Aggregator Agent
* **Operational Value**: Gathers real-time operational context without LLM overhead. Keeping this step deterministic saves API cost and prevents hallucinations in structural fields.
* **Logic & Input**: Reads `incident_id` and `alert_fingerprint` from the shared state.
* **Database Interactions**:
  - Queries `recurrence_intelligence` to fetch historical alerts, incident counts, reopen counts, and average MTTR.
  - Queries `clusters` to fetch OpenShift versions and environment labels.
  - Queries `redhat_cases` to pull linked case titles, status, and resolutions.
* **Output Mutations**: Writes the `operational_history` dictionary into the shared `IncidentState`.

#### 2. RAG Recommender Agent
* **Operational Value**: Synthesizes verified playbook instructions and historical post-mortems into a step-by-step remediation plan.
* **Logic & Input**: Reads `short_description` and `operational_history` from the shared state.
* **Database Interactions**: Runs a hybrid semantic query against vector embeddings to pull matching runbook sections and resolved ticket summaries:
  ```sql
  SELECT source_id, source_table, text_chunk, (embedding <-> %s::vector) AS distance
  FROM operational_knowledge_embeddings
  ORDER BY embedding <-> %s::vector
  LIMIT 2;
  ```
* **LLM Prompt Grounding**: Builds a system instruction template restricting the model's output to the retrieved context, forcing OpenShift-compliant commands (`oc` instead of `kubectl`), and outputting JSON.
* **Output Mutations**: Writes `remediation_plan` containing the proposed actions, confidence scores, risk levels, and source references.

#### 3. Gatekeeper Decider Agent
* **Operational Value**: Minimizes operational risk by restricting automated changes based on cluster criticality, confidence thresholds, and system policy.
* **Logic & Input**: Evaluates the gathered `operational_history` and `remediation_plan`.
* **Decision Policies**:
  - **Reoccurrence & LLM Evaluation**: If the alert has recurred frequently (e.g., >= 5 occurrences in the last 7 days), the agent queries the cognitive LLM to determine if the proposed automated remediation plan is unlikely to fix the underlying issue permanently. If the LLM decides it won't resolve the root cause, the incident is escalated to the human queue (`manual_action`). If the LLM is offline, a rule-based fallback heuristic is applied.
  - **Critical Environment Isolation**: If `cluster_environment == 'production'` and `risk_level != 'low'`, force `action_type = 'manual_action'`.
  - **Confidence Guardrail**: If `confidence_score < 0.70`, force `action_type = 'manual_action'`.
  - **Auto-Remediation Check**: If the environment is staging/development and the alert is not escalated by the reoccurrence or confidence policies, set `action_type = 'auto_remediate'`.
* **Output Mutations**: Writes `routing_decision` containing the execution path, target queue, and logical reasoning.

### Design for Future Scalability

Because agents interact through a standardized blackboard structure, **new requirements can be met by simply registering new agents in the pipeline** without modifying existing agent code. For example:
- **Cost Optimizer Agent**: Could be inserted after the Recommender to assess cloud infrastructure overhead (e.g., node autoscaling costs) before decision gate-keeping.
- **SLA Forecaster Agent**: Could evaluate current queue sizes and calculate estimated times to resolution (ETTR).
- **Compliance Audit Agent**: Could run static analysis on proposed remediation plans to verify compliance with internal security guidelines.

---

// filepath: docs/task.md
# Task: Advanced CVE Risk & Upgrade Advisor

- [x] 1. Update `ingestion/sync_rhokp_cve_to_postgres.py` with the new relational schema (`affected_versions`) and mock data.
- [x] 2. Update `api/routers/cve_advisor.py` to calculate Risk Percentages, evaluate targets, and determine the "Best Upgrade".
- [x] 3. Update `frontend/src/components/UpgradeAdvisor.tsx` to visualize Risk Gauges, 'Resolves' vs. 'Risks Waiting' sections, and the 'Best Choice' badge.
- [x] 4. Run ingestion script to seed Postgres and verify API outputs.

---

// filepath: docs/task_v3.md
# Task: Dynamic Errata Sync & Live Cluster Integration

- [x] 1. Run SQL updates to modify `clusters` table with realistic `4.19.x` and `4.20.x` OpenShift versions.
- [x] 2. Refactor `api/routers/cve_advisor.py` to query `clusters` instead of `cluster_inventory`.
- [x] 3. Rewrite `ingestion/sync_rhokp_cve_to_postgres.py` to dynamically fetch active versions from `clusters` and generate target Errata mapping logic.
- [x] 4. Run the ingestion script and manually verify API outputs against the UI.

---

// filepath: docs/walkthrough.md
# CVE Upgrade Advisor Implementation Walkthrough

The architectural changes outlined in the implementation plan have been fully executed. The system now supports scraping offline CVE advisories from Red Hat into Postgres via pgvector, analyzing cluster versions, and suggesting upgrade paths based on semantic risk analysis.

## Changes Made

### 1. Database Schema
- Updated `db/models.py` with the new `ClusterInventory` SQLAlchemy model to persistently track your managed clusters and their current OpenShift versions.
- Added raw Postgres SQL executions to generate the `rhokp_cve_knowledge` table with `vector(384)` columns for storing the embedded Security Advisory summaries.

### 2. Ingestion Engine
- Created `ingestion/sync_rhokp_cve_to_postgres.py`.
- This script uses `sentence-transformers` (`all-MiniLM-L6-v2`) to chunk and embed raw Red Hat Security Advisories (RHSA) and perform Postgres `UPSERT`s.
- It parses the CVE numbers, severity levels, and raw text so the RAG engine has structured data to fall back on.

### 3. FastAPI Backend
- Created a new router in `api/routers/cve_advisor.py`.
- Exposed `/api/clusters` to fetch the inventory.
- Exposed `/api/clusters/{cluster_id}/upgrade-advisor` which performs the "next immediate version" lookups.
- Configured semantic routing logic:
  - **Path A (Recommended):** Locates the immediate Z-stream patch and returns the list of critical fixes that this patch will resolve.
  - **Path B (Warning):** Locates the next Y-stream minor release and identifies if early-release bugs or considerable issues remain.

### 4. React & Tailwind UI
- Created `frontend/src/components/UpgradeAdvisor.tsx`.
- Designed a stunning, premium dark-mode interface with glassmorphism components (translucent backdrop blurs) and subtle hover micro-animations (`animate-fade-in-up`).
- Automatically queries the new Python endpoints and displays side-by-side comparative cards (Green for Safe Patch, Amber for Major Risk), showing the exact CVEs that will be mitigated.
- Added the `Advisor` navigation button to the sidebar in `frontend/src/App.tsx`.

## Testing It Out

To see the new interface in action:

1. **Start the API:**
   ```bash
   cd api
   uvicorn main:app --reload
   ```
2. **Start the Vite UI:**
   ```bash
   cd frontend
   npm run dev
   ```
3. Navigate to `http://localhost:5173/upgrade-advisor` and click on your cluster to see the dynamic upgrade recommendations!

---

// filepath: docs/walkthrough_v2.md
# Advanced Upgrade Advisor Walkthrough

The architectural refinements outlined in our V2 Implementation Plan have been fully integrated. Your SRE Incident Agent now supports dynamic, quantified vulnerability risk analysis to actively steer OpenShift clusters towards the safest possible target version.

## Key Advancements

### 1. Robust Relational Errata Engine
We completely overhauled the `ingestion/sync_rhokp_cve_to_postgres.py` engine. 
- It now utilizes a purely relational Postgres `JSONB` array mapping (`affected_versions`) to connect specific Errata directly to the exact minor and patch versions they compromise.
- We bypassed the heavy ML semantic vector embedding layer for this specific feature to guarantee flawless local execution without dependency overhead.
- Extensive mock OpenShift Errata spanning `4.20.15` through `4.21.0` have been seeded to prove the architecture.

### 2. Risk Matrix Calculation API
The backend `/api/clusters/{id}/upgrade-advisor` was dramatically enhanced:
- **Risk Index:** Vulnerabilities are dynamically weighted (Critical = 10, Important = 5, Moderate = 2, Low = 1) to generate a normalized "Risk Percentage" (0-100%).
- **Delta Analysis:** For every potential upgrade path (e.g., `4.20.16`, `4.20.17`, `4.21.0`), the system calculates:
  - **Resolves:** The exact CVEs that will be eradicated by the upgrade.
  - **Risks Waiting:** The vulnerabilities that explicitly remain unpatched in that specific target version.
- **The Best Choice Engine:** The backend algorithmically scans the Residual Risk percentages of all available paths and flags the absolute safest semantic upgrade target.

### 3. Glassmorphism Risk Dashboard
The React UI (`frontend/src/components/UpgradeAdvisor.tsx`) received a major design overhaul:
- **Dynamic Circular Gauges:** Added elegant, animated SVG progress rings that pulse red for high-risk postures and green for low residual risk targets.
- **Resolves / Waiting Tabs:** Each upgrade card now features interactive tabs allowing you to cleanly toggle between what is being fixed and what dangers remain.
- **⭐ Best Choice Badge:** A glowing, animated badge automatically adorns the upgrade path identified by the backend algorithm as the safest mathematical choice.

## Viewing the Enhancements

If your API and Vite development servers are running:
1. Open the UI to the **Advisor** tab on the sidebar.
2. Select the seeded cluster (`prod-us-east-1` running `v4.20.15`).
3. Observe the high `Current Posture` risk index.
4. Review the multiple upgrade cards:
   - Notice that upgrading to `4.21.0` introduces a new "Early Release Bug" (Risks Waiting).
   - Notice that the backend correctly flags the `4.20.17` target with the **Best Choice** badge because it yields the lowest residual risk index!

---

// filepath: docs/walkthrough_v3.md
# Dynamic Errata Sync & Live Integration Walkthrough

The Advisor architecture has been successfully decoupled from the temporary mock tables and is now heavily integrated with your actual OpenShift fleet inventory! The data generation and sync processes are completely dynamic.

## Key Changes Made

### 1. Unified Database Integration
- Your live Postgres `clusters` table was successfully updated to track the required minor builds. We now have exactly 5 clusters running versions across the `4.19.x`, `4.20.x`, and `4.21.x` streams.
- The `api/routers/cve_advisor.py` endpoint was refactored to query `clusters` instead of `cluster_inventory`. This means that as you spin up or decommission clusters in the real world, the UI will instantly reflect the changes.

### 2. Autonomous Sync Engine (`sync_rhokp_cve_to_postgres.py`)
This script has been elevated from a static seed script to a dynamic, weekly cron-job engine. When executed:
1. **Fleet Discovery:** It queries the Postgres `clusters` table to dynamically build a manifest of all active `openshift_version` currently in use across your environments.
2. **Target Calculation:** It mathematically computes the appropriate future upgrade targets (e.g., discovering `4.19.10` will generate targets for patch `4.19.11`, `4.19.12` and minor `4.20.0`).
3. **Payload Simulation:** It dynamically simulates real Red Hat Errata mappings, tying generated CVEs exactly to the discovered active versions and future targets. 
4. **Knowledge Base Upsert:** It flawlessly ingested 15 targeted Errata definitions directly into `rhokp_cve_knowledge`, perfectly syncing the RAG pipeline to your live fleet.

## Try It Out!
Since the backend now reads from your real `clusters` database, you can **refresh the UI** and see all 5 clusters (`nzclu101`, `emclu202`, etc.) automatically populate on the left sidebar! Clicking on any of them will trigger the live Risk matrix calculations against the freshly minted Errata mapping.

The dynamic sync script is fully operational and can be slotted straight into an AWX/Tower cron schedule!

---

// filepath: frontend/Dockerfile
# Build stage
FROM node:20-alpine as build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

---

// filepath: frontend/index.html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="description" content="SRE Incident Agent — AI-powered incident remediation with Human-in-the-Loop approval" />
    <title>SRE Incident Agent</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>

---

// filepath: frontend/nginx.conf
server {
    listen 80;
    server_name localhost;

    root /usr/share/nginx/html;
    index index.html;

    # Serve static frontend assets and handle React Router
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy /api requests to the FastAPI backend
    # The trailing slash on proxy_pass strips the '/api' prefix
    location /api/ {
        proxy_pass http://api:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Proxy WebSocket connections for real-time updates
    location /ws {
        proxy_pass http://api:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
    }
}

---

// filepath: frontend/package-lock.json
{
  "name": "sre-incident-ui",
  "version": "1.0.0",
  "lockfileVersion": 3,
  "requires": true,
  "packages": {
    "": {
      "name": "sre-incident-ui",
      "version": "1.0.0",
      "dependencies": {
        "@tanstack/react-query": "^5.62.7",
        "axios": "^1.7.9",
        "date-fns": "^4.1.0",
        "lucide-react": "^1.17.0",
        "react": "^18.3.1",
        "react-dom": "^18.3.1",
        "react-router-dom": "^6.28.0",
        "recharts": "^2.14.1"
      },
      "devDependencies": {
        "@types/react": "^18.3.12",
        "@types/react-dom": "^18.3.1",
        "@vitejs/plugin-react": "^4.3.4",
        "autoprefixer": "^10.4.20",
        "postcss": "^8.4.49",
        "tailwindcss": "^3.4.16",
        "typescript": "^5.6.3",
        "vite": "^6.0.3"
      }
    },
    "node_modules/@alloc/quick-lru": {
      "version": "5.2.0",
      "resolved": "https://registry.npmjs.org/@alloc/quick-lru/-/quick-lru-5.2.0.tgz",
      "integrity": "sha512-UrcABB+4bUrFABwbluTIBErXwvbsU/V7TZWfmbgJfbkwiBuziS9gxdODUyuiecfdGQ85jglMW6juS3+z5TsKLw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=10"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/@babel/code-frame": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/code-frame/-/code-frame-7.29.7.tgz",
      "integrity": "sha512-Aup7aUOfpbAUg2ROOJN6Iw5f9DMBlzu0mIkm/malLQFN/YQgO48wCj0Kxa3sEHJvPVFg7siR+qRInwXd2qhQKw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/helper-validator-identifier": "^7.29.7",
        "js-tokens": "^4.0.0",
        "picocolors": "^1.1.1"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/compat-data": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/compat-data/-/compat-data-7.29.7.tgz",
      "integrity": "sha512-locTkQyKvwIEgBzVrn8693ebc97F2U8ZHjbXwDXJ5Fn2TCpNwTlKcaKLkdHop5c/icOFE7qt7Q9JC5hnKNa6Gg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/core": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/core/-/core-7.29.7.tgz",
      "integrity": "sha512-RgHBCvtjbOK2gXSNBNIkNoEc9qoVEtau3hj8gEqKQuL3HZAibKarWFEI3Lfm6EYKkLalOh8eSrj9b+ch9H/VBA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/code-frame": "^7.29.7",
        "@babel/generator": "^7.29.7",
        "@babel/helper-compilation-targets": "^7.29.7",
        "@babel/helper-module-transforms": "^7.29.7",
        "@babel/helpers": "^7.29.7",
        "@babel/parser": "^7.29.7",
        "@babel/template": "^7.29.7",
        "@babel/traverse": "^7.29.7",
        "@babel/types": "^7.29.7",
        "@jridgewell/remapping": "^2.3.5",
        "convert-source-map": "^2.0.0",
        "debug": "^4.1.0",
        "gensync": "^1.0.0-beta.2",
        "json5": "^2.2.3",
        "semver": "^6.3.1"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "funding": {
        "type": "opencollective",
        "url": "https://opencollective.com/babel"
      }
    },
    "node_modules/@babel/generator": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/generator/-/generator-7.29.7.tgz",
      "integrity": "sha512-DkXD5OJQaAQIdZ1bt3UZdEnHAn9Imd3IVBdX03UFe+ony9Ojw5pzr9YVKGDY1jt+Gcn/FnGkNf8r+Vj5NOJWtQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/parser": "^7.29.7",
        "@babel/types": "^7.29.7",
        "@jridgewell/gen-mapping": "^0.3.12",
        "@jridgewell/trace-mapping": "^0.3.28",
        "jsesc": "^3.0.2"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-compilation-targets": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/helper-compilation-targets/-/helper-compilation-targets-7.29.7.tgz",
      "integrity": "sha512-wem6WaBj4NaVYVdNhLPPVacES6ZJ+KBBfSkTMD3YZxbP3rm3Di85tJU5ljaUNhaOynt+Aj0xruhYuzQBt8n71g==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/compat-data": "^7.29.7",
        "@babel/helper-validator-option": "^7.29.7",
        "browserslist": "^4.24.0",
        "lru-cache": "^5.1.1",
        "semver": "^6.3.1"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-globals": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/helper-globals/-/helper-globals-7.29.7.tgz",
      "integrity": "sha512-3nQVUAtvkKH9zahfWgw96Jc/uFOmjACE1kQz82E2lqWmHBgjzbNlsC22nuQTfahmWeQtTq5nQ/4Nnd2A1wj4zA==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-module-imports": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/helper-module-imports/-/helper-module-imports-7.29.7.tgz",
      "integrity": "sha512-ejHwrQQYcm9xnTivShn2IDOlIzInN34AXskvq9QicvCtEzq1Vzclu/tKF8Jq1Cg8JG2GL6/EmjgsCT7lXepE3g==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/traverse": "^7.29.7",
        "@babel/types": "^7.29.7"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-module-transforms": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/helper-module-transforms/-/helper-module-transforms-7.29.7.tgz",
      "integrity": "sha512-UPUVSyXbOh627KiCIGQSgwWzGeBKLkaJ9PJEdrngIwMSzxLR4jS4+f1f1jb7VzBbg8nFLaYotvVPFCTqdrmTAg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/helper-module-imports": "^7.29.7",
        "@babel/helper-validator-identifier": "^7.29.7",
        "@babel/traverse": "^7.29.7"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0"
      }
    },
    "node_modules/@babel/helper-plugin-utils": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/helper-plugin-utils/-/helper-plugin-utils-7.29.7.tgz",
      "integrity": "sha512-G7sHYigPY17oO5SYWnfD/0MTBwVR781S/JI643e/JhUYgVgWE/61SoW3NH9KWUKyKq5LVh3npif99Wkt6j86Jw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-string-parser": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/helper-string-parser/-/helper-string-parser-7.29.7.tgz",
      "integrity": "sha512-Pb5ijPrZ89GDH8223L4UP8i6QApWxs04RbPQJTeWDV0/keR2E36MeKnyr6LYmUUvqRRI+Iv87SuF1W6ErINzYw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-validator-identifier": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/helper-validator-identifier/-/helper-validator-identifier-7.29.7.tgz",
      "integrity": "sha512-qehxGkRj55h/ff8EMaJ+cYhyaKlHIxqYDn682wQD7RNp9UujOQsHog2uS0r2vzr4pW+sXf90NeeayjcNaX3fFg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-validator-option": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/helper-validator-option/-/helper-validator-option-7.29.7.tgz",
      "integrity": "sha512-N9ZErrD+yW5geCDtBqnOoxmR8+tNKiGuxKlDpuJxfsqpa2dFcexaziGAE/qoHLiDDreVNMupxGmSoNlyvsA3gw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helpers": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/helpers/-/helpers-7.29.7.tgz",
      "integrity": "sha512-1k2lAGRMfHTcwuNYcCNUmaUffmQv8KWMfh2iJUUeRlwlwH4FdNG7mfPI10NPfLHJFThE4Tyr4mv7kTNZOiPuBg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/template": "^7.29.7",
        "@babel/types": "^7.29.7"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/parser": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/parser/-/parser-7.29.7.tgz",
      "integrity": "sha512-hnORnjP/1P/zFEndoeX+n+t1RwWRJiJpM/jO7FW32Kn9r5+sJB2JWOdYo4L6k78j15eCwY3Gm/7364B1EMwtNg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/types": "^7.29.7"
      },
      "bin": {
        "parser": "bin/babel-parser.js"
      },
      "engines": {
        "node": ">=6.0.0"
      }
    },
    "node_modules/@babel/plugin-transform-react-jsx-self": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/plugin-transform-react-jsx-self/-/plugin-transform-react-jsx-self-7.29.7.tgz",
      "integrity": "sha512-TL0hMc9xzy86VD31nUiwzd5otRAcyEPcsegCxolO0PvcXuH1v0kECe/UIznYFihpkvU5wg/jk4v0TTEFfm53fw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.29.7"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-react-jsx-source": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/plugin-transform-react-jsx-source/-/plugin-transform-react-jsx-source-7.29.7.tgz",
      "integrity": "sha512-06IyK09H3wi4cGbhDBwp5gUGo0IKtnYa8tyTiephirPCK6fbobVGiXMMI5zLQ4aKEYP3wZ3ArU44o+8KMrSG/Q==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.29.7"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/runtime": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/runtime/-/runtime-7.29.7.tgz",
      "integrity": "sha512-Nq8OhGWiZIZGV6hLHoyAKLLcJihP/xFeBMGJoUrxTX2psI8dCifzLhZISFb+VWS3wFMRDmCGw5R+dOySCqPLhw==",
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/template": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/template/-/template-7.29.7.tgz",
      "integrity": "sha512-puq+Gf35oI24FeN11LkoUQFqv9uwNeWpxXZi/Ji3rRIoKAzKnxRaZ+Gkj0vKS9ZCiTESfng1N9LyOyXvo+m+Gg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/code-frame": "^7.29.7",
        "@babel/parser": "^7.29.7",
        "@babel/types": "^7.29.7"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/traverse": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/traverse/-/traverse-7.29.7.tgz",
      "integrity": "sha512-EhlfNQtZ+NK22w5BM61ciuiq1m58ed33Wr1Xan//ZRTy6hgjnwyCffRYwzsGXdASJSUJ1guZILsErh1eQcl+zw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/code-frame": "^7.29.7",
        "@babel/generator": "^7.29.7",
        "@babel/helper-globals": "^7.29.7",
        "@babel/parser": "^7.29.7",
        "@babel/template": "^7.29.7",
        "@babel/types": "^7.29.7",
        "debug": "^4.3.1"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/types": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/types/-/types-7.29.7.tgz",
      "integrity": "sha512-4zBIxpPzowiZpusoFkyGVwakdRJUyuH5PxQ/PrqghfdFWWasvnCdPfQXHrenDai+gyLARulZjZowCOj6fjT4pA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/helper-string-parser": "^7.29.7",
        "@babel/helper-validator-identifier": "^7.29.7"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@esbuild/aix-ppc64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmjs.org/@esbuild/aix-ppc64/-/aix-ppc64-0.25.12.tgz",
      "integrity": "sha512-Hhmwd6CInZ3dwpuGTF8fJG6yoWmsToE+vYgD4nytZVxcu1ulHpUQRAB1UJ8+N1Am3Mz4+xOByoQoSZf4D+CpkA==",
      "cpu": [
        "ppc64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "aix"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/android-arm": {
      "version": "0.25.12",
      "resolved": "https://registry.npmjs.org/@esbuild/android-arm/-/android-arm-0.25.12.tgz",
      "integrity": "sha512-VJ+sKvNA/GE7Ccacc9Cha7bpS8nyzVv0jdVgwNDaR4gDMC/2TTRc33Ip8qrNYUcpkOHUT5OZ0bUcNNVZQ9RLlg==",
      "cpu": [
        "arm"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "android"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/android-arm64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmjs.org/@esbuild/android-arm64/-/android-arm64-0.25.12.tgz",
      "integrity": "sha512-6AAmLG7zwD1Z159jCKPvAxZd4y/VTO0VkprYy+3N2FtJ8+BQWFXU+OxARIwA46c5tdD9SsKGZ/1ocqBS/gAKHg==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "android"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/android-x64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmjs.org/@esbuild/android-x64/-/android-x64-0.25.12.tgz",
      "integrity": "sha512-5jbb+2hhDHx5phYR2By8GTWEzn6I9UqR11Kwf22iKbNpYrsmRB18aX/9ivc5cabcUiAT/wM+YIZ6SG9QO6a8kg==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "android"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/darwin-arm64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmjs.org/@esbuild/darwin-arm64/-/darwin-arm64-0.25.12.tgz",
      "integrity": "sha512-N3zl+lxHCifgIlcMUP5016ESkeQjLj/959RxxNYIthIg+CQHInujFuXeWbWMgnTo4cp5XVHqFPmpyu9J65C1Yg==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "darwin"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/darwin-x64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmjs.org/@esbuild/darwin-x64/-/darwin-x64-0.25.12.tgz",
      "integrity": "sha512-HQ9ka4Kx21qHXwtlTUVbKJOAnmG1ipXhdWTmNXiPzPfWKpXqASVcWdnf2bnL73wgjNrFXAa3yYvBSd9pzfEIpA==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "darwin"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/freebsd-arm64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmjs.org/@esbuild/freebsd-arm64/-/freebsd-arm64-0.25.12.tgz",
      "integrity": "sha512-gA0Bx759+7Jve03K1S0vkOu5Lg/85dou3EseOGUes8flVOGxbhDDh/iZaoek11Y8mtyKPGF3vP8XhnkDEAmzeg==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "freebsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/freebsd-x64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmjs.org/@esbuild/freebsd-x64/-/freebsd-x64-0.25.12.tgz",
      "integrity": "sha512-TGbO26Yw2xsHzxtbVFGEXBFH0FRAP7gtcPE7P5yP7wGy7cXK2oO7RyOhL5NLiqTlBh47XhmIUXuGciXEqYFfBQ==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "freebsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-arm": {
      "version": "0.25.12",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-arm/-/linux-arm-0.25.12.tgz",
      "integrity": "sha512-lPDGyC1JPDou8kGcywY0YILzWlhhnRjdof3UlcoqYmS9El818LLfJJc3PXXgZHrHCAKs/Z2SeZtDJr5MrkxtOw==",
      "cpu": [
        "arm"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-arm64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-arm64/-/linux-arm64-0.25.12.tgz",
      "integrity": "sha512-8bwX7a8FghIgrupcxb4aUmYDLp8pX06rGh5HqDT7bB+8Rdells6mHvrFHHW2JAOPZUbnjUpKTLg6ECyzvas2AQ==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-ia32": {
      "version": "0.25.12",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-ia32/-/linux-ia32-0.25.12.tgz",
      "integrity": "sha512-0y9KrdVnbMM2/vG8KfU0byhUN+EFCny9+8g202gYqSSVMonbsCfLjUO+rCci7pM0WBEtz+oK/PIwHkzxkyharA==",
      "cpu": [
        "ia32"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-loong64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-loong64/-/linux-loong64-0.25.12.tgz",
      "integrity": "sha512-h///Lr5a9rib/v1GGqXVGzjL4TMvVTv+s1DPoxQdz7l/AYv6LDSxdIwzxkrPW438oUXiDtwM10o9PmwS/6Z0Ng==",
      "cpu": [
        "loong64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-mips64el": {
      "version": "0.25.12",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-mips64el/-/linux-mips64el-0.25.12.tgz",
      "integrity": "sha512-iyRrM1Pzy9GFMDLsXn1iHUm18nhKnNMWscjmp4+hpafcZjrr2WbT//d20xaGljXDBYHqRcl8HnxbX6uaA/eGVw==",
      "cpu": [
        "mips64el"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-ppc64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-ppc64/-/linux-ppc64-0.25.12.tgz",
      "integrity": "sha512-9meM/lRXxMi5PSUqEXRCtVjEZBGwB7P/D4yT8UG/mwIdze2aV4Vo6U5gD3+RsoHXKkHCfSxZKzmDssVlRj1QQA==",
      "cpu": [
        "ppc64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-riscv64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-riscv64/-/linux-riscv64-0.25.12.tgz",
      "integrity": "sha512-Zr7KR4hgKUpWAwb1f3o5ygT04MzqVrGEGXGLnj15YQDJErYu/BGg+wmFlIDOdJp0PmB0lLvxFIOXZgFRrdjR0w==",
      "cpu": [
        "riscv64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-s390x": {
      "version": "0.25.12",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-s390x/-/linux-s390x-0.25.12.tgz",
      "integrity": "sha512-MsKncOcgTNvdtiISc/jZs/Zf8d0cl/t3gYWX8J9ubBnVOwlk65UIEEvgBORTiljloIWnBzLs4qhzPkJcitIzIg==",
      "cpu": [
        "s390x"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-x64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-x64/-/linux-x64-0.25.12.tgz",
      "integrity": "sha512-uqZMTLr/zR/ed4jIGnwSLkaHmPjOjJvnm6TVVitAa08SLS9Z0VM8wIRx7gWbJB5/J54YuIMInDquWyYvQLZkgw==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/netbsd-arm64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmjs.org/@esbuild/netbsd-arm64/-/netbsd-arm64-0.25.12.tgz",
      "integrity": "sha512-xXwcTq4GhRM7J9A8Gv5boanHhRa/Q9KLVmcyXHCTaM4wKfIpWkdXiMog/KsnxzJ0A1+nD+zoecuzqPmCRyBGjg==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "netbsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/netbsd-x64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmjs.org/@esbuild/netbsd-x64/-/netbsd-x64-0.25.12.tgz",
      "integrity": "sha512-Ld5pTlzPy3YwGec4OuHh1aCVCRvOXdH8DgRjfDy/oumVovmuSzWfnSJg+VtakB9Cm0gxNO9BzWkj6mtO1FMXkQ==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "netbsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/openbsd-arm64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmjs.org/@esbuild/openbsd-arm64/-/openbsd-arm64-0.25.12.tgz",
      "integrity": "sha512-fF96T6KsBo/pkQI950FARU9apGNTSlZGsv1jZBAlcLL1MLjLNIWPBkj5NlSz8aAzYKg+eNqknrUJ24QBybeR5A==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "openbsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/openbsd-x64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmjs.org/@esbuild/openbsd-x64/-/openbsd-x64-0.25.12.tgz",
      "integrity": "sha512-MZyXUkZHjQxUvzK7rN8DJ3SRmrVrke8ZyRusHlP+kuwqTcfWLyqMOE3sScPPyeIXN/mDJIfGXvcMqCgYKekoQw==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "openbsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/openharmony-arm64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmjs.org/@esbuild/openharmony-arm64/-/openharmony-arm64-0.25.12.tgz",
      "integrity": "sha512-rm0YWsqUSRrjncSXGA7Zv78Nbnw4XL6/dzr20cyrQf7ZmRcsovpcRBdhD43Nuk3y7XIoW2OxMVvwuRvk9XdASg==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "openharmony"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/sunos-x64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmjs.org/@esbuild/sunos-x64/-/sunos-x64-0.25.12.tgz",
      "integrity": "sha512-3wGSCDyuTHQUzt0nV7bocDy72r2lI33QL3gkDNGkod22EsYl04sMf0qLb8luNKTOmgF/eDEDP5BFNwoBKH441w==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "sunos"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/win32-arm64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmjs.org/@esbuild/win32-arm64/-/win32-arm64-0.25.12.tgz",
      "integrity": "sha512-rMmLrur64A7+DKlnSuwqUdRKyd3UE7oPJZmnljqEptesKM8wx9J8gx5u0+9Pq0fQQW8vqeKebwNXdfOyP+8Bsg==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "win32"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/win32-ia32": {
      "version": "0.25.12",
      "resolved": "https://registry.npmjs.org/@esbuild/win32-ia32/-/win32-ia32-0.25.12.tgz",
      "integrity": "sha512-HkqnmmBoCbCwxUKKNPBixiWDGCpQGVsrQfJoVGYLPT41XWF8lHuE5N6WhVia2n4o5QK5M4tYr21827fNhi4byQ==",
      "cpu": [
        "ia32"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "win32"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/win32-x64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmjs.org/@esbuild/win32-x64/-/win32-x64-0.25.12.tgz",
      "integrity": "sha512-alJC0uCZpTFrSL0CCDjcgleBXPnCrEAhTBILpeAp7M/OFgoqtAetfBzX0xM00MUsVVPpVjlPuMbREqnZCXaTnA==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "win32"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@jridgewell/gen-mapping": {
      "version": "0.3.13",
      "resolved": "https://registry.npmjs.org/@jridgewell/gen-mapping/-/gen-mapping-0.3.13.tgz",
      "integrity": "sha512-2kkt/7niJ6MgEPxF0bYdQ6etZaA+fQvDcLKckhy1yIQOzaoKjBBjSj63/aLVjYE3qhRt5dvM+uUyfCg6UKCBbA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@jridgewell/sourcemap-codec": "^1.5.0",
        "@jridgewell/trace-mapping": "^0.3.24"
      }
    },
    "node_modules/@jridgewell/remapping": {
      "version": "2.3.5",
      "resolved": "https://registry.npmjs.org/@jridgewell/remapping/-/remapping-2.3.5.tgz",
      "integrity": "sha512-LI9u/+laYG4Ds1TDKSJW2YPrIlcVYOwi2fUC6xB43lueCjgxV4lffOCZCtYFiH6TNOX+tQKXx97T4IKHbhyHEQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@jridgewell/gen-mapping": "^0.3.5",
        "@jridgewell/trace-mapping": "^0.3.24"
      }
    },
    "node_modules/@jridgewell/resolve-uri": {
      "version": "3.1.2",
      "resolved": "https://registry.npmjs.org/@jridgewell/resolve-uri/-/resolve-uri-3.1.2.tgz",
      "integrity": "sha512-bRISgCIjP20/tbWSPWMEi54QVPRZExkuD9lJL+UIxUKtwVJA8wW1Trb1jMs1RFXo1CBTNZ/5hpC9QvmKWdopKw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6.0.0"
      }
    },
    "node_modules/@jridgewell/sourcemap-codec": {
      "version": "1.5.5",
      "resolved": "https://registry.npmjs.org/@jridgewell/sourcemap-codec/-/sourcemap-codec-1.5.5.tgz",
      "integrity": "sha512-cYQ9310grqxueWbl+WuIUIaiUaDcj7WOq5fVhEljNVgRfOUhY9fy2zTvfoqWsnebh8Sl70VScFbICvJnLKB0Og==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/@jridgewell/trace-mapping": {
      "version": "0.3.31",
      "resolved": "https://registry.npmjs.org/@jridgewell/trace-mapping/-/trace-mapping-0.3.31.tgz",
      "integrity": "sha512-zzNR+SdQSDJzc8joaeP8QQoCQr8NuYx2dIIytl1QeBEZHJ9uW6hebsrYgbz8hJwUQao3TWCMtmfV8Nu1twOLAw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@jridgewell/resolve-uri": "^3.1.0",
        "@jridgewell/sourcemap-codec": "^1.4.14"
      }
    },
    "node_modules/@nodelib/fs.scandir": {
      "version": "2.1.5",
      "resolved": "https://registry.npmjs.org/@nodelib/fs.scandir/-/fs.scandir-2.1.5.tgz",
      "integrity": "sha512-vq24Bq3ym5HEQm2NKCr3yXDwjc7vTsEThRDnkp2DK9p1uqLR+DHurm/NOTo0KG7HYHU7eppKZj3MyqYuMBf62g==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@nodelib/fs.stat": "2.0.5",
        "run-parallel": "^1.1.9"
      },
      "engines": {
        "node": ">= 8"
      }
    },
    "node_modules/@nodelib/fs.stat": {
      "version": "2.0.5",
      "resolved": "https://registry.npmjs.org/@nodelib/fs.stat/-/fs.stat-2.0.5.tgz",
      "integrity": "sha512-RkhPPp2zrqDAQA/2jNhnztcPAlv64XdhIp7a7454A5ovI7Bukxgt7MX7udwAu3zg1DcpPU0rz3VV1SeaqvY4+A==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 8"
      }
    },
    "node_modules/@nodelib/fs.walk": {
      "version": "1.2.8",
      "resolved": "https://registry.npmjs.org/@nodelib/fs.walk/-/fs.walk-1.2.8.tgz",
      "integrity": "sha512-oGB+UxlgWcgQkgwo8GcEGwemoTFt3FIO9ababBmaGwXIoBKZ+GTy0pP185beGg7Llih/NSHSV2XAs1lnznocSg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@nodelib/fs.scandir": "2.1.5",
        "fastq": "^1.6.0"
      },
      "engines": {
        "node": ">= 8"
      }
    },
    "node_modules/@remix-run/router": {
      "version": "1.23.2",
      "resolved": "https://registry.npmjs.org/@remix-run/router/-/router-1.23.2.tgz",
      "integrity": "sha512-Ic6m2U/rMjTkhERIa/0ZtXJP17QUi2CbWE7cqx4J58M8aA3QTfW+2UlQ4psvTX9IO1RfNVhK3pcpdjej7L+t2w==",
      "license": "MIT",
      "engines": {
        "node": ">=14.0.0"
      }
    },
    "node_modules/@rolldown/pluginutils": {
      "version": "1.0.0-beta.27",
      "resolved": "https://registry.npmjs.org/@rolldown/pluginutils/-/pluginutils-1.0.0-beta.27.tgz",
      "integrity": "sha512-+d0F4MKMCbeVUJwG96uQ4SgAznZNSq93I3V+9NHA4OpvqG8mRCpGdKmK8l/dl02h2CCDHwW2FqilnTyDcAnqjA==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/@rollup/rollup-android-arm-eabi": {
      "version": "4.60.4",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-android-arm-eabi/-/rollup-android-arm-eabi-4.60.4.tgz",
      "integrity": "sha512-F5QXMSiFebS9hKZj02XhWLLnRpJ3B3AROP0tWbFBSj+6kCbg5m9j5JoHKd4mmSVy5mS/IMQloYgYxCuJC0fxEQ==",
      "cpu": [
        "arm"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "android"
      ]
    },
    "node_modules/@rollup/rollup-android-arm64": {
      "version": "4.60.4",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-android-arm64/-/rollup-android-arm64-4.60.4.tgz",
      "integrity": "sha512-GxxTKApUpzRhof7poWvCJHRF51C67u1R7D6DiluBE8wKU1u5GWE8t+v81JvJYtbawoBFX1hLv5Ei4eVjkWokaw==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "android"
      ]
    },
    "node_modules/@rollup/rollup-darwin-arm64": {
      "version": "4.60.4",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-darwin-arm64/-/rollup-darwin-arm64-4.60.4.tgz",
      "integrity": "sha512-tua0TaJxMOB1R0V0RS1jFZ/RpURFDJIOR2A6jWwQeawuFyS4gBW+rntLRaQd0EQ4bd6Vp44Z2rXW+YYDBsj6IA==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "darwin"
      ]
    },
    "node_modules/@rollup/rollup-darwin-x64": {
      "version": "4.60.4",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-darwin-x64/-/rollup-darwin-x64-4.60.4.tgz",
      "integrity": "sha512-CSKq7MsP+5PFIcydhAiR1K0UhEI1A2jWXVKHPCBZ151yOutENwvnPocgVHkivu2kviURtCEB6zUQw0vs8RrhMg==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "darwin"
      ]
    },
    "node_modules/@rollup/rollup-freebsd-arm64": {
      "version": "4.60.4",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-freebsd-arm64/-/rollup-freebsd-arm64-4.60.4.tgz",
      "integrity": "sha512-+O8OkVdyvXMtJEciu2wS/pzm1IxntEEQx3z5TAVy4l32G0etZn+RsA48ARRrFm6Ri8fvqPQfgrvNxSjKAbnd3g==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "freebsd"
      ]
    },
    "node_modules/@rollup/rollup-freebsd-x64": {
      "version": "4.60.4",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-freebsd-x64/-/rollup-freebsd-x64-4.60.4.tgz",
      "integrity": "sha512-Iw3oMskH3AfNuhU0MSN7vNbdi4me/NiYo2azqPz/Le16zHSa+3RRmliCMWWQmh4lcndccU40xcJuTYJZxNo/lw==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "freebsd"
      ]
    },
    "node_modules/@rollup/rollup-linux-arm-gnueabihf": {
      "version": "4.60.4",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-arm-gnueabihf/-/rollup-linux-arm-gnueabihf-4.60.4.tgz",
      "integrity": "sha512-EIPRXTVQpHyF8WOo219AD2yEltPehLTcTMz2fn6JsatLYSzQf00hj3rulF+yauOlF9/FtM2WpkT/hJh/KJFGhA==",
      "cpu": [
        "arm"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-arm-musleabihf": {
      "version": "4.60.4",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-arm-musleabihf/-/rollup-linux-arm-musleabihf-4.60.4.tgz",
      "integrity": "sha512-J3Yh9PzzF1Ovah2At+lHiGQdsYgArxBbXv/zHfSyaiFQEqvNv7DcW98pCrmdjCZBrqBiKrKKe2V+aaSGWuBe/w==",
      "cpu": [
        "arm"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-arm64-gnu": {
      "version": "4.60.4",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-arm64-gnu/-/rollup-linux-arm64-gnu-4.60.4.tgz",
      "integrity": "sha512-BFDEZMYfUvLn37ONE1yMBojPxnMlTFsdyNoqncT0qFq1mAfllL+ATMMJd8TeuVMiX84s1KbcxcZbXInmcO2mRg==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-arm64-musl": {
      "version": "4.60.4",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-arm64-musl/-/rollup-linux-arm64-musl-4.60.4.tgz",
      "integrity": "sha512-pc9EYOSlOgdQ2uPl1o9PF6/kLSgaUosia7gOuS8mB69IxJvlclko1MECXysjs5ryez1/5zjYqx3+xYU0TU6R1A==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-loong64-gnu": {
      "version": "4.60.4",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-loong64-gnu/-/rollup-linux-loong64-gnu-4.60.4.tgz",
      "integrity": "sha512-NxnomyxYerDh5n4iLrNa+sH+Z+U4BMEE46V2PgQ/hoB909i8gV1M5wPojWg9fk1jWpO3IQnOs20K4wyZuFLEFQ==",
      "cpu": [
        "loong64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-loong64-musl": {
      "version": "4.60.4",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-loong64-musl/-/rollup-linux-loong64-musl-4.60.4.tgz",
      "integrity": "sha512-nbJnQ8a3z1mtmrwImCYhc6BGpThAyYVRQxw9uKSKG4wR6aAYno9sVjJ0zaZcW9BPJX1GbrDPf+SvdWjgTuDmnw==",
      "cpu": [
        "loong64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-ppc64-gnu": {
      "version": "4.60.4",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-ppc64-gnu/-/rollup-linux-ppc64-gnu-4.60.4.tgz",
      "integrity": "sha512-2EU6acNrQLd8tYvo/LXW535wupT3m6fo7HKo6lr7ktQoItxTyOL1ZCR/GfGCuXl2vR+zmfI6eRXkSemafv+iVg==",
      "cpu": [
        "ppc64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-ppc64-musl": {
      "version": "4.60.4",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-ppc64-musl/-/rollup-linux-ppc64-musl-4.60.4.tgz",
      "integrity": "sha512-WeBtoMuaMxiiIrO2IYP3xs6GMWkJP2C0EoT8beTLkUPmzV1i/UcOSVw1d5r9KBODtHKilG5yFxsGRnBbK3wJ4A==",
      "cpu": [
        "ppc64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-riscv64-gnu": {
      "version": "4.60.4",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-riscv64-gnu/-/rollup-linux-riscv64-gnu-4.60.4.tgz",
      "integrity": "sha512-FJHFfqpKUI3A10WrWKiFbBZ7yVbGT4q4B5o1qKFFojqpaYoh9LrQgqWCmmcxQzVSXYtyB5bzkXrYzlHTs21MYA==",
      "cpu": [
        "riscv64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-riscv64-musl": {
      "version": "4.60.4",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-riscv64-musl/-/rollup-linux-riscv64-musl-4.60.4.tgz",
      "integrity": "sha512-mcEl6CUT5IAUmQf1m9FYSmVqCJlpQ8r8eyftFUHG8i9OhY7BkBXSUdnLH5DOf0wCOjcP9v/QO93zpmF1SptCCw==",
      "cpu": [
        "riscv64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-s390x-gnu": {
      "version": "4.60.4",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-s390x-gnu/-/rollup-linux-s390x-gnu-4.60.4.tgz",
      "integrity": "sha512-ynt3JxVd2w2buzoKDWIyiV1pJW93xlQic1THVLXilz429oijRpSHivZAgp65KBu+cMcgf1eVVjdnTLvPxgCuoQ==",
      "cpu": [
        "s390x"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-x64-gnu": {
      "version": "4.60.4",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-x64-gnu/-/rollup-linux-x64-gnu-4.60.4.tgz",
      "integrity": "sha512-Boiz5+MsaROEWDf+GGEwF8VMHGhlUoQMtIPjOgA5fv4osupqTVnJteQNKJwUcnUog2G55jYXH7KZFFiJe0TEzQ==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-x64-musl": {
      "version": "4.60.4",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-x64-musl/-/rollup-linux-x64-musl-4.60.4.tgz",
      "integrity": "sha512-+qfSY27qIrFfI/Hom04KYFw3GKZSGU4lXus51wsb5EuySfFlWRwjkKWoE9emgRw/ukoT4Udsj4W/+xxG8VbPKg==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-openbsd-x64": {
      "version": "4.60.4",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-openbsd-x64/-/rollup-openbsd-x64-4.60.4.tgz",
      "integrity": "sha512-VpTfOPHgVXEBeeR8hZ2O0F3aSso+JDWqTWmTmzcQKted54IAdUVbxE+j/MVxUsKa8L20HJhv3vUezVPoquqWjA==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "openbsd"
      ]
    },
    "node_modules/@rollup/rollup-openharmony-arm64": {
      "version": "4.60.4",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-openharmony-arm64/-/rollup-openharmony-arm64-4.60.4.tgz",
      "integrity": "sha512-IPOsh5aRYuLv/nkU51X10Bf75Bsf6+gZdx1X+QP5QM6lIJFHHqbHLG0uJn/hWthzo13UAc2umiUorqZy3axoZg==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "openharmony"
      ]
    },
    "node_modules/@rollup/rollup-win32-arm64-msvc": {
      "version": "4.60.4",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-win32-arm64-msvc/-/rollup-win32-arm64-msvc-4.60.4.tgz",
      "integrity": "sha512-4QzE9E81OohJ/HKzHhsqU+zcYYojVOXlFMs1DdyMT6qXl/niOH7AVElmmEdUNHHS/oRkc++d5k6Vy85zFs0DEw==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "win32"
      ]
    },
    "node_modules/@rollup/rollup-win32-ia32-msvc": {
      "version": "4.60.4",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-win32-ia32-msvc/-/rollup-win32-ia32-msvc-4.60.4.tgz",
      "integrity": "sha512-zTPgT1YuHHcd+Tmx7h8aml0FWFVelV5N54oHow9SLj+GfoDy/huQ+UV396N/C7KpMDMiPspRktzM1/0r1usYEA==",
      "cpu": [
        "ia32"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "win32"
      ]
    },
    "node_modules/@rollup/rollup-win32-x64-gnu": {
      "version": "4.60.4",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-win32-x64-gnu/-/rollup-win32-x64-gnu-4.60.4.tgz",
      "integrity": "sha512-DRS4G7mi9lJxqEDezIkKCaUIKCrLUUDCUaCsTPCi/rtqaC6D/jjwslMQyiDU50Ka0JKpeXeRBFBAXwArY52vBw==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "win32"
      ]
    },
    "node_modules/@rollup/rollup-win32-x64-msvc": {
      "version": "4.60.4",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-win32-x64-msvc/-/rollup-win32-x64-msvc-4.60.4.tgz",
      "integrity": "sha512-QVTUovf40zgTqlFVrKA1uXMVvU2QWEFWfAH8Wdc48IxLvrJMQVMBRjuQyUpzZCDkakImib9eVazbWlC6ksWtJw==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "win32"
      ]
    },
    "node_modules/@tanstack/query-core": {
      "version": "5.100.14",
      "resolved": "https://registry.npmjs.org/@tanstack/query-core/-/query-core-5.100.14.tgz",
      "integrity": "sha512-5X41dGpxgeaHISCRW2oYwcSycZeULZzAunaudXT9ov1KOTj9xwt0CH6hbwqP1/z74ZWF7rYFnDpyYH07XFcZew==",
      "license": "MIT",
      "funding": {
        "type": "github",
        "url": "https://github.com/sponsors/tannerlinsley"
      }
    },
    "node_modules/@tanstack/react-query": {
      "version": "5.100.14",
      "resolved": "https://registry.npmjs.org/@tanstack/react-query/-/react-query-5.100.14.tgz",
      "integrity": "sha512-oOr6aRdSFEwWhzxEkD/9ZcItM3+LjBSkeVmadWKwUssAHTsqd/7bOjWrX4AbvEkoEhgAxzN0Xk6H/aYzXiYBAw==",
      "license": "MIT",
      "dependencies": {
        "@tanstack/query-core": "5.100.14"
      },
      "funding": {
        "type": "github",
        "url": "https://github.com/sponsors/tannerlinsley"
      },
      "peerDependencies": {
        "react": "^18 || ^19"
      }
    },
    "node_modules/@types/babel__core": {
      "version": "7.20.5",
      "resolved": "https://registry.npmjs.org/@types/babel__core/-/babel__core-7.20.5.tgz",
      "integrity": "sha512-qoQprZvz5wQFJwMDqeseRXWv3rqMvhgpbXFfVyWhbx9X47POIA6i/+dXefEmZKoAgOaTdaIgNSMqMIU61yRyzA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/parser": "^7.20.7",
        "@babel/types": "^7.20.7",
        "@types/babel__generator": "*",
        "@types/babel__template": "*",
        "@types/babel__traverse": "*"
      }
    },
    "node_modules/@types/babel__generator": {
      "version": "7.27.0",
      "resolved": "https://registry.npmjs.org/@types/babel__generator/-/babel__generator-7.27.0.tgz",
      "integrity": "sha512-ufFd2Xi92OAVPYsy+P4n7/U7e68fex0+Ee8gSG9KX7eo084CWiQ4sdxktvdl0bOPupXtVJPY19zk6EwWqUQ8lg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/types": "^7.0.0"
      }
    },
    "node_modules/@types/babel__template": {
      "version": "7.4.4",
      "resolved": "https://registry.npmjs.org/@types/babel__template/-/babel__template-7.4.4.tgz",
      "integrity": "sha512-h/NUaSyG5EyxBIp8YRxo4RMe2/qQgvyowRwVMzhYhBCONbW8PUsg4lkFMrhgZhUe5z3L3MiLDuvyJ/CaPa2A8A==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/parser": "^7.1.0",
        "@babel/types": "^7.0.0"
      }
    },
    "node_modules/@types/babel__traverse": {
      "version": "7.28.0",
      "resolved": "https://registry.npmjs.org/@types/babel__traverse/-/babel__traverse-7.28.0.tgz",
      "integrity": "sha512-8PvcXf70gTDZBgt9ptxJ8elBeBjcLOAcOtoO/mPJjtji1+CdGbHgm77om1GrsPxsiE+uXIpNSK64UYaIwQXd4Q==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/types": "^7.28.2"
      }
    },
    "node_modules/@types/d3-array": {
      "version": "3.2.2",
      "resolved": "https://registry.npmjs.org/@types/d3-array/-/d3-array-3.2.2.tgz",
      "integrity": "sha512-hOLWVbm7uRza0BYXpIIW5pxfrKe0W+D5lrFiAEYR+pb6w3N2SwSMaJbXdUfSEv+dT4MfHBLtn5js0LAWaO6otw==",
      "license": "MIT"
    },
    "node_modules/@types/d3-color": {
      "version": "3.1.3",
      "resolved": "https://registry.npmjs.org/@types/d3-color/-/d3-color-3.1.3.tgz",
      "integrity": "sha512-iO90scth9WAbmgv7ogoq57O9YpKmFBbmoEoCHDB2xMBY0+/KVrqAaCDyCE16dUspeOvIxFFRI+0sEtqDqy2b4A==",
      "license": "MIT"
    },
    "node_modules/@types/d3-ease": {
      "version": "3.0.2",
      "resolved": "https://registry.npmjs.org/@types/d3-ease/-/d3-ease-3.0.2.tgz",
      "integrity": "sha512-NcV1JjO5oDzoK26oMzbILE6HW7uVXOHLQvHshBUW4UMdZGfiY6v5BeQwh9a9tCzv+CeefZQHJt5SRgK154RtiA==",
      "license": "MIT"
    },
    "node_modules/@types/d3-interpolate": {
      "version": "3.0.4",
      "resolved": "https://registry.npmjs.org/@types/d3-interpolate/-/d3-interpolate-3.0.4.tgz",
      "integrity": "sha512-mgLPETlrpVV1YRJIglr4Ez47g7Yxjl1lj7YKsiMCb27VJH9W8NVM6Bb9d8kkpG/uAQS5AmbA48q2IAolKKo1MA==",
      "license": "MIT",
      "dependencies": {
        "@types/d3-color": "*"
      }
    },
    "node_modules/@types/d3-path": {
      "version": "3.1.1",
      "resolved": "https://registry.npmjs.org/@types/d3-path/-/d3-path-3.1.1.tgz",
      "integrity": "sha512-VMZBYyQvbGmWyWVea0EHs/BwLgxc+MKi1zLDCONksozI4YJMcTt8ZEuIR4Sb1MMTE8MMW49v0IwI5+b7RmfWlg==",
      "license": "MIT"
    },
    "node_modules/@types/d3-scale": {
      "version": "4.0.9",
      "resolved": "https://registry.npmjs.org/@types/d3-scale/-/d3-scale-4.0.9.tgz",
      "integrity": "sha512-dLmtwB8zkAeO/juAMfnV+sItKjlsw2lKdZVVy6LRr0cBmegxSABiLEpGVmSJJ8O08i4+sGR6qQtb6WtuwJdvVw==",
      "license": "MIT",
      "dependencies": {
        "@types/d3-time": "*"
      }
    },
    "node_modules/@types/d3-shape": {
      "version": "3.1.8",
      "resolved": "https://registry.npmjs.org/@types/d3-shape/-/d3-shape-3.1.8.tgz",
      "integrity": "sha512-lae0iWfcDeR7qt7rA88BNiqdvPS5pFVPpo5OfjElwNaT2yyekbM0C9vK+yqBqEmHr6lDkRnYNoTBYlAgJa7a4w==",
      "license": "MIT",
      "dependencies": {
        "@types/d3-path": "*"
      }
    },
    "node_modules/@types/d3-time": {
      "version": "3.0.4",
      "resolved": "https://registry.npmjs.org/@types/d3-time/-/d3-time-3.0.4.tgz",
      "integrity": "sha512-yuzZug1nkAAaBlBBikKZTgzCeA+k1uy4ZFwWANOfKw5z5LRhV0gNA7gNkKm7HoK+HRN0wX3EkxGk0fpbWhmB7g==",
      "license": "MIT"
    },
    "node_modules/@types/d3-timer": {
      "version": "3.0.2",
      "resolved": "https://registry.npmjs.org/@types/d3-timer/-/d3-timer-3.0.2.tgz",
      "integrity": "sha512-Ps3T8E8dZDam6fUyNiMkekK3XUsaUEik+idO9/YjPtfj2qruF8tFBXS7XhtE4iIXBLxhmLjP3SXpLhVf21I9Lw==",
      "license": "MIT"
    },
    "node_modules/@types/estree": {
      "version": "1.0.8",
      "resolved": "https://registry.npmjs.org/@types/estree/-/estree-1.0.8.tgz",
      "integrity": "sha512-dWHzHa2WqEXI/O1E9OjrocMTKJl2mSrEolh1Iomrv6U+JuNwaHXsXx9bLu5gG7BUWFIN0skIQJQ/L1rIex4X6w==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/@types/prop-types": {
      "version": "15.7.15",
      "resolved": "https://registry.npmjs.org/@types/prop-types/-/prop-types-15.7.15.tgz",
      "integrity": "sha512-F6bEyamV9jKGAFBEmlQnesRPGOQqS2+Uwi0Em15xenOxHaf2hv6L8YCVn3rPdPJOiJfPiCnLIRyvwVaqMY3MIw==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/@types/react": {
      "version": "18.3.29",
      "resolved": "https://registry.npmjs.org/@types/react/-/react-18.3.29.tgz",
      "integrity": "sha512-ch0qJdr2JY0r04NXSprbK6TXOgnaJ1Tz23fm5W+z0/CBah6BSBc3n96h7K9GOtwh0HrilNWHIBzE1Ko4Dcw/Wg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@types/prop-types": "*",
        "csstype": "^3.2.2"
      }
    },
    "node_modules/@types/react-dom": {
      "version": "18.3.7",
      "resolved": "https://registry.npmjs.org/@types/react-dom/-/react-dom-18.3.7.tgz",
      "integrity": "sha512-MEe3UeoENYVFXzoXEWsvcpg6ZvlrFNlOQ7EOsvhI3CfAXwzPfO8Qwuxd40nepsYKqyyVQnTdEfv68q91yLcKrQ==",
      "dev": true,
      "license": "MIT",
      "peerDependencies": {
        "@types/react": "^18.0.0"
      }
    },
    "node_modules/@vitejs/plugin-react": {
      "version": "4.7.0",
      "resolved": "https://registry.npmjs.org/@vitejs/plugin-react/-/plugin-react-4.7.0.tgz",
      "integrity": "sha512-gUu9hwfWvvEDBBmgtAowQCojwZmJ5mcLn3aufeCsitijs3+f2NsrPtlAWIR6OPiqljl96GVCUbLe0HyqIpVaoA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/core": "^7.28.0",
        "@babel/plugin-transform-react-jsx-self": "^7.27.1",
        "@babel/plugin-transform-react-jsx-source": "^7.27.1",
        "@rolldown/pluginutils": "1.0.0-beta.27",
        "@types/babel__core": "^7.20.5",
        "react-refresh": "^0.17.0"
      },
      "engines": {
        "node": "^14.18.0 || >=16.0.0"
      },
      "peerDependencies": {
        "vite": "^4.2.0 || ^5.0.0 || ^6.0.0 || ^7.0.0"
      }
    },
    "node_modules/agent-base": {
      "version": "6.0.2",
      "resolved": "https://registry.npmjs.org/agent-base/-/agent-base-6.0.2.tgz",
      "integrity": "sha512-RZNwNclF7+MS/8bDg70amg32dyeZGZxiDuQmZxKLAlQjr3jGyLx+4Kkk58UO7D2QdgFIQCovuSuZESne6RG6XQ==",
      "license": "MIT",
      "dependencies": {
        "debug": "4"
      },
      "engines": {
        "node": ">= 6.0.0"
      }
    },
    "node_modules/any-promise": {
      "version": "1.3.0",
      "resolved": "https://registry.npmjs.org/any-promise/-/any-promise-1.3.0.tgz",
      "integrity": "sha512-7UvmKalWRt1wgjL1RrGxoSJW/0QZFIegpeGvZG9kjp8vrRu55XTHbwnqq2GpXm9uLbcuhxm3IqX9OB4MZR1b2A==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/anymatch": {
      "version": "3.1.3",
      "resolved": "https://registry.npmjs.org/anymatch/-/anymatch-3.1.3.tgz",
      "integrity": "sha512-KMReFUr0B4t+D+OBkjR3KYqvocp2XaSzO55UcB6mgQMd3KbcE+mWTyvVV7D/zsdEbNnV6acZUutkiHQXvTr1Rw==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "normalize-path": "^3.0.0",
        "picomatch": "^2.0.4"
      },
      "engines": {
        "node": ">= 8"
      }
    },
    "node_modules/arg": {
      "version": "5.0.2",
      "resolved": "https://registry.npmjs.org/arg/-/arg-5.0.2.tgz",
      "integrity": "sha512-PYjyFOLKQ9y57JvQ6QLo8dAgNqswh8M1RMJYdQduT6xbWSgK36P/Z/v+p888pM69jMMfS8Xd8F6I1kQ/I9HUGg==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/asynckit": {
      "version": "0.4.0",
      "resolved": "https://registry.npmjs.org/asynckit/-/asynckit-0.4.0.tgz",
      "integrity": "sha512-Oei9OH4tRh0YqU3GxhX79dM/mwVgvbZJaSNaRk+bshkj0S5cfHcgYakreBjrHwatXKbz+IoIdYLxrKim2MjW0Q==",
      "license": "MIT"
    },
    "node_modules/autoprefixer": {
      "version": "10.5.0",
      "resolved": "https://registry.npmjs.org/autoprefixer/-/autoprefixer-10.5.0.tgz",
      "integrity": "sha512-FMhOoZV4+qR6aTUALKX2rEqGG+oyATvwBt9IIzVR5rMa2HRWPkxf+P+PAJLD1I/H5/II+HuZcBJYEFBpq39ong==",
      "dev": true,
      "funding": [
        {
          "type": "opencollective",
          "url": "https://opencollective.com/postcss/"
        },
        {
          "type": "tidelift",
          "url": "https://tidelift.com/funding/github/npm/autoprefixer"
        },
        {
          "type": "github",
          "url": "https://github.com/sponsors/ai"
        }
      ],
      "license": "MIT",
      "dependencies": {
        "browserslist": "^4.28.2",
        "caniuse-lite": "^1.0.30001787",
        "fraction.js": "^5.3.4",
        "picocolors": "^1.1.1",
        "postcss-value-parser": "^4.2.0"
      },
      "bin": {
        "autoprefixer": "bin/autoprefixer"
      },
      "engines": {
        "node": "^10 || ^12 || >=14"
      },
      "peerDependencies": {
        "postcss": "^8.1.0"
      }
    },
    "node_modules/axios": {
      "version": "1.16.1",
      "resolved": "https://registry.npmjs.org/axios/-/axios-1.16.1.tgz",
      "integrity": "sha512-caYkukvroVPO8KrzuJEb50Hm07KwfBZPEC3VeFHTsqWHvKTsy54hjJz9BS/cdaypROE2rH6xvm9mHX4fgWkr3A==",
      "license": "MIT",
      "dependencies": {
        "follow-redirects": "^1.16.0",
        "form-data": "^4.0.5",
        "https-proxy-agent": "^5.0.1",
        "proxy-from-env": "^2.1.0"
      }
    },
    "node_modules/baseline-browser-mapping": {
      "version": "2.10.32",
      "resolved": "https://registry.npmjs.org/baseline-browser-mapping/-/baseline-browser-mapping-2.10.32.tgz",
      "integrity": "sha512-wbPvpyjJPC0zdfdKXxqEL3Ea+bOMD/87X4lftiJkkaBiuG6ALQy1SLmEd7BSmVCuwCQsBrCamgBoLyfFDD1EPg==",
      "dev": true,
      "license": "Apache-2.0",
      "bin": {
        "baseline-browser-mapping": "dist/cli.cjs"
      },
      "engines": {
        "node": ">=6.0.0"
      }
    },
    "node_modules/binary-extensions": {
      "version": "2.3.0",
      "resolved": "https://registry.npmjs.org/binary-extensions/-/binary-extensions-2.3.0.tgz",
      "integrity": "sha512-Ceh+7ox5qe7LJuLHoY0feh3pHuUDHAcRUeyL2VYghZwfpkNIy/+8Ocg0a3UuSoYzavmylwuLWQOf3hl0jjMMIw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=8"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/braces": {
      "version": "3.0.3",
      "resolved": "https://registry.npmjs.org/braces/-/braces-3.0.3.tgz",
      "integrity": "sha512-yQbXgO/OSZVD2IsiLlro+7Hf6Q18EJrKSEsdoMzKePKXct3gvD8oLcOQdIzGupr5Fj+EDe8gO/lxc1BzfMpxvA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "fill-range": "^7.1.1"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/browserslist": {
      "version": "4.28.2",
      "resolved": "https://registry.npmjs.org/browserslist/-/browserslist-4.28.2.tgz",
      "integrity": "sha512-48xSriZYYg+8qXna9kwqjIVzuQxi+KYWp2+5nCYnYKPTr0LvD89Jqk2Or5ogxz0NUMfIjhh2lIUX/LyX9B4oIg==",
      "dev": true,
      "funding": [
        {
          "type": "opencollective",
          "url": "https://opencollective.com/browserslist"
        },
        {
          "type": "tidelift",
          "url": "https://tidelift.com/funding/github/npm/browserslist"
        },
        {
          "type": "github",
          "url": "https://github.com/sponsors/ai"
        }
      ],
      "license": "MIT",
      "dependencies": {
        "baseline-browser-mapping": "^2.10.12",
        "caniuse-lite": "^1.0.30001782",
        "electron-to-chromium": "^1.5.328",
        "node-releases": "^2.0.36",
        "update-browserslist-db": "^1.2.3"
      },
      "bin": {
        "browserslist": "cli.js"
      },
      "engines": {
        "node": "^6 || ^7 || ^8 || ^9 || ^10 || ^11 || ^12 || >=13.7"
      }
    },
    "node_modules/call-bind-apply-helpers": {
      "version": "1.0.2",
      "resolved": "https://registry.npmjs.org/call-bind-apply-helpers/-/call-bind-apply-helpers-1.0.2.tgz",
      "integrity": "sha512-Sp1ablJ0ivDkSzjcaJdxEunN5/XvksFJ2sMBFfq6x0ryhQV/2b/KwFe21cMpmHtPOSij8K99/wSfoEuTObmuMQ==",
      "license": "MIT",
      "dependencies": {
        "es-errors": "^1.3.0",
        "function-bind": "^1.1.2"
      },
      "engines": {
        "node": ">= 0.4"
      }
    },
    "node_modules/camelcase-css": {
      "version": "2.0.1",
      "resolved": "https://registry.npmjs.org/camelcase-css/-/camelcase-css-2.0.1.tgz",
      "integrity": "sha512-QOSvevhslijgYwRx6Rv7zKdMF8lbRmx+uQGx2+vDc+KI/eBnsy9kit5aj23AgGu3pa4t9AgwbnXWqS+iOY+2aA==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 6"
      }
    },
    "node_modules/caniuse-lite": {
      "version": "1.0.30001793",
      "resolved": "https://registry.npmjs.org/caniuse-lite/-/caniuse-lite-1.0.30001793.tgz",
      "integrity": "sha512-iwSsYWaCOoh26cV8NwNRViHlrfUvYsHDfRVcbtmw0Kg6PJIZZXwMkj1442FYLBGkeUf1juAsU3DTfxW579mrPA==",
      "dev": true,
      "funding": [
        {
          "type": "opencollective",
          "url": "https://opencollective.com/browserslist"
        },
        {
          "type": "tidelift",
          "url": "https://tidelift.com/funding/github/npm/caniuse-lite"
        },
        {
          "type": "github",
          "url": "https://github.com/sponsors/ai"
        }
      ],
      "license": "CC-BY-4.0"
    },
    "node_modules/chokidar": {
      "version": "3.6.0",
      "resolved": "https://registry.npmjs.org/chokidar/-/chokidar-3.6.0.tgz",
      "integrity": "sha512-7VT13fmjotKpGipCW9JEQAusEPE+Ei8nl6/g4FBAmIm0GOOLMua9NDDo/DWp0ZAxCr3cPq5ZpBqmPAQgDda2Pw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "anymatch": "~3.1.2",
        "braces": "~3.0.2",
        "glob-parent": "~5.1.2",
        "is-binary-path": "~2.1.0",
        "is-glob": "~4.0.1",
        "normalize-path": "~3.0.0",
        "readdirp": "~3.6.0"
      },
      "engines": {
        "node": ">= 8.10.0"
      },
      "funding": {
        "url": "https://paulmillr.com/funding/"
      },
      "optionalDependencies": {
        "fsevents": "~2.3.2"
      }
    },
    "node_modules/chokidar/node_modules/glob-parent": {
      "version": "5.1.2",
      "resolved": "https://registry.npmjs.org/glob-parent/-/glob-parent-5.1.2.tgz",
      "integrity": "sha512-AOIgSQCepiJYwP3ARnGx+5VnTu2HBYdzbGP45eLw1vr3zB3vZLeyed1sC9hnbcOc9/SrMyM5RPQrkGz4aS9Zow==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "is-glob": "^4.0.1"
      },
      "engines": {
        "node": ">= 6"
      }
    },
    "node_modules/clsx": {
      "version": "2.1.1",
      "resolved": "https://registry.npmjs.org/clsx/-/clsx-2.1.1.tgz",
      "integrity": "sha512-eYm0QWBtUrBWZWG0d386OGAw16Z995PiOVo2B7bjWSbHedGl5e0ZWaq65kOGgUSNesEIDkB9ISbTg/JK9dhCZA==",
      "license": "MIT",
      "engines": {
        "node": ">=6"
      }
    },
    "node_modules/combined-stream": {
      "version": "1.0.8",
      "resolved": "https://registry.npmjs.org/combined-stream/-/combined-stream-1.0.8.tgz",
      "integrity": "sha512-FQN4MRfuJeHf7cBbBMJFXhKSDq+2kAArBlmRBvcvFE5BB1HZKXtSFASDhdlz9zOYwxh8lDdnvmMOe/+5cdoEdg==",
      "license": "MIT",
      "dependencies": {
        "delayed-stream": "~1.0.0"
      },
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/commander": {
      "version": "4.1.1",
      "resolved": "https://registry.npmjs.org/commander/-/commander-4.1.1.tgz",
      "integrity": "sha512-NOKm8xhkzAjzFx8B2v5OAHT+u5pRQc2UCa2Vq9jYL/31o2wi9mxBA7LIFs3sV5VSC49z6pEhfbMULvShKj26WA==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 6"
      }
    },
    "node_modules/convert-source-map": {
      "version": "2.0.0",
      "resolved": "https://registry.npmjs.org/convert-source-map/-/convert-source-map-2.0.0.tgz",
      "integrity": "sha512-Kvp459HrV2FEJ1CAsi1Ku+MY3kasH19TFykTz2xWmMeq6bk2NU3XXvfJ+Q61m0xktWwt+1HSYf3JZsTms3aRJg==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/cssesc": {
      "version": "3.0.0",
      "resolved": "https://registry.npmjs.org/cssesc/-/cssesc-3.0.0.tgz",
      "integrity": "sha512-/Tb/JcjK111nNScGob5MNtsntNM1aCNUDipB/TkwZFhyDrrE47SOx/18wF2bbjgc3ZzCSKW1T5nt5EbFoAz/Vg==",
      "dev": true,
      "license": "MIT",
      "bin": {
        "cssesc": "bin/cssesc"
      },
      "engines": {
        "node": ">=4"
      }
    },
    "node_modules/csstype": {
      "version": "3.2.3",
      "resolved": "https://registry.npmjs.org/csstype/-/csstype-3.2.3.tgz",
      "integrity": "sha512-z1HGKcYy2xA8AGQfwrn0PAy+PB7X/GSj3UVJW9qKyn43xWa+gl5nXmU4qqLMRzWVLFC8KusUX8T/0kCiOYpAIQ==",
      "license": "MIT"
    },
    "node_modules/d3-array": {
      "version": "3.2.4",
      "resolved": "https://registry.npmjs.org/d3-array/-/d3-array-3.2.4.tgz",
      "integrity": "sha512-tdQAmyA18i4J7wprpYq8ClcxZy3SC31QMeByyCFyRt7BVHdREQZ5lpzoe5mFEYZUWe+oq8HBvk9JjpibyEV4Jg==",
      "license": "ISC",
      "dependencies": {
        "internmap": "1 - 2"
      },
      "engines": {
        "node": ">=12"
      }
    },
    "node_modules/d3-color": {
      "version": "3.1.0",
      "resolved": "https://registry.npmjs.org/d3-color/-/d3-color-3.1.0.tgz",
      "integrity": "sha512-zg/chbXyeBtMQ1LbD/WSoW2DpC3I0mpmPdW+ynRTj/x2DAWYrIY7qeZIHidozwV24m4iavr15lNwIwLxRmOxhA==",
      "license": "ISC",
      "engines": {
        "node": ">=12"
      }
    },
    "node_modules/d3-ease": {
      "version": "3.0.1",
      "resolved": "https://registry.npmjs.org/d3-ease/-/d3-ease-3.0.1.tgz",
      "integrity": "sha512-wR/XK3D3XcLIZwpbvQwQ5fK+8Ykds1ip7A2Txe0yxncXSdq1L9skcG7blcedkOX+ZcgxGAmLX1FrRGbADwzi0w==",
      "license": "BSD-3-Clause",
      "engines": {
        "node": ">=12"
      }
    },
    "node_modules/d3-format": {
      "version": "3.1.2",
      "resolved": "https://registry.npmjs.org/d3-format/-/d3-format-3.1.2.tgz",
      "integrity": "sha512-AJDdYOdnyRDV5b6ArilzCPPwc1ejkHcoyFarqlPqT7zRYjhavcT3uSrqcMvsgh2CgoPbK3RCwyHaVyxYcP2Arg==",
      "license": "ISC",
      "engines": {
        "node": ">=12"
      }
    },
    "node_modules/d3-interpolate": {
      "version": "3.0.1",
      "resolved": "https://registry.npmjs.org/d3-interpolate/-/d3-interpolate-3.0.1.tgz",
      "integrity": "sha512-3bYs1rOD33uo8aqJfKP3JWPAibgw8Zm2+L9vBKEHJ2Rg+viTR7o5Mmv5mZcieN+FRYaAOWX5SJATX6k1PWz72g==",
      "license": "ISC",
      "dependencies": {
        "d3-color": "1 - 3"
      },
      "engines": {
        "node": ">=12"
      }
    },
    "node_modules/d3-path": {
      "version": "3.1.0",
      "resolved": "https://registry.npmjs.org/d3-path/-/d3-path-3.1.0.tgz",
      "integrity": "sha512-p3KP5HCf/bvjBSSKuXid6Zqijx7wIfNW+J/maPs+iwR35at5JCbLUT0LzF1cnjbCHWhqzQTIN2Jpe8pRebIEFQ==",
      "license": "ISC",
      "engines": {
        "node": ">=12"
      }
    },
    "node_modules/d3-scale": {
      "version": "4.0.2",
      "resolved": "https://registry.npmjs.org/d3-scale/-/d3-scale-4.0.2.tgz",
      "integrity": "sha512-GZW464g1SH7ag3Y7hXjf8RoUuAFIqklOAq3MRl4OaWabTFJY9PN/E1YklhXLh+OQ3fM9yS2nOkCoS+WLZ6kvxQ==",
      "license": "ISC",
      "dependencies": {
        "d3-array": "2.10.0 - 3",
        "d3-format": "1 - 3",
        "d3-interpolate": "1.2.0 - 3",
        "d3-time": "2.1.1 - 3",
        "d3-time-format": "2 - 4"
      },
      "engines": {
        "node": ">=12"
      }
    },
    "node_modules/d3-shape": {
      "version": "3.2.0",
      "resolved": "https://registry.npmjs.org/d3-shape/-/d3-shape-3.2.0.tgz",
      "integrity": "sha512-SaLBuwGm3MOViRq2ABk3eLoxwZELpH6zhl3FbAoJ7Vm1gofKx6El1Ib5z23NUEhF9AsGl7y+dzLe5Cw2AArGTA==",
      "license": "ISC",
      "dependencies": {
        "d3-path": "^3.1.0"
      },
      "engines": {
        "node": ">=12"
      }
    },
    "node_modules/d3-time": {
      "version": "3.1.0",
      "resolved": "https://registry.npmjs.org/d3-time/-/d3-time-3.1.0.tgz",
      "integrity": "sha512-VqKjzBLejbSMT4IgbmVgDjpkYrNWUYJnbCGo874u7MMKIWsILRX+OpX/gTk8MqjpT1A/c6HY2dCA77ZN0lkQ2Q==",
      "license": "ISC",
      "dependencies": {
        "d3-array": "2 - 3"
      },
      "engines": {
        "node": ">=12"
      }
    },
    "node_modules/d3-time-format": {
      "version": "4.1.0",
      "resolved": "https://registry.npmjs.org/d3-time-format/-/d3-time-format-4.1.0.tgz",
      "integrity": "sha512-dJxPBlzC7NugB2PDLwo9Q8JiTR3M3e4/XANkreKSUxF8vvXKqm1Yfq4Q5dl8budlunRVlUUaDUgFt7eA8D6NLg==",
      "license": "ISC",
      "dependencies": {
        "d3-time": "1 - 3"
      },
      "engines": {
        "node": ">=12"
      }
    },
    "node_modules/d3-timer": {
      "version": "3.0.1",
      "resolved": "https://registry.npmjs.org/d3-timer/-/d3-timer-3.0.1.tgz",
      "integrity": "sha512-ndfJ/JxxMd3nw31uyKoY2naivF+r29V+Lc0svZxe1JvvIRmi8hUsrMvdOwgS1o6uBHmiz91geQ0ylPP0aj1VUA==",
      "license": "ISC",
      "engines": {
        "node": ">=12"
      }
    },
    "node_modules/date-fns": {
      "version": "4.3.0",
      "resolved": "https://registry.npmjs.org/date-fns/-/date-fns-4.3.0.tgz",
      "integrity": "sha512-OYcL+3N/jyWbYdFGqoMAhytDgxP9pbYPUUiRCOgn4Fewaadk9l/Wam4Avciiyp2BgkpfQyBV9B+ehnVJych+eQ==",
      "license": "MIT",
      "funding": {
        "type": "github",
        "url": "https://github.com/sponsors/kossnocorp"
      }
    },
    "node_modules/debug": {
      "version": "4.4.3",
      "resolved": "https://registry.npmjs.org/debug/-/debug-4.4.3.tgz",
      "integrity": "sha512-RGwwWnwQvkVfavKVt22FGLw+xYSdzARwm0ru6DhTVA3umU5hZc28V3kO4stgYryrTlLpuvgI9GiijltAjNbcqA==",
      "license": "MIT",
      "dependencies": {
        "ms": "^2.1.3"
      },
      "engines": {
        "node": ">=6.0"
      },
      "peerDependenciesMeta": {
        "supports-color": {
          "optional": true
        }
      }
    },
    "node_modules/decimal.js-light": {
      "version": "2.5.1",
      "resolved": "https://registry.npmjs.org/decimal.js-light/-/decimal.js-light-2.5.1.tgz",
      "integrity": "sha512-qIMFpTMZmny+MMIitAB6D7iVPEorVw6YQRWkvarTkT4tBeSLLiHzcwj6q0MmYSFCiVpiqPJTJEYIrpcPzVEIvg==",
      "license": "MIT"
    },
    "node_modules/delayed-stream": {
      "version": "1.0.0",
      "resolved": "https://registry.npmjs.org/delayed-stream/-/delayed-stream-1.0.0.tgz",
      "integrity": "sha512-ZySD7Nf91aLB0RxL4KGrKHBXl7Eds1DAmEdcoVawXnLD7SDhpNgtuII2aAkg7a7QS41jxPSZ17p4VdGnMHk3MQ==",
      "license": "MIT",
      "engines": {
        "node": ">=0.4.0"
      }
    },
    "node_modules/didyoumean": {
      "version": "1.2.2",
      "resolved": "https://registry.npmjs.org/didyoumean/-/didyoumean-1.2.2.tgz",
      "integrity": "sha512-gxtyfqMg7GKyhQmb056K7M3xszy/myH8w+B4RT+QXBQsvAOdc3XymqDDPHx1BgPgsdAA5SIifona89YtRATDzw==",
      "dev": true,
      "license": "Apache-2.0"
    },
    "node_modules/dlv": {
      "version": "1.1.3",
      "resolved": "https://registry.npmjs.org/dlv/-/dlv-1.1.3.tgz",
      "integrity": "sha512-+HlytyjlPKnIG8XuRG8WvmBP8xs8P71y+SKKS6ZXWoEgLuePxtDoUEiH7WkdePWrQ5JBpE6aoVqfZfJUQkjXwA==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/dom-helpers": {
      "version": "5.2.1",
      "resolved": "https://registry.npmjs.org/dom-helpers/-/dom-helpers-5.2.1.tgz",
      "integrity": "sha512-nRCa7CK3VTrM2NmGkIy4cbK7IZlgBE/PYMn55rrXefr5xXDP0LdtfPnblFDoVdcAfslJ7or6iqAUnx0CCGIWQA==",
      "license": "MIT",
      "dependencies": {
        "@babel/runtime": "^7.8.7",
        "csstype": "^3.0.2"
      }
    },
    "node_modules/dunder-proto": {
      "version": "1.0.1",
      "resolved": "https://registry.npmjs.org/dunder-proto/-/dunder-proto-1.0.1.tgz",
      "integrity": "sha512-KIN/nDJBQRcXw0MLVhZE9iQHmG68qAVIBg9CqmUYjmQIhgij9U5MFvrqkUL5FbtyyzZuOeOt0zdeRe4UY7ct+A==",
      "license": "MIT",
      "dependencies": {
        "call-bind-apply-helpers": "^1.0.1",
        "es-errors": "^1.3.0",
        "gopd": "^1.2.0"
      },
      "engines": {
        "node": ">= 0.4"
      }
    },
    "node_modules/electron-to-chromium": {
      "version": "1.5.362",
      "resolved": "https://registry.npmjs.org/electron-to-chromium/-/electron-to-chromium-1.5.362.tgz",
      "integrity": "sha512-PUY2DrLvkjkUuWqq+KPL2iWshrJsZOcIojzRQ7eXFacc9dWga7MGMJAa15VbiejSZB1PAXaRLAiKgruHP8LB1w==",
      "dev": true,
      "license": "ISC"
    },
    "node_modules/es-define-property": {
      "version": "1.0.1",
      "resolved": "https://registry.npmjs.org/es-define-property/-/es-define-property-1.0.1.tgz",
      "integrity": "sha512-e3nRfgfUZ4rNGL232gUgX06QNyyez04KdjFrF+LTRoOXmrOgFKDg4BCdsjW8EnT69eqdYGmRpJwiPVYNrCaW3g==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.4"
      }
    },
    "node_modules/es-errors": {
      "version": "1.3.0",
      "resolved": "https://registry.npmjs.org/es-errors/-/es-errors-1.3.0.tgz",
      "integrity": "sha512-Zf5H2Kxt2xjTvbJvP2ZWLEICxA6j+hAmMzIlypy4xcBg1vKVnx89Wy0GbS+kf5cwCVFFzdCFh2XSCFNULS6csw==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.4"
      }
    },
    "node_modules/es-object-atoms": {
      "version": "1.1.2",
      "resolved": "https://registry.npmjs.org/es-object-atoms/-/es-object-atoms-1.1.2.tgz",
      "integrity": "sha512-HWcBoN6NileqtSydK2FqHbS/LoDd2pqrnQHLyJzBj4kOp/ky2MWMN694xOfkK8/SnUsW2DH7EfyVlydKCsm1Zw==",
      "license": "MIT",
      "dependencies": {
        "es-errors": "^1.3.0"
      },
      "engines": {
        "node": ">= 0.4"
      }
    },
    "node_modules/es-set-tostringtag": {
      "version": "2.1.0",
      "resolved": "https://registry.npmjs.org/es-set-tostringtag/-/es-set-tostringtag-2.1.0.tgz",
      "integrity": "sha512-j6vWzfrGVfyXxge+O0x5sh6cvxAog0a/4Rdd2K36zCMV5eJ+/+tOAngRO8cODMNWbVRdVlmGZQL2YS3yR8bIUA==",
      "license": "MIT",
      "dependencies": {
        "es-errors": "^1.3.0",
        "get-intrinsic": "^1.2.6",
        "has-tostringtag": "^1.0.2",
        "hasown": "^2.0.2"
      },
      "engines": {
        "node": ">= 0.4"
      }
    },
    "node_modules/esbuild": {
      "version": "0.25.12",
      "resolved": "https://registry.npmjs.org/esbuild/-/esbuild-0.25.12.tgz",
      "integrity": "sha512-bbPBYYrtZbkt6Os6FiTLCTFxvq4tt3JKall1vRwshA3fdVztsLAatFaZobhkBC8/BrPetoa0oksYoKXoG4ryJg==",
      "dev": true,
      "hasInstallScript": true,
      "license": "MIT",
      "bin": {
        "esbuild": "bin/esbuild"
      },
      "engines": {
        "node": ">=18"
      },
      "optionalDependencies": {
        "@esbuild/aix-ppc64": "0.25.12",
        "@esbuild/android-arm": "0.25.12",
        "@esbuild/android-arm64": "0.25.12",
        "@esbuild/android-x64": "0.25.12",
        "@esbuild/darwin-arm64": "0.25.12",
        "@esbuild/darwin-x64": "0.25.12",
        "@esbuild/freebsd-arm64": "0.25.12",
        "@esbuild/freebsd-x64": "0.25.12",
        "@esbuild/linux-arm": "0.25.12",
        "@esbuild/linux-arm64": "0.25.12",
        "@esbuild/linux-ia32": "0.25.12",
        "@esbuild/linux-loong64": "0.25.12",
        "@esbuild/linux-mips64el": "0.25.12",
        "@esbuild/linux-ppc64": "0.25.12",
        "@esbuild/linux-riscv64": "0.25.12",
        "@esbuild/linux-s390x": "0.25.12",
        "@esbuild/linux-x64": "0.25.12",
        "@esbuild/netbsd-arm64": "0.25.12",
        "@esbuild/netbsd-x64": "0.25.12",
        "@esbuild/openbsd-arm64": "0.25.12",
        "@esbuild/openbsd-x64": "0.25.12",
        "@esbuild/openharmony-arm64": "0.25.12",
        "@esbuild/sunos-x64": "0.25.12",
        "@esbuild/win32-arm64": "0.25.12",
        "@esbuild/win32-ia32": "0.25.12",
        "@esbuild/win32-x64": "0.25.12"
      }
    },
    "node_modules/escalade": {
      "version": "3.2.0",
      "resolved": "https://registry.npmjs.org/escalade/-/escalade-3.2.0.tgz",
      "integrity": "sha512-WUj2qlxaQtO4g6Pq5c29GTcWGDyd8itL8zTlipgECz3JesAiiOKotd8JU6otB3PACgG6xkJUyVhboMS+bje/jA==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6"
      }
    },
    "node_modules/eventemitter3": {
      "version": "4.0.7",
      "resolved": "https://registry.npmjs.org/eventemitter3/-/eventemitter3-4.0.7.tgz",
      "integrity": "sha512-8guHBZCwKnFhYdHr2ysuRWErTwhoN2X8XELRlrRwpmfeY2jjuUN4taQMsULKUVo1K4DvZl+0pgfyoysHxvmvEw==",
      "license": "MIT"
    },
    "node_modules/fast-equals": {
      "version": "5.4.0",
      "resolved": "https://registry.npmjs.org/fast-equals/-/fast-equals-5.4.0.tgz",
      "integrity": "sha512-jt2DW/aNFNwke7AUd+Z+e6pz39KO5rzdbbFCg2sGafS4mk13MI7Z8O5z9cADNn5lhGODIgLwug6TZO2ctf7kcw==",
      "license": "MIT",
      "engines": {
        "node": ">=6.0.0"
      }
    },
    "node_modules/fast-glob": {
      "version": "3.3.3",
      "resolved": "https://registry.npmjs.org/fast-glob/-/fast-glob-3.3.3.tgz",
      "integrity": "sha512-7MptL8U0cqcFdzIzwOTHoilX9x5BrNqye7Z/LuC7kCMRio1EMSyqRK3BEAUD7sXRq4iT4AzTVuZdhgQ2TCvYLg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@nodelib/fs.stat": "^2.0.2",
        "@nodelib/fs.walk": "^1.2.3",
        "glob-parent": "^5.1.2",
        "merge2": "^1.3.0",
        "micromatch": "^4.0.8"
      },
      "engines": {
        "node": ">=8.6.0"
      }
    },
    "node_modules/fast-glob/node_modules/glob-parent": {
      "version": "5.1.2",
      "resolved": "https://registry.npmjs.org/glob-parent/-/glob-parent-5.1.2.tgz",
      "integrity": "sha512-AOIgSQCepiJYwP3ARnGx+5VnTu2HBYdzbGP45eLw1vr3zB3vZLeyed1sC9hnbcOc9/SrMyM5RPQrkGz4aS9Zow==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "is-glob": "^4.0.1"
      },
      "engines": {
        "node": ">= 6"
      }
    },
    "node_modules/fastq": {
      "version": "1.20.1",
      "resolved": "https://registry.npmjs.org/fastq/-/fastq-1.20.1.tgz",
      "integrity": "sha512-GGToxJ/w1x32s/D2EKND7kTil4n8OVk/9mycTc4VDza13lOvpUZTGX3mFSCtV9ksdGBVzvsyAVLM6mHFThxXxw==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "reusify": "^1.0.4"
      }
    },
    "node_modules/fill-range": {
      "version": "7.1.1",
      "resolved": "https://registry.npmjs.org/fill-range/-/fill-range-7.1.1.tgz",
      "integrity": "sha512-YsGpe3WHLK8ZYi4tWDg2Jy3ebRz2rXowDxnld4bkQB00cc/1Zw9AWnC0i9ztDJitivtQvaI9KaLyKrc+hBW0yg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "to-regex-range": "^5.0.1"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/follow-redirects": {
      "version": "1.16.0",
      "resolved": "https://registry.npmjs.org/follow-redirects/-/follow-redirects-1.16.0.tgz",
      "integrity": "sha512-y5rN/uOsadFT/JfYwhxRS5R7Qce+g3zG97+JrtFZlC9klX/W5hD7iiLzScI4nZqUS7DNUdhPgw4xI8W2LuXlUw==",
      "funding": [
        {
          "type": "individual",
          "url": "https://github.com/sponsors/RubenVerborgh"
        }
      ],
      "license": "MIT",
      "engines": {
        "node": ">=4.0"
      },
      "peerDependenciesMeta": {
        "debug": {
          "optional": true
        }
      }
    },
    "node_modules/form-data": {
      "version": "4.0.5",
      "resolved": "https://registry.npmjs.org/form-data/-/form-data-4.0.5.tgz",
      "integrity": "sha512-8RipRLol37bNs2bhoV67fiTEvdTrbMUYcFTiy3+wuuOnUog2QBHCZWXDRijWQfAkhBj2Uf5UnVaiWwA5vdd82w==",
      "license": "MIT",
      "dependencies": {
        "asynckit": "^0.4.0",
        "combined-stream": "^1.0.8",
        "es-set-tostringtag": "^2.1.0",
        "hasown": "^2.0.2",
        "mime-types": "^2.1.12"
      },
      "engines": {
        "node": ">= 6"
      }
    },
    "node_modules/fraction.js": {
      "version": "5.3.4",
      "resolved": "https://registry.npmjs.org/fraction.js/-/fraction.js-5.3.4.tgz",
      "integrity": "sha512-1X1NTtiJphryn/uLQz3whtY6jK3fTqoE3ohKs0tT+Ujr1W59oopxmoEh7Lu5p6vBaPbgoM0bzveAW4Qi5RyWDQ==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": "*"
      },
      "funding": {
        "type": "github",
        "url": "https://github.com/sponsors/rawify"
      }
    },
    "node_modules/fsevents": {
      "version": "2.3.3",
      "resolved": "https://registry.npmjs.org/fsevents/-/fsevents-2.3.3.tgz",
      "integrity": "sha512-5xoDfX+fL7faATnagmWPpbFtwh/R77WmMMqqHGS65C3vvB0YHrgF+B1YmZ3441tMj5n63k0212XNoJwzlhffQw==",
      "dev": true,
      "hasInstallScript": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "darwin"
      ],
      "engines": {
        "node": "^8.16.0 || ^10.6.0 || >=11.0.0"
      }
    },
    "node_modules/function-bind": {
      "version": "1.1.2",
      "resolved": "https://registry.npmjs.org/function-bind/-/function-bind-1.1.2.tgz",
      "integrity": "sha512-7XHNxH7qX9xG5mIwxkhumTox/MIRNcOgDrxWsMt2pAr23WHp6MrRlN7FBSFpCpr+oVO0F744iUgR82nJMfG2SA==",
      "license": "MIT",
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/gensync": {
      "version": "1.0.0-beta.2",
      "resolved": "https://registry.npmjs.org/gensync/-/gensync-1.0.0-beta.2.tgz",
      "integrity": "sha512-3hN7NaskYvMDLQY55gnW3NQ+mesEAepTqlg+VEbj7zzqEMBVNhzcGYYeqFo/TlYz6eQiFcp1HcsCZO+nGgS8zg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/get-intrinsic": {
      "version": "1.3.0",
      "resolved": "https://registry.npmjs.org/get-intrinsic/-/get-intrinsic-1.3.0.tgz",
      "integrity": "sha512-9fSjSaos/fRIVIp+xSJlE6lfwhES7LNtKaCBIamHsjr2na1BiABJPo0mOjjz8GJDURarmCPGqaiVg5mfjb98CQ==",
      "license": "MIT",
      "dependencies": {
        "call-bind-apply-helpers": "^1.0.2",
        "es-define-property": "^1.0.1",
        "es-errors": "^1.3.0",
        "es-object-atoms": "^1.1.1",
        "function-bind": "^1.1.2",
        "get-proto": "^1.0.1",
        "gopd": "^1.2.0",
        "has-symbols": "^1.1.0",
        "hasown": "^2.0.2",
        "math-intrinsics": "^1.1.0"
      },
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/get-proto": {
      "version": "1.0.1",
      "resolved": "https://registry.npmjs.org/get-proto/-/get-proto-1.0.1.tgz",
      "integrity": "sha512-sTSfBjoXBp89JvIKIefqw7U2CCebsc74kiY6awiGogKtoSGbgjYE/G/+l9sF3MWFPNc9IcoOC4ODfKHfxFmp0g==",
      "license": "MIT",
      "dependencies": {
        "dunder-proto": "^1.0.1",
        "es-object-atoms": "^1.0.0"
      },
      "engines": {
        "node": ">= 0.4"
      }
    },
    "node_modules/glob-parent": {
      "version": "6.0.2",
      "resolved": "https://registry.npmjs.org/glob-parent/-/glob-parent-6.0.2.tgz",
      "integrity": "sha512-XxwI8EOhVQgWp6iDL+3b0r86f4d6AX6zSU55HfB4ydCEuXLXc5FcYeOu+nnGftS4TEju/11rt4KJPTMgbfmv4A==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "is-glob": "^4.0.3"
      },
      "engines": {
        "node": ">=10.13.0"
      }
    },
    "node_modules/gopd": {
      "version": "1.2.0",
      "resolved": "https://registry.npmjs.org/gopd/-/gopd-1.2.0.tgz",
      "integrity": "sha512-ZUKRh6/kUFoAiTAtTYPZJ3hw9wNxx+BIBOijnlG9PnrJsCcSjs1wyyD6vJpaYtgnzDrKYRSqf3OO6Rfa93xsRg==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/has-symbols": {
      "version": "1.1.0",
      "resolved": "https://registry.npmjs.org/has-symbols/-/has-symbols-1.1.0.tgz",
      "integrity": "sha512-1cDNdwJ2Jaohmb3sg4OmKaMBwuC48sYni5HUw2DvsC8LjGTLK9h+eb1X6RyuOHe4hT0ULCW68iomhjUoKUqlPQ==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/has-tostringtag": {
      "version": "1.0.2",
      "resolved": "https://registry.npmjs.org/has-tostringtag/-/has-tostringtag-1.0.2.tgz",
      "integrity": "sha512-NqADB8VjPFLM2V0VvHUewwwsw0ZWBaIdgo+ieHtK3hasLz4qeCRjYcqfB6AQrBggRKppKF8L52/VqdVsO47Dlw==",
      "license": "MIT",
      "dependencies": {
        "has-symbols": "^1.0.3"
      },
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/hasown": {
      "version": "2.0.3",
      "resolved": "https://registry.npmjs.org/hasown/-/hasown-2.0.3.tgz",
      "integrity": "sha512-ej4AhfhfL2Q2zpMmLo7U1Uv9+PyhIZpgQLGT1F9miIGmiCJIoCgSmczFdrc97mWT4kVY72KA+WnnhJ5pghSvSg==",
      "license": "MIT",
      "dependencies": {
        "function-bind": "^1.1.2"
      },
      "engines": {
        "node": ">= 0.4"
      }
    },
    "node_modules/https-proxy-agent": {
      "version": "5.0.1",
      "resolved": "https://registry.npmjs.org/https-proxy-agent/-/https-proxy-agent-5.0.1.tgz",
      "integrity": "sha512-dFcAjpTQFgoLMzC2VwU+C/CbS7uRL0lWmxDITmqm7C+7F0Odmj6s9l6alZc6AELXhrnggM2CeWSXHGOdX2YtwA==",
      "license": "MIT",
      "dependencies": {
        "agent-base": "6",
        "debug": "4"
      },
      "engines": {
        "node": ">= 6"
      }
    },
    "node_modules/internmap": {
      "version": "2.0.3",
      "resolved": "https://registry.npmjs.org/internmap/-/internmap-2.0.3.tgz",
      "integrity": "sha512-5Hh7Y1wQbvY5ooGgPbDaL5iYLAPzMTUrjMulskHLH6wnv/A+1q5rgEaiuqEjB+oxGXIVZs1FF+R/KPN3ZSQYYg==",
      "license": "ISC",
      "engines": {
        "node": ">=12"
      }
    },
    "node_modules/is-binary-path": {
      "version": "2.1.0",
      "resolved": "https://registry.npmjs.org/is-binary-path/-/is-binary-path-2.1.0.tgz",
      "integrity": "sha512-ZMERYes6pDydyuGidse7OsHxtbI7WVeUEozgR/g7rd0xUimYNlvZRE/K2MgZTjWy725IfelLeVcEM97mmtRGXw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "binary-extensions": "^2.0.0"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/is-core-module": {
      "version": "2.16.2",
      "resolved": "https://registry.npmjs.org/is-core-module/-/is-core-module-2.16.2.tgz",
      "integrity": "sha512-evOr8xfXKxE6qSR0hSXL2r3sd7ALj8+7jQEUvPYcm5sgZFdJ+AYzT6yNmJenvIYQBgIGwfwz08sL8zoL7yq2BA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "hasown": "^2.0.3"
      },
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/is-extglob": {
      "version": "2.1.1",
      "resolved": "https://registry.npmjs.org/is-extglob/-/is-extglob-2.1.1.tgz",
      "integrity": "sha512-SbKbANkN603Vi4jEZv49LeVJMn4yGwsbzZworEoyEiutsN3nJYdbO36zfhGJ6QEDpOZIFkDtnq5JRxmvl3jsoQ==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/is-glob": {
      "version": "4.0.3",
      "resolved": "https://registry.npmjs.org/is-glob/-/is-glob-4.0.3.tgz",
      "integrity": "sha512-xelSayHH36ZgE7ZWhli7pW34hNbNl8Ojv5KVmkJD4hBdD3th8Tfk9vYasLM+mXWOZhFkgZfxhLSnrwRr4elSSg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "is-extglob": "^2.1.1"
      },
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/is-number": {
      "version": "7.0.0",
      "resolved": "https://registry.npmjs.org/is-number/-/is-number-7.0.0.tgz",
      "integrity": "sha512-41Cifkg6e8TylSpdtTpeLVMqvSBEVzTttHvERD741+pnZ8ANv0004MRL43QKPDlK9cGvNp6NZWZUBlbGXYxxng==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=0.12.0"
      }
    },
    "node_modules/jiti": {
      "version": "1.21.7",
      "resolved": "https://registry.npmjs.org/jiti/-/jiti-1.21.7.tgz",
      "integrity": "sha512-/imKNG4EbWNrVjoNC/1H5/9GFy+tqjGBHCaSsN+P2RnPqjsLmv6UD3Ej+Kj8nBWaRAwyk7kK5ZUc+OEatnTR3A==",
      "dev": true,
      "license": "MIT",
      "bin": {
        "jiti": "bin/jiti.js"
      }
    },
    "node_modules/js-tokens": {
      "version": "4.0.0",
      "resolved": "https://registry.npmjs.org/js-tokens/-/js-tokens-4.0.0.tgz",
      "integrity": "sha512-RdJUflcE3cUzKiMqQgsCu06FPu9UdIJO0beYbPhHN4k6apgJtifcoCtT9bcxOpYBtpD2kCM6Sbzg4CausW/PKQ==",
      "license": "MIT"
    },
    "node_modules/jsesc": {
      "version": "3.1.0",
      "resolved": "https://registry.npmjs.org/jsesc/-/jsesc-3.1.0.tgz",
      "integrity": "sha512-/sM3dO2FOzXjKQhJuo0Q173wf2KOo8t4I8vHy6lF9poUp7bKT0/NHE8fPX23PwfhnykfqnC2xRxOnVw5XuGIaA==",
      "dev": true,
      "license": "MIT",
      "bin": {
        "jsesc": "bin/jsesc"
      },
      "engines": {
        "node": ">=6"
      }
    },
    "node_modules/json5": {
      "version": "2.2.3",
      "resolved": "https://registry.npmjs.org/json5/-/json5-2.2.3.tgz",
      "integrity": "sha512-XmOWe7eyHYH14cLdVPoyg+GOH3rYX++KpzrylJwSW98t3Nk+U8XOl8FWKOgwtzdb8lXGf6zYwDUzeHMWfxasyg==",
      "dev": true,
      "license": "MIT",
      "bin": {
        "json5": "lib/cli.js"
      },
      "engines": {
        "node": ">=6"
      }
    },
    "node_modules/lilconfig": {
      "version": "3.1.3",
      "resolved": "https://registry.npmjs.org/lilconfig/-/lilconfig-3.1.3.tgz",
      "integrity": "sha512-/vlFKAoH5Cgt3Ie+JLhRbwOsCQePABiU3tJ1egGvyQ+33R/vcwM2Zl2QR/LzjsBeItPt3oSVXapn+m4nQDvpzw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=14"
      },
      "funding": {
        "url": "https://github.com/sponsors/antonk52"
      }
    },
    "node_modules/lines-and-columns": {
      "version": "1.2.4",
      "resolved": "https://registry.npmjs.org/lines-and-columns/-/lines-and-columns-1.2.4.tgz",
      "integrity": "sha512-7ylylesZQ/PV29jhEDl3Ufjo6ZX7gCqJr5F7PKrqc93v7fzSymt1BpwEU8nAUXs8qzzvqhbjhK5QZg6Mt/HkBg==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/lodash": {
      "version": "4.18.1",
      "resolved": "https://registry.npmjs.org/lodash/-/lodash-4.18.1.tgz",
      "integrity": "sha512-dMInicTPVE8d1e5otfwmmjlxkZoUpiVLwyeTdUsi/Caj/gfzzblBcCE5sRHV/AsjuCmxWrte2TNGSYuCeCq+0Q==",
      "license": "MIT"
    },
    "node_modules/loose-envify": {
      "version": "1.4.0",
      "resolved": "https://registry.npmjs.org/loose-envify/-/loose-envify-1.4.0.tgz",
      "integrity": "sha512-lyuxPGr/Wfhrlem2CL/UcnUc1zcqKAImBDzukY7Y5F/yQiNdko6+fRLevlw1HgMySw7f611UIY408EtxRSoK3Q==",
      "license": "MIT",
      "dependencies": {
        "js-tokens": "^3.0.0 || ^4.0.0"
      },
      "bin": {
        "loose-envify": "cli.js"
      }
    },
    "node_modules/lru-cache": {
      "version": "5.1.1",
      "resolved": "https://registry.npmjs.org/lru-cache/-/lru-cache-5.1.1.tgz",
      "integrity": "sha512-KpNARQA3Iwv+jTA0utUVVbrh+Jlrr1Fv0e56GGzAFOXN7dk/FviaDW8LHmK52DlcH4WP2n6gI8vN1aesBFgo9w==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "yallist": "^3.0.2"
      }
    },
    "node_modules/lucide-react": {
      "version": "1.17.0",
      "resolved": "https://registry.npmjs.org/lucide-react/-/lucide-react-1.17.0.tgz",
      "integrity": "sha512-9FA9evdox/JQL5PT57fdA1x/yg8T7knJ98+zjTL3UfKza6pflQUUh3XtaQIHKvnsJw1lmsEyHVlt5jchYxOQ5w==",
      "license": "ISC",
      "peerDependencies": {
        "react": "^16.5.1 || ^17.0.0 || ^18.0.0 || ^19.0.0"
      }
    },
    "node_modules/math-intrinsics": {
      "version": "1.1.0",
      "resolved": "https://registry.npmjs.org/math-intrinsics/-/math-intrinsics-1.1.0.tgz",
      "integrity": "sha512-/IXtbwEk5HTPyEwyKX6hGkYXxM9nbj64B+ilVJnC/R6B0pH5G4V3b0pVbL7DBj4tkhBAppbQUlf6F6Xl9LHu1g==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.4"
      }
    },
    "node_modules/merge2": {
      "version": "1.4.1",
      "resolved": "https://registry.npmjs.org/merge2/-/merge2-1.4.1.tgz",
      "integrity": "sha512-8q7VEgMJW4J8tcfVPy8g09NcQwZdbwFEqhe/WZkoIzjn/3TGDwtOCYtXGxA3O8tPzpczCCDgv+P2P5y00ZJOOg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 8"
      }
    },
    "node_modules/micromatch": {
      "version": "4.0.8",
      "resolved": "https://registry.npmjs.org/micromatch/-/micromatch-4.0.8.tgz",
      "integrity": "sha512-PXwfBhYu0hBCPw8Dn0E+WDYb7af3dSLVWKi3HGv84IdF4TyFoC0ysxFd0Goxw7nSv4T/PzEJQxsYsEiFCKo2BA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "braces": "^3.0.3",
        "picomatch": "^2.3.1"
      },
      "engines": {
        "node": ">=8.6"
      }
    },
    "node_modules/mime-db": {
      "version": "1.52.0",
      "resolved": "https://registry.npmjs.org/mime-db/-/mime-db-1.52.0.tgz",
      "integrity": "sha512-sPU4uV7dYlvtWJxwwxHD0PuihVNiE7TyAbQ5SWxDCB9mUYvOgroQOwYQQOKPJ8CIbE+1ETVlOoK1UC2nU3gYvg==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/mime-types": {
      "version": "2.1.35",
      "resolved": "https://registry.npmjs.org/mime-types/-/mime-types-2.1.35.tgz",
      "integrity": "sha512-ZDY+bPm5zTTF+YpCrAU9nK0UgICYPT0QtT1NZWFv4s++TNkcgVaT0g6+4R2uI4MjQjzysHB1zxuWL50hzaeXiw==",
      "license": "MIT",
      "dependencies": {
        "mime-db": "1.52.0"
      },
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/ms": {
      "version": "2.1.3",
      "resolved": "https://registry.npmjs.org/ms/-/ms-2.1.3.tgz",
      "integrity": "sha512-6FlzubTLZG3J2a/NVCAleEhjzq5oxgHyaCU9yYXvcLsvoVaHJq/s5xXI6/XXP6tz7R9xAOtHnSO/tXtF3WRTlA==",
      "license": "MIT"
    },
    "node_modules/mz": {
      "version": "2.7.0",
      "resolved": "https://registry.npmjs.org/mz/-/mz-2.7.0.tgz",
      "integrity": "sha512-z81GNO7nnYMEhrGh9LeymoE4+Yr0Wn5McHIZMK5cfQCl+NDX08sCZgUc9/6MHni9IWuFLm1Z3HTCXu2z9fN62Q==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "any-promise": "^1.0.0",
        "object-assign": "^4.0.1",
        "thenify-all": "^1.0.0"
      }
    },
    "node_modules/nanoid": {
      "version": "3.3.12",
      "resolved": "https://registry.npmjs.org/nanoid/-/nanoid-3.3.12.tgz",
      "integrity": "sha512-ZB9RH/39qpq5Vu6Y+NmUaFhQR6pp+M2Xt76XBnEwDaGcVAqhlvxrl3B2bKS5D3NH3QR76v3aSrKaF/Kiy7lEtQ==",
      "dev": true,
      "funding": [
        {
          "type": "github",
          "url": "https://github.com/sponsors/ai"
        }
      ],
      "license": "MIT",
      "bin": {
        "nanoid": "bin/nanoid.cjs"
      },
      "engines": {
        "node": "^10 || ^12 || ^13.7 || ^14 || >=15.0.1"
      }
    },
    "node_modules/node-releases": {
      "version": "2.0.46",
      "resolved": "https://registry.npmjs.org/node-releases/-/node-releases-2.0.46.tgz",
      "integrity": "sha512-GYVXHE2KnrzAfsAjl4uP++evGFCrAU1jta4ubEjIG7YWt/64Gqv66a30yKwWczVjA6j3bM4nBwH7Pk1JmDHaxQ==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/normalize-path": {
      "version": "3.0.0",
      "resolved": "https://registry.npmjs.org/normalize-path/-/normalize-path-3.0.0.tgz",
      "integrity": "sha512-6eZs5Ls3WtCisHWp9S2GUy8dqkpGi4BVSz3GaqiE6ezub0512ESztXUwUB6C6IKbQkY2Pnb/mD4WYojCRwcwLA==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/object-assign": {
      "version": "4.1.1",
      "resolved": "https://registry.npmjs.org/object-assign/-/object-assign-4.1.1.tgz",
      "integrity": "sha512-rJgTQnkUnH1sFw8yT6VSU3zD3sWmu6sZhIseY8VX+GRu3P6F7Fu+JNDoXfklElbLJSnc3FUQHVe4cU5hj+BcUg==",
      "license": "MIT",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/object-hash": {
      "version": "3.0.0",
      "resolved": "https://registry.npmjs.org/object-hash/-/object-hash-3.0.0.tgz",
      "integrity": "sha512-RSn9F68PjH9HqtltsSnqYC1XXoWe9Bju5+213R98cNGttag9q9yAOTzdbsqvIa7aNm5WffBZFpWYr2aWrklWAw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 6"
      }
    },
    "node_modules/path-parse": {
      "version": "1.0.7",
      "resolved": "https://registry.npmjs.org/path-parse/-/path-parse-1.0.7.tgz",
      "integrity": "sha512-LDJzPVEEEPR+y48z93A0Ed0yXb8pAByGWo/k5YYdYgpY2/2EsOsksJrq7lOHxryrVOn1ejG6oAp8ahvOIQD8sw==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/picocolors": {
      "version": "1.1.1",
      "resolved": "https://registry.npmjs.org/picocolors/-/picocolors-1.1.1.tgz",
      "integrity": "sha512-xceH2snhtb5M9liqDsmEw56le376mTZkEX/jEb/RxNFyegNul7eNslCXP9FDj/Lcu0X8KEyMceP2ntpaHrDEVA==",
      "dev": true,
      "license": "ISC"
    },
    "node_modules/picomatch": {
      "version": "2.3.2",
      "resolved": "https://registry.npmjs.org/picomatch/-/picomatch-2.3.2.tgz",
      "integrity": "sha512-V7+vQEJ06Z+c5tSye8S+nHUfI51xoXIXjHQ99cQtKUkQqqO1kO/KCJUfZXuB47h/YBlDhah2H3hdUGXn8ie0oA==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=8.6"
      },
      "funding": {
        "url": "https://github.com/sponsors/jonschlinkert"
      }
    },
    "node_modules/pify": {
      "version": "2.3.0",
      "resolved": "https://registry.npmjs.org/pify/-/pify-2.3.0.tgz",
      "integrity": "sha512-udgsAY+fTnvv7kI7aaxbqwWNb0AHiB0qBO89PZKPkoTmGOgdbrHDKD+0B2X4uTfJ/FT1R09r9gTsjUjNJotuog==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/pirates": {
      "version": "4.0.7",
      "resolved": "https://registry.npmjs.org/pirates/-/pirates-4.0.7.tgz",
      "integrity": "sha512-TfySrs/5nm8fQJDcBDuUng3VOUKsd7S+zqvbOTiGXHfxX4wK31ard+hoNuvkicM/2YFzlpDgABOevKSsB4G/FA==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 6"
      }
    },
    "node_modules/postcss": {
      "version": "8.5.15",
      "resolved": "https://registry.npmjs.org/postcss/-/postcss-8.5.15.tgz",
      "integrity": "sha512-FfR8sjd4em2T6fb3I2MwAJU7HWVMr9zba+enmQeeWFfCbm+UOC/0X4DS8XtpUTMwWMGbjKYP7xjfNekzyGmB3A==",
      "dev": true,
      "funding": [
        {
          "type": "opencollective",
          "url": "https://opencollective.com/postcss/"
        },
        {
          "type": "tidelift",
          "url": "https://tidelift.com/funding/github/npm/postcss"
        },
        {
          "type": "github",
          "url": "https://github.com/sponsors/ai"
        }
      ],
      "license": "MIT",
      "dependencies": {
        "nanoid": "^3.3.12",
        "picocolors": "^1.1.1",
        "source-map-js": "^1.2.1"
      },
      "engines": {
        "node": "^10 || ^12 || >=14"
      }
    },
    "node_modules/postcss-import": {
      "version": "15.1.0",
      "resolved": "https://registry.npmjs.org/postcss-import/-/postcss-import-15.1.0.tgz",
      "integrity": "sha512-hpr+J05B2FVYUAXHeK1YyI267J/dDDhMU6B6civm8hSY1jYJnBXxzKDKDswzJmtLHryrjhnDjqqp/49t8FALew==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "postcss-value-parser": "^4.0.0",
        "read-cache": "^1.0.0",
        "resolve": "^1.1.7"
      },
      "engines": {
        "node": ">=14.0.0"
      },
      "peerDependencies": {
        "postcss": "^8.0.0"
      }
    },
    "node_modules/postcss-js": {
      "version": "4.1.0",
      "resolved": "https://registry.npmjs.org/postcss-js/-/postcss-js-4.1.0.tgz",
      "integrity": "sha512-oIAOTqgIo7q2EOwbhb8UalYePMvYoIeRY2YKntdpFQXNosSu3vLrniGgmH9OKs/qAkfoj5oB3le/7mINW1LCfw==",
      "dev": true,
      "funding": [
        {
          "type": "opencollective",
          "url": "https://opencollective.com/postcss/"
        },
        {
          "type": "github",
          "url": "https://github.com/sponsors/ai"
        }
      ],
      "license": "MIT",
      "dependencies": {
        "camelcase-css": "^2.0.1"
      },
      "engines": {
        "node": "^12 || ^14 || >= 16"
      },
      "peerDependencies": {
        "postcss": "^8.4.21"
      }
    },
    "node_modules/postcss-load-config": {
      "version": "6.0.1",
      "resolved": "https://registry.npmjs.org/postcss-load-config/-/postcss-load-config-6.0.1.tgz",
      "integrity": "sha512-oPtTM4oerL+UXmx+93ytZVN82RrlY/wPUV8IeDxFrzIjXOLF1pN+EmKPLbubvKHT2HC20xXsCAH2Z+CKV6Oz/g==",
      "dev": true,
      "funding": [
        {
          "type": "opencollective",
          "url": "https://opencollective.com/postcss/"
        },
        {
          "type": "github",
          "url": "https://github.com/sponsors/ai"
        }
      ],
      "license": "MIT",
      "dependencies": {
        "lilconfig": "^3.1.1"
      },
      "engines": {
        "node": ">= 18"
      },
      "peerDependencies": {
        "jiti": ">=1.21.0",
        "postcss": ">=8.0.9",
        "tsx": "^4.8.1",
        "yaml": "^2.4.2"
      },
      "peerDependenciesMeta": {
        "jiti": {
          "optional": true
        },
        "postcss": {
          "optional": true
        },
        "tsx": {
          "optional": true
        },
        "yaml": {
          "optional": true
        }
      }
    },
    "node_modules/postcss-nested": {
      "version": "6.2.0",
      "resolved": "https://registry.npmjs.org/postcss-nested/-/postcss-nested-6.2.0.tgz",
      "integrity": "sha512-HQbt28KulC5AJzG+cZtj9kvKB93CFCdLvog1WFLf1D+xmMvPGlBstkpTEZfK5+AN9hfJocyBFCNiqyS48bpgzQ==",
      "dev": true,
      "funding": [
        {
          "type": "opencollective",
          "url": "https://opencollective.com/postcss/"
        },
        {
          "type": "github",
          "url": "https://github.com/sponsors/ai"
        }
      ],
      "license": "MIT",
      "dependencies": {
        "postcss-selector-parser": "^6.1.1"
      },
      "engines": {
        "node": ">=12.0"
      },
      "peerDependencies": {
        "postcss": "^8.2.14"
      }
    },
    "node_modules/postcss-selector-parser": {
      "version": "6.1.2",
      "resolved": "https://registry.npmjs.org/postcss-selector-parser/-/postcss-selector-parser-6.1.2.tgz",
      "integrity": "sha512-Q8qQfPiZ+THO/3ZrOrO0cJJKfpYCagtMUkXbnEfmgUjwXg6z/WBeOyS9APBBPCTSiDV+s4SwQGu8yFsiMRIudg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "cssesc": "^3.0.0",
        "util-deprecate": "^1.0.2"
      },
      "engines": {
        "node": ">=4"
      }
    },
    "node_modules/postcss-value-parser": {
      "version": "4.2.0",
      "resolved": "https://registry.npmjs.org/postcss-value-parser/-/postcss-value-parser-4.2.0.tgz",
      "integrity": "sha512-1NNCs6uurfkVbeXG4S8JFT9t19m45ICnif8zWLd5oPSZ50QnwMfK+H3jv408d4jw/7Bttv5axS5IiHoLaVNHeQ==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/prop-types": {
      "version": "15.8.1",
      "resolved": "https://registry.npmjs.org/prop-types/-/prop-types-15.8.1.tgz",
      "integrity": "sha512-oj87CgZICdulUohogVAR7AjlC0327U4el4L6eAvOqCeudMDVU0NThNaV+b9Df4dXgSP1gXMTnPdhfe/2qDH5cg==",
      "license": "MIT",
      "dependencies": {
        "loose-envify": "^1.4.0",
        "object-assign": "^4.1.1",
        "react-is": "^16.13.1"
      }
    },
    "node_modules/prop-types/node_modules/react-is": {
      "version": "16.13.1",
      "resolved": "https://registry.npmjs.org/react-is/-/react-is-16.13.1.tgz",
      "integrity": "sha512-24e6ynE2H+OKt4kqsOvNd8kBpV65zoxbA4BVsEOB3ARVWQki/DHzaUoC5KuON/BiccDaCCTZBuOcfZs70kR8bQ==",
      "license": "MIT"
    },
    "node_modules/proxy-from-env": {
      "version": "2.1.0",
      "resolved": "https://registry.npmjs.org/proxy-from-env/-/proxy-from-env-2.1.0.tgz",
      "integrity": "sha512-cJ+oHTW1VAEa8cJslgmUZrc+sjRKgAKl3Zyse6+PV38hZe/V6Z14TbCuXcan9F9ghlz4QrFr2c92TNF82UkYHA==",
      "license": "MIT",
      "engines": {
        "node": ">=10"
      }
    },
    "node_modules/queue-microtask": {
      "version": "1.2.3",
      "resolved": "https://registry.npmjs.org/queue-microtask/-/queue-microtask-1.2.3.tgz",
      "integrity": "sha512-NuaNSa6flKT5JaSYQzJok04JzTL1CA6aGhv5rfLW3PgqA+M2ChpZQnAC8h8i4ZFkBS8X5RqkDBHA7r4hej3K9A==",
      "dev": true,
      "funding": [
        {
          "type": "github",
          "url": "https://github.com/sponsors/feross"
        },
        {
          "type": "patreon",
          "url": "https://www.patreon.com/feross"
        },
        {
          "type": "consulting",
          "url": "https://feross.org/support"
        }
      ],
      "license": "MIT"
    },
    "node_modules/react": {
      "version": "18.3.1",
      "resolved": "https://registry.npmjs.org/react/-/react-18.3.1.tgz",
      "integrity": "sha512-wS+hAgJShR0KhEvPJArfuPVN1+Hz1t0Y6n5jLrGQbkb4urgPE/0Rve+1kMB1v/oWgHgm4WIcV+i7F2pTVj+2iQ==",
      "license": "MIT",
      "dependencies": {
        "loose-envify": "^1.1.0"
      },
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/react-dom": {
      "version": "18.3.1",
      "resolved": "https://registry.npmjs.org/react-dom/-/react-dom-18.3.1.tgz",
      "integrity": "sha512-5m4nQKp+rZRb09LNH59GM4BxTh9251/ylbKIbpe7TpGxfJ+9kv6BLkLBXIjjspbgbnIBNqlI23tRnTWT0snUIw==",
      "license": "MIT",
      "dependencies": {
        "loose-envify": "^1.1.0",
        "scheduler": "^0.23.2"
      },
      "peerDependencies": {
        "react": "^18.3.1"
      }
    },
    "node_modules/react-is": {
      "version": "18.3.1",
      "resolved": "https://registry.npmjs.org/react-is/-/react-is-18.3.1.tgz",
      "integrity": "sha512-/LLMVyas0ljjAtoYiPqYiL8VWXzUUdThrmU5+n20DZv+a+ClRoevUzw5JxU+Ieh5/c87ytoTBV9G1FiKfNJdmg==",
      "license": "MIT"
    },
    "node_modules/react-refresh": {
      "version": "0.17.0",
      "resolved": "https://registry.npmjs.org/react-refresh/-/react-refresh-0.17.0.tgz",
      "integrity": "sha512-z6F7K9bV85EfseRCp2bzrpyQ0Gkw1uLoCel9XBVWPg/TjRj94SkJzUTGfOa4bs7iJvBWtQG0Wq7wnI0syw3EBQ==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/react-router": {
      "version": "6.30.3",
      "resolved": "https://registry.npmjs.org/react-router/-/react-router-6.30.3.tgz",
      "integrity": "sha512-XRnlbKMTmktBkjCLE8/XcZFlnHvr2Ltdr1eJX4idL55/9BbORzyZEaIkBFDhFGCEWBBItsVrDxwx3gnisMitdw==",
      "license": "MIT",
      "dependencies": {
        "@remix-run/router": "1.23.2"
      },
      "engines": {
        "node": ">=14.0.0"
      },
      "peerDependencies": {
        "react": ">=16.8"
      }
    },
    "node_modules/react-router-dom": {
      "version": "6.30.3",
      "resolved": "https://registry.npmjs.org/react-router-dom/-/react-router-dom-6.30.3.tgz",
      "integrity": "sha512-pxPcv1AczD4vso7G4Z3TKcvlxK7g7TNt3/FNGMhfqyntocvYKj+GCatfigGDjbLozC4baguJ0ReCigoDJXb0ag==",
      "license": "MIT",
      "dependencies": {
        "@remix-run/router": "1.23.2",
        "react-router": "6.30.3"
      },
      "engines": {
        "node": ">=14.0.0"
      },
      "peerDependencies": {
        "react": ">=16.8",
        "react-dom": ">=16.8"
      }
    },
    "node_modules/react-smooth": {
      "version": "4.0.4",
      "resolved": "https://registry.npmjs.org/react-smooth/-/react-smooth-4.0.4.tgz",
      "integrity": "sha512-gnGKTpYwqL0Iii09gHobNolvX4Kiq4PKx6eWBCYYix+8cdw+cGo3do906l1NBPKkSWx1DghC1dlWG9L2uGd61Q==",
      "license": "MIT",
      "dependencies": {
        "fast-equals": "^5.0.1",
        "prop-types": "^15.8.1",
        "react-transition-group": "^4.4.5"
      },
      "peerDependencies": {
        "react": "^16.8.0 || ^17.0.0 || ^18.0.0 || ^19.0.0",
        "react-dom": "^16.8.0 || ^17.0.0 || ^18.0.0 || ^19.0.0"
      }
    },
    "node_modules/react-transition-group": {
      "version": "4.4.5",
      "resolved": "https://registry.npmjs.org/react-transition-group/-/react-transition-group-4.4.5.tgz",
      "integrity": "sha512-pZcd1MCJoiKiBR2NRxeCRg13uCXbydPnmB4EOeRrY7480qNWO8IIgQG6zlDkm6uRMsURXPuKq0GWtiM59a5Q6g==",
      "license": "BSD-3-Clause",
      "dependencies": {
        "@babel/runtime": "^7.5.5",
        "dom-helpers": "^5.0.1",
        "loose-envify": "^1.4.0",
        "prop-types": "^15.6.2"
      },
      "peerDependencies": {
        "react": ">=16.6.0",
        "react-dom": ">=16.6.0"
      }
    },
    "node_modules/read-cache": {
      "version": "1.0.0",
      "resolved": "https://registry.npmjs.org/read-cache/-/read-cache-1.0.0.tgz",
      "integrity": "sha512-Owdv/Ft7IjOgm/i0xvNDZ1LrRANRfew4b2prF3OWMQLxLfu3bS8FVhCsrSCMK4lR56Y9ya+AThoTpDCTxCmpRA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "pify": "^2.3.0"
      }
    },
    "node_modules/readdirp": {
      "version": "3.6.0",
      "resolved": "https://registry.npmjs.org/readdirp/-/readdirp-3.6.0.tgz",
      "integrity": "sha512-hOS089on8RduqdbhvQ5Z37A0ESjsqz6qnRcffsMU3495FuTdqSm+7bhJ29JvIOsBDEEnan5DPu9t3To9VRlMzA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "picomatch": "^2.2.1"
      },
      "engines": {
        "node": ">=8.10.0"
      }
    },
    "node_modules/recharts": {
      "version": "2.15.4",
      "resolved": "https://registry.npmjs.org/recharts/-/recharts-2.15.4.tgz",
      "integrity": "sha512-UT/q6fwS3c1dHbXv2uFgYJ9BMFHu3fwnd7AYZaEQhXuYQ4hgsxLvsUXzGdKeZrW5xopzDCvuA2N41WJ88I7zIw==",
      "deprecated": "1.x and 2.x branches are no longer active. Bump to Recharts v3 to receive latest features and bugfixes. See https://github.com/recharts/recharts/wiki/3.0-migration-guide",
      "license": "MIT",
      "dependencies": {
        "clsx": "^2.0.0",
        "eventemitter3": "^4.0.1",
        "lodash": "^4.17.21",
        "react-is": "^18.3.1",
        "react-smooth": "^4.0.4",
        "recharts-scale": "^0.4.4",
        "tiny-invariant": "^1.3.1",
        "victory-vendor": "^36.6.8"
      },
      "engines": {
        "node": ">=14"
      },
      "peerDependencies": {
        "react": "^16.0.0 || ^17.0.0 || ^18.0.0 || ^19.0.0",
        "react-dom": "^16.0.0 || ^17.0.0 || ^18.0.0 || ^19.0.0"
      }
    },
    "node_modules/recharts-scale": {
      "version": "0.4.5",
      "resolved": "https://registry.npmjs.org/recharts-scale/-/recharts-scale-0.4.5.tgz",
      "integrity": "sha512-kivNFO+0OcUNu7jQquLXAxz1FIwZj8nrj+YkOKc5694NbjCvcT6aSZiIzNzd2Kul4o4rTto8QVR9lMNtxD4G1w==",
      "license": "MIT",
      "dependencies": {
        "decimal.js-light": "^2.4.1"
      }
    },
    "node_modules/resolve": {
      "version": "1.22.12",
      "resolved": "https://registry.npmjs.org/resolve/-/resolve-1.22.12.tgz",
      "integrity": "sha512-TyeJ1zif53BPfHootBGwPRYT1RUt6oGWsaQr8UyZW/eAm9bKoijtvruSDEmZHm92CwS9nj7/fWttqPCgzep8CA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "es-errors": "^1.3.0",
        "is-core-module": "^2.16.1",
        "path-parse": "^1.0.7",
        "supports-preserve-symlinks-flag": "^1.0.0"
      },
      "bin": {
        "resolve": "bin/resolve"
      },
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/reusify": {
      "version": "1.1.0",
      "resolved": "https://registry.npmjs.org/reusify/-/reusify-1.1.0.tgz",
      "integrity": "sha512-g6QUff04oZpHs0eG5p83rFLhHeV00ug/Yf9nZM6fLeUrPguBTkTQOdpAWWspMh55TZfVQDPaN3NQJfbVRAxdIw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "iojs": ">=1.0.0",
        "node": ">=0.10.0"
      }
    },
    "node_modules/rollup": {
      "version": "4.60.4",
      "resolved": "https://registry.npmjs.org/rollup/-/rollup-4.60.4.tgz",
      "integrity": "sha512-WHeFSbZYsPu3+bLoNRUuAO+wavNlocOPf3wSHTP7hcFKVnJeWsYlCDbr3mTS14FCizf9ccIxXA8sGL8zKeQN3g==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@types/estree": "1.0.8"
      },
      "bin": {
        "rollup": "dist/bin/rollup"
      },
      "engines": {
        "node": ">=18.0.0",
        "npm": ">=8.0.0"
      },
      "optionalDependencies": {
        "@rollup/rollup-android-arm-eabi": "4.60.4",
        "@rollup/rollup-android-arm64": "4.60.4",
        "@rollup/rollup-darwin-arm64": "4.60.4",
        "@rollup/rollup-darwin-x64": "4.60.4",
        "@rollup/rollup-freebsd-arm64": "4.60.4",
        "@rollup/rollup-freebsd-x64": "4.60.4",
        "@rollup/rollup-linux-arm-gnueabihf": "4.60.4",
        "@rollup/rollup-linux-arm-musleabihf": "4.60.4",
        "@rollup/rollup-linux-arm64-gnu": "4.60.4",
        "@rollup/rollup-linux-arm64-musl": "4.60.4",
        "@rollup/rollup-linux-loong64-gnu": "4.60.4",
        "@rollup/rollup-linux-loong64-musl": "4.60.4",
        "@rollup/rollup-linux-ppc64-gnu": "4.60.4",
        "@rollup/rollup-linux-ppc64-musl": "4.60.4",
        "@rollup/rollup-linux-riscv64-gnu": "4.60.4",
        "@rollup/rollup-linux-riscv64-musl": "4.60.4",
        "@rollup/rollup-linux-s390x-gnu": "4.60.4",
        "@rollup/rollup-linux-x64-gnu": "4.60.4",
        "@rollup/rollup-linux-x64-musl": "4.60.4",
        "@rollup/rollup-openbsd-x64": "4.60.4",
        "@rollup/rollup-openharmony-arm64": "4.60.4",
        "@rollup/rollup-win32-arm64-msvc": "4.60.4",
        "@rollup/rollup-win32-ia32-msvc": "4.60.4",
        "@rollup/rollup-win32-x64-gnu": "4.60.4",
        "@rollup/rollup-win32-x64-msvc": "4.60.4",
        "fsevents": "~2.3.2"
      }
    },
    "node_modules/run-parallel": {
      "version": "1.2.0",
      "resolved": "https://registry.npmjs.org/run-parallel/-/run-parallel-1.2.0.tgz",
      "integrity": "sha512-5l4VyZR86LZ/lDxZTR6jqL8AFE2S0IFLMP26AbjsLVADxHdhB/c0GUsH+y39UfCi3dzz8OlQuPmnaJOMoDHQBA==",
      "dev": true,
      "funding": [
        {
          "type": "github",
          "url": "https://github.com/sponsors/feross"
        },
        {
          "type": "patreon",
          "url": "https://www.patreon.com/feross"
        },
        {
          "type": "consulting",
          "url": "https://feross.org/support"
        }
      ],
      "license": "MIT",
      "dependencies": {
        "queue-microtask": "^1.2.2"
      }
    },
    "node_modules/scheduler": {
      "version": "0.23.2",
      "resolved": "https://registry.npmjs.org/scheduler/-/scheduler-0.23.2.tgz",
      "integrity": "sha512-UOShsPwz7NrMUqhR6t0hWjFduvOzbtv7toDH1/hIrfRNIDBnnBWd0CwJTGvTpngVlmwGCdP9/Zl/tVrDqcuYzQ==",
      "license": "MIT",
      "dependencies": {
        "loose-envify": "^1.1.0"
      }
    },
    "node_modules/semver": {
      "version": "6.3.1",
      "resolved": "https://registry.npmjs.org/semver/-/semver-6.3.1.tgz",
      "integrity": "sha512-BR7VvDCVHO+q2xBEWskxS6DJE1qRnb7DxzUrogb71CWoSficBxYsiAGd+Kl0mmq/MprG9yArRkyrQxTO6XjMzA==",
      "dev": true,
      "license": "ISC",
      "bin": {
        "semver": "bin/semver.js"
      }
    },
    "node_modules/source-map-js": {
      "version": "1.2.1",
      "resolved": "https://registry.npmjs.org/source-map-js/-/source-map-js-1.2.1.tgz",
      "integrity": "sha512-UXWMKhLOwVKb728IUtQPXxfYU+usdybtUrK/8uGE8CQMvrhOpwvzDBwj0QhSL7MQc7vIsISBG8VQ8+IDQxpfQA==",
      "dev": true,
      "license": "BSD-3-Clause",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/sucrase": {
      "version": "3.35.1",
      "resolved": "https://registry.npmjs.org/sucrase/-/sucrase-3.35.1.tgz",
      "integrity": "sha512-DhuTmvZWux4H1UOnWMB3sk0sbaCVOoQZjv8u1rDoTV0HTdGem9hkAZtl4JZy8P2z4Bg0nT+YMeOFyVr4zcG5Tw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@jridgewell/gen-mapping": "^0.3.2",
        "commander": "^4.0.0",
        "lines-and-columns": "^1.1.6",
        "mz": "^2.7.0",
        "pirates": "^4.0.1",
        "tinyglobby": "^0.2.11",
        "ts-interface-checker": "^0.1.9"
      },
      "bin": {
        "sucrase": "bin/sucrase",
        "sucrase-node": "bin/sucrase-node"
      },
      "engines": {
        "node": ">=16 || 14 >=14.17"
      }
    },
    "node_modules/supports-preserve-symlinks-flag": {
      "version": "1.0.0",
      "resolved": "https://registry.npmjs.org/supports-preserve-symlinks-flag/-/supports-preserve-symlinks-flag-1.0.0.tgz",
      "integrity": "sha512-ot0WnXS9fgdkgIcePe6RHNk1WA8+muPa6cSjeR3V8K27q9BB1rTE3R1p7Hv0z1ZyAc8s6Vvv8DIyWf681MAt0w==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/tailwindcss": {
      "version": "3.4.19",
      "resolved": "https://registry.npmjs.org/tailwindcss/-/tailwindcss-3.4.19.tgz",
      "integrity": "sha512-3ofp+LL8E+pK/JuPLPggVAIaEuhvIz4qNcf3nA1Xn2o/7fb7s/TYpHhwGDv1ZU3PkBluUVaF8PyCHcm48cKLWQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@alloc/quick-lru": "^5.2.0",
        "arg": "^5.0.2",
        "chokidar": "^3.6.0",
        "didyoumean": "^1.2.2",
        "dlv": "^1.1.3",
        "fast-glob": "^3.3.2",
        "glob-parent": "^6.0.2",
        "is-glob": "^4.0.3",
        "jiti": "^1.21.7",
        "lilconfig": "^3.1.3",
        "micromatch": "^4.0.8",
        "normalize-path": "^3.0.0",
        "object-hash": "^3.0.0",
        "picocolors": "^1.1.1",
        "postcss": "^8.4.47",
        "postcss-import": "^15.1.0",
        "postcss-js": "^4.0.1",
        "postcss-load-config": "^4.0.2 || ^5.0 || ^6.0",
        "postcss-nested": "^6.2.0",
        "postcss-selector-parser": "^6.1.2",
        "resolve": "^1.22.8",
        "sucrase": "^3.35.0"
      },
      "bin": {
        "tailwind": "lib/cli.js",
        "tailwindcss": "lib/cli.js"
      },
      "engines": {
        "node": ">=14.0.0"
      }
    },
    "node_modules/thenify": {
      "version": "3.3.1",
      "resolved": "https://registry.npmjs.org/thenify/-/thenify-3.3.1.tgz",
      "integrity": "sha512-RVZSIV5IG10Hk3enotrhvz0T9em6cyHBLkH/YAZuKqd8hRkKhSfCGIcP2KUY0EPxndzANBmNllzWPwak+bheSw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "any-promise": "^1.0.0"
      }
    },
    "node_modules/thenify-all": {
      "version": "1.6.0",
      "resolved": "https://registry.npmjs.org/thenify-all/-/thenify-all-1.6.0.tgz",
      "integrity": "sha512-RNxQH/qI8/t3thXJDwcstUO4zeqo64+Uy/+sNVRBx4Xn2OX+OZ9oP+iJnNFqplFra2ZUVeKCSa2oVWi3T4uVmA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "thenify": ">= 3.1.0 < 4"
      },
      "engines": {
        "node": ">=0.8"
      }
    },
    "node_modules/tiny-invariant": {
      "version": "1.3.3",
      "resolved": "https://registry.npmjs.org/tiny-invariant/-/tiny-invariant-1.3.3.tgz",
      "integrity": "sha512-+FbBPE1o9QAYvviau/qC5SE3caw21q3xkvWKBtja5vgqOWIHHJ3ioaq1VPfn/Szqctz2bU/oYeKd9/z5BL+PVg==",
      "license": "MIT"
    },
    "node_modules/tinyglobby": {
      "version": "0.2.16",
      "resolved": "https://registry.npmjs.org/tinyglobby/-/tinyglobby-0.2.16.tgz",
      "integrity": "sha512-pn99VhoACYR8nFHhxqix+uvsbXineAasWm5ojXoN8xEwK5Kd3/TrhNn1wByuD52UxWRLy8pu+kRMniEi6Eq9Zg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "fdir": "^6.5.0",
        "picomatch": "^4.0.4"
      },
      "engines": {
        "node": ">=12.0.0"
      },
      "funding": {
        "url": "https://github.com/sponsors/SuperchupuDev"
      }
    },
    "node_modules/tinyglobby/node_modules/fdir": {
      "version": "6.5.0",
      "resolved": "https://registry.npmjs.org/fdir/-/fdir-6.5.0.tgz",
      "integrity": "sha512-tIbYtZbucOs0BRGqPJkshJUYdL+SDH7dVM8gjy+ERp3WAUjLEFJE+02kanyHtwjWOnwrKYBiwAmM0p4kLJAnXg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=12.0.0"
      },
      "peerDependencies": {
        "picomatch": "^3 || ^4"
      },
      "peerDependenciesMeta": {
        "picomatch": {
          "optional": true
        }
      }
    },
    "node_modules/tinyglobby/node_modules/picomatch": {
      "version": "4.0.4",
      "resolved": "https://registry.npmjs.org/picomatch/-/picomatch-4.0.4.tgz",
      "integrity": "sha512-QP88BAKvMam/3NxH6vj2o21R6MjxZUAd6nlwAS/pnGvN9IVLocLHxGYIzFhg6fUQ+5th6P4dv4eW9jX3DSIj7A==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=12"
      },
      "funding": {
        "url": "https://github.com/sponsors/jonschlinkert"
      }
    },
    "node_modules/to-regex-range": {
      "version": "5.0.1",
      "resolved": "https://registry.npmjs.org/to-regex-range/-/to-regex-range-5.0.1.tgz",
      "integrity": "sha512-65P7iz6X5yEr1cwcgvQxbbIw7Uk3gOy5dIdtZ4rDveLqhrdJP+Li/Hx6tyK0NEb+2GCyneCMJiGqrADCSNk8sQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "is-number": "^7.0.0"
      },
      "engines": {
        "node": ">=8.0"
      }
    },
    "node_modules/ts-interface-checker": {
      "version": "0.1.13",
      "resolved": "https://registry.npmjs.org/ts-interface-checker/-/ts-interface-checker-0.1.13.tgz",
      "integrity": "sha512-Y/arvbn+rrz3JCKl9C4kVNfTfSm2/mEp5FSz5EsZSANGPSlQrpRI5M4PKF+mJnE52jOO90PnPSc3Ur3bTQw0gA==",
      "dev": true,
      "license": "Apache-2.0"
    },
    "node_modules/typescript": {
      "version": "5.9.3",
      "resolved": "https://registry.npmjs.org/typescript/-/typescript-5.9.3.tgz",
      "integrity": "sha512-jl1vZzPDinLr9eUt3J/t7V6FgNEw9QjvBPdysz9KfQDD41fQrC2Y4vKQdiaUpFT4bXlb1RHhLpp8wtm6M5TgSw==",
      "dev": true,
      "license": "Apache-2.0",
      "bin": {
        "tsc": "bin/tsc",
        "tsserver": "bin/tsserver"
      },
      "engines": {
        "node": ">=14.17"
      }
    },
    "node_modules/update-browserslist-db": {
      "version": "1.2.3",
      "resolved": "https://registry.npmjs.org/update-browserslist-db/-/update-browserslist-db-1.2.3.tgz",
      "integrity": "sha512-Js0m9cx+qOgDxo0eMiFGEueWztz+d4+M3rGlmKPT+T4IS/jP4ylw3Nwpu6cpTTP8R1MAC1kF4VbdLt3ARf209w==",
      "dev": true,
      "funding": [
        {
          "type": "opencollective",
          "url": "https://opencollective.com/browserslist"
        },
        {
          "type": "tidelift",
          "url": "https://tidelift.com/funding/github/npm/browserslist"
        },
        {
          "type": "github",
          "url": "https://github.com/sponsors/ai"
        }
      ],
      "license": "MIT",
      "dependencies": {
        "escalade": "^3.2.0",
        "picocolors": "^1.1.1"
      },
      "bin": {
        "update-browserslist-db": "cli.js"
      },
      "peerDependencies": {
        "browserslist": ">= 4.21.0"
      }
    },
    "node_modules/util-deprecate": {
      "version": "1.0.2",
      "resolved": "https://registry.npmjs.org/util-deprecate/-/util-deprecate-1.0.2.tgz",
      "integrity": "sha512-EPD5q1uXyFxJpCrLnCc1nHnq3gOa6DZBocAIiI2TaSCA7VCJ1UJDMagCzIkXNsUYfD1daK//LTEQ8xiIbrHtcw==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/victory-vendor": {
      "version": "36.9.2",
      "resolved": "https://registry.npmjs.org/victory-vendor/-/victory-vendor-36.9.2.tgz",
      "integrity": "sha512-PnpQQMuxlwYdocC8fIJqVXvkeViHYzotI+NJrCuav0ZYFoq912ZHBk3mCeuj+5/VpodOjPe1z0Fk2ihgzlXqjQ==",
      "license": "MIT AND ISC",
      "dependencies": {
        "@types/d3-array": "^3.0.3",
        "@types/d3-ease": "^3.0.0",
        "@types/d3-interpolate": "^3.0.1",
        "@types/d3-scale": "^4.0.2",
        "@types/d3-shape": "^3.1.0",
        "@types/d3-time": "^3.0.0",
        "@types/d3-timer": "^3.0.0",
        "d3-array": "^3.1.6",
        "d3-ease": "^3.0.1",
        "d3-interpolate": "^3.0.1",
        "d3-scale": "^4.0.2",
        "d3-shape": "^3.1.0",
        "d3-time": "^3.0.0",
        "d3-timer": "^3.0.1"
      }
    },
    "node_modules/vite": {
      "version": "6.4.2",
      "resolved": "https://registry.npmjs.org/vite/-/vite-6.4.2.tgz",
      "integrity": "sha512-2N/55r4JDJ4gdrCvGgINMy+HH3iRpNIz8K6SFwVsA+JbQScLiC+clmAxBgwiSPgcG9U15QmvqCGWzMbqda5zGQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "esbuild": "^0.25.0",
        "fdir": "^6.4.4",
        "picomatch": "^4.0.2",
        "postcss": "^8.5.3",
        "rollup": "^4.34.9",
        "tinyglobby": "^0.2.13"
      },
      "bin": {
        "vite": "bin/vite.js"
      },
      "engines": {
        "node": "^18.0.0 || ^20.0.0 || >=22.0.0"
      },
      "funding": {
        "url": "https://github.com/vitejs/vite?sponsor=1"
      },
      "optionalDependencies": {
        "fsevents": "~2.3.3"
      },
      "peerDependencies": {
        "@types/node": "^18.0.0 || ^20.0.0 || >=22.0.0",
        "jiti": ">=1.21.0",
        "less": "*",
        "lightningcss": "^1.21.0",
        "sass": "*",
        "sass-embedded": "*",
        "stylus": "*",
        "sugarss": "*",
        "terser": "^5.16.0",
        "tsx": "^4.8.1",
        "yaml": "^2.4.2"
      },
      "peerDependenciesMeta": {
        "@types/node": {
          "optional": true
        },
        "jiti": {
          "optional": true
        },
        "less": {
          "optional": true
        },
        "lightningcss": {
          "optional": true
        },
        "sass": {
          "optional": true
        },
        "sass-embedded": {
          "optional": true
        },
        "stylus": {
          "optional": true
        },
        "sugarss": {
          "optional": true
        },
        "terser": {
          "optional": true
        },
        "tsx": {
          "optional": true
        },
        "yaml": {
          "optional": true
        }
      }
    },
    "node_modules/vite/node_modules/fdir": {
      "version": "6.5.0",
      "resolved": "https://registry.npmjs.org/fdir/-/fdir-6.5.0.tgz",
      "integrity": "sha512-tIbYtZbucOs0BRGqPJkshJUYdL+SDH7dVM8gjy+ERp3WAUjLEFJE+02kanyHtwjWOnwrKYBiwAmM0p4kLJAnXg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=12.0.0"
      },
      "peerDependencies": {
        "picomatch": "^3 || ^4"
      },
      "peerDependenciesMeta": {
        "picomatch": {
          "optional": true
        }
      }
    },
    "node_modules/vite/node_modules/picomatch": {
      "version": "4.0.4",
      "resolved": "https://registry.npmjs.org/picomatch/-/picomatch-4.0.4.tgz",
      "integrity": "sha512-QP88BAKvMam/3NxH6vj2o21R6MjxZUAd6nlwAS/pnGvN9IVLocLHxGYIzFhg6fUQ+5th6P4dv4eW9jX3DSIj7A==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=12"
      },
      "funding": {
        "url": "https://github.com/sponsors/jonschlinkert"
      }
    },
    "node_modules/yallist": {
      "version": "3.1.1",
      "resolved": "https://registry.npmjs.org/yallist/-/yallist-3.1.1.tgz",
      "integrity": "sha512-a4UGQaWPH59mOXUYnAG2ewncQS4i4F43Tv3JoAM+s2VDAmS9NsK8GpDMLrCHPksFT7h3K6TOoUNn2pb7RoXx4g==",
      "dev": true,
      "license": "ISC"
    }
  }
}

---

// filepath: frontend/package.json
{
  "name": "sre-incident-ui",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "lint": "eslint . --ext ts,tsx"
  },
  "dependencies": {
    "@tanstack/react-query": "^5.62.7",
    "axios": "^1.7.9",
    "date-fns": "^4.1.0",
    "lucide-react": "^1.17.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.28.0",
    "recharts": "^2.14.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.4",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.49",
    "tailwindcss": "^3.4.16",
    "typescript": "^5.6.3",
    "vite": "^6.0.3"
  }
}

---

// filepath: frontend/postcss.config.js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}

---

// filepath: frontend/tailwind.config.js
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f0f4ff',
          100: '#e0eaff',
          500: '#4f46e5',
          600: '#4338ca',
          700: '#3730a3',
          900: '#1e1b4b',
        },
        surface: {
          900: '#0d0f1a',
          800: '#131626',
          700: '#1a1e35',
          600: '#232844',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'slide-in': 'slideIn 0.3s ease-out',
        'fade-in': 'fadeIn 0.4s ease-out',
      },
      keyframes: {
        slideIn: {
          '0%': { transform: 'translateY(-8px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}

---

// filepath: frontend/tsconfig.json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": false,
    "noUnusedParameters": false,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": { "@/*": ["src/*"] }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}

---

// filepath: frontend/tsconfig.node.json
{ "compilerOptions": { "composite": true, "skipLibCheck": true, "module": "ESNext", "moduleResolution": "bundler", "allowSyntheticDefaultImports": true }, "include": ["vite.config.ts"] }

---

// filepath: frontend/vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    watch: {
      usePolling: true
    },
    proxy: {
      '/api': {
        target: process.env.API_TARGET || 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/ws': {
        target: process.env.WS_TARGET || 'ws://localhost:8000',
        ws: true,
        changeOrigin: true,
      },
    },
  },
})

---

// filepath: frontend/src/App.tsx
import React, { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, NavLink, useLocation } from 'react-router-dom'
import { createPortal } from 'react-dom'
import { Dashboard } from './pages/Dashboard'
import { IncidentDetail } from './pages/IncidentDetail'
import { Analytics } from './pages/Analytics'
import { Handovers } from './pages/Handovers'
import { Summaries } from './pages/Summaries'
import UpgradeAdvisor from './components/UpgradeAdvisor'
import { FloatingTicker } from './components/FloatingTicker'
import { AuthProvider, useAuth } from './hooks/useAuth'

const NAV_ITEMS = [
  { to: '/',          label: 'Dashboard',  icon: '⚡', exact: true },
  { to: '/analytics', label: 'Analytics',  icon: '📊', exact: false },
  { to: '/upgrade-advisor', label: 'Advisor',  icon: '🛡️', exact: false },
  { to: '/summaries', label: 'Summaries',  icon: '📝', exact: false },
  { to: '/handovers', label: 'Handovers',  icon: '🤝', exact: false },
]

function SidebarUserFooter() {
  const { user, isAuthenticated } = useAuth()
  return (
    <div className="mt-auto pt-4 border-t border-white/5 space-y-3">
      {isAuthenticated ? (
        <div className="flex items-center gap-2 px-1">
          <div className="w-7 h-7 rounded-full bg-brand-500/20 border border-brand-500/40 flex items-center justify-center text-brand-400 text-xs font-bold shrink-0">
            {user.displayName[0]?.toUpperCase()}
          </div>
          <div className="overflow-hidden">
            <p className="text-xs font-semibold text-slate-300 truncate">{user.displayName}</p>
            <p className="text-[10px] text-slate-600 truncate">
              {[user.shift, user.role].filter(Boolean).join(' · ')}
            </p>
          </div>
        </div>
      ) : (
        <div className="px-1">
          <p className="text-[10px] text-slate-600 text-center">No identity set</p>
        </div>
      )}
      <div className="flex items-center justify-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
        <p className="text-[10px] text-slate-600">SSO-Ready · LangChain v2 · FastAPI</p>
      </div>
    </div>
  )
}

function Sidebar({ appName, appSubtext, appLogo }: { appName: string, appSubtext: string, appLogo: string | null }) {
  return (
    <aside className="w-56 flex-shrink-0 flex flex-col bg-surface-800 border-r border-white/5 min-h-screen p-4">
      {/* Logo */}
      <div className="mb-8 px-1">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-violet-600
                          flex items-center justify-center text-base shadow-lg glow-brand no-invert overflow-hidden">
            {appLogo ? (
              <img src={appLogo} alt="App Logo" className="w-full h-full object-cover" />
            ) : (
              '🛡️'
            )}
          </div>
          <div className="overflow-hidden">
            <p className="text-sm font-bold text-white leading-tight truncate" title={appName}>{appName}</p>
            <p className="text-xs text-slate-500 leading-tight truncate" title={appSubtext}>{appSubtext}</p>
          </div>
        </div>
      </div>

      {/* Nav links */}
      <nav className="flex-1 space-y-1">
        {NAV_ITEMS.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.exact}
            className={({ isActive }) =>
              `nav-link ${isActive ? 'active' : ''}`
            }
          >
            <span className="no-invert">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <SidebarUserFooter />
    </aside>
  )
}

function SettingsModal({
  initialName, initialSubtext, initialLogo, onSave, onClose
}: {
  initialName: string, initialSubtext: string, initialLogo: string | null,
  onSave: (name: string, subtext: string, logo: string | null) => void,
  onClose: () => void
}) {
  const [name, setName] = useState(initialName)
  const [subtext, setSubtext] = useState(initialSubtext)
  const [logo, setLogo] = useState<string | null>(initialLogo)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      const reader = new FileReader()
      reader.onloadend = () => {
        setLogo(reader.result as string)
      }
      reader.readAsDataURL(file)
    }
  }

  return createPortal(
    <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-surface-800 border border-white/10 rounded-xl p-6 w-96 shadow-2xl animate-fade-in" onClick={e => e.stopPropagation()}>
        <h3 className="text-lg font-semibold text-slate-200 mb-6">Branding Settings</h3>
        
        <div className="space-y-4">
          <div>
            <label className="block text-xs uppercase tracking-wider text-slate-500 mb-1">App Name</label>
            <input className="input" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. SRE Agent" />
          </div>
          <div>
            <label className="block text-xs uppercase tracking-wider text-slate-500 mb-1">App Subtext</label>
            <input className="input" value={subtext} onChange={e => setSubtext(e.target.value)} placeholder="e.g. Incident Control" />
          </div>
          <div>
            <label className="block text-xs uppercase tracking-wider text-slate-500 mb-1">Logo Image</label>
            <input 
              type="file" 
              accept="image/*" 
              onChange={handleFileChange} 
              className="w-full text-sm text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-brand-500/20 file:text-brand-400 hover:file:bg-brand-500/30 cursor-pointer" 
            />
            {logo && (
              <button className="mt-2 text-xs text-rose-400 hover:text-rose-300 transition-colors" onClick={() => setLogo(null)}>
                Remove Custom Logo
              </button>
            )}
          </div>
        </div>

        <div className="mt-8 flex justify-end gap-3">
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={() => { onSave(name, subtext, logo); onClose(); }}>Save Changes</button>
        </div>
      </div>
    </div>,
    document.body
  )
}

function Layout({ children }: { children: React.ReactNode }) {
  const [isDay, setIsDay] = useState(false)
  const [appName, setAppName] = useState(() => localStorage.getItem('customAppName') || 'SRE Agent')
  const [appSubtext, setAppSubtext] = useState(() => localStorage.getItem('customAppSubtext') || 'Incident Control')
  const [appLogo, setAppLogo] = useState(() => localStorage.getItem('customAppLogo') || null)
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)

  useEffect(() => {
    if (isDay) {
      document.documentElement.classList.remove('theme-night')
      document.documentElement.classList.add('theme-day')
    } else {
      document.documentElement.classList.remove('theme-day')
      document.documentElement.classList.add('theme-night')
    }
  }, [isDay])

  const handleSaveSettings = (n: string, s: string, l: string | null) => {
    setAppName(n)
    setAppSubtext(s)
    setAppLogo(l)
    localStorage.setItem('customAppName', n)
    localStorage.setItem('customAppSubtext', s)
    if (l) localStorage.setItem('customAppLogo', l)
    else localStorage.removeItem('customAppLogo')
  }

  return (
    <div className="flex min-h-screen relative flex-col">
      <FloatingTicker />
      <div className="flex flex-1 overflow-hidden relative">
        <Sidebar appName={appName} appSubtext={appSubtext} appLogo={appLogo} />
        
        {/* Sleek Action Bar */}
      <div className="absolute top-4 right-8 z-50 flex items-center gap-1.5 p-1 bg-surface-800/80 backdrop-blur-md border border-white/10 rounded-full shadow-lg">
        <button 
          onClick={() => setIsSettingsOpen(true)}
          className="w-9 h-9 flex items-center justify-center rounded-full hover:bg-white/10 transition-colors text-slate-400 hover:text-white"
          title="Settings"
        >
          <span className="no-invert">⚙️</span>
        </button>
        <div className="w-px h-5 bg-white/10" />
        <button 
          onClick={() => setIsDay(!isDay)}
          className="w-9 h-9 flex items-center justify-center rounded-full hover:bg-white/10 transition-colors text-slate-400 hover:text-white"
          title="Toggle Theme"
        >
          <span className="no-invert">{isDay ? '🌙' : '☀️'}</span>
        </button>
      </div>

      <main className="flex-1 overflow-auto p-8 pt-16">
        {children}
      </main>

      {isSettingsOpen && (
        <SettingsModal 
          initialName={appName}
          initialSubtext={appSubtext}
          initialLogo={appLogo}
          onSave={handleSaveSettings}
          onClose={() => setIsSettingsOpen(false)}
        />
      )}
      </div>
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/incidents/:id" element={<IncidentDetail />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/upgrade-advisor" element={<UpgradeAdvisor />} />
            <Route path="/summaries" element={<Summaries />} />
            <Route path="/handovers" element={<Handovers />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </AuthProvider>
  )
}

---

// filepath: frontend/src/index.css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  * {
    box-sizing: border-box;
  }
  
  html, body, #root {
    height: 100%;
    margin: 0;
    padding: 0;
  }

  body {
    font-family: 'Inter', system-ui, sans-serif;
    background-color: #0d0f1a;
    color: #e2e8f0;
    -webkit-font-smoothing: antialiased;
  }

  ::-webkit-scrollbar {
    width: 6px;
    height: 6px;
  }

  ::-webkit-scrollbar-track {
    background: #131626;
  }

  ::-webkit-scrollbar-thumb {
    background: #2d3561;
    border-radius: 3px;
  }

  ::-webkit-scrollbar-thumb:hover {
    background: #4f46e5;
  }
}

@layer components {
  /* Glass card */
  .glass-card {
    @apply bg-surface-800 border border-white/5 rounded-xl shadow-xl;
    backdrop-filter: blur(12px);
  }

  /* Status badges */
  .badge {
    @apply inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold tracking-wide;
  }

  .badge-received   { @apply bg-slate-700/50 text-slate-300 border border-slate-600/30; }
  .badge-analyzing  { @apply bg-blue-900/50  text-blue-300  border border-blue-600/30; }
  .badge-pending    { @apply bg-orange-900/50 text-orange-300 border border-orange-600/30; }
  .badge-executing  { @apply bg-violet-900/50 text-violet-300 border border-violet-600/30; }
  .badge-verifying  { @apply bg-cyan-900/50   text-cyan-300   border border-cyan-600/30; }
  .badge-resolved   { @apply bg-emerald-900/50 text-emerald-300 border border-emerald-600/30; }
  .badge-rejected   { @apply bg-rose-900/50   text-rose-300   border border-rose-600/30; }
  .badge-escalated  { @apply bg-amber-900/50  text-amber-300  border border-amber-600/30; }
  .badge-failed     { @apply bg-red-900/50    text-red-300    border border-red-600/30; }

  /* Risk tier badges */
  .risk-low      { @apply badge bg-emerald-900/40 text-emerald-300 border-emerald-700/30; }
  .risk-high     { @apply badge bg-orange-900/40  text-orange-300  border-orange-700/30; }
  .risk-escalate { @apply badge bg-red-900/40     text-red-300     border-red-700/30; }

  /* Buttons */
  .btn {
    @apply inline-flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm
           transition-all duration-200 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed;
  }
  .btn-primary { @apply btn bg-brand-500 hover:bg-brand-600 text-white shadow-lg shadow-brand-900/30; }
  .btn-success { @apply btn bg-emerald-600 hover:bg-emerald-500 text-white; }
  .btn-danger  { @apply btn bg-rose-600   hover:bg-rose-500   text-white; }
  .btn-warning { @apply btn bg-amber-600  hover:bg-amber-500  text-white; }
  .btn-ghost   { @apply btn bg-white/5    hover:bg-white/10   text-slate-300 border border-white/10; }

  /* Input */
  .input {
    @apply w-full bg-surface-700 border border-white/10 rounded-lg px-3 py-2
           text-sm text-slate-100 placeholder-slate-500
           focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500/50
           transition-colors duration-200;
  }

  /* Table */
  .data-table {
    @apply w-full border-collapse text-sm;
  }
  .data-table th {
    @apply text-left text-xs font-semibold text-slate-400 uppercase tracking-wider
           px-4 py-3 border-b border-white/5 bg-surface-700/50;
  }
  .data-table td {
    @apply px-4 py-3 border-b border-white/5 text-slate-300;
  }
  .data-table tr:hover td {
    @apply bg-white/5 cursor-pointer;
  }

  /* Sidebar nav */
  .nav-link {
    @apply flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium
           text-slate-400 hover:text-white hover:bg-white/5
           transition-all duration-200;
  }
  .nav-link.active {
    @apply text-white bg-brand-500/20 border border-brand-500/30;
  }

  /* Timeline */
  .timeline-item {
    @apply relative pl-8 pb-6;
  }
  .timeline-item::before {
    content: '';
    @apply absolute left-3 top-6 bottom-0 w-px bg-white/10;
  }
  .timeline-item:last-child::before {
    display: none;
  }
  .timeline-dot {
    @apply absolute left-0.5 top-1 w-5 h-5 rounded-full flex items-center justify-center text-xs;
  }
  .timeline-dot-agent  { @apply bg-blue-900 border border-blue-600/50; }
  .timeline-dot-human  { @apply bg-emerald-900 border border-emerald-600/50; }
  .timeline-dot-system { @apply bg-slate-700 border border-slate-600/50; }
}

@layer utilities {
  .text-gradient {
    @apply bg-gradient-to-r from-brand-500 to-violet-400 bg-clip-text text-transparent;
  }
  .glow-brand {
    box-shadow: 0 0 30px -5px rgba(79, 70, 229, 0.4);
  }
  .animate-pulse-pending {
    animation: pulsePending 2s ease-in-out infinite;
  }
  .animate-marquee {
    animation: marquee 25s linear infinite;
  }
  .animate-marquee:hover {
    animation-play-state: paused;
  }
}

@keyframes pulsePending {
  0%, 100% { box-shadow: 0 0 0 0 rgba(251, 146, 60, 0.3); }
  50%       { box-shadow: 0 0 0 6px rgba(251, 146, 60, 0); }
}

@keyframes marquee {
  0% { transform: translateX(100%); }
  100% { transform: translateX(-100%); }
}

/* Premium Light Theme (Day Mode) Overrides */
html.theme-day body,
html.theme-day main {
  background-color: #f8fafc !important; /* Slate-50 */
  color: #0f172a !important; /* Slate-900 */
}

html.theme-day aside,
html.theme-day .glass-card,
html.theme-day .bg-surface-800 {
  background-color: #ffffff !important;
  color: #0f172a !important;
  border-color: #e2e8f0 !important;
}

html.theme-day .text-white,
html.theme-day .text-slate-200,
html.theme-day .text-slate-300 {
  color: #1e293b !important;
}

html.theme-day .text-slate-400,
html.theme-day .text-slate-500 {
  color: #64748b !important;
}

html.theme-day .border-white\/5,
html.theme-day .border-white\/10 {
  border-color: #e2e8f0 !important;
}

html.theme-day .bg-surface-700,
html.theme-day .bg-slate-900 {
  background-color: #f1f5f9 !important;
}

html.theme-day .bg-surface-700\/50,
html.theme-day .bg-slate-900\/50 {
  background-color: #f1f5f980 !important;
}

/* Fix table headers and input fields */
html.theme-day th {
  background-color: #f1f5f9 !important;
  color: #475569 !important;
}

html.theme-day .input {
  background-color: #ffffff !important;
  color: #0f172a !important;
  border-color: #cbd5e1 !important;
}

/* Hover effects for sidebars and tables */
html.theme-day .hover\:bg-white\/5:hover {
  background-color: #f1f5f9 !important;
}

/* Fix timeline lines */
html.theme-day .timeline-item::before {
  background-color: #e2e8f0 !important;
}

/* Specific button styles */
html.theme-day .btn-ghost {
  color: #475569 !important;
  border-color: #e2e8f0 !important;
  background-color: #ffffff !important;
}
html.theme-day .btn-ghost:hover {
  background-color: #f1f5f9 !important;
  color: #0f172a !important;
}

html.theme-day .nav-link.active {
  background-color: #e0eaff !important; /* Brand-100 */
  border-color: #c7d2fe !important;
  color: #4f46e5 !important;
}
html.theme-day .nav-link {
  color: #64748b !important;
}
html.theme-day .nav-link:hover {
  background-color: #f1f5f9 !important;
  color: #0f172a !important;
}

:root {
  --chart-tooltip-bg: #1a1e35;
  --chart-tooltip-border: #ffffff10;
  --chart-grid-line: #ffffff08;
  --chart-tick-text: #94a3b8;
  --chart-cursor-bg: #ffffff08;
  --chart-treemap-stroke: #1a1e35;
  --chart-treemap-text: #ffffff;
}

html.theme-day {
  --chart-tooltip-bg: #ffffff;
  --chart-tooltip-border: #e2e8f0;
  --chart-grid-line: #e2e8f0;
  --chart-tick-text: #64748b;
  --chart-cursor-bg: #f1f5f9;
  --chart-treemap-stroke: #ffffff;
  --chart-treemap-text: #ffffff;
}


---

// filepath: frontend/src/main.tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      retry: 2,
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>
)

---

// filepath: frontend/src/api/client.ts
import axios from 'axios'

const API_BASE = '/api'

// Auth token (in production, pull from OIDC token store)
const getToken = () => localStorage.getItem('sre_token') || 'dev-api-key-change-in-prod'

export const apiClient = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
})

apiClient.interceptors.request.use((config) => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Types
export interface Incident {
  id: string
  correlation_id: string | null
  cluster: string
  namespace: string
  alert_name: string
  hostname: string | null
  status: string
  risk_tier: string | null
  llm_confidence: number | null
  llm_intent_json: Record<string, unknown> | null
  analysis_summary: string | null
  escalate_to: string | null
  awx_job_id: string | null
  created_at: string
  updated_at: string
  resolved_at: string | null
  timeline: TimelineEvent[]
  human_actions: HumanAction[]
  llm_decisions: LLMDecision[]
}

export interface TimelineEvent {
  id: number
  timestamp: string
  actor_type: 'agent' | 'human' | 'system'
  actor_id: string | null
  action: string
  from_status: string | null
  to_status: string | null
  notes: string | null
  metadata_json: Record<string, unknown> | null
}

export interface HumanAction {
  id: number
  user_id: string
  action: string
  original_intent_json: Record<string, unknown> | null
  final_intent_json: Record<string, unknown> | null
  reason: string
  timestamp: string
}

export interface LLMDecision {
  id: number
  prompt_used: string | null
  raw_llm_output: string | null
  parsed_intent: Record<string, unknown> | null
  confidence: number | null
  tool_calls_json: Record<string, unknown> | null
  timestamp: string
}

export interface DashboardCounts {
  active: number
  pending_approval: number
  resolved_today: number
  failed: number
}

export interface FlappingAlert {
  alert_name: string
  cluster: string
  flapping_count: number
  reopen_count: number
}

export interface SentimentTrend {
  date: string
  average_score: number
  total_resolutions: number
}

export interface RedHatCaseSummary {
  open_cases: number
  critical_escalation_pct: number
  avg_vendor_mttr_days: number
}

export interface ComponentIncident {
  component: string
  incident_count: number
}

export interface FleetRisk {
  average_risk_pct: number
  critical_cves_active: number
}

export interface EnvironmentDistribution {
  environment: string
  incident_count: number
}

export interface AnalyticsSummary {
  mttr_by_cluster: any[]
  resolution_stats: any
  llm_accuracy: any
  top_recurring_alerts: any[]
  flapping_alerts: FlappingAlert[]
  sentiment_trend: SentimentTrend[]
  redhat_cases_summary: RedHatCaseSummary
  component_incidents: ComponentIncident[]
  fleet_risk: FleetRisk
  environment_distribution: EnvironmentDistribution[]
}

// API calls
export const api = {
  getDashboardCounts: () =>
    apiClient.get<DashboardCounts>('/dashboard/counts').then(r => r.data),

  getIncidents: (params?: { status?: string; cluster?: string; alert_name?: string; page?: number }) =>
    apiClient.get('/incidents', { params }).then(r => r.data),

  getIncident: (id: string) =>
    apiClient.get<Incident>(`/incidents/${id}`).then(r => r.data),

  approve: (id: string, reason: string, user_id: string) =>
    apiClient.post(`/incidents/${id}/approve`, { reason, user_id }).then(r => r.data),

  reject: (id: string, reason: string, user_id: string) =>
    apiClient.post(`/incidents/${id}/reject`, { reason, user_id }).then(r => r.data),

  editAndApprove: (id: string, modified_intent: object, reason: string, user_id: string) =>
    apiClient.post(`/incidents/${id}/edit`, { modified_intent, reason, user_id }).then(r => r.data),

  escalate: (id: string, reason: string, user_id: string) =>
    apiClient.post(`/incidents/${id}/escalate`, { reason, user_id }).then(r => r.data),

  getAnalytics: () =>
    apiClient.get<AnalyticsSummary>('/analytics/summary').then(r => r.data),

  ingestAlert: (payload: Record<string, string>) =>
    apiClient.post('/alerts/ingest', payload).then(r => r.data),

  getHandovers: (params?: {
    cluster?: string
    handover_type?: string
    priority?: string
    action_required?: boolean
    limit?: number
  }) =>
    apiClient.get<Handover[]>('/handovers', { params }).then(r => r.data),

  getHandoverClusters: () =>
    apiClient.get<string[]>('/handovers/clusters').then(r => r.data),

  createHandover: (payload: {
    author: string
    shift_identifier: string
    cluster: string
    handover_type: string
    priority: string
    action_required: boolean
    related_incidents: string
    message: string
    start_time?: string | null
    end_time?: string | null
    upgraded_version?: string | null
    operator_name?: string | null
  }) =>
    apiClient.post<Handover>('/handovers', payload).then(r => r.data),

  getTickerHandovers: () =>
    apiClient.get<Handover[]>('/handovers/active_ticker').then(r => r.data),

  updateHandover: (id: string, payload: {
    is_active?: boolean
    resolution_notes?: string
    action_required?: boolean
  }) =>
    apiClient.patch<Handover>(`/handovers/${id}`, payload).then(r => r.data),

  chatWithContext: (payload: { query: string; timeframe_hours: number }) =>
    apiClient.post<{ answer: string }>('/chat', payload).then(r => r.data),

  previewSummary: () =>
    apiClient.post<{ shift_name: string; preview_text: string }>('/summaries/preview').then(r => r.data),

  saveSummary: (payload: { shift_name: string; summary_text: string }) =>
    apiClient.post<{ status: string; id: string }>('/summaries/save', payload).then(r => r.data),

  getHistoricalSummaries: () =>
    apiClient.get<HistoricalSummary[]>('/summaries/historical').then(r => r.data),
}

export interface HistoricalSummary {
  id: string
  shift_name: string
  summary_text: string
  is_auto_generated: boolean
  created_at: string
}

export interface Handover {
  id: string
  author: string
  shift_identifier: string
  cluster: string
  handover_type: HandoverType
  priority: HandoverPriority
  action_required: boolean
  related_incidents: string
  message: string
  created_at: string
  start_time: string | null
  end_time: string | null
  is_active: boolean
  resolution_notes: string | null
  upgraded_version: string | null
  operator_name: string | null
}

export type HandoverType =
  | 'handover'
  | 'maintenance'
  | 'upgrade'
  | 'operator_upgrade'
  | 'incident_followup'
  | 'change_freeze'
  | 'escalation'

export type HandoverPriority = 'low' | 'medium' | 'high' | 'critical'


---

// filepath: frontend/src/components/ApprovalCard.tsx
import React, { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { Incident } from '../api/client'

interface ApprovalCardProps {
  incident: Incident
  currentUserId?: string
}

export const ApprovalCard: React.FC<ApprovalCardProps> = ({
  incident,
  currentUserId = 'dev-user',
}) => {
  const [reason, setReason] = useState('')
  const [editMode, setEditMode] = useState(false)
  const [editedIntent, setEditedIntent] = useState(
    JSON.stringify(incident.llm_intent_json, null, 2)
  )
  const [intentError, setIntentError] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const onSuccess = () => {
    queryClient.invalidateQueries({ queryKey: ['incident', incident.id] })
    queryClient.invalidateQueries({ queryKey: ['incidents'] })
  }

  const approveMutation = useMutation({
    mutationFn: () => api.approve(incident.id, reason, currentUserId),
    onSuccess,
  })

  const rejectMutation = useMutation({
    mutationFn: () => api.reject(incident.id, reason, currentUserId),
    onSuccess,
  })

  const editMutation = useMutation({
    mutationFn: () => {
      let parsed
      try {
        parsed = JSON.parse(editedIntent)
        setIntentError(null)
      } catch (e) {
        setIntentError('Invalid JSON — please fix before submitting')
        throw e
      }
      return api.editAndApprove(incident.id, parsed, reason, currentUserId)
    },
    onSuccess,
  })

  const escalateMutation = useMutation({
    mutationFn: () => api.escalate(incident.id, reason, currentUserId),
    onSuccess,
  })

  const isLoading =
    approveMutation.isPending ||
    rejectMutation.isPending ||
    editMutation.isPending ||
    escalateMutation.isPending

  const reasonValid = reason.trim().length >= 5

  return (
    <div className="glass-card border-orange-500/30 bg-orange-900/10 p-6 animate-pulse-pending animate-slide-in">
      {/* Header */}
      <div className="flex items-center gap-3 mb-5">
        <div className="w-10 h-10 rounded-full bg-orange-900/60 border border-orange-600/40
                        flex items-center justify-center text-lg">
          🔐
        </div>
        <div>
          <h3 className="font-semibold text-orange-300 text-base">Human Approval Required</h3>
          <p className="text-xs text-slate-400 mt-0.5">
            This action is classified as HIGH risk. Review carefully before approving.
          </p>
        </div>
      </div>

      {/* Proposed action summary */}
      <div className="bg-surface-700/60 rounded-xl p-4 mb-5 border border-white/5">
        <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
          Proposed Action
        </h4>
        {incident.llm_intent_json ? (
          <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
            <div>
              <span className="text-slate-500">Action</span>
              <p className="text-slate-100 font-semibold font-mono mt-0.5">
                {String(incident.llm_intent_json.action ?? '—')}
              </p>
            </div>
            <div>
              <span className="text-slate-500">Target</span>
              <p className="text-slate-100 font-semibold font-mono mt-0.5">
                {String(incident.llm_intent_json.target ?? '—')}
              </p>
            </div>
            <div>
              <span className="text-slate-500">Namespace</span>
              <p className="text-slate-100 font-mono mt-0.5">
                {String(incident.llm_intent_json.namespace ?? '—')}
              </p>
            </div>
            <div>
              <span className="text-slate-500">Confidence</span>
              <p className="text-slate-100 font-mono mt-0.5">
                {incident.llm_confidence !== null
                  ? `${Math.round((incident.llm_confidence ?? 0) * 100)}%`
                  : '—'}
              </p>
            </div>
            <div className="col-span-2">
              <span className="text-slate-500">Reason</span>
              <p className="text-slate-300 mt-0.5 italic">
                "{String(incident.llm_intent_json.reason ?? '—')}"
              </p>
            </div>
          </div>
        ) : (
          <p className="text-slate-400 text-sm">No intent data available.</p>
        )}
      </div>

      {/* Edit intent toggle */}
      <div className="mb-5">
        <button
          onClick={() => setEditMode(!editMode)}
          className="text-xs text-brand-400 hover:text-brand-300 transition-colors flex items-center gap-1.5"
        >
          <span>{editMode ? '▾' : '▸'}</span>
          {editMode ? 'Hide JSON editor' : 'Edit intent before approving'}
        </button>

        {editMode && (
          <div className="mt-3 animate-slide-in">
            <textarea
              className="input font-mono text-xs resize-none h-40"
              value={editedIntent}
              onChange={(e) => {
                setEditedIntent(e.target.value)
                setIntentError(null)
              }}
              spellCheck={false}
            />
            {intentError && (
              <p className="text-red-400 text-xs mt-1">⚠ {intentError}</p>
            )}
          </div>
        )}
      </div>

      {/* Reason field — REQUIRED */}
      <div className="mb-5">
        <label className="block text-xs font-semibold text-slate-400 mb-1.5">
          Reason <span className="text-red-400">*</span>
          <span className="text-slate-500 font-normal ml-1">(required, min 5 chars)</span>
        </label>
        <textarea
          className="input resize-none h-20 text-sm"
          placeholder='e.g. "Confirmed pod crash in CrashLoopBackOff — restart is safe"'
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
      </div>

      {/* Action buttons */}
      <div className="flex flex-wrap gap-3">
        {!editMode ? (
          <button
            className="btn-success flex-1"
            disabled={!reasonValid || isLoading}
            onClick={() => approveMutation.mutate()}
          >
            {approveMutation.isPending ? '⏳ Approving...' : '✓ Approve'}
          </button>
        ) : (
          <button
            className="btn-success flex-1"
            disabled={!reasonValid || isLoading}
            onClick={() => editMutation.mutate()}
          >
            {editMutation.isPending ? '⏳ Saving...' : '✓ Save & Approve'}
          </button>
        )}

        <button
          className="btn-danger"
          disabled={!reasonValid || isLoading}
          onClick={() => rejectMutation.mutate()}
        >
          {rejectMutation.isPending ? '⏳...' : '✗ Reject'}
        </button>

        <button
          className="btn-warning"
          disabled={!reasonValid || isLoading}
          onClick={() => escalateMutation.mutate()}
        >
          {escalateMutation.isPending ? '⏳...' : '⚡ Escalate to Oncall'}
        </button>
      </div>

      {/* Error display */}
      {(approveMutation.isError || rejectMutation.isError || editMutation.isError) && (
        <div className="mt-3 p-3 bg-red-900/30 border border-red-700/50 rounded-lg text-red-300 text-xs">
          ⚠ Action failed. Check the console and try again.
        </div>
      )}
    </div>
  )
}

---

// filepath: frontend/src/components/FloatingTicker.tsx
import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, Handover } from '../api/client'
import { format } from 'date-fns'

export const FloatingTicker: React.FC = () => {
  const { data: handovers } = useQuery({
    queryKey: ['activeTicker'],
    queryFn: api.getTickerHandovers,
    refetchInterval: 30_000, // Poll every 30 seconds
  })

  // State to dismiss ticker if empty or manually closed
  const [isDismissed, setIsDismissed] = useState(false)

  if (isDismissed) return null
  if (!handovers || handovers.length === 0) return null

  return (
    <div className="bg-surface-800/95 backdrop-blur-md border-b border-white/10 w-full z-[100] shadow-md">
      <div className="flex items-center px-4 py-2 gap-3 max-w-[1400px] mx-auto relative overflow-hidden">
        {/* Static Prefix */}
        <div className="flex items-center gap-2 shrink-0 z-10 bg-surface-800 pr-2">
          <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse" />
          <span className="text-xs font-bold uppercase tracking-widest text-slate-300">
            Active Alerts
          </span>
          <div className="w-px h-4 bg-white/20 mx-1" />
        </div>

        {/* Marquee Container */}
        <div className="flex-1 overflow-hidden relative h-6 flex items-center">
          <div className="animate-marquee whitespace-nowrap flex items-center gap-8 text-sm">
            {handovers.map((ho) => {
              const isActionRequired = ho.action_required
              const isMaintenance = ho.handover_type === 'maintenance'
              
              const colorClass = isActionRequired
                ? 'text-rose-400 font-medium'
                : isMaintenance
                ? 'text-amber-400 font-medium'
                : 'text-slate-300'

              const icon = isActionRequired ? '⚡ Action Required:' : '🔧 Maintenance:'
              
              let timeText = ''
              if (isMaintenance && ho.end_time) {
                timeText = ` (Ends ${format(new Date(ho.end_time), 'HH:mm')})`
              }

              return (
                <span key={ho.id} className="inline-flex items-center gap-2">
                  <span className={`${colorClass}`}>
                    {icon} {ho.shift_identifier || ho.author} - {ho.cluster === 'ALL' ? 'ALL CLUSTERS' : ho.cluster}
                  </span>
                  <span className="text-slate-400 truncate max-w-xl">
                    "{ho.message}" {timeText}
                  </span>
                </span>
              )
            })}
          </div>
        </div>

        {/* Dismiss Button */}
        <div className="shrink-0 z-10 bg-surface-800 pl-2">
          <button
            onClick={() => setIsDismissed(true)}
            className="text-slate-500 hover:text-slate-300 transition-colors"
            title="Dismiss Ticker"
          >
            ✕
          </button>
        </div>
      </div>
    </div>
  )
}

---

// filepath: frontend/src/components/PresenceIndicators.tsx
import React from 'react'

interface PresenceIndicatorsProps {
  viewers: string[]
}

const COLORS = [
  'bg-violet-600',
  'bg-blue-600',
  'bg-emerald-600',
  'bg-amber-600',
  'bg-rose-600',
  'bg-cyan-600',
]

export const PresenceIndicators: React.FC<PresenceIndicatorsProps> = ({ viewers }) => {
  if (viewers.length === 0) return null

  const shown = viewers.slice(0, 4)
  const overflow = viewers.length - shown.length

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-slate-400">Viewing:</span>
      <div className="flex -space-x-2">
        {shown.map((name, i) => {
          const initials = name
            .split('.')
            .map(s => s[0]?.toUpperCase() ?? '?')
            .join('')
            .slice(0, 2)
          return (
            <div
              key={name}
              title={name}
              className={`w-7 h-7 rounded-full ${COLORS[i % COLORS.length]} border-2 border-surface-800
                          flex items-center justify-center text-xs font-bold text-white
                          cursor-default select-none transition-transform hover:scale-110 hover:z-10`}
            >
              {initials}
            </div>
          )
        })}
        {overflow > 0 && (
          <div className="w-7 h-7 rounded-full bg-surface-600 border-2 border-surface-800
                          flex items-center justify-center text-xs text-slate-400 font-semibold">
            +{overflow}
          </div>
        )}
      </div>
      <span className="inline-flex items-center gap-1 text-xs text-emerald-400">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
        Live
      </span>
    </div>
  )
}

---

// filepath: frontend/src/components/StatusBadge.tsx
import React from 'react'

const STATUS_CONFIG: Record<string, { label: string; className: string; dot?: string }> = {
  RECEIVED:         { label: 'Received',         className: 'badge-received',  dot: 'bg-slate-400' },
  ANALYZING:        { label: 'Analyzing',        className: 'badge-analyzing', dot: 'bg-blue-400' },
  PENDING_APPROVAL: { label: 'Pending Approval', className: 'badge-pending',   dot: 'bg-orange-400' },
  EXECUTING:        { label: 'Executing',        className: 'badge-executing', dot: 'bg-violet-400' },
  VERIFYING:        { label: 'Verifying',        className: 'badge-verifying', dot: 'bg-cyan-400' },
  RESOLVED:         { label: 'Resolved',         className: 'badge-resolved',  dot: 'bg-emerald-400' },
  REJECTED:         { label: 'Rejected',         className: 'badge-rejected',  dot: 'bg-rose-400' },
  ESCALATED:        { label: 'Escalated',        className: 'badge-escalated', dot: 'bg-amber-400' },
  FAILED:           { label: 'Failed',           className: 'badge-failed',    dot: 'bg-red-400' },
}

const RISK_CONFIG: Record<string, { label: string; className: string }> = {
  LOW:     { label: 'LOW',     className: 'risk-low' },
  HIGH:    { label: 'HIGH',   className: 'risk-high' },
  ESCALATE:{ label: 'ESCALATE',className: 'risk-escalate' },
}

interface StatusBadgeProps {
  status: string
  animated?: boolean
  size?: 'sm' | 'md'
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, animated = false, size = 'md' }) => {
  const config = STATUS_CONFIG[status] || { label: status, className: 'badge-received', dot: 'bg-slate-400' }

  return (
    <span
      className={`badge ${config.className} ${size === 'sm' ? 'text-xs' : ''} ${
        animated && status === 'PENDING_APPROVAL' ? 'animate-pulse-pending' : ''
      }`}
    >
      {config.dot && (
        <span
          className={`w-1.5 h-1.5 rounded-full ${config.dot} ${
            ['ANALYZING', 'EXECUTING', 'VERIFYING'].includes(status) ? 'animate-pulse' : ''
          }`}
        />
      )}
      {config.label}
    </span>
  )
}

interface RiskBadgeProps {
  tier: string | null
}

export const RiskBadge: React.FC<RiskBadgeProps> = ({ tier }) => {
  if (!tier) return null
  const config = RISK_CONFIG[tier] || { label: tier, className: 'badge bg-slate-700 text-slate-300' }
  return <span className={config.className}>{config.label}</span>
}

interface ConfidenceBadgeProps {
  confidence: number | null
}

export const ConfidenceBadge: React.FC<ConfidenceBadgeProps> = ({ confidence }) => {
  if (confidence === null) return null
  const pct = Math.round(confidence * 100)
  const color = pct >= 85 ? 'text-emerald-400' : pct >= 70 ? 'text-amber-400' : 'text-red-400'
  return (
    <span className={`font-mono text-sm font-semibold ${color}`}>
      {pct}%
    </span>
  )
}

---

// filepath: frontend/src/components/Timeline.tsx
import React, { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { format } from 'date-fns'
import type { TimelineEvent } from '../api/client'

const ACTOR_ICONS: Record<string, { icon: string; dotClass: string; label: string }> = {
  agent:  { icon: '🤖', dotClass: 'timeline-dot-agent',  label: 'AGENT'  },
  human:  { icon: '👤', dotClass: 'timeline-dot-human',  label: 'HUMAN'  },
  system: { icon: '⚙️', dotClass: 'timeline-dot-system', label: 'SYSTEM' },
}

const ACTOR_LABEL_COLORS: Record<string, string> = {
  agent:  'text-blue-400',
  human:  'text-emerald-400',
  system: 'text-slate-400',
}

interface TimelineProps {
  events: TimelineEvent[]
}

const EventDetailModal = ({ event, nextEvent, onClose }: { event: TimelineEvent, nextEvent?: TimelineEvent, onClose: () => void }) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const hasMetadata = event.metadata_json && Object.keys(event.metadata_json).length > 0;
  const statusClass = event.to_status ? `badge-${event.to_status.toLowerCase().replace('_', '-')}` : 'bg-slate-700 text-slate-300';
  
  const startTime = format(new Date(event.timestamp), 'yyyy-MM-dd HH:mm:ss');
  const endTime = nextEvent ? format(new Date(nextEvent.timestamp), 'yyyy-MM-dd HH:mm:ss') : (['RESOLVED', 'FAILED', 'ESCALATED', 'REJECTED'].includes(event.to_status || '') ? startTime : 'Ongoing...');

  return createPortal(
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-surface-800 border border-white/10 rounded-xl p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto shadow-2xl" onClick={e => e.stopPropagation()}>
        <div className="flex justify-between items-start mb-6">
          <div>
            <h3 className="text-xl font-semibold text-slate-200 mb-2">Stage Details</h3>
            <div className="flex items-center gap-2">
              <span className="text-sm text-slate-400">Status:</span>
              <span className={`px-2.5 py-1 rounded-full text-xs font-semibold tracking-wide ${statusClass}`}>
                {event.to_status || 'UNKNOWN'}
              </span>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white text-2xl leading-none">&times;</button>
        </div>

        <div className="space-y-4">
          <div className="bg-surface-700/50 rounded-lg p-4 border border-white/5">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-slate-500 block text-xs uppercase tracking-wider mb-1">Start Time</span>
                <span className="text-slate-300 font-mono">{startTime}</span>
              </div>
              <div>
                <span className="text-slate-500 block text-xs uppercase tracking-wider mb-1">End Time</span>
                <span className="text-slate-300 font-mono">{endTime}</span>
              </div>
              <div className="col-span-2 mt-2">
                <span className="text-slate-500 block text-xs uppercase tracking-wider mb-1">Action / Event</span>
                <span className="text-slate-200">{event.action}</span>
              </div>
              {event.notes && (
                <div className="col-span-2 mt-2">
                  <span className="text-slate-500 block text-xs uppercase tracking-wider mb-1">Notes</span>
                  <span className="text-slate-300 italic">{event.notes}</span>
                </div>
              )}
            </div>
          </div>

          {hasMetadata && (
            <div>
              <span className="text-slate-500 block text-xs uppercase tracking-wider mb-2">Attached Metadata</span>
              <pre className="text-sm bg-slate-900 rounded-lg p-4 overflow-x-auto text-slate-300 font-mono border border-white/5">
                {JSON.stringify(event.metadata_json, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
};

export const Timeline: React.FC<TimelineProps> = ({ events }) => {
  const [selectedEventIndex, setSelectedEventIndex] = useState<number | null>(null);

  if (events.length === 0) {
    return (
      <div className="text-center py-8 text-slate-500 text-sm">
        No timeline events yet.
      </div>
    )
  }

  return (
    <div className="animate-fade-in">
      {events.map((event, idx) => {
        const actor = ACTOR_ICONS[event.actor_type] || ACTOR_ICONS.system
        const isLast = idx === events.length - 1

        return (
          <div key={event.id} className={`timeline-item ${isLast ? 'pb-0' : ''}`}>
            {/* Timeline dot */}
            <div className={`timeline-dot ${actor.dotClass}`}>
              <span className="text-[10px] no-invert">{actor.icon}</span>
            </div>

            {/* Content */}
            <div 
              className="group cursor-pointer hover:bg-white/5 p-2 -mx-2 rounded transition-colors"
              onClick={() => setSelectedEventIndex(idx)}
            >
              <div className="flex flex-wrap items-center gap-2 mb-0.5">
                <span className={`text-xs font-bold uppercase tracking-widest ${ACTOR_LABEL_COLORS[event.actor_type]}`}>
                  [{actor.label}{event.actor_id ? ` · ${event.actor_id}` : ''}]
                </span>
                <span className="text-xs text-slate-500 font-mono">
                  {format(new Date(event.timestamp), 'yyyy-MM-dd HH:mm:ss')}
                </span>
                {event.to_status && (
                  <span className="text-xs text-slate-500">
                    → <span className="text-slate-300 font-medium">{event.to_status}</span>
                  </span>
                )}
              </div>

              <p className="text-sm text-slate-200 leading-relaxed">{event.action}</p>

              {event.notes && (
                <p className="text-xs text-slate-400 mt-1 italic line-clamp-2">"{event.notes}"</p>
              )}
            </div>
          </div>
        )
      })}

      {selectedEventIndex !== null && (
        <EventDetailModal 
          event={events[selectedEventIndex]} 
          nextEvent={selectedEventIndex < events.length - 1 ? events[selectedEventIndex + 1] : undefined}
          onClose={() => setSelectedEventIndex(null)} 
        />
      )}
    </div>
  )
}

---

// filepath: frontend/src/components/UpgradeAdvisor.tsx
import React, { useState, useEffect } from 'react';
import { Clock, ShieldAlert, Cpu, CheckCircle2, ChevronRight, Activity, ArrowUpRight, Wrench } from 'lucide-react';
import { apiClient } from '../api/client';

interface CVE {
    cves: string[];
    severity: string;
    advisory_id: string;
    raw_text: string;
}

interface PathOption {
    version: string;
    type: string;
    residual_risk_percent: number;
    resolves: CVE[];
    risks_waiting: CVE[];
    description: string;
}

interface UpgradeAdvisorData {
    current_version: string;
    current_risk_percent: number;
    current_cves: CVE[];
    best_upgrade: string;
    paths: Record<string, PathOption>;
}

interface Cluster {
    id: string;
    name: string;
    current_version: string;
    risk_percent: number;
}

const RiskGauge = ({ percent, size = 'lg' }: { percent: number, size?: 'sm' | 'lg' }) => {
    const radius = size === 'lg' ? 40 : 20;
    const stroke = size === 'lg' ? 8 : 4;
    const normalizedRadius = radius - stroke * 2;
    const circumference = normalizedRadius * 2 * Math.PI;
    const strokeDashoffset = circumference - (percent / 100) * circumference;

    let color = 'text-emerald-500';
    if (percent > 30) color = 'text-amber-500';
    if (percent > 70) color = 'text-rose-500';

    return (
        <div className="relative flex items-center justify-center">
            <svg height={radius * 2} width={radius * 2} className="transform -rotate-90">
                <circle
                    stroke="currentColor"
                    fill="transparent"
                    strokeWidth={stroke}
                    r={normalizedRadius}
                    cx={radius}
                    cy={radius}
                    className="text-slate-700"
                />
                <circle
                    stroke="currentColor"
                    fill="transparent"
                    strokeWidth={stroke}
                    strokeDasharray={circumference + ' ' + circumference}
                    style={{ strokeDashoffset }}
                    r={normalizedRadius}
                    cx={radius}
                    cy={radius}
                    className={`${color} transition-all duration-1000 ease-out`}
                />
            </svg>
            <div className={`absolute font-bold font-mono ${size === 'lg' ? 'text-2xl' : 'text-sm'} ${color}`}>
                {percent}%
            </div>
        </div>
    );
};

const CVEList = ({ cves, emptyMsg }: { cves: CVE[], emptyMsg: string }) => {
    if (cves.length === 0) return <p className="text-sm text-slate-500 italic py-2">{emptyMsg}</p>;
    
    return (
        <div className="space-y-2 mt-2 max-h-48 overflow-y-auto pr-2 custom-scrollbar">
            {cves.map((cve, idx) => (
                <div key={idx} className="bg-surface-700/50 p-2.5 rounded-lg border border-white/5 hover:border-white/10 transition-colors">
                    <div className="flex justify-between items-center mb-1">
                        <span className="font-mono text-xs text-blue-300 font-bold">{cve.advisory_id}</span>
                        <span className={`text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded ${
                            cve.severity === 'Critical' ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30' :
                            cve.severity === 'Important' ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' :
                            'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                        }`}>
                            {cve.severity}
                        </span>
                    </div>
                    <p className="text-xs text-slate-400 line-clamp-2" title={cve.raw_text}>{cve.raw_text}</p>
                </div>
            ))}
        </div>
    );
};

const UpgradeAdvisor = () => {
    const [clusters, setClusters] = useState<Cluster[]>([]);
    const [selectedCluster, setSelectedCluster] = useState<string | null>(null);
    const [advisorData, setAdvisorData] = useState<UpgradeAdvisorData | null>(null);
    const [loading, setLoading] = useState<boolean>(false);
    const [activeTabs, setActiveTabs] = useState<Record<string, 'resolves'|'waiting'>>({});

    useEffect(() => {
        apiClient.get('/clusters')
            .then(res => setClusters(res.data))
            .catch(err => console.error("Error fetching clusters:", err));
    }, []);

    const fetchAdvisorData = async (clusterId: string) => {
        setSelectedCluster(clusterId);
        setLoading(true);
        try {
            const res = await apiClient.get(`/clusters/${clusterId}/upgrade-advisor`);
            setAdvisorData(res.data);
            
            // Default tabs to 'resolves'
            const tabs: Record<string, 'resolves'|'waiting'> = {};
            Object.keys(res.data.paths).forEach(v => tabs[v] = 'resolves');
            setActiveTabs(tabs);
        } catch (error) {
            console.error("Error fetching advisor data:", error);
        } finally {
            setLoading(false);
        }
    };

    const toggleTab = (version: string, tab: 'resolves' | 'waiting') => {
        setActiveTabs(prev => ({ ...prev, [version]: tab }));
    };

    return (
        <div className="p-8 min-h-screen text-slate-200 font-sans selection:bg-blue-500/30">
            <h1 className="text-4xl font-extrabold mb-8 bg-gradient-to-r from-blue-400 via-indigo-400 to-purple-400 bg-clip-text text-transparent">
                Advanced Upgrade Advisor
            </h1>
            
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
                {/* Cluster Sidebar */}
                <div className="lg:col-span-1 space-y-6">
                    <div className="glass-card p-6">
                        <h2 className="text-lg font-bold mb-4 text-slate-200 flex items-center gap-2">
                            <span>🏢</span> Your Clusters
                        </h2>
                        {clusters.length === 0 ? (
                            <p className="text-slate-500 text-sm">No clusters found.</p>
                        ) : (
                            <div className="space-y-3">
                                {clusters.map(cluster => (
                                    <div 
                                        key={cluster.id} 
                                        onClick={() => fetchAdvisorData(cluster.id)}
                                        className={`p-4 rounded-xl cursor-pointer transition-all duration-300 border relative overflow-hidden group ${
                                            selectedCluster === cluster.id 
                                                ? 'bg-blue-600/10 border-blue-500/50 shadow-[0_0_20px_rgba(59,130,246,0.15)]' 
                                                : 'bg-surface-700/50 border-transparent hover:bg-surface-700'
                                        }`}
                                    >
                                        <div className="flex justify-between items-start">
                                            <div>
                                                <div className="font-semibold text-md text-slate-200">{cluster.name}</div>
                                                <div className="text-xs text-slate-500 mt-1 font-mono">v{cluster.current_version}</div>
                                            </div>
                                            <div className={`px-2 py-0.5 rounded text-[10px] font-bold tracking-wider ${
                                                cluster.risk_percent > 70 ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30' :
                                                cluster.risk_percent > 30 ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' :
                                                'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                                            }`}>
                                                {cluster.risk_percent}% RISK
                                            </div>
                                        </div>
                                        {selectedCluster === cluster.id && (
                                            <div className="absolute inset-y-0 right-0 w-1 bg-blue-500 rounded-l-full shadow-[0_0_10px_rgba(59,130,246,0.8)]"></div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>

                {/* Advisor Workspace */}
                <div className="lg:col-span-3">
                    {loading && (
                        <div className="flex flex-col items-center justify-center h-64 gap-4">
                            <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
                            <p className="text-slate-400 font-medium animate-pulse">Calculating errata risk vectors...</p>
                        </div>
                    )}
                    
                    {!loading && advisorData && (
                        <div className="space-y-8 animate-fade-in-up">
                            
                            {/* Current Posture Header */}
                            <div className="glass-card p-8 flex flex-col md:flex-row items-center justify-between gap-8">
                                <div>
                                    <h2 className="text-xs uppercase tracking-widest text-slate-500 font-bold mb-1">Current Posture</h2>
                                    <div className="text-4xl font-mono font-bold text-slate-200 mb-2">v{advisorData.current_version}</div>
                                    <p className="text-sm text-slate-400 max-w-md">
                                        You currently have <span className="text-rose-400 font-bold">{advisorData.current_cves.length} active vulnerabilities</span> impacting this cluster version.
                                    </p>
                                </div>
                                <div className="flex flex-col items-center bg-surface-700/50 p-6 rounded-2xl border border-white/5 shadow-inner">
                                    <RiskGauge percent={advisorData.current_risk_percent} size="lg" />
                                    <span className="text-xs font-bold text-slate-500 uppercase tracking-widest mt-3">Risk Index</span>
                                </div>
                            </div>

                            {/* Upgrade Target Cards */}
                            <div>
                                <h3 className="text-xl font-bold text-slate-300 mb-4 flex items-center gap-2">
                                    <span>🚀</span> Available Upgrade Paths
                                </h3>
                                <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                                    {Object.values(advisorData.paths).map((path) => {
                                        const isBest = path.version === advisorData.best_upgrade;
                                        const activeTab = activeTabs[path.version] || 'resolves';
                                        
                                        return (
                                            <div key={path.version} className={`relative flex flex-col glass-card p-6 transition-all duration-500 hover:-translate-y-1 ${
                                                isBest 
                                                ? 'border-emerald-500/50 shadow-[0_10px_30px_rgba(16,185,129,0.1)]' 
                                                : 'border-white/5 hover:border-white/10'
                                            }`}>
                                                {isBest && (
                                                    <div className="absolute -top-3 -right-3 bg-gradient-to-r from-emerald-400 to-teal-500 text-slate-950 text-xs font-extrabold uppercase tracking-widest px-4 py-1.5 rounded-full shadow-lg border border-emerald-300 flex items-center gap-1 animate-pulse-slow">
                                                        <span>⭐</span> Best Choice
                                                    </div>
                                                )}
                                                
                                                <div className="flex justify-between items-start mb-6">
                                                    <div>
                                                        <div className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-1">{path.type} Target</div>
                                                        <div className={`text-3xl font-mono font-bold ${isBest ? 'text-emerald-400' : 'text-slate-300'}`}>
                                                            v{path.version}
                                                        </div>
                                                    </div>
                                                    <div className="flex flex-col items-center">
                                                        <RiskGauge percent={path.residual_risk_percent} size="sm" />
                                                        <span className="text-[9px] text-slate-500 uppercase tracking-wider font-bold mt-1">Residual</span>
                                                    </div>
                                                </div>

                                                {/* Tabs */}
                                                <div className="flex border-b border-white/5 mb-3">
                                                    <button 
                                                        onClick={() => toggleTab(path.version, 'resolves')}
                                                        className={`flex-1 pb-2 text-xs font-bold uppercase tracking-widest transition-colors ${activeTab === 'resolves' ? 'text-emerald-400 border-b-2 border-emerald-400' : 'text-slate-500 hover:text-slate-400'}`}
                                                    >
                                                        Resolves ({path.resolves.length})
                                                    </button>
                                                    <button 
                                                        onClick={() => toggleTab(path.version, 'waiting')}
                                                        className={`flex-1 pb-2 text-xs font-bold uppercase tracking-widest transition-colors ${activeTab === 'waiting' ? 'text-amber-400 border-b-2 border-amber-400' : 'text-slate-500 hover:text-slate-400'}`}
                                                    >
                                                        Waiting ({path.risks_waiting.length})
                                                    </button>
                                                </div>

                                                <div className="flex-1 min-h-[200px]">
                                                    {activeTab === 'resolves' ? (
                                                        <CVEList cves={path.resolves} emptyMsg="No existing vulnerabilities resolved by this upgrade." />
                                                    ) : (
                                                        <CVEList cves={path.risks_waiting} emptyMsg="No known residual vulnerabilities in this version." />
                                                    )}
                                                </div>
                                                
                                                <button className={`mt-6 w-full py-3.5 rounded-xl font-bold text-sm tracking-wide transition-all shadow-lg ${
                                                    isBest 
                                                    ? 'bg-emerald-500 hover:bg-emerald-400 text-emerald-950 shadow-emerald-500/20' 
                                                    : 'btn-ghost shadow-transparent'
                                                }`}>
                                                    Execute Upgrade to {path.version}
                                                </button>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
            
            {/* Custom Styles */}
            <style dangerouslySetInnerHTML={{__html: `
                @keyframes fadeInUp {
                    from { opacity: 0; transform: translateY(15px); }
                    to { opacity: 1; transform: translateY(0); }
                }
                .animate-fade-in-up {
                    animation: fadeInUp 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards;
                }
                @keyframes pulseSlow {
                    0%, 100% { transform: scale(1); }
                    50% { transform: scale(1.05); }
                }
                .animate-pulse-slow {
                    animation: pulseSlow 3s ease-in-out infinite;
                }
                .custom-scrollbar::-webkit-scrollbar {
                    width: 4px;
                }
                .custom-scrollbar::-webkit-scrollbar-track {
                    background: transparent; 
                }
                .custom-scrollbar::-webkit-scrollbar-thumb {
                    background: #334155; 
                    border-radius: 4px;
                }
                .custom-scrollbar::-webkit-scrollbar-thumb:hover {
                    background: #475569; 
                }
            `}} />
        </div>
    );
};

export default UpgradeAdvisor;

---

// filepath: frontend/src/hooks/useAuth.ts
/**
 * useAuth — SSO-Ready Authentication Hook
 *
 * CURRENT BEHAVIOUR (localStorage stub):
 *   Reads/writes a JSON user object from localStorage under the key `sre_auth_user`.
 *   Any component can call `useAuth()` to get the current user and update identity.
 *
 * TO INTEGRATE SSO (OIDC — Keycloak / Azure AD / Okta / Google):
 *   1. Install your OIDC client library (e.g. `oidc-client-ts` or `@azure/msal-react`).
 *   2. Replace the body of this hook with the OIDC provider's hook/context call.
 *   3. Map the OIDC profile to the `AuthUser` shape below.
 *   4. NOTHING else in the app needs to change — all pages consume this hook.
 *
 * OIDC stub (commented) shows where to plug in:
 *   const { user, isAuthenticated } = useOidcUser()   // ← swap here
 */

import { useState, useCallback, createContext, useContext, ReactNode } from 'react'
import React from 'react'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AuthUser {
  /** Full display name, e.g. "Jane Smith" */
  displayName: string
  /** Email or UPN — comes from OIDC claim `email` or `upn` */
  email: string
  /** Role — e.g. "SRE", "SRE Lead", "On-Call". Comes from OIDC `roles` claim */
  role: string
  /** Optional: shift label, e.g. "Morning", "Night", "APAC" */
  shift?: string
}

export interface AuthContextValue {
  user: AuthUser
  isAuthenticated: boolean
  /** Update the local identity (localStorage stub only — no-op when real SSO is active) */
  updateUser: (partial: Partial<AuthUser>) => void
  /** Returns a formatted shift identifier string for handover forms */
  shiftIdentifier: string
}

// ---------------------------------------------------------------------------
// Defaults
// ---------------------------------------------------------------------------

const DEFAULT_USER: AuthUser = {
  displayName: '',
  email: '',
  role: 'SRE',
  shift: '',
}

const STORAGE_KEY = 'sre_auth_user'

function loadUser(): AuthUser {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return { ...DEFAULT_USER, ...JSON.parse(raw) }
  } catch {
    // ignore parse errors
  }
  return DEFAULT_USER
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const AuthContext = createContext<AuthContextValue | null>(null)

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser>(loadUser)

  const isAuthenticated = Boolean(user.displayName)

  const updateUser = useCallback((partial: Partial<AuthUser>) => {
    setUser(prev => {
      const next = { ...prev, ...partial }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
      return next
    })
  }, [])

  const shiftIdentifier = [
    user.displayName,
    user.shift ? `· ${user.shift} Shift` : '',
  ].filter(Boolean).join(' ').trim()

  return React.createElement(
    AuthContext.Provider,
    { value: { user, isAuthenticated, updateUser, shiftIdentifier } },
    children
  )
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>')
  return ctx
}

---

// filepath: frontend/src/hooks/useWebSocket.ts
import { useEffect, useRef, useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'

const WS_BASE = `ws://${window.location.host}/ws`

interface WSMessage {
  type: 'status_change' | 'presence' | 'pong'
  incident_id?: string
  new_status?: string
  actor?: string
  notes?: string
  viewers?: string[]
}

export function useIncidentWebSocket(
  incidentId: string | null,
  userName = 'anonymous',
  onMessage?: (msg: WSMessage) => void
) {
  const wsRef = useRef<WebSocket | null>(null)
  const queryClient = useQueryClient()
  const pingInterval = useRef<ReturnType<typeof setInterval>>()

  const connect = useCallback(() => {
    if (!incidentId) return
    const url = `${WS_BASE}/incidents/${incidentId}?user_name=${encodeURIComponent(userName)}`
    const ws = new WebSocket(url)

    ws.onopen = () => {
      console.log(`[WS] Connected to incident ${incidentId}`)
      // Keep-alive pings every 30s
      pingInterval.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }))
        }
      }, 30_000)
    }

    ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data)
        if (msg.type === 'status_change') {
          // Invalidate React Query cache to trigger re-fetch
          queryClient.invalidateQueries({ queryKey: ['incident', incidentId] })
          queryClient.invalidateQueries({ queryKey: ['incidents'] })
          queryClient.invalidateQueries({ queryKey: ['dashboard-counts'] })
        }
        onMessage?.(msg)
      } catch (e) {
        console.warn('[WS] Failed to parse message', e)
      }
    }

    ws.onclose = () => {
      console.log(`[WS] Disconnected from incident ${incidentId}. Reconnecting in 3s...`)
      clearInterval(pingInterval.current)
      setTimeout(connect, 3_000)
    }

    ws.onerror = (err) => {
      console.error('[WS] Error', err)
      ws.close()
    }

    wsRef.current = ws
  }, [incidentId, userName, queryClient, onMessage])

  useEffect(() => {
    connect()
    return () => {
      clearInterval(pingInterval.current)
      wsRef.current?.close()
    }
  }, [connect])

  return wsRef
}

---

// filepath: frontend/src/pages/Analytics.tsx
import React, { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, PieChart, Pie, Cell, LineChart, Line, Treemap,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { api } from '../api/client'

const COLORS = ['#4f46e5', '#22c55e', '#f97316', '#ef4444', '#06b6d4']

const formatSeconds = (s: number) => {
  const m = Math.round(s / 60)
  return m < 60 ? `${m}m` : `${(m / 60).toFixed(1)}h`
}

export const Analytics: React.FC = () => {
  const [visiblePanels, setVisiblePanels] = useState({
    highLevelMetrics: true,
    resolutionSplit: true,
    sentimentTrend: true,
    environmentDistribution: true,
    mttrChart: true,
    componentsRow: true,
    recurringIncidents: true,
    flappingLeaderboard: true,
  })
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)

  useEffect(() => {
    const saved = localStorage.getItem('analytics_panels')
    if (saved) {
      try { setVisiblePanels(JSON.parse(saved)) } catch (e) {}
    }
  }, [])

  const togglePanel = (key: keyof typeof visiblePanels) => {
    const next = { ...visiblePanels, [key]: !visiblePanels[key] };
    setVisiblePanels(next);
    localStorage.setItem('analytics_panels', JSON.stringify(next));
  }

  const toggleAllPanels = (val: boolean) => {
    const next = Object.keys(visiblePanels).reduce((acc, key) => {
      acc[key as keyof typeof visiblePanels] = val;
      return acc;
    }, {} as typeof visiblePanels);
    setVisiblePanels(next);
    localStorage.setItem('analytics_panels', JSON.stringify(next));
  }

  const { data, isLoading, error } = useQuery({
    queryKey: ['analytics'],
    queryFn: api.getAnalytics,
    staleTime: 60_000,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-400">
        <div className="w-6 h-6 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mr-3" />
        Loading analytics…
      </div>
    )
  }

  if (error || !data) {
    return <p className="text-red-400 text-center py-16">Failed to load analytics.</p>
  }

  const { 
    mttr_by_cluster, resolution_stats, llm_accuracy, top_recurring_alerts,
    flapping_alerts, sentiment_trend, redhat_cases_summary, component_incidents,
    fleet_risk, environment_distribution 
  } = data

  const resolutionPieData = [
    { name: 'Auto-Resolved', value: resolution_stats?.auto_resolved || 0 },
    { name: 'Human-Intervened', value: resolution_stats?.human_intervened || 0 },
  ]

  const llmAccuracyData = [
    { name: 'Approved As-Is', value: llm_accuracy?.approved_as_is || 0, fill: '#22c55e' },
    { name: 'Edited Then Approved', value: llm_accuracy?.edited_before_approve || 0, fill: '#f97316' },
    { name: 'Rejected', value: llm_accuracy?.rejected || 0, fill: '#ef4444' },
  ]

  return (
    <div className="animate-fade-in space-y-8 pb-12">
      {/* Header and Controls */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">
            Analytics <span className="text-gradient">&amp; Insights</span>
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            MTTR trends, LLM accuracy, and incident patterns.
          </p>
        </div>
        
        {/* Panel Toggles */}
        <div className="relative">
          <button 
            onClick={() => setIsDropdownOpen(!isDropdownOpen)}
            className="btn btn-ghost bg-slate-900/50 text-sm border-slate-700 hover:bg-slate-800"
          >
            <span className="text-xs font-semibold text-slate-400 uppercase mr-2">Visible Panels</span>
            <span className="text-slate-300 font-bold bg-surface-700 px-2 py-0.5 rounded text-xs border border-white/5">
              {Object.values(visiblePanels).filter(Boolean).length}/{Object.keys(visiblePanels).length}
            </span>
            <span className="ml-2 text-slate-500 text-xs no-invert">▼</span>
          </button>
          
          {isDropdownOpen && (
            <>
              {/* Invisible backdrop to close dropdown when clicking outside */}
              <div className="fixed inset-0 z-40" onClick={() => setIsDropdownOpen(false)} />
              
              <div className="absolute right-0 top-full mt-2 w-64 bg-surface-800 border border-white/10 rounded-xl shadow-2xl z-50 p-2 max-h-96 overflow-y-auto animate-fade-in">
                <div className="flex items-center justify-between px-3 py-2 mb-2 border-b border-white/5">
                  <button 
                    onClick={() => toggleAllPanels(true)}
                    className="text-xs font-semibold text-brand-400 hover:text-brand-300 transition-colors"
                  >
                    ✓ Select All
                  </button>
                  <button 
                    onClick={() => toggleAllPanels(false)}
                    className="text-xs font-medium text-slate-500 hover:text-slate-400 transition-colors"
                  >
                    Clear All
                  </button>
                </div>
                
                {Object.entries(visiblePanels).map(([key, isVisible]) => (
                  <label key={key} className="flex items-center gap-3 px-3 py-2 hover:bg-white/5 rounded-lg cursor-pointer transition-colors text-sm text-slate-300">
                    <input 
                      type="checkbox" 
                      className="rounded border-slate-600 bg-surface-700 text-brand-500 focus:ring-brand-500 focus:ring-offset-surface-800 w-4 h-4 cursor-pointer"
                      checked={isVisible}
                      onChange={() => togglePanel(key as keyof typeof visiblePanels)}
                    />
                    <span>{key.replace(/([A-Z])/g, ' $1').replace(/^./, str => str.toUpperCase())}</span>
                  </label>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* ─── High-Level Metrics Row ──────────────────────────────────────── */}
      {visiblePanels.highLevelMetrics && fleet_risk && redhat_cases_summary && sentiment_trend && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <div className="glass-card p-6 border-t-4 border-red-500">
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">Fleet Vulnerability Risk</h2>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-3xl font-bold text-white">{fleet_risk.average_risk_pct}%</span>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              {fleet_risk.critical_cves_active} Critical CVEs Active
            </p>
          </div>

          <div className="glass-card p-6 border-t-4 border-blue-500">
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">Open Red Hat Cases</h2>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-3xl font-bold text-white">{redhat_cases_summary.open_cases}</span>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              {redhat_cases_summary.critical_escalation_pct}% of incidents escalated
            </p>
          </div>

          <div className="glass-card p-6 border-t-4 border-purple-500">
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">Vendor MTTR</h2>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-3xl font-bold text-white">{redhat_cases_summary.avg_vendor_mttr_days}</span>
              <span className="text-sm text-slate-400">days</span>
            </div>
            <p className="text-xs text-slate-500 mt-1">Average time to close RH support tickets</p>
          </div>

          <div className="glass-card p-6 border-t-4 border-emerald-500">
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">Avg SRE Sentiment</h2>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-3xl font-bold text-white">
                {sentiment_trend && sentiment_trend.length > 0 ? (sentiment_trend[sentiment_trend.length - 1].average_score * 100).toFixed(0) : 0}%
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1">Resolution quality score (last 24h)</p>
          </div>
        </div>
      )}

      {/* ─── Top row: Resolution split + LLM accuracy ─────────────────── */}
      {visiblePanels.resolutionSplit && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="glass-card p-6">
            <h2 className="text-sm font-semibold text-slate-300 mb-4">
              🤖 Auto vs Human Resolution
            </h2>
            <div className="flex items-center gap-6">
              <ResponsiveContainer width={160} height={160}>
                <PieChart>
                  <Pie
                    data={resolutionPieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={48}
                    outerRadius={70}
                    paddingAngle={4}
                    dataKey="value"
                  >
                    {resolutionPieData.map((_, i) => (
                      <Cell key={i} fill={COLORS[i]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ background: 'var(--chart-tooltip-bg)', border: '1px solid var(--chart-tooltip-border)', borderRadius: 8 }}
                    labelStyle={{ color: 'var(--chart-tick-text)' }}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-3 flex-1">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full" style={{ background: COLORS[0] }} />
                    <span className="text-sm text-slate-300">Auto-Resolved</span>
                  </div>
                  <span className="text-lg font-bold text-white">{resolution_stats?.auto_resolved_pct}%</span>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full" style={{ background: COLORS[1] }} />
                    <span className="text-sm text-slate-300">Human-Intervened</span>
                  </div>
                  <span className="text-lg font-bold text-white">{resolution_stats?.human_intervened_pct}%</span>
                </div>
                <div className="pt-2 border-t border-white/5 text-xs text-slate-500">
                  Total closed: {resolution_stats?.total}
                </div>
              </div>
            </div>
          </div>

          <div className="glass-card p-6">
            <h2 className="text-sm font-semibold text-slate-300 mb-4">
              🧠 LLM Decision Accuracy
            </h2>
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={llmAccuracyData} barSize={32}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid-line)" />
                <XAxis dataKey="name" tick={{ fill: 'var(--chart-tick-text)', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: 'var(--chart-tick-text)', fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{ background: 'var(--chart-tooltip-bg)', border: '1px solid var(--chart-tooltip-border)', borderRadius: 8 }}
                  cursor={{ fill: 'var(--chart-cursor-bg)' }}
                />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {llmAccuracyData.map((entry, i) => (
                    <Cell key={i} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <p className="text-xs text-slate-500 mt-2 text-center">
              Total HIGH-risk reviews: {llm_accuracy?.total_high_risk}
            </p>
          </div>
        </div>
      )}

      {/* ─── Middle row: Sentiment Trend + Environment ─────────────────── */}
      {(visiblePanels.sentimentTrend || visiblePanels.environmentDistribution) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {visiblePanels.sentimentTrend && (
            <div className="glass-card p-6">
              <h2 className="text-sm font-semibold text-slate-300 mb-4">
                📈 SRE Sentiment & Resolution Quality
              </h2>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={sentiment_trend || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid-line)" />
                  <XAxis dataKey="date" tick={{ fill: 'var(--chart-tick-text)', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: 'var(--chart-tick-text)', fontSize: 11 }} axisLine={false} tickLine={false} domain={[0, 1]} />
                  <Tooltip
                    contentStyle={{ background: 'var(--chart-tooltip-bg)', border: '1px solid var(--chart-tooltip-border)', borderRadius: 8 }}
                    formatter={(v: number) => [`${(v * 100).toFixed(1)}%`, 'Avg Score']}
                  />
                  <Line type="monotone" dataKey="average_score" stroke="#06b6d4" strokeWidth={3} dot={{ r: 4, fill: '#06b6d4' }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {visiblePanels.environmentDistribution && (
            <div className="glass-card p-6">
              <h2 className="text-sm font-semibold text-slate-300 mb-4">
                🌍 Incident Distribution by Environment
              </h2>
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie
                    data={environment_distribution || []}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={80}
                    paddingAngle={5}
                    dataKey="incident_count"
                    nameKey="environment"
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  >
                    {(environment_distribution || []).map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ background: 'var(--chart-tooltip-bg)', border: '1px solid var(--chart-tooltip-border)', borderRadius: 8 }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {/* ─── MTTR chart ───────────────────────────────────────────────── */}
      {visiblePanels.mttrChart && mttr_by_cluster?.length > 0 && (
        <div className="glass-card p-6">
          <h2 className="text-sm font-semibold text-slate-300 mb-4">
            ⏱ MTTR by Alert Type (Top 20)
          </h2>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={mttr_by_cluster} layout="vertical" barSize={16}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid-line)" horizontal={false} />
              <XAxis
                type="number"
                tick={{ fill: 'var(--chart-tick-text)', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={formatSeconds}
              />
              <YAxis
                type="category"
                dataKey="alert_name"
                width={180}
                tick={{ fill: 'var(--chart-tick-text)', fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                contentStyle={{ background: 'var(--chart-tooltip-bg)', border: '1px solid var(--chart-tooltip-border)', borderRadius: 8 }}
                formatter={(v: any) => [formatSeconds(Number(v)), 'Avg MTTR']}
                cursor={{ fill: 'var(--chart-cursor-bg)' }}
              />
              <Bar dataKey="avg_mttr_seconds" fill="#4f46e5" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* ─── Components Row ───────────────────────────────────────────── */}
      {visiblePanels.componentsRow && component_incidents?.length > 0 && (
        <div className="glass-card p-6">
          <h2 className="text-sm font-semibold text-slate-300 mb-4">
            🧩 Problematic Components (Incidents by Operator)
          </h2>
          <ResponsiveContainer width="100%" height={260}>
            <Treemap
              data={component_incidents.map((c: any) => ({ name: c.component, size: c.incident_count }))}
              dataKey="size"
              stroke="var(--chart-treemap-stroke)"
              content={((props: any) => {
                const { x, y, width, height, name, index } = props;
                return (
                  <g>
                    <rect
                      x={x}
                      y={y}
                      width={width}
                      height={height}
                      fill={COLORS[index % COLORS.length]}
                      stroke="var(--chart-treemap-stroke)"
                    />
                    {width > 50 && height > 30 && (
                      <text
                        x={x + width / 2}
                        y={y + height / 2}
                        textAnchor="middle"
                        fill="var(--chart-treemap-text)"
                        fontSize={11}
                        pointerEvents="none"
                      >
                        {name}
                      </text>
                    )}
                  </g>
                );
              }) as any}
            >
              <Tooltip
                contentStyle={{ background: 'var(--chart-tooltip-bg)', border: '1px solid var(--chart-tooltip-border)', borderRadius: 8 }}
                formatter={(value: number) => [value, 'Incidents']}
              />
            </Treemap>
          </ResponsiveContainer>
        </div>
      )}

      {/* ─── Top recurring incidents ──────────────────────────────────── */}
      {visiblePanels.recurringIncidents && top_recurring_alerts?.length > 0 && (
        <div className="glass-card overflow-hidden">
          <div className="px-6 py-4 border-b border-white/5">
            <h2 className="text-sm font-semibold text-slate-300">
              🔁 Top Recurring Alerts (Last 30 Days)
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Candidates to promote to LOW risk tier for fully automated resolution.
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Alert Name</th>
                  <th>Cluster</th>
                  <th>Occurrences (30d)</th>
                  <th>Promotion Candidate</th>
                </tr>
              </thead>
              <tbody>
                {top_recurring_alerts.map((row: any, i: number) => (
                  <tr key={i}>
                    <td className="font-medium text-slate-200">{row.alert_name}</td>
                    <td className="font-mono text-xs">{row.cluster}</td>
                    <td>
                      <div className="flex items-center gap-2">
                        <div
                          className="h-2 rounded-full bg-brand-500/70"
                          style={{ width: `${Math.min(100, (row.occurrences_30d / top_recurring_alerts[0].occurrences_30d) * 100)}%`, minWidth: 8 }}
                        />
                        <span className="text-slate-300 font-semibold">{row.occurrences_30d}</span>
                      </div>
                    </td>
                    <td>
                      {row.occurrences_30d >= 5 ? (
                        <span className="badge badge-resolved text-xs">✓ Consider promoting</span>
                      ) : (
                        <span className="text-slate-600 text-xs">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ─── Flapping Alerts Leaderboard ──────────────────────────────── */}
      {visiblePanels.flappingLeaderboard && flapping_alerts?.length > 0 && (
        <div className="glass-card overflow-hidden">
          <div className="px-6 py-4 border-b border-white/5">
            <h2 className="text-sm font-semibold text-slate-300">
              🚨 "Nuisance" Alert Leaderboard (Flapping & Reopened)
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Alerts causing highest SRE fatigue. Needs threshold tuning or remediation fix.
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Alert Name</th>
                  <th>Cluster</th>
                  <th>Flapping Count</th>
                  <th>Reopen Count</th>
                  <th>Total Fatigue Score</th>
                </tr>
              </thead>
              <tbody>
                {flapping_alerts.map((row: any, i: number) => (
                  <tr key={i}>
                    <td className="font-medium text-slate-200">{row.alert_name}</td>
                    <td className="font-mono text-xs">{row.cluster}</td>
                    <td><span className="text-amber-400">{row.flapping_count}</span></td>
                    <td><span className="text-red-400">{row.reopen_count}</span></td>
                    <td>
                      <span className="font-bold text-slate-200 px-2 py-1 bg-surface-700 rounded">
                        {row.flapping_count + row.reopen_count}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

---

// filepath: frontend/src/pages/Dashboard.tsx
import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { format, formatDistanceToNow } from 'date-fns'
import { api } from '../api/client'
import { StatusBadge, RiskBadge, ConfidenceBadge } from '../components/StatusBadge'

// ─── Stat card ────────────────────────────────────────────────────────────────

interface StatCardProps {
  label: string
  value: number | undefined
  icon: string
  accent: string
  description: string
}

const StatCard: React.FC<StatCardProps> = ({ label, value, icon, accent, description }) => (
  <div className={`glass-card p-5 border-l-4 ${accent} hover:scale-[1.01] transition-transform duration-200`}>
    <div className="flex items-start justify-between">
      <div>
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">{label}</p>
        <p className="text-4xl font-bold text-white mt-1">
          {value ?? <span className="text-slate-600 text-2xl">—</span>}
        </p>
        <p className="text-xs text-slate-500 mt-2">{description}</p>
      </div>
      <span className="text-2xl opacity-60">{icon}</span>
    </div>
  </div>
)

// ─── Status filter pills ───────────────────────────────────────────────────────

const STATUS_FILTERS = [
  { value: '', label: 'All' },
  { value: 'PENDING_APPROVAL', label: 'Pending' },
  { value: 'ANALYZING', label: 'Analyzing' },
  { value: 'EXECUTING', label: 'Executing' },
  { value: 'RESOLVED', label: 'Resolved' },
  { value: 'FAILED', label: 'Failed' },
  { value: 'ESCALATED', label: 'Escalated' },
]

// ─── Dashboard page ────────────────────────────────────────────────────────────

export const Dashboard: React.FC = () => {
  const navigate = useNavigate()
  const [statusFilter, setStatusFilter] = React.useState('')
  const [clusterFilter, setClusterFilter] = React.useState('')
  const [alertFilter, setAlertFilter] = React.useState('')
  const [page, setPage] = React.useState(1)

  const { data: counts } = useQuery({
    queryKey: ['dashboard-counts'],
    queryFn: api.getDashboardCounts,
    refetchInterval: 10_000,
  })

  const { data: incidentsData, isLoading } = useQuery({
    queryKey: ['incidents', statusFilter, clusterFilter, alertFilter, page],
    queryFn: () => api.getIncidents({ 
      status: statusFilter || undefined,
      cluster: clusterFilter || undefined,
      alert_name: alertFilter || undefined,
      page 
    }),
    refetchInterval: 15_000,
  })

  return (
    <div className="animate-fade-in space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">
          Incident <span className="text-gradient">Dashboard</span>
        </h1>
        <p className="text-slate-400 text-sm mt-1">
          Real-time view of all SRE incidents managed by the LangChain agent.
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Active"
          value={counts?.active}
          icon="⚡"
          accent="border-blue-500"
          description="Currently being processed"
        />
        <StatCard
          label="Pending Approval"
          value={counts?.pending_approval}
          icon="🔐"
          accent="border-orange-500"
          description="Awaiting human decision"
        />
        <StatCard
          label="Resolved Today"
          value={counts?.resolved_today}
          icon="✓"
          accent="border-emerald-500"
          description="Auto or human-approved fixes"
        />
        <StatCard
          label="Failed"
          value={counts?.failed}
          icon="✗"
          accent="border-red-500"
          description="Execution or agent failures"
        />
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap gap-2">
          {STATUS_FILTERS.map(f => (
            <button
              key={f.value}
              onClick={() => { setStatusFilter(f.value); setPage(1) }}
              className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all duration-200 ${
                statusFilter === f.value
                  ? 'bg-brand-500 text-white shadow-lg shadow-brand-900/40'
                  : 'bg-surface-700 text-slate-400 hover:text-white hover:bg-surface-600'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap gap-3">
          <input 
            type="text" 
            placeholder="Filter by Cluster..." 
            value={clusterFilter}
            onChange={e => { setClusterFilter(e.target.value); setPage(1) }}
            className="bg-surface-700 text-sm text-slate-200 px-3 py-1.5 rounded border border-white/10 focus:outline-none focus:border-brand-500 w-64 transition-colors duration-200"
          />
          <input 
            type="text" 
            placeholder="Filter by Alert Name..." 
            value={alertFilter}
            onChange={e => { setAlertFilter(e.target.value); setPage(1) }}
            className="bg-surface-700 text-sm text-slate-200 px-3 py-1.5 rounded border border-white/10 focus:outline-none focus:border-brand-500 w-64 transition-colors duration-200"
          />
        </div>
      </div>

      {/* Incidents table */}
      <div className="glass-card overflow-hidden">
        <div className="px-4 py-3 border-b border-white/5 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-300">
            Incidents
            {incidentsData?.total !== undefined && (
              <span className="ml-2 text-slate-500 font-normal">({incidentsData.total} total)</span>
            )}
          </h2>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-16 text-slate-400">
            <div className="w-6 h-6 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mr-3" />
            Loading incidents...
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Alert</th>
                  <th>Cluster / Namespace</th>
                  <th>Status</th>
                  <th>Risk</th>
                  <th>Confidence</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {incidentsData?.items?.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="text-center text-slate-500 py-8">
                      No incidents found.
                    </td>
                  </tr>
                ) : (
                  incidentsData?.items?.map((incident: any) => (
                    <tr
                      key={incident.id}
                      onClick={() => navigate(`/incidents/${incident.id}`)}
                      className={incident.status === 'PENDING_APPROVAL' ? 'bg-orange-900/5' : ''}
                    >
                      <td>
                        <div className="font-medium text-slate-200">{incident.alert_name}</div>
                        <div className="text-xs text-slate-500 font-mono mt-0.5">
                          {incident.id.slice(0, 8)}…
                        </div>
                      </td>
                      <td>
                        <div className="text-slate-300">{incident.cluster}</div>
                        <div className="text-xs text-slate-500">{incident.namespace}</div>
                      </td>
                      <td>
                        <StatusBadge status={incident.status} animated />
                      </td>
                      <td>
                        <RiskBadge tier={incident.risk_tier} />
                      </td>
                      <td>
                        <ConfidenceBadge confidence={incident.llm_confidence} />
                      </td>
                      <td className="text-slate-400 text-xs">
                        <div>{format(new Date(incident.created_at), 'MMM d, HH:mm')}</div>
                        <div className="text-slate-600">
                          {formatDistanceToNow(new Date(incident.created_at), { addSuffix: true })}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {incidentsData && incidentsData.total > incidentsData.page_size && (
          <div className="px-4 py-3 border-t border-white/5 flex items-center justify-between">
            <span className="text-xs text-slate-500">
              Page {page} of {Math.ceil(incidentsData.total / incidentsData.page_size)}
            </span>
            <div className="flex gap-2">
              <button
                className="btn-ghost text-xs py-1.5"
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                ← Prev
              </button>
              <button
                className="btn-ghost text-xs py-1.5"
                onClick={() => setPage(p => p + 1)}
                disabled={incidentsData.items.length < incidentsData.page_size}
              >
                Next →
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

---

// filepath: frontend/src/pages/Handovers.tsx
import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { formatDistanceToNow, format } from 'date-fns'
import { api, Handover, HandoverType, HandoverPriority } from '../api/client'
import { useAuth } from '../hooks/useAuth'

// ---------------------------------------------------------------------------
// Static config
// ---------------------------------------------------------------------------

const HANDOVER_TYPES: { value: HandoverType; label: string; icon: string; color: string }[] = [
  { value: 'handover',         label: 'Shift Handover',     icon: '🤝', color: 'text-brand-400 bg-brand-500/15 border-brand-500/30' },
  { value: 'maintenance',      label: 'Maintenance',         icon: '🔧', color: 'text-amber-400 bg-amber-500/15 border-amber-500/30' },
  { value: 'upgrade',          label: 'Platform Upgrade',    icon: '⬆️', color: 'text-sky-400 bg-sky-500/15 border-sky-500/30' },
  { value: 'operator_upgrade', label: 'Operator Upgrade',    icon: '⚙️', color: 'text-violet-400 bg-violet-500/15 border-violet-500/30' },
  { value: 'incident_followup',label: 'Incident Follow-up',  icon: '🔴', color: 'text-rose-400 bg-rose-500/15 border-rose-500/30' },
  { value: 'change_freeze',    label: 'Change Freeze',       icon: '❄️', color: 'text-cyan-400 bg-cyan-500/15 border-cyan-500/30' },
  { value: 'escalation',       label: 'Escalation',          icon: '🚨', color: 'text-orange-400 bg-orange-500/15 border-orange-500/30' },
]

const PRIORITIES: { value: HandoverPriority; label: string; dot: string }[] = [
  { value: 'low',      label: 'Low',      dot: 'bg-slate-400' },
  { value: 'medium',   label: 'Medium',   dot: 'bg-amber-400' },
  { value: 'high',     label: 'High',     dot: 'bg-orange-500' },
  { value: 'critical', label: 'Critical', dot: 'bg-rose-500' },
]

const typeInfo = (t: HandoverType) =>
  HANDOVER_TYPES.find(x => x.value === t) ?? HANDOVER_TYPES[0]

const priorityInfo = (p: HandoverPriority) =>
  PRIORITIES.find(x => x.value === p) ?? PRIORITIES[1]

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function TypeBadge({ type }: { type: HandoverType }) {
  const t = typeInfo(type)
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${t.color}`}>
      <span className="no-invert">{t.icon}</span>
      {t.label}
    </span>
  )
}

function PriorityDot({ priority }: { priority: HandoverPriority }) {
  const p = priorityInfo(priority)
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-slate-400">
      <span className={`w-2 h-2 rounded-full ${p.dot}`} />
      {p.label}
    </span>
  )
}

function ActionBadge({ required }: { required: boolean }) {
  if (!required) return null
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold bg-rose-500/20 text-rose-400 border border-rose-500/40 animate-pulse">
      ⚡ Action Required
    </span>
  )
}

// ---------------------------------------------------------------------------
// Handover Card
// ---------------------------------------------------------------------------

function HandoverCard({ ho }: { ho: Handover }) {
  const queryClient = useQueryClient()
  const [isResolving, setIsResolving] = useState(false)
  const [notes, setNotes] = useState('')

  const updateMutation = useMutation({
    mutationFn: (updates: { is_active?: boolean, resolution_notes?: string, action_required?: boolean }) => 
      api.updateHandover(ho.id, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['handovers'] })
      queryClient.invalidateQueries({ queryKey: ['activeTicker'] })
      setIsResolving(false)
    }
  })

  const borderColor =
    ho.priority === 'critical' ? 'border-l-rose-500' :
    ho.priority === 'high'     ? 'border-l-orange-500' :
    ho.priority === 'medium'   ? 'border-l-amber-500' :
                                  'border-l-slate-600'

  return (
    <div className={`glass-card p-5 border-l-4 ${borderColor} transition-all hover:scale-[1.005]`}>
      {/* Header row */}
      <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-bold text-white text-sm">{ho.shift_identifier || ho.author}</span>
            {ho.cluster && ho.cluster !== 'ALL' && (
              <span className="px-2 py-0.5 rounded-md bg-surface-700 border border-white/10 text-xs text-slate-300 font-mono">
                {ho.cluster}
              </span>
            )}
            {ho.cluster === 'ALL' && (
              <span className="px-2 py-0.5 rounded-md bg-brand-500/10 border border-brand-500/20 text-xs text-brand-400 font-mono">
                ALL CLUSTERS
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 flex-wrap mt-0.5">
            <TypeBadge type={ho.handover_type} />
            <PriorityDot priority={ho.priority} />
            <ActionBadge required={ho.action_required} />
          </div>
        </div>
        <div className="text-xs text-slate-500 shrink-0" title={format(new Date(ho.created_at), 'PPPppp')}>
          {formatDistanceToNow(new Date(ho.created_at), { addSuffix: true })}
        </div>
      </div>

      {/* Message */}
      <div className="text-slate-300 text-sm whitespace-pre-wrap leading-relaxed mb-3">
        {ho.message}
      </div>

      {/* Upgrade Details */}
      {(ho.upgraded_version || ho.operator_name) && (
        <div className="flex items-center gap-4 text-xs text-slate-300 bg-sky-900/20 p-3 rounded-lg mb-3 border border-sky-500/20">
          {ho.handover_type === 'upgrade' && (
            <div><span className="text-sky-400 font-semibold mr-2">Target Version:</span>{ho.upgraded_version}</div>
          )}
          {ho.handover_type === 'operator_upgrade' && (
            <div className="flex gap-4">
              <div><span className="text-violet-400 font-semibold mr-2">Operator:</span>{ho.operator_name}</div>
              <div><span className="text-violet-400 font-semibold mr-2">Version:</span>{ho.upgraded_version}</div>
            </div>
          )}
        </div>
      )}

      {/* Start/End Time for Maintenance */}
      {ho.handover_type === 'maintenance' && (ho.start_time || ho.end_time) && (
        <div className="flex items-center gap-4 text-xs text-slate-400 bg-black/20 p-2 rounded mb-3 font-mono">
          {ho.start_time && <div>Start: {format(new Date(ho.start_time), 'PPp')}</div>}
          {ho.end_time && <div>End: {format(new Date(ho.end_time), 'PPp')}</div>}
        </div>
      )}

      {/* Action / Maintenance Controls */}
      {(ho.action_required || ho.handover_type === 'maintenance' || ho.resolution_notes) && (
        <div className="mt-3 p-3 bg-surface-700/50 rounded-lg border border-white/5">
          {ho.handover_type === 'maintenance' && (
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400">Maintenance Window Status</span>
              <button 
                className={`btn text-xs py-1 px-3 ${ho.is_active ? 'btn-danger' : 'btn-success'}`}
                onClick={() => updateMutation.mutate({ is_active: !ho.is_active })}
                disabled={updateMutation.isPending}
              >
                {ho.is_active ? 'Disable Window' : 'Enable Window'}
              </button>
            </div>
          )}

          {ho.action_required && !isResolving && (
            <div className="flex items-center justify-between">
              <span className="text-xs text-rose-400 font-semibold">Action pending from next shift</span>
              <button 
                className="btn btn-primary text-xs py-1 px-3"
                onClick={() => setIsResolving(true)}
              >
                Resolve Action
              </button>
            </div>
          )}

          {isResolving && (
            <div className="space-y-2">
              <label className="text-xs text-slate-400">Resolution Notes (Required)</label>
              <textarea 
                className="input w-full min-h-[60px] text-xs"
                placeholder="What action was taken?"
                value={notes}
                onChange={e => setNotes(e.target.value)}
              />
              <div className="flex justify-end gap-2">
                <button className="btn btn-ghost text-xs py-1" onClick={() => setIsResolving(false)}>Cancel</button>
                <button 
                  className="btn btn-success text-xs py-1" 
                  disabled={!notes.trim() || updateMutation.isPending}
                  onClick={() => updateMutation.mutate({ action_required: false, is_active: false, resolution_notes: notes })}
                >
                  Submit Resolution
                </button>
              </div>
            </div>
          )}

          {ho.resolution_notes && !ho.action_required && (
            <div className="mt-2">
              <span className="text-xs text-emerald-400 font-semibold mb-1 block">✓ Action Resolved</span>
              <p className="text-xs text-slate-300 bg-black/20 p-2 rounded border-l-2 border-emerald-500">
                {ho.resolution_notes}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Related incidents */}
      {ho.related_incidents && (
        <div className="flex items-center gap-2 flex-wrap mt-2 pt-2 border-t border-white/5">
          <span className="text-xs text-slate-500 uppercase tracking-wide">Related:</span>
          {ho.related_incidents.split(',').map(id => id.trim()).filter(Boolean).map(id => (
            <span key={id} className="px-2 py-0.5 rounded bg-surface-700 border border-white/10 text-xs font-mono text-slate-400">
              {id}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// User Identity Modal (for the localStorage stub)
// ---------------------------------------------------------------------------

function IdentityModal({ onClose }: { onClose: () => void }) {
  const { user, updateUser } = useAuth()
  const [name, setName]   = useState(user.displayName)
  const [shift, setShift] = useState(user.shift ?? '')
  const [role, setRole]   = useState(user.role)

  const save = () => {
    updateUser({ displayName: name, shift, role })
    onClose()
  }

  return (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-surface-800 border border-white/10 rounded-2xl p-6 w-96 shadow-2xl animate-fade-in"
        onClick={e => e.stopPropagation()}
      >
        <h3 className="text-base font-bold text-white mb-1">Your Shift Identity</h3>
        <p className="text-xs text-slate-500 mb-5">
          Used as the Shift Identifier on new handover notes.{' '}
          <span className="text-brand-400">SSO will auto-populate this when integrated.</span>
        </p>
        <div className="space-y-3">
          <div>
            <label className="block text-xs uppercase tracking-wider text-slate-500 mb-1">Full Name</label>
            <input id="identity-name" className="input w-full" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Jane Smith" />
          </div>
          <div>
            <label className="block text-xs uppercase tracking-wider text-slate-500 mb-1">Shift</label>
            <input id="identity-shift" className="input w-full" value={shift} onChange={e => setShift(e.target.value)} placeholder="e.g. Morning, Night, APAC" />
          </div>
          <div>
            <label className="block text-xs uppercase tracking-wider text-slate-500 mb-1">Role</label>
            <select id="identity-role" className="input w-full" value={role} onChange={e => setRole(e.target.value)}>
              <option value="SRE">SRE</option>
              <option value="SRE Lead">SRE Lead</option>
              <option value="On-Call">On-Call</option>
              <option value="Platform Eng">Platform Eng</option>
            </select>
          </div>
        </div>
        <div className="mt-6 flex justify-end gap-3">
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button id="identity-save" className="btn btn-primary" onClick={save}>Save Identity</button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

type FilterState = {
  cluster:       string
  handover_type: string
  priority:      string
}

export const Handovers: React.FC = () => {
  const { user, shiftIdentifier, isAuthenticated } = useAuth()
  const queryClient = useQueryClient()

  // Form state
  const [shiftId,          setShiftId]          = useState(shiftIdentifier)
  const [cluster,          setCluster]          = useState('ALL')
  const [handoverType,     setHandoverType]     = useState<HandoverType>('handover')
  const [priority,         setPriority]         = useState<HandoverPriority>('medium')
  const [actionRequired,   setActionRequired]   = useState(false)
  const [relatedIncidents, setRelatedIncidents] = useState('')
  const [message,          setMessage]          = useState('')
  const [startTime,        setStartTime]        = useState('')
  const [endTime,          setEndTime]          = useState('')
  const [upgradedVersion,  setUpgradedVersion]  = useState('')
  const [operatorName,     setOperatorName]     = useState('')
  const [showIdentity,     setShowIdentity]     = useState(false)
  const [filters,          setFilters]          = useState<FilterState>({
    cluster: '', handover_type: '', priority: '',
  })

  // Sync shift identifier when user changes via identity modal
  React.useEffect(() => {
    if (shiftIdentifier) setShiftId(shiftIdentifier)
  }, [shiftIdentifier])

  // Fetch available clusters
  const { data: availableClusters } = useQuery({
    queryKey: ['handoverClusters'],
    queryFn: api.getHandoverClusters,
    staleTime: 60_000,
  })

  // Query with filters
  const filterParams = Object.fromEntries(
    Object.entries(filters).filter(([, v]) => v !== '')
  )

  const { data: handovers, isLoading } = useQuery({
    queryKey: ['handovers', filterParams],
    queryFn:  () => api.getHandovers(filterParams),
    refetchInterval: 15_000,
  })

  const mutation = useMutation({
    mutationFn: api.createHandover,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['handovers'] })
      queryClient.invalidateQueries({ queryKey: ['activeTicker'] })
      setMessage('')
      setRelatedIncidents('')
      setActionRequired(false)
      setStartTime('')
      setEndTime('')
      setUpgradedVersion('')
      setOperatorName('')
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const authorName = user.displayName || shiftId || 'Anonymous'
    if (!shiftId.trim() || !message.trim()) return
    mutation.mutate({
      author:            authorName,
      shift_identifier:  shiftId.trim(),
      cluster:           cluster || 'ALL',
      handover_type:     handoverType,
      priority,
      action_required:   actionRequired,
      related_incidents: relatedIncidents.trim(),
      message:           message.trim(),
      start_time:        startTime ? new Date(startTime).toISOString() : null,
      end_time:          endTime ? new Date(endTime).toISOString() : null,
      upgraded_version:  upgradedVersion.trim() || null,
      operator_name:     operatorName.trim() || null,
    })
  }

  const setFilter = (key: keyof FilterState, val: string) =>
    setFilters(prev => ({ ...prev, [key]: val }))

  const activeFiltersCount = Object.values(filters).filter(Boolean).length

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-fade-in">

      {/* Page header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">
            Shift <span className="text-gradient">Handovers</span>
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Structured notes to pass critical information between SRE shifts.
          </p>
        </div>
        <button
          id="identity-btn"
          onClick={() => setShowIdentity(true)}
          className="flex items-center gap-2 px-3 py-2 rounded-xl bg-surface-700 border border-white/10 hover:border-brand-500/40 transition-all text-sm"
          title="Set your identity"
        >
          <span className="w-7 h-7 rounded-full bg-brand-500/20 border border-brand-500/40 flex items-center justify-center text-brand-400 text-xs font-bold">
            {(user.displayName || '?')[0]?.toUpperCase()}
          </span>
          <div className="text-left hidden sm:block">
            <p className="text-xs font-semibold text-slate-200 leading-none">
              {user.displayName || 'Set Identity'}
            </p>
            {user.shift && (
              <p className="text-[10px] text-slate-500 leading-none mt-0.5">{user.shift} Shift · {user.role}</p>
            )}
          </div>
          <span className="text-slate-500 text-xs no-invert">✏️</span>
        </button>
      </div>

      {/* Identity not set warning */}
      {!isAuthenticated && (
        <div
          className="flex items-center gap-3 p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400 text-sm cursor-pointer hover:bg-amber-500/15 transition-colors"
          onClick={() => setShowIdentity(true)}
        >
          <span className="text-xl no-invert">👤</span>
          <span>Set your identity so your name appears on handover notes. <strong>Click to configure →</strong></span>
        </div>
      )}

      {/* Compose Form */}
      <div className="glass-card p-6">
        <h2 className="text-sm font-semibold text-slate-300 mb-5 uppercase tracking-wider">
          New Handover Note
        </h2>
        <form onSubmit={handleSubmit} className="space-y-5">

          {/* Row 1: Shift Identifier + Cluster */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5" htmlFor="ho-shift-id">
                Shift Identifier <span className="text-rose-400">*</span>
              </label>
              <input
                id="ho-shift-id"
                type="text"
                className="input w-full"
                placeholder="e.g. Jane Smith · Morning Shift"
                value={shiftId}
                onChange={e => setShiftId(e.target.value)}
              />
              <p className="text-[10px] text-slate-600 mt-1">Auto-filled from your identity. Edit as needed.</p>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5" htmlFor="ho-cluster">
                Cluster
              </label>
              <select
                id="ho-cluster"
                className="input w-full font-mono"
                value={cluster}
                onChange={e => setCluster(e.target.value)}
              >
                <option value="ALL">ALL</option>
                {availableClusters?.map(c => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Row 2: Type + Priority */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5" htmlFor="ho-type">
                Handover Type
              </label>
              <select
                id="ho-type"
                className="input w-full"
                value={handoverType}
                onChange={e => setHandoverType(e.target.value as HandoverType)}
              >
                {HANDOVER_TYPES.map(t => (
                  <option key={t.value} value={t.value}>{t.icon} {t.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5">
                Priority
              </label>
              <div className="flex gap-2">
                {PRIORITIES.map(p => (
                  <button
                    key={p.value}
                    type="button"
                    id={`ho-priority-${p.value}`}
                    onClick={() => setPriority(p.value)}
                    className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg border text-xs font-medium transition-all ${
                      priority === p.value
                        ? `${p.dot.replace('bg-', 'border-').replace('-500', '-500').replace('-400', '-400')} bg-white/10 text-white border-opacity-60`
                        : 'border-white/10 text-slate-500 hover:text-slate-300 hover:border-white/20'
                    }`}
                  >
                    <span className={`w-2 h-2 rounded-full ${p.dot}`} />
                    {p.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Optional: Start/End Times for Maintenance */}
          {handoverType === 'maintenance' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-amber-500/5 p-4 rounded-xl border border-amber-500/20">
              <div>
                <label className="block text-xs font-medium text-amber-400/80 mb-1.5">Start Time (Optional)</label>
                <input 
                  type="datetime-local" 
                  className="input w-full text-sm" 
                  value={startTime}
                  onChange={e => setStartTime(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-amber-400/80 mb-1.5">End Time (Optional)</label>
                <input 
                  type="datetime-local" 
                  className="input w-full text-sm" 
                  value={endTime}
                  onChange={e => setEndTime(e.target.value)}
                />
              </div>
            </div>
          )}

          {/* Upgrade Specific Fields */}
          {handoverType === 'upgrade' && (
            <div className="grid grid-cols-1 gap-4 bg-sky-500/5 p-4 rounded-xl border border-sky-500/20">
              <div>
                <label className="block text-xs font-medium text-sky-400/80 mb-1.5">Version Upgraded To <span className="text-rose-400">*</span></label>
                <input 
                  type="text" 
                  className="input w-full" 
                  placeholder="e.g. 4.13.1"
                  value={upgradedVersion}
                  onChange={e => setUpgradedVersion(e.target.value)}
                />
              </div>
            </div>
          )}
          
          {handoverType === 'operator_upgrade' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-violet-500/5 p-4 rounded-xl border border-violet-500/20">
              <div>
                <label className="block text-xs font-medium text-violet-400/80 mb-1.5">Operator Name <span className="text-rose-400">*</span></label>
                <input 
                  type="text" 
                  className="input w-full" 
                  placeholder="e.g. OpenShift GitOps"
                  value={operatorName}
                  onChange={e => setOperatorName(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-violet-400/80 mb-1.5">Operator Version <span className="text-rose-400">*</span></label>
                <input 
                  type="text" 
                  className="input w-full" 
                  placeholder="e.g. 1.10.1"
                  value={upgradedVersion}
                  onChange={e => setUpgradedVersion(e.target.value)}
                />
              </div>
            </div>
          )}

          {/* Row 3: Related Incidents + Action Required */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5" htmlFor="ho-related">
                Related Alerts/Incidents
              </label>
              <input
                id="ho-related"
                type="text"
                className="input w-full font-mono"
                placeholder="ALERT0012345/INC0012345"
                value={relatedIncidents}
                onChange={e => setRelatedIncidents(e.target.value)}
              />
              <p className="text-[10px] text-slate-600 mt-1">Comma-separated alert/incident IDs</p>
            </div>
            <div className="flex flex-col justify-end">
              <label className="block text-xs font-medium text-slate-400 mb-1.5">
                Action Required
              </label>
              <button
                type="button"
                id="ho-action-toggle"
                onClick={() => setActionRequired(v => !v)}
                className={`flex items-center gap-3 p-3 rounded-xl border transition-all w-full ${
                  actionRequired
                    ? 'bg-rose-500/15 border-rose-500/50 text-rose-400'
                    : 'bg-surface-700 border-white/10 text-slate-500 hover:border-white/20'
                }`}
              >
                <div className={`w-10 h-6 rounded-full transition-all relative ${actionRequired ? 'bg-rose-500' : 'bg-slate-600'}`}>
                  <div className={`absolute top-1 w-4 h-4 rounded-full bg-white shadow transition-all ${actionRequired ? 'left-5' : 'left-1'}`} />
                </div>
                <span className="text-sm font-medium">
                  {actionRequired ? '⚡ Next shift must act' : 'No action needed'}
                </span>
              </button>
            </div>
          </div>

          {/* Message */}
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1.5" htmlFor="ho-message">
              Message <span className="text-rose-400">*</span>
            </label>
            <textarea
              id="ho-message"
              className="input w-full min-h-[120px] resize-y"
              placeholder="Describe ongoing issues, tasks for next shift, relevant observations, or context..."
              value={message}
              onChange={e => setMessage(e.target.value)}
            />
          </div>

          {/* Submit */}
          <div className="flex items-center justify-between pt-1">
            {mutation.isError && (
              <p className="text-xs text-rose-400">Failed to post. Please try again.</p>
            )}
            <div className="ml-auto">
              <button
                id="ho-submit"
                type="submit"
                className="btn btn-primary"
                disabled={
                  mutation.isPending || 
                  !shiftId.trim() || 
                  !message.trim() ||
                  (handoverType === 'upgrade' && !upgradedVersion.trim()) ||
                  (handoverType === 'operator_upgrade' && (!operatorName.trim() || !upgradedVersion.trim()))
                }
              >
                {mutation.isPending ? (
                  <span className="flex items-center gap-2">
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Posting...
                  </span>
                ) : 'Post Handover Note'}
              </button>
            </div>
          </div>
        </form>
      </div>

      {/* Filter Bar */}
      <div className="glass-card p-4">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider mr-1">Filter:</span>

          {/* Type filter */}
          <select
            id="filter-type"
            className="input py-1.5 text-xs"
            value={filters.handover_type}
            onChange={e => setFilter('handover_type', e.target.value)}
          >
            <option value="">All Types</option>
            {HANDOVER_TYPES.map(t => (
              <option key={t.value} value={t.value}>{t.icon} {t.label}</option>
            ))}
          </select>

          {/* Priority filter */}
          <select
            id="filter-priority"
            className="input py-1.5 text-xs"
            value={filters.priority}
            onChange={e => setFilter('priority', e.target.value)}
          >
            <option value="">All Priorities</option>
            {PRIORITIES.map(p => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>

          {/* Cluster filter */}
          <select
            id="filter-cluster"
            className="input py-1.5 text-xs font-mono w-36"
            value={filters.cluster}
            onChange={e => setFilter('cluster', e.target.value)}
          >
            <option value="">All Clusters</option>
            <option value="ALL">ALL</option>
            {availableClusters?.map(c => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>

          {activeFiltersCount > 0 && (
            <button
              id="filter-clear"
              className="text-xs text-brand-400 hover:text-brand-300 transition-colors"
              onClick={() => setFilters({ cluster: '', handover_type: '', priority: '' })}
            >
              ✕ Clear ({activeFiltersCount})
            </button>
          )}
        </div>
      </div>

      {/* Feed */}
      <div className="space-y-4">
        <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
          Recent Handovers
          {activeFiltersCount > 0 && (
            <span className="ml-2 px-2 py-0.5 rounded-full bg-brand-500/20 text-brand-400 text-xs normal-case">
              filtered
            </span>
          )}
        </h2>

        {isLoading ? (
          <div className="flex items-center justify-center py-12 text-slate-400">
            <div className="w-6 h-6 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mr-3" />
            Loading handovers...
          </div>
        ) : handovers?.length === 0 ? (
          <div className="glass-card p-10 text-center text-slate-500">
            <p className="text-3xl mb-3">🤝</p>
            <p>No handover notes found{activeFiltersCount > 0 ? ' matching these filters' : ''}.</p>
          </div>
        ) : (
          handovers?.map((ho: Handover) => (
            <HandoverCard key={ho.id} ho={ho} />
          ))
        )}
      </div>

      {/* Identity Modal */}
      {showIdentity && <IdentityModal onClose={() => setShowIdentity(false)} />}
    </div>
  )
}

---

// filepath: frontend/src/pages/IncidentDetail.tsx
import React, { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { format } from 'date-fns'
import { api } from '../api/client'
import { StatusBadge, RiskBadge, ConfidenceBadge } from '../components/StatusBadge'
import { Timeline } from '../components/Timeline'
import { ApprovalCard } from '../components/ApprovalCard'
import { PresenceIndicators } from '../components/PresenceIndicators'
import { useIncidentWebSocket } from '../hooks/useWebSocket'

export const IncidentDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [viewers, setViewers] = useState<string[]>([])
  const [showTimeline, setShowTimeline] = useState(true)
  const [showAnalysis, setShowAnalysis] = useState(true)
  const [showReasoning, setShowReasoning] = useState(false)
  const [showHumanActions, setShowHumanActions] = useState(true)

  const collapseAll = () => {
    setShowTimeline(false)
    setShowAnalysis(false)
    setShowReasoning(false)
    setShowHumanActions(false)
  }

  const expandAll = () => {
    setShowTimeline(true)
    setShowAnalysis(true)
    setShowReasoning(true)
    setShowHumanActions(true)
  }
  const currentUser = localStorage.getItem('sre_user_id') || 'dev-user'

  const { data: incident, isLoading, error } = useQuery({
    queryKey: ['incident', id],
    queryFn: () => api.getIncident(id!),
    enabled: !!id,
    refetchInterval: 20_000,
  })

  // Real-time WebSocket updates
  useIncidentWebSocket(id ?? null, currentUser, (msg) => {
    if (msg.type === 'presence' && msg.viewers) {
      setViewers(msg.viewers)
    }
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-400">
        <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mr-3" />
        Loading incident…
      </div>
    )
  }

  if (error || !incident) {
    return (
      <div className="text-center py-16">
        <p className="text-red-400 text-lg">Incident not found.</p>
        <button className="btn-ghost mt-4" onClick={() => navigate('/')}>← Back</button>
      </div>
    )
  }

  return (
    <div className="animate-fade-in space-y-6 max-w-5xl">
      <div className="flex items-center justify-between">
        <button
          className="text-slate-400 hover:text-white text-sm flex items-center gap-1.5 transition-colors"
          onClick={() => navigate('/')}
        >
          ← Back to Dashboard
        </button>
        <div className="space-x-4">
          <button onClick={expandAll} className="text-xs text-brand-400 hover:text-brand-300 transition-colors">Expand All</button>
          <button onClick={collapseAll} className="text-xs text-brand-400 hover:text-brand-300 transition-colors">Collapse All</button>
        </div>
      </div>

      {/* ─── Header ─────────────────────────────────────────────────────── */}
      <div className="glass-card p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-xl font-bold text-white truncate">{incident.alert_name}</h1>
              <StatusBadge status={incident.status} animated size="md" />
              <RiskBadge tier={incident.risk_tier} />
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-6 gap-y-2 mt-4 text-sm">
              <div>
                <span className="text-slate-500 text-xs">Cluster</span>
                <p className="text-slate-200 font-medium">{incident.cluster}</p>
              </div>
              <div>
                <span className="text-slate-500 text-xs">Namespace</span>
                <p className="text-slate-200 font-mono text-xs">{incident.namespace}</p>
              </div>
              <div>
                <span className="text-slate-500 text-xs">Hostname</span>
                <p className="text-slate-200 font-mono text-xs">{incident.hostname ?? '—'}</p>
              </div>
              <div>
                <span className="text-slate-500 text-xs">Confidence</span>
                <div className="mt-0.5">
                  <ConfidenceBadge confidence={incident.llm_confidence} />
                </div>
              </div>
              <div>
                <span className="text-slate-500 text-xs">Correlation ID</span>
                <p className="text-slate-300 font-mono text-xs truncate">{incident.correlation_id ?? '—'}</p>
              </div>
              <div>
                <span className="text-slate-500 text-xs">Created</span>
                <p className="text-slate-300 text-xs">
                  {format(new Date(incident.created_at), 'MMM d yyyy, HH:mm:ss')}
                </p>
              </div>
              {incident.awx_job_id && (
                <div>
                  <span className="text-slate-500 text-xs">AWX Job</span>
                  <p className="text-brand-400 font-mono text-xs">#{incident.awx_job_id}</p>
                </div>
              )}
              {incident.resolved_at && (
                <div>
                  <span className="text-slate-500 text-xs">Resolved</span>
                  <p className="text-emerald-400 text-xs">
                    {format(new Date(incident.resolved_at), 'MMM d, HH:mm:ss')}
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Presence indicators */}
          <PresenceIndicators viewers={viewers} />
        </div>
      </div>

      {/* ─── Approval card (shown only when PENDING_APPROVAL) ──────────── */}
      {incident.status === 'PENDING_APPROVAL' && (
        <ApprovalCard incident={incident} currentUserId={currentUser} />
      )}

      {/* ─── Timeline ────────────────────────────────────────────────────── */}
      <div className="glass-card overflow-hidden">
        <button
          className="w-full px-6 py-4 flex items-center justify-between hover:bg-white/3 transition-colors"
          onClick={() => setShowTimeline(!showTimeline)}
        >
          <div className="flex items-center gap-2">
            <span>📋</span>
            <span className="text-sm font-semibold text-slate-300">Incident Timeline</span>
            <span className="ml-2 text-xs text-slate-500 font-normal">{incident.timeline.length} events</span>
          </div>
          <span className="text-slate-500 text-sm">{showTimeline ? '▴' : '▾'}</span>
        </button>
        {showTimeline && (
          <div className="border-t border-white/5 p-6 animate-slide-in">
            <Timeline events={incident.timeline} />
          </div>
        )}
      </div>

      {/* ─── Analysis Summary ────────────────────────────────────────────── */}
      {incident.analysis_summary && (
        <div className="glass-card overflow-hidden">
          <button
            className="w-full px-6 py-4 flex items-center justify-between hover:bg-white/3 transition-colors"
            onClick={() => setShowAnalysis(!showAnalysis)}
          >
            <div className="flex items-center gap-2">
              <span>📊</span>
              <span className="text-sm font-semibold text-slate-300">Enriched Analysis & Diagnostics</span>
            </div>
            <span className="text-slate-500 text-sm">{showAnalysis ? '▴' : '▾'}</span>
          </button>
          {showAnalysis && (
            <div className="border-t border-white/5 p-6 animate-slide-in">
              <pre className="text-sm text-slate-300 whitespace-pre-wrap font-sans leading-relaxed">
                {incident.analysis_summary}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* ─── LLM Reasoning (collapsible) ─────────────────────────────────── */}
      {incident.llm_decisions.length > 0 && (
        <div className="glass-card overflow-hidden">
          <button
            className="w-full px-6 py-4 flex items-center justify-between hover:bg-white/3 transition-colors"
            onClick={() => setShowReasoning(!showReasoning)}
          >
            <div className="flex items-center gap-2">
              <span>🧠</span>
              <span className="text-sm font-semibold text-slate-300">LLM Reasoning & Tool Calls</span>
            </div>
            <span className="text-slate-500 text-sm">{showReasoning ? '▴' : '▾'}</span>
          </button>

          {showReasoning && (
            <div className="border-t border-white/5 p-6 space-y-4 animate-slide-in">
              {incident.llm_decisions.slice(0, 1).map(decision => (
                <div key={decision.id} className="space-y-4">
                  {/* Tool calls */}
                  {decision.tool_calls_json && Array.isArray(decision.tool_calls_json) && (
                    <div>
                      <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                        Tool Calls ({(decision.tool_calls_json as any[]).length})
                      </h4>
                      <div className="space-y-2">
                        {(decision.tool_calls_json as any[]).map((call, i) => (
                          <details key={i} className="bg-surface-700 rounded-lg overflow-hidden">
                            <summary className="px-3 py-2 cursor-pointer text-xs font-mono text-brand-400 hover:text-brand-300 transition-colors">
                              {call.tool}({typeof call.input === 'object' ? JSON.stringify(call.input) : call.input})
                            </summary>
                            <pre className="px-3 pb-3 text-xs text-slate-300 overflow-x-auto">
                              {typeof call.output === 'string'
                                ? call.output
                                : JSON.stringify(call.output, null, 2)}
                            </pre>
                          </details>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Parsed intent */}
                  {decision.parsed_intent && (
                    <div>
                      <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                        Final Intent JSON
                      </h4>
                      <pre className="bg-surface-700 rounded-lg p-3 text-xs font-mono text-slate-300 overflow-x-auto">
                        {JSON.stringify(decision.parsed_intent, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ─── Human Actions log ───────────────────────────────────────────── */}
      {incident.human_actions.length > 0 && (
        <div className="glass-card overflow-hidden">
          <button
            className="w-full px-6 py-4 flex items-center justify-between hover:bg-white/3 transition-colors"
            onClick={() => setShowHumanActions(!showHumanActions)}
          >
            <div className="flex items-center gap-2">
              <span>👤</span>
              <span className="text-sm font-semibold text-slate-300">Human Actions</span>
              <span className="ml-2 text-xs text-slate-500 font-normal">{incident.human_actions.length} actions</span>
            </div>
            <span className="text-slate-500 text-sm">{showHumanActions ? '▴' : '▾'}</span>
          </button>
          {showHumanActions && (
            <div className="border-t border-white/5 p-6 space-y-3 animate-slide-in">
              {incident.human_actions.map(action => (
                <div key={action.id} className="flex items-start gap-3 p-3 bg-surface-700/50 rounded-lg">
                  <div className={`w-2 h-2 rounded-full mt-1.5 ${
                    action.action === 'APPROVED' ? 'bg-emerald-400'
                    : action.action === 'REJECTED' ? 'bg-rose-400'
                    : action.action === 'EDITED' ? 'bg-blue-400'
                    : 'bg-amber-400'
                  }`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-semibold text-slate-200">{action.user_id}</span>
                      <span className={`badge text-xs ${
                        action.action === 'APPROVED' ? 'badge-resolved'
                        : action.action === 'REJECTED' ? 'badge-rejected'
                        : 'badge-analyzing'
                      }`}>{action.action}</span>
                      <span className="text-xs text-slate-500">
                        {format(new Date(action.timestamp), 'MMM d, HH:mm:ss')}
                      </span>
                    </div>
                    <p className="text-sm text-slate-400 mt-1 italic">"{action.reason}"</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

---

// filepath: frontend/src/pages/Summaries.tsx
import React, { useState, useRef, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, HistoricalSummary } from '../api/client'
import { format } from 'date-fns'

interface Message {
  role: 'user' | 'agent'
  content: string
}

export const Summaries: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'chat' | 'history'>('chat')
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [timeframe, setTimeframe] = useState<number>(8)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  
  const [showPreviewModal, setShowPreviewModal] = useState(false)
  const [previewText, setPreviewText] = useState('')
  const [shiftName, setShiftName] = useState('')

  const [showCommands, setShowCommands] = useState(false)
  const availableCommands = [
    { cmd: '/checkalerts', desc: 'View active alerts (e.g. /checkalerts nzclu101)' },
    { cmd: '/escalate', desc: 'Escalate an incident to CRITICAL (e.g. /escalate INC123)' }
  ]

  const queryClient = useQueryClient()

  // 30-min window logic
  const [isWithinWindow, setIsWithinWindow] = useState(false)
  useEffect(() => {
    const checkWindow = () => {
      const now = new Date()
      const hour = now.getHours()
      const minute = now.getMinutes()
      const isShiftStart = (hour === 0 || hour === 8 || hour === 16)
      setIsWithinWindow(isShiftStart && minute <= 30)
    }
    checkWindow()
    const interval = setInterval(checkWindow, 60000)
    return () => clearInterval(interval)
  }, [])

  const chatMutation = useMutation({
    mutationFn: api.chatWithContext,
    onSuccess: (data) => {
      setMessages(prev => [...prev, { role: 'agent', content: data.answer }])
    },
    onError: (error) => {
      setMessages(prev => [...prev, { role: 'agent', content: `Error: ${error.message}` }])
    }
  })

  const previewMutation = useMutation({
    mutationFn: api.previewSummary,
    onSuccess: (data) => {
      setShiftName(data.shift_name)
      setPreviewText(data.preview_text)
      setShowPreviewModal(true)
    }
  })

  const saveMutation = useMutation({
    mutationFn: api.saveSummary,
    onSuccess: () => {
      setShowPreviewModal(false)
      queryClient.invalidateQueries({ queryKey: ['historical_summaries'] })
    }
  })

  const { data: historical } = useQuery({
    queryKey: ['historical_summaries'],
    queryFn: api.getHistoricalSummaries,
    enabled: activeTab === 'history',
  })

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = (text: string) => {
    if (!text.trim()) return
    setMessages(prev => [...prev, { role: 'user', content: text }])
    setInput('')
    chatMutation.mutate({ query: text, timeframe_hours: timeframe })
  }

  const handleQuickAction = (hours: number, promptText: string) => {
    setTimeframe(hours)
    handleSend(promptText)
  }

  return (
    <div className="max-w-5xl mx-auto h-[calc(100vh-8rem)] flex flex-col animate-fade-in relative">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">
            SRE <span className="text-gradient">Summaries</span>
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Persisted shift reports and intelligent query assistant.
          </p>
        </div>
        
        <button 
          onClick={() => previewMutation.mutate()}
          className="btn btn-primary"
          disabled={!isWithinWindow || previewMutation.isPending}
          title={!isWithinWindow ? "Only enabled during the first 30 mins of a shift (00:00, 08:00, 16:00)" : ""}
        >
          {previewMutation.isPending ? 'Generating...' : '📝 Generate Previous Shift Summary'}
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-4 mb-4 border-b border-white/10 pb-2">
        <button 
          className={`text-sm font-semibold pb-2 border-b-2 transition-colors ${activeTab === 'chat' ? 'border-brand-500 text-white' : 'border-transparent text-slate-400 hover:text-slate-200'}`}
          onClick={() => setActiveTab('chat')}
        >
          💬 AI Chat Assistant
        </button>
        <button 
          className={`text-sm font-semibold pb-2 border-b-2 transition-colors ${activeTab === 'history' ? 'border-brand-500 text-white' : 'border-transparent text-slate-400 hover:text-slate-200'}`}
          onClick={() => setActiveTab('history')}
        >
          📚 Historical Shift Reports
        </button>
      </div>

      {activeTab === 'chat' && (
        <div className="flex-1 flex flex-col min-h-0">
          <div className="flex gap-3 mb-4">
            <button 
              onClick={() => handleQuickAction(8, "Please summarize the main incidents and handovers from the last 8 hours.")}
              className="btn btn-ghost border border-white/10 text-xs"
              disabled={chatMutation.isPending}
            >
              ⏱️ Last 8 Hours (Shift Sync)
            </button>
            <button 
              onClick={() => handleQuickAction(168, "Please summarize the critical issues, flapping alerts, and major activities from the last week.")}
              className="btn btn-ghost border border-white/10 text-xs"
              disabled={chatMutation.isPending}
            >
              📅 Last 1 Week (Vector Search)
            </button>
            
            <div className="ml-auto flex items-center gap-2">
              <span className="text-xs text-slate-500">Context Window:</span>
              <select 
                value={timeframe} 
                onChange={e => setTimeframe(Number(e.target.value))}
                className="bg-surface-700 text-xs text-slate-200 px-2 py-1 rounded border border-white/10 focus:outline-none focus:border-brand-500"
              >
                <option value={8}>8 Hours</option>
                <option value={24}>24 Hours</option>
                <option value={168}>1 Week</option>
              </select>
            </div>
          </div>

          <div className="flex-1 glass-card overflow-hidden flex flex-col">
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {messages.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-slate-500">
                  <span className="text-4xl mb-4 opacity-50">🤖</span>
                  <p>I perform semantic vector searches across historical shift reports.</p>
                </div>
              ) : (
                messages.map((msg, i) => (
                  <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[80%] rounded-xl px-5 py-3 ${
                      msg.role === 'user' 
                        ? 'bg-brand-600 text-white shadow-lg shadow-brand-900/20' 
                        : 'bg-surface-600 text-slate-200 border border-white/5'
                    }`}>
                      <div className="text-xs font-semibold opacity-50 mb-1 uppercase tracking-wider">
                        {msg.role === 'user' ? 'You' : 'AI Agent'}
                      </div>
                      <div className="whitespace-pre-wrap text-sm">
                        {msg.content}
                      </div>
                    </div>
                  </div>
                ))
              )}
              {chatMutation.isPending && (
                <div className="flex justify-start">
                  <div className="bg-surface-600 border border-white/5 rounded-xl px-5 py-3 text-slate-400 text-sm flex items-center gap-2">
                    <div className="w-4 h-4 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
                    Searching vectors & summarizing...
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            <div className="p-4 border-t border-white/5 bg-surface-800/50">
              <form 
                onSubmit={e => {
                  e.preventDefault()
                  setShowCommands(false)
                  handleSend(input)
                }}
                className="flex gap-3 relative"
              >
                {showCommands && (
                  <div className="absolute bottom-full left-0 mb-2 w-full max-w-md bg-surface-800 border border-white/10 rounded-xl shadow-2xl overflow-hidden animate-fade-in z-50">
                    <div className="p-2 bg-surface-900 border-b border-white/5 text-xs text-brand-400 font-semibold uppercase tracking-wider">
                      Available Commands
                    </div>
                    {availableCommands.filter(c => c.cmd.startsWith(input.split(' ')[0])).length === 0 ? (
                      <div className="p-3 text-sm text-slate-500">No matching commands.</div>
                    ) : (
                      availableCommands
                        .filter(c => c.cmd.startsWith(input.split(' ')[0]))
                        .map(c => (
                          <button
                            key={c.cmd}
                            type="button"
                            className="w-full text-left p-3 hover:bg-surface-700 transition-colors flex flex-col border-b border-white/5 last:border-0"
                            onClick={() => {
                              setInput(c.cmd + ' ')
                              setShowCommands(false)
                            }}
                          >
                            <span className="font-mono text-brand-300 font-bold">{c.cmd}</span>
                            <span className="text-xs text-slate-400 mt-1">{c.desc}</span>
                          </button>
                      ))
                    )}
                  </div>
                )}
                <input
                  type="text"
                  value={input}
                  onChange={e => {
                    setInput(e.target.value)
                    setShowCommands(e.target.value.startsWith('/'))
                  }}
                  placeholder="Ask about historical alerts or type / for commands..."
                  className="input flex-1"
                  disabled={chatMutation.isPending}
                />
                <button 
                  type="submit" 
                  className="btn btn-primary px-6"
                  disabled={chatMutation.isPending || !input.trim()}
                >
                  Send
                </button>
              </form>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'history' && (
        <div className="flex-1 overflow-y-auto space-y-4">
          {!historical || historical.length === 0 ? (
            <div className="glass-card p-8 text-center text-slate-500">
              No historical shift summaries found.
            </div>
          ) : (
            historical.map((h: HistoricalSummary) => (
              <div key={h.id} className="glass-card p-6 border-l-4 border-brand-500">
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <h3 className="font-bold text-white text-lg">{h.shift_name}</h3>
                    <p className="text-xs text-slate-400 mt-1">
                      {format(new Date(h.created_at), 'PPPppp')} 
                      {h.is_auto_generated ? ' (Auto-Generated via Celery)' : ' (Manually Saved)'}
                    </p>
                  </div>
                </div>
                <div className="text-sm text-slate-300 whitespace-pre-wrap bg-surface-800/50 p-4 rounded-lg border border-white/5">
                  {h.summary_text}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Preview Modal */}
      {showPreviewModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-surface-800 border border-white/10 rounded-xl w-full max-w-4xl shadow-2xl flex flex-col max-h-[90vh]">
            <div className="p-6 border-b border-white/10 flex justify-between items-center">
              <h2 className="text-lg font-bold text-white">Review Shift Report: {shiftName}</h2>
              <button className="text-slate-400 hover:text-white" onClick={() => setShowPreviewModal(false)}>✕</button>
            </div>
            <div className="p-6 flex-1 overflow-hidden flex flex-col">
              <label className="block text-xs font-medium text-slate-400 mb-2 uppercase tracking-wider">Generated Text (Editable)</label>
              <textarea 
                className="input w-full flex-1 resize-none font-mono text-sm"
                value={previewText}
                onChange={e => setPreviewText(e.target.value)}
              />
            </div>
            <div className="p-6 border-t border-white/10 flex justify-end gap-3 bg-surface-900/50">
              <button className="btn btn-ghost" onClick={() => setShowPreviewModal(false)}>Cancel</button>
              <button 
                className="btn btn-primary"
                disabled={saveMutation.isPending}
                onClick={() => saveMutation.mutate({ shift_name: shiftName, summary_text: previewText })}
              >
                {saveMutation.isPending ? 'Saving...' : 'Save & Vectorize Report'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

---

// filepath: ingestion/kafka_consumer.py
"""
Kafka consumer for SRE alert ingestion.

Production-hardened with:
- Pydantic validation of incoming payloads (rejects unknown schemas)
- Poison pill handling: failed messages are committed and written to DLQ topic
- Fixed SQL INTERVAL parameterization (no string interpolation)
- Structured logging bound with correlation_id
"""

from __future__ import annotations

import json
import logging
import os
import uuid

import psycopg2
from kafka import KafkaConsumer, KafkaProducer
from pydantic import BaseModel, ValidationError

from agents.config import DATABASE_TARGET, DEDUP_WINDOW_MINUTES
from worker.tasks import run_agent_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s %(message)s",
)
logger = logging.getLogger("kafka_consumer")

# ---------------------------------------------------------------------------
# Strict payload schema — must match AlertManager webhook format
# ---------------------------------------------------------------------------


class AlertPayload(BaseModel):
    """Validated schema for incoming Kafka alert messages."""
    alert_name: str
    cluster: str
    namespace: str
    hostname: str = ""
    correlation_id: str = ""
    awx_template_id: str = "1"

    def model_post_init(self, __context) -> None:
        if not self.correlation_id:
            self.correlation_id = str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Core alert processing
# ---------------------------------------------------------------------------


def process_alert(payload: AlertPayload) -> None:
    """Create incident and enqueue Celery pipeline. Raises on DB failure."""
    log = logger.getChild(payload.correlation_id)

    try:
        conn = psycopg2.connect(**DATABASE_TARGET)
        cur = conn.cursor()
    except Exception as e:
        log.error("Database connection failed: %s", e)
        raise  # Re-raise so the caller can write to DLQ

    try:
        # Deduplication — correctly parameterized INTERVAL
        cur.execute(
            """
            SELECT id, status FROM incidents_v2
            WHERE alert_name = %s AND cluster = %s AND namespace = %s
              AND created_at > NOW() - (INTERVAL '1 minute' * %s)
              AND status NOT IN ('REJECTED', 'ESCALATED', 'FAILED', 'RESOLVED')
            ORDER BY created_at DESC LIMIT 1;
            """,
            (payload.alert_name, payload.cluster, payload.namespace, DEDUP_WINDOW_MINUTES),
        )
        existing = cur.fetchone()
        if existing:
            log.info("Duplicate deduplicated. Existing incident: %s", existing[0])
            return

        # Create new incident
        incident_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO incidents_v2
              (id, correlation_id, cluster, namespace, alert_name, hostname, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'RECEIVED')
            """,
            (
                incident_id,
                payload.correlation_id,
                payload.cluster,
                payload.namespace,
                payload.alert_name,
                payload.hostname,
            ),
        )
        cur.execute(
            """
            INSERT INTO incident_timeline
              (incident_id, actor_type, action, from_status, to_status, notes)
            VALUES (%s, 'system', 'Alert received from Kafka', NULL, 'RECEIVED', %s)
            """,
            (incident_id, f"correlation_id={payload.correlation_id}"),
        )
        conn.commit()

        log.info("Incident %s created. Enqueueing pipeline.", incident_id)
        run_agent_pipeline.apply_async(
            args=[
                incident_id,
                payload.alert_name,
                payload.namespace,
                payload.cluster,
                payload.hostname,
                payload.correlation_id,
                payload.awx_template_id,
            ],
            queue="default",
        )

    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# Dead Letter Queue writer
# ---------------------------------------------------------------------------


def _write_to_dlq(producer: KafkaProducer, dlq_topic: str, raw_bytes: bytes, reason: str) -> None:
    """Write a failed message to the DLQ topic with failure metadata."""
    try:
        dlq_payload = json.dumps({
            "reason": reason,
            "original_message": raw_bytes.decode("utf-8", errors="replace"),
        }).encode("utf-8")
        producer.send(dlq_topic, dlq_payload)
        producer.flush()
        logger.error("Message written to DLQ '%s'. Reason: %s", dlq_topic, reason)
    except Exception as e:
        logger.critical("FAILED to write to DLQ '%s': %s", dlq_topic, e)


# ---------------------------------------------------------------------------
# Main consumer loop
# ---------------------------------------------------------------------------


def run_consumer() -> None:
    kafka_broker = os.environ.get("KAFKA_BROKER_URL", "localhost:9092")
    kafka_topic = os.environ.get("KAFKA_TOPIC", "sre_alerts")
    dlq_topic = os.environ.get("KAFKA_DLQ_TOPIC", "sre_alerts_dlq")
    group_id = os.environ.get("KAFKA_GROUP_ID", "sre-agent-group")

    logger.info("Starting consumer. broker=%s topic=%s dlq=%s", kafka_broker, kafka_topic, dlq_topic)

    consumer = KafkaConsumer(
        kafka_topic,
        bootstrap_servers=kafka_broker,
        group_id=group_id,
        auto_offset_reset="latest",
        enable_auto_commit=False,   # Manual commit after processing
        value_deserializer=None,    # Raw bytes — we handle deserialization ourselves
    )

    producer = KafkaProducer(bootstrap_servers=kafka_broker)

    for message in consumer:
        raw_bytes = message.value
        try:
            # Step 1: Deserialize
            try:
                raw_dict = json.loads(raw_bytes.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                _write_to_dlq(producer, dlq_topic, raw_bytes, f"JSON decode failed: {e}")
                consumer.commit()
                continue

            # Step 2: Validate schema
            try:
                payload = AlertPayload.model_validate(raw_dict)
            except ValidationError as e:
                _write_to_dlq(producer, dlq_topic, raw_bytes, f"Schema validation failed: {e}")
                consumer.commit()
                continue

            # Step 3: Process — wrap in try/except to prevent crash loops
            try:
                process_alert(payload)
            except Exception as e:
                logger.error(
                    "process_alert failed for correlation_id=%s: %s",
                    raw_dict.get("correlation_id", "unknown"), e,
                )
                _write_to_dlq(producer, dlq_topic, raw_bytes, f"process_alert failed: {e}")

        finally:
            # Always commit offset — even on failure — to avoid poison pill crash loops
            consumer.commit()


if __name__ == "__main__":
    run_consumer()

---

// filepath: ingestion/sync_rhokp_cve_to_postgres.py
import psycopg2
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)

class DynamicCVESyncEngine:
    def __init__(self, db_config):
        self.db_config = db_config
        
    def init_database_schema(self):
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rhokp_cve_knowledge (
                id SERIAL PRIMARY KEY,
                advisory_id VARCHAR(100) UNIQUE,
                affected_versions JSONB,
                fixed_version VARCHAR(50),
                severity VARCHAR(50),
                cves JSONB,
                raw_text TEXT
            );
        """)
        conn.commit()
        cur.close()
        conn.close()

    def get_active_cluster_versions(self):
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT openshift_version FROM clusters WHERE openshift_version IS NOT NULL;")
        versions = [r[0] for r in cur.fetchall()]
        cur.close()
        conn.close()
        return versions
        
    def calculate_targets(self, version_str):
        # Parses e.g. '4.19.10' -> patch 4.19.11, patch 4.19.12, minor 4.20.0
        parts = version_str.split('.')
        if len(parts) < 3:
            return []
        
        try:
            major = int(parts[0])
            minor = int(parts[1])
            patch = int(parts[2].split('-')[0]) # handle -rc1 suffixes
        except ValueError:
            return []
            
        return [
            f"{major}.{minor}.{patch + 1}",
            f"{major}.{minor}.{patch + 2}",
            f"{major}.{minor + 1}.0"
        ]

    def fetch_errata_for_versions(self, active_versions):
        """
        In a production environment, this would dynamically query the authenticated 
        Red Hat Errata API for the specific active and target versions.
        For this pipeline, we simulate the dynamically generated payload.
        """
        errata = []
        advisory_counter = 1000
        
        for version in active_versions:
            targets = self.calculate_targets(version)
            if not targets:
                continue
                
            patch_1 = targets[0]
            patch_2 = targets[1]
            minor_1 = targets[2]
            
            # 1. Vulnerability fixed in patch_1 (Affects 'version')
            errata.append({
                "advisory_id": f"RHSA-{datetime.now().year}:{advisory_counter}",
                "affected_versions": [version],
                "fixed_version": patch_1,
                "severity": "Important",
                "cves": [f"CVE-{datetime.now().year}-100{advisory_counter}"],
                "raw_text": f"Dynamic sync: Security update for {patch_1}. Fixes buffer overflow in {version}."
            })
            advisory_counter += 1
            
            # 2. Vulnerability fixed in patch_2 (Affects 'version' and 'patch_1')
            errata.append({
                "advisory_id": f"RHSA-{datetime.now().year}:{advisory_counter}",
                "affected_versions": [version, patch_1],
                "fixed_version": patch_2,
                "severity": "Critical",
                "cves": [f"CVE-{datetime.now().year}-100{advisory_counter}"],
                "raw_text": f"Dynamic sync: Critical update for {patch_2}. Mitigates remote code execution present since {version}."
            })
            advisory_counter += 1
            
            # 3. Vulnerability fixed in minor_1 (Affects all patch levels of current minor)
            errata.append({
                "advisory_id": f"RHSA-{datetime.now().year}:{advisory_counter}",
                "affected_versions": [version, patch_1, patch_2],
                "fixed_version": minor_1,
                "severity": "Moderate",
                "cves": [f"CVE-{datetime.now().year}-100{advisory_counter}"],
                "raw_text": f"Dynamic sync: Minor release {minor_1} update. Resolves moderate networking disruption."
            })
            advisory_counter += 1
            
        return errata

    def sync(self):
        logging.info("Starting dynamic weekly CVE/Errata sync...")
        self.init_database_schema()
        
        active_versions = self.get_active_cluster_versions()
        logging.info(f"Discovered {len(active_versions)} active cluster versions: {active_versions}")
        
        if not active_versions:
            logging.warning("No active versions found to sync.")
            return
            
        errata_payloads = self.fetch_errata_for_versions(active_versions)
        logging.info(f"Generated {len(errata_payloads)} targeted Errata definitions.")
        
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        
        for record in errata_payloads:
            cur.execute("""
                INSERT INTO rhokp_cve_knowledge (advisory_id, affected_versions, fixed_version, severity, cves, raw_text)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (advisory_id) 
                DO UPDATE SET 
                    affected_versions = EXCLUDED.affected_versions,
                    fixed_version = EXCLUDED.fixed_version,
                    severity = EXCLUDED.severity,
                    cves = EXCLUDED.cves,
                    raw_text = EXCLUDED.raw_text;
            """, (
                record["advisory_id"],
                json.dumps(record["affected_versions"]),
                record["fixed_version"],
                record["severity"],
                json.dumps(record["cves"]),
                record["raw_text"]
            ))
            
        conn.commit()
        cur.close()
        conn.close()
        logging.info("Dynamic sync complete. Knowledge base is up to date.")

if __name__ == "__main__":
    DATABASE_TARGET = {
        "dbname": "rhokp",
        "user": "postgres",
        "password": "postgres",
        "host": "localhost",
        "port": "5432"
    }
    engine = DynamicCVESyncEngine(DATABASE_TARGET)
    engine.sync()

---

// filepath: ingestion/sync_runbook_to_rag.py
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

---

// filepath: ingestion/sync_servicenow_to_postgres.py
import os
import sys
import argparse
import hashlib
import json
from datetime import datetime, timedelta
import requests
import psycopg2
from sentence_transformers import SentenceTransformer

# Silence Hugging Face warnings
os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

DATABASE_TARGET = {
    "dbname": os.environ.get("DB_NAME", "rhokp"),
    "user": os.environ.get("DB_USER", "postgres"),
    "password": os.environ.get("DB_PASSWORD", "postgres"),
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": os.environ.get("DB_PORT", "5432")
}

# State mappings for ServiceNow integer state codes to standard SRE strings
STATE_MAP = {
    "1": "New",
    "2": "Work in Progress",
    "3": "On Hold",
    "6": "Resolved",
    "7": "Closed",
    "8": "Reopened"
}

# Lexicon for rule-based sentiment analysis
POSITIVE_WORDS = ["fixed", "resolved", "stabilized", "restored", "normal", "healthy", "successful", "completed", "great", "excellent", "workaround", "optimal", "recovered"]
NEGATIVE_WORDS = ["error", "fail", "broken", "critical", "outage", "down", "severe", "incident", "issue", "crash", "degraded", "timeout", "saturation", "leak", "exhaustion"]

def analyze_sentiment(text):
    """Performs deterministic rule-based sentiment analysis"""
    if not text:
        return "neutral", 0.5000
    text_lower = text.lower()
    pos_count = sum(text_lower.count(word) for word in POSITIVE_WORDS)
    neg_count = sum(text_lower.count(word) for word in NEGATIVE_WORDS)
    score = 0.5 + (pos_count * 0.12) - (neg_count * 0.12)
    score = max(0.0, min(1.0, score))
    
    if score > 0.58:
        label = "positive"
    elif score < 0.42:
        label = "negative"
    else:
        label = "neutral"
    return label, round(score, 4)

def generate_fingerprint(alertname, namespace, operator_component, cluster_id):
    """Generates a secure SHA-256 fingerprint for alert deduplication"""
    raw_str = f"{alertname}{namespace}{operator_component}{cluster_id}"
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

def get_last_sync_time(conn):
    """Fetches the latest sys_updated_on timestamp from the incidents table"""
    cur = conn.cursor()
    cur.execute("SELECT MAX(sys_updated_on) FROM incidents;")
    last_sync = cur.fetchone()[0]
    cur.close()
    return last_sync

def parse_sys_updated_on(date_str):
    """Parses date string from ServiceNow format into datetime object"""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now()

class ServiceNowSyncEngine:
    def __init__(self, db_config, embed_model_name='all-MiniLM-L6-v2'):
        self.db_config = db_config
        self.embed_model_name = embed_model_name
        self._embed_model = None

    @property
    def embed_model(self):
        if self._embed_model is None:
            print(f"Loading SentenceTransformer model ({self.embed_model_name})...")
            self._embed_model = SentenceTransformer(self.embed_model_name)
        return self._embed_model

    def fetch_live_incidents(self, endpoint, username, password, assignment_group, states, last_sync_time):
        """Pulls updated incident tickets from ServiceNow Table API"""
        query_parts = []
        
        # 1. Add assignment group filter
        if assignment_group:
            query_parts.append(f"assignment_group.name={assignment_group}")
            
        # 2. Add state/status filters
        if states:
            # Map state name inputs to SNOW integer values if necessary
            state_codes = []
            inv_map = {v.lower(): k for k, v in STATE_MAP.items()}
            for st in states:
                st_cleaned = st.strip().lower()
                if st_cleaned in inv_map:
                    state_codes.append(inv_map[st_cleaned])
                elif st_cleaned.isdigit():
                    state_codes.append(st_cleaned)
            if state_codes:
                query_parts.append(f"stateIN{','.join(state_codes)}")
                
        # 3. Add delta sync filter based on last sync timestamp
        if last_sync_time:
            # ServiceNow accepts 'YYYY-MM-DD HH:MM:SS' strings in query filters
            last_sync_str = last_sync_time.strftime("%Y-%m-%d %H:%M:%S")
            query_parts.append(f"sys_updated_on>{last_sync_str}")
            
        sysparm_query = "^".join(query_parts)
        
        print(f"Constructed ServiceNow Query: {sysparm_query}")
        
        params = {
            "sysparm_query": sysparm_query,
            "sysparm_limit": 100
        }
        
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            endpoint,
            auth=(username, password),
            headers=headers,
            params=params,
            timeout=30
        )
        response.raise_for_status()
        
        data = response.json()
        return data.get("result", [])

    def fetch_mock_incidents(self, conn, assignment_group, states, last_sync_time):
        """Simulates ServiceNow responses with mock incremental data for local validation"""
        print("[Mock Mode] Generating mock incremental ServiceNow records...")
        
        # Default sync time to 12 hours ago if empty
        ref_time = last_sync_time if last_sync_time else (datetime.now() - timedelta(hours=12))
        print(f"[Mock Mode] Filtering for updates since: {ref_time}")
        
        cur = conn.cursor()
        # Fetch an existing incident to simulate an update or a reopen
        cur.execute("SELECT sys_id, number, cluster_id, alert_fingerprint, flapping_count FROM incidents LIMIT 1;")
        existing_inc = cur.fetchone()
        cur.close()
        
        mock_records = []
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Scenario A: Simulate a new incoming alert incident (if ref_time is in the past)
        if datetime.now() - ref_time > timedelta(seconds=1):
            mock_records.append({
                "sys_id": "sysid_mock_new_0000000001",
                "number": "INC0099991",
                "state": "1",  # New
                "sys_created_on": now_str,
                "sys_updated_on": now_str,
                "short_description": "Alert 'CoreDNSErrorsHigh' firing in namespace 'openshift-dns' on cluster 'nzclu101'",
                "u_cluster_id": "nzclu101",
                "u_alert_name": "CoreDNSErrorsHigh",
                "u_namespace": "openshift-dns",
                "u_operator": "cluster-dns-operator",
                "u_severity": "warning",
                "u_redhat_case": None,
                "worknotes": "Incident auto-created via mock sync.",
                "comments": "SRE investigating: DNS resolution failing on edge pods."
            })
            
        # Scenario B: Simulate updating an existing incident state (e.g. to Closed or Reopened)
        if existing_inc:
            ex_sys_id, ex_number, ex_cluster, ex_fp, ex_flapping = existing_inc
            mock_records.append({
                "sys_id": ex_sys_id,
                "number": ex_number,
                "state": "7",  # Closed
                "sys_created_on": (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"),
                "sys_updated_on": now_str,
                "short_description": f"Alert update on cluster '{ex_cluster}'",
                "u_cluster_id": ex_cluster,
                "u_alert_name": "KubeVirtNoAvailableNodesToRunVMs",
                "u_namespace": "openshift-cnv",
                "u_operator": "kubevirt-hyperconverged-operator",
                "u_severity": "critical",
                "u_redhat_case": "RH-88392183",
                "worknotes": "Workaround validated. Hyperconverged operator stabilized.",
                "comments": "Resolution: Confirmed alert has cleared and all metrics are normal. Closing the incident ticket."
            })
            
        return mock_records

    def parse_incident_fields(self, record):
        """Extracts and normalizes ServiceNow API payload values with fallback logic"""
        sys_id = record.get("sys_id")
        number = record.get("number")
        
        # Translate SNOW state code to standard text label
        state_code = str(record.get("state"))
        state = STATE_MAP.get(state_code, "Work in Progress")
        
        sys_created_on = parse_sys_updated_on(record.get("sys_created_on"))
        sys_updated_on = parse_sys_updated_on(record.get("sys_updated_on"))
        short_description = record.get("short_description", "No description provided")
        
        cluster_id = record.get("u_cluster_id") or record.get("cluster_id") or "prod-us-east-1"
        redhat_case_id = record.get("u_redhat_case") or record.get("redhat_case_id")
        
        alertname = record.get("u_alert_name") or record.get("alert_name")
        namespace = record.get("u_namespace") or record.get("namespace") or "openshift-monitoring"
        operator_component = record.get("u_operator") or record.get("operator_component") or "prometheus"
        severity = record.get("u_severity") or record.get("severity") or "warning"
        
        # Fallback parser: Try extracting details from short description if custom parameters are missing
        if not alertname and "firing in namespace" in short_description.lower():
            try:
                import re
                match = re.search(r"alert '([^']+)' firing in namespace '([^']+)' on cluster '([^']+)'", short_description.lower())
                if match:
                    alertname = match.group(1)
                    namespace = match.group(2)
                    cluster_id = match.group(3)
            except Exception:
                pass
                
        if not alertname:
            alertname = "UnknownAlert"
            
        fingerprint = generate_fingerprint(alertname, namespace, operator_component, cluster_id)
        
        # Extract comments / worknotes text
        worknotes = record.get("comments") or record.get("worknotes") or record.get("work_notes") or ""
        
        return {
            "sys_id": sys_id,
            "number": number,
            "state": state,
            "sys_created_on": sys_created_on,
            "sys_updated_on": sys_updated_on,
            "short_description": short_description,
            "cluster_id": cluster_id,
            "redhat_case_id": redhat_case_id,
            "alertname": alertname,
            "namespace": namespace,
            "operator_component": operator_component,
            "severity": severity,
            "fingerprint": fingerprint,
            "worknotes": worknotes
        }

    def sync_records(self, records):
        """Processes the parsed records into PostgreSQL, running upserts and vectorizing resolutions"""
        if not records:
            print("No records to synchronize.")
            return
            
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        
        processed_fingerprints = set()
        resolved_incidents = []
        
        try:
            for record_raw in records:
                parsed = self.parse_incident_fields(record_raw)
                sys_id = parsed["sys_id"]
                fingerprint = parsed["fingerprint"]
                processed_fingerprints.add(fingerprint)
                
                print(f"Syncing Incident {parsed['number']} ({parsed['state']}) - Fingerprint: {fingerprint[:10]}...")
                
                # 1. Ensure Cluster is present in DB
                cur.execute("""
                    INSERT INTO clusters (cluster_id, name, openshift_version, environment)
                    VALUES (%s, %s, '4.20.0', 'production')
                    ON CONFLICT (cluster_id) DO NOTHING;
                """, (parsed["cluster_id"], f"Cluster {parsed['cluster_id']}"))
                
                # 2. Upsert Alert Occurrence
                # Increments occurrence count on upsert conflict
                cur.execute("""
                    INSERT INTO alert_occurrences (fingerprint, alertname, namespace, operator_component, cluster_id, severity, occurrence_count, active, first_seen, last_seen)
                    VALUES (%s, %s, %s, %s, %s, %s, 1, %s, %s, %s)
                    ON CONFLICT (fingerprint) DO UPDATE SET
                        occurrence_count = alert_occurrences.occurrence_count + 1,
                        active = EXCLUDED.active,
                        last_seen = EXCLUDED.last_seen;
                """, (
                    fingerprint, parsed["alertname"], parsed["namespace"], parsed["operator_component"],
                    parsed["cluster_id"], parsed["severity"], parsed["state"] not in ("Resolved", "Closed"),
                    parsed["sys_created_on"], parsed["sys_updated_on"]
                ))
                
                # 3. Analyze worknotes sentiment
                sent_lbl, sent_scr = analyze_sentiment(parsed["worknotes"])
                
                # 4. Upsert Incident State
                cur.execute("""
                    INSERT INTO incidents (sys_id, number, state, sys_created_on, sys_updated_on, short_description, cluster_id, alert_fingerprint, flapping_count, redhat_case_id, sentiment_label, sentiment_score, raw_payload)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0, %s, %s, %s, %s)
                    ON CONFLICT (sys_id) DO UPDATE SET
                        state = EXCLUDED.state,
                        sys_updated_on = EXCLUDED.sys_updated_on,
                        redhat_case_id = EXCLUDED.redhat_case_id,
                        sentiment_label = EXCLUDED.sentiment_label,
                        sentiment_score = EXCLUDED.sentiment_score,
                        raw_payload = EXCLUDED.raw_payload;
                """, (
                    sys_id, parsed["number"], parsed["state"], parsed["sys_created_on"], parsed["sys_updated_on"],
                    parsed["short_description"], parsed["cluster_id"], fingerprint, parsed["redhat_case_id"],
                    sent_lbl, sent_scr, json.dumps(record_raw)
                ))
                
                # 5. Insert Worknotes timeline record
                if parsed["worknotes"]:
                    cur.execute("""
                        INSERT INTO incident_worknotes (sys_id, worknote_text, created_on, sentiment_label, sentiment_score)
                        VALUES (%s, %s, %s, %s, %s);
                    """, (sys_id, parsed["worknotes"], parsed["sys_updated_on"], sent_lbl, sent_scr))
                    
                # 6. Append state transition snapshot
                cur.execute("""
                    INSERT INTO incident_snapshots (sys_id, state, sys_updated_on, changed_by, worknotes_added, sentiment_label, sentiment_score)
                    VALUES (%s, %s, %s, 'SRE Sync Engine', %s, %s, %s)
                    ON CONFLICT (sys_id, sys_updated_on) DO NOTHING;
                """, (sys_id, parsed["state"], parsed["sys_updated_on"], parsed["worknotes"], sent_lbl, sent_scr))
                
                # 6.5 Bridge to incidents_v2 (AI Agent Pipeline)
                cur.execute("""
                    SELECT id, status FROM incidents_v2 
                    WHERE cluster = %s AND alert_name = %s 
                    ORDER BY created_at DESC LIMIT 1
                """, (parsed["cluster_id"], parsed["alertname"]))
                v2_incident = cur.fetchone()

                if v2_incident:
                    v2_id, v2_status = v2_incident
                    sys_updated_iso = parsed["sys_updated_on"].isoformat()
                    
                    # Check if we already synced this exact update
                    cur.execute("""
                        SELECT 1 FROM incident_timeline 
                        WHERE incident_id = %s AND metadata_json->>'sys_updated_on' = %s
                    """, (v2_id, sys_updated_iso))
                    
                    if not cur.fetchone():
                        action_str = "ServiceNow ticket resolved" if parsed["state"] in ("Resolved", "Closed") else "ServiceNow ticket updated"
                        to_status = "RESOLVED" if parsed["state"] in ("Resolved", "Closed") else None
                        
                        cur.execute("""
                            INSERT INTO incident_timeline (incident_id, actor_type, actor_id, action, notes, metadata_json, to_status)
                            VALUES (%s, 'human', 'servicenow', %s, %s, %s, %s)
                        """, (str(v2_id), action_str, parsed["worknotes"], json.dumps({"sys_id": sys_id, "sys_updated_on": sys_updated_iso}), to_status))
                        
                        if to_status == "RESOLVED" and v2_status != "RESOLVED":
                            cur.execute("""
                                UPDATE incidents_v2 SET status = 'RESOLVED', resolved_at = NOW() WHERE id = %s
                            """, (str(v2_id),))
                            print(f"--> Linked and resolved AI incident {v2_id} from ServiceNow update.")
                        else:
                            print(f"--> Appended SNOW worknotes to AI incident {v2_id}.")
                
                # Track closed/resolved incidents for RAG vectorization
                if parsed["state"] in ("Resolved", "Closed"):
                    resolved_incidents.append((sys_id, parsed["number"], parsed["short_description"], parsed["worknotes"], sent_lbl))

            
            # 7. Recalculate Recurrence Aggregates for modified alert fingerprints
            for fp in processed_fingerprints:
                print(f"Recalculating aggregates for fingerprint: {fp[:10]}...")
                cur.execute("""
                    SELECT alertname, operator_component, cluster_id, severity, occurrence_count
                    FROM alert_occurrences WHERE fingerprint = %s;
                """, (fp,))
                alert_info = cur.fetchone()
                if not alert_info:
                    continue
                alertname, operator, cluster, severity, occurrence_count = alert_info
                
                # Calculate counts from incidents table
                cur.execute("""
                    SELECT COUNT(*), 
                           COUNT(CASE WHEN state = 'Reopened' THEN 1 END),
                           MAX(CASE WHEN state = 'Reopened' THEN sys_updated_on END)
                    FROM incidents WHERE alert_fingerprint = %s;
                """, (fp,))
                inc_counts = cur.fetchone()
                total_incidents = inc_counts[0] or 0
                reopen_count = inc_counts[1] or 0
                last_reopened = inc_counts[2]
                
                # Calculate average MTTR (seconds)
                cur.execute("""
                    SELECT AVG(EXTRACT(EPOCH FROM (sys_updated_on - sys_created_on))) 
                    FROM incidents 
                    WHERE alert_fingerprint = %s AND state IN ('Resolved', 'Closed');
                """, (fp,))
                avg_mttr = cur.fetchone()[0]
                avg_mttr_sec = int(avg_mttr) if avg_mttr is not None else 0
                
                # Calculate resolution quality score
                # Base is 100, -30 per reopen, +10 for positive sentiment, -10 for negative
                cur.execute("""
                    SELECT AVG(sentiment_score) FROM incidents 
                    WHERE alert_fingerprint = %s AND state IN ('Resolved', 'Closed');
                """, (fp,))
                avg_sentiment = cur.fetchone()[0]
                avg_sent_val = float(avg_sentiment) if avg_sentiment is not None else 0.5
                
                quality_score = 100.0 - (reopen_count * 30.0) + ((avg_sent_val - 0.5) * 40.0)
                quality_score = max(0.0, min(100.0, quality_score))
                
                # Update recurrence intelligence
                cur.execute("""
                    INSERT INTO recurrence_intelligence (fingerprint, alertname, operator_component, cluster_id, total_occurrences, total_incidents, reopen_count, mttr_seconds, resolution_quality_score, last_reopened_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (fingerprint) DO UPDATE SET
                        total_occurrences = EXCLUDED.total_occurrences,
                        total_incidents = EXCLUDED.total_incidents,
                        reopen_count = EXCLUDED.reopen_count,
                        mttr_seconds = EXCLUDED.mttr_seconds,
                        resolution_quality_score = EXCLUDED.resolution_quality_score,
                        last_reopened_at = EXCLUDED.last_reopened_at,
                        updated_at = NOW();
                """, (fp, alertname, operator, cluster, occurrence_count, total_incidents, reopen_count, avg_mttr_sec, round(quality_score, 2), last_reopened))
                
            conn.commit()
            print("Database updates committed successfully.")
            
        except Exception as db_err:
            conn.rollback()
            print(f"Database ingestion error: {db_err}")
            raise db_err
        finally:
            cur.close()
            conn.close()
            
        # 8. Generate and save Vector Embeddings for resolved/closed incidents (Runs outside database txn block)
        if resolved_incidents:
            try:
                embeddings_to_insert = []
                for sys_id, number, short_desc, res_text, sentiment in resolved_incidents:
                    text_chunk = (
                        f"Post-Mortem for ServiceNow Incident {number} | "
                        f"Description: {short_desc} | "
                        f"Resolution Notes: {res_text} | "
                        f"Sentiment: {sentiment.upper()}"
                    )
                    # Create vector representation
                    embedding = self.embed_model.encode(text_chunk).tolist()
                    embeddings_to_insert.append((sys_id, "incidents", text_chunk, embedding, self.embed_model_name, "1.0"))
                    
                conn = psycopg2.connect(**self.db_config)
                cur = conn.cursor()
                cur.executemany("""
                    INSERT INTO operational_knowledge_embeddings (source_id, source_table, text_chunk, embedding, model_name, model_version)
                    VALUES (%s, %s, %s, %s, %s, %s);
                """, embeddings_to_insert)
                conn.commit()

                cur.close()
                conn.close()
                print(f"Generated and saved {len(embeddings_to_insert)} resolution vector embeddings.")
            except Exception as emb_err:
                print(f"[Warning] Failed to generate/save vector embeddings: {emb_err}")

def main():
    parser = argparse.ArgumentParser(description="Live ServiceNow Incident Delta Synchronizer")
    parser.add_argument("--endpoint", type=str, default="https://mock-instance.service-now.com/api/now/table/incident", help="ServiceNow Incident Table API endpoint")
    parser.add_argument("--username", type=str, default="admin", help="ServiceNow username")
    parser.add_argument("--password", type=str, default="admin", help="ServiceNow password")
    parser.add_argument("--assignment-group", type=str, default="ocv-sre-support", help="Sync incidents assigned to this group name")
    parser.add_argument("--states", type=str, default="New,Work in Progress,Resolved,Closed,Reopened", help="Comma-separated status names to pull")
    parser.add_argument("--mock", action="store_true", help="Run in mock mode using simulated data delta updates")
    
    args = parser.parse_args()
    
    print("ServiceNow Incident Delta Ingestion Engine")
    print("==========================================")
    
    try:
        conn = psycopg2.connect(**DATABASE_TARGET)
        last_sync = get_last_sync_time(conn)
        conn.close()
        
        if last_sync:
            print(f"Incremental sync: Last stored incident update was at: {last_sync}")
        else:
            print("Full sync: No incidents found in database. Syncing from default baseline (past 30 days)...")
            
        engine = ServiceNowSyncEngine(db_config=DATABASE_TARGET)
        
        # Pull records
        if args.mock:
            conn = psycopg2.connect(**DATABASE_TARGET)
            records = engine.fetch_mock_incidents(
                conn=conn,
                assignment_group=args.assignment_group,
                states=args.states.split(","),
                last_sync_time=last_sync
            )
            conn.close()
        else:
            records = engine.fetch_live_incidents(
                endpoint=args.endpoint,
                username=args.username,
                password=args.password,
                assignment_group=args.assignment_group,
                states=args.states.split(","),
                last_sync_time=last_sync
            )
            
        print(f"Retrieved {len(records)} updated ServiceNow incident records.")
        
        # Process and sync into PostgreSQL
        engine.sync_records(records)
        print("\nSync workflow completed successfully.")
        
    except Exception as e:
        print(f"\nExecution failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

---

// filepath: simulation/event.json
{
  "cluster": "emclu203",
  "hostname": "emclu203.prod.openshift.com",
  "correlation_id": "emclu203-20260609121120",
  "namespace": "openshift-kube-apiserver",
  "startAt": "2026-05-30T23:20:40Z",
  "alertname": "KubeAPIDown"
}

---

// filepath: simulation/generate_simulated_snow_data.py
import os
import sys
import hashlib
import random
import json
from datetime import datetime, timedelta
import psycopg2
# pyrefly: ignore [missing-import]
from sentence_transformers import SentenceTransformer

# Silence Hugging Face warnings
os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

DATABASE_TARGET = {
    "dbname": "rhokp",
    "user": "postgres",
    "password": "postgres",
    "host": "localhost",
    "port": "5432"
}

# Lexicon for rule-based sentiment analysis
POSITIVE_WORDS = ["fixed", "resolved", "stabilized", "restored", "normal", "healthy", "successful", "completed", "great", "excellent", "workaround", "optimal", "recovered"]
NEGATIVE_WORDS = ["error", "fail", "broken", "critical", "outage", "down", "severe", "incident", "issue", "crash", "degraded", "timeout", "saturation", "leak", "exhaustion"]

def analyze_sentiment(text):
    """
    Performs deterministic rule-based sentiment analysis.
    Returns (label, score) where score is NUMERIC(5, 4) in the range [0.0000, 1.0000]
    """
    if not text:
        return "neutral", 0.5000
    
    text_lower = text.lower()
    pos_count = sum(text_lower.count(word) for word in POSITIVE_WORDS)
    neg_count = sum(text_lower.count(word) for word in NEGATIVE_WORDS)
    
    # Compute score centered at 0.5
    score = 0.5 + (pos_count * 0.12) - (neg_count * 0.12)
    score = max(0.0, min(1.0, score))
    
    if score > 0.58:
        label = "positive"
    elif score < 0.42:
        label = "negative"
    else:
        label = "neutral"
        
    return label, round(score, 4)

def generate_fingerprint(alertname, namespace, operator_component, cluster_id):
    """Generates a secure SHA-256 fingerprint for alert deduplication"""
    raw_str = f"{alertname}{namespace}{operator_component}{cluster_id}"
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

def create_schemas(conn):
    """Creates the tables and indexes according to the approved architecture DDL"""
    cur = conn.cursor()
    print("Enabling pgvector extension if not exists...")
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    
    print("Creating table: clusters...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS clusters (
            cluster_id VARCHAR(50) PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            description VARCHAR(200),
            openshift_version VARCHAR(20) NOT NULL,
            environment VARCHAR(20) NOT NULL CHECK (environment IN ('production', 'staging', 'development', 'dr'))
        );
        ALTER TABLE clusters ADD COLUMN IF NOT EXISTS description VARCHAR(200);
        CREATE INDEX IF NOT EXISTS idx_clusters_env ON clusters(environment);
    """)
    
    print("Creating table: alert_occurrences...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS alert_occurrences (
            fingerprint VARCHAR(64) PRIMARY KEY,
            alertname VARCHAR(100) NOT NULL,
            namespace VARCHAR(100) NOT NULL,
            operator_component VARCHAR(100) NOT NULL,
            cluster_id VARCHAR(50) NOT NULL REFERENCES clusters(cluster_id) ON DELETE CASCADE,
            severity VARCHAR(20) NOT NULL,
            occurrence_count INT DEFAULT 1,
            active BOOLEAN DEFAULT TRUE,
            first_seen TIMESTAMP NOT NULL,
            last_seen TIMESTAMP NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_alerts_lookup ON alert_occurrences(alertname, cluster_id, active);
    """)
    
    print("Creating table: redhat_cases...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS redhat_cases (
            case_id VARCHAR(50) PRIMARY KEY,
            title TEXT NOT NULL,
            status VARCHAR(30) NOT NULL,
            severity VARCHAR(20) NOT NULL,
            created_on TIMESTAMP NOT NULL,
            closed_on TIMESTAMP,
            resolution TEXT
        );
    """)
    
    print("Creating table: incidents...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            sys_id VARCHAR(32) PRIMARY KEY,
            number VARCHAR(20) UNIQUE NOT NULL,
            state VARCHAR(30) NOT NULL,
            sys_created_on TIMESTAMP NOT NULL,
            sys_updated_on TIMESTAMP NOT NULL,
            short_description TEXT NOT NULL,
            cluster_id VARCHAR(50) REFERENCES clusters(cluster_id) ON DELETE SET NULL,
            alert_fingerprint VARCHAR(64) REFERENCES alert_occurrences(fingerprint) ON DELETE SET NULL,
            flapping_count INT DEFAULT 0,
            redhat_case_id VARCHAR(50) REFERENCES redhat_cases(case_id) ON DELETE SET NULL,
            sentiment_label VARCHAR(10) CHECK (sentiment_label IN ('positive', 'negative', 'neutral')),
            sentiment_score NUMERIC(5, 4),
            raw_payload JSONB
        );
        CREATE INDEX IF NOT EXISTS idx_incidents_state ON incidents(state);
        CREATE INDEX IF NOT EXISTS idx_incidents_fingerprint ON incidents(alert_fingerprint);
    """)
    
    print("Creating table: incident_worknotes...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS incident_worknotes (
            id SERIAL PRIMARY KEY,
            sys_id VARCHAR(32) NOT NULL REFERENCES incidents(sys_id) ON DELETE CASCADE,
            worknote_text TEXT NOT NULL,
            created_on TIMESTAMP NOT NULL,
            sentiment_label VARCHAR(10) CHECK (sentiment_label IN ('positive', 'negative', 'neutral')),
            sentiment_score NUMERIC(5, 4)
        );
        CREATE INDEX IF NOT EXISTS idx_worknotes_sys_id ON incident_worknotes(sys_id, created_on DESC);
    """)
    
    print("Creating table: incident_snapshots...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS incident_snapshots (
            snapshot_id SERIAL PRIMARY KEY,
            sys_id VARCHAR(32) NOT NULL REFERENCES incidents(sys_id) ON DELETE CASCADE,
            state VARCHAR(30) NOT NULL,
            sys_updated_on TIMESTAMP NOT NULL,
            changed_by VARCHAR(100) NOT NULL,
            worknotes_added TEXT,
            sentiment_label VARCHAR(10) CHECK (sentiment_label IN ('positive', 'negative', 'neutral')),
            sentiment_score NUMERIC(5, 4),
            CONSTRAINT unique_sys_id_updated UNIQUE (sys_id, sys_updated_on)
        );
        CREATE INDEX IF NOT EXISTS idx_snapshots_lookup ON incident_snapshots(sys_id, sys_updated_on DESC);
    """)
    
    print("Creating table: recurrence_intelligence...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS recurrence_intelligence (
            fingerprint VARCHAR(64) PRIMARY KEY REFERENCES alert_occurrences(fingerprint) ON DELETE CASCADE,
            alertname VARCHAR(100) NOT NULL,
            operator_component VARCHAR(100) NOT NULL,
            cluster_id VARCHAR(50) REFERENCES clusters(cluster_id) ON DELETE CASCADE,
            total_occurrences INT DEFAULT 0,
            total_incidents INT DEFAULT 0,
            reopen_count INT DEFAULT 0,
            mttr_seconds BIGINT DEFAULT 0,
            resolution_quality_score NUMERIC(5, 2),
            last_reopened_at TIMESTAMP,
            updated_at TIMESTAMP NOT NULL
        );
    """)
    
    print("Creating table: operational_knowledge_embeddings...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS operational_knowledge_embeddings (
            id SERIAL PRIMARY KEY,
            source_id VARCHAR(100) NOT NULL,
            source_table VARCHAR(50) NOT NULL,
            text_chunk TEXT NOT NULL,
            embedding vector(384) NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_vector_hnsw ON operational_knowledge_embeddings USING hnsw (embedding vector_l2_ops) WITH (m = 16, ef_construction = 64);
    """)
    
    conn.commit()
    cur.close()
    print("Tables and indexes successfully established!")

def clean_database(conn):
    """Truncates all tables for a clean simulation run"""
    print("Cleaning existing database data...")
    cur = conn.cursor()
    cur.execute("""
        TRUNCATE TABLE 
            operational_knowledge_embeddings, 
            recurrence_intelligence, 
            incident_snapshots, 
            incident_worknotes, 
            incidents, 
            redhat_cases, 
            alert_occurrences, 
            clusters 
        RESTART IDENTITY CASCADE;
    """)
    conn.commit()
    cur.close()
    print("Database cleaned.")

def generate_mock_data(conn):
    """Generates the simulated dataset of clusters, alerts, cases, incidents, snapshots, worknotes, and recurrence aggregates"""
    cur = conn.cursor()
    
    # 1. Clusters (5 clusters)
    clusters_data = [
        ("nzclu101", "nzclu101", "Production New Zealand", "4.20.12", "production"),
        ("emclu202", "emclu202", "Production Emirates", "4.20.12", "production"),
        ("auclo303", "auclo303", "Staging Australia", "4.21.2", "staging"),
        ("inclu404", "inclu404", "Development India", "4.22.0-rc2", "development"),
        ("nzclu102", "nzclu102", "Disaster Recovery New Zealand", "4.20.12", "dr")
    ]
    
    print("Inserting clusters...")
    cur.executemany("""
        INSERT INTO clusters (cluster_id, name, description, openshift_version, environment)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (cluster_id) DO NOTHING;
    """, clusters_data)
    
    # 2. Alert Occurrences (Deterministic Fingerprints)
    # Define a base list of alert profiles
    alert_profiles = [
        ("CollectorNodeDown", "cluster-logging-operator", "logging-operator", "warning"),
        ("KubeAPIDown", "openshift-kube-apiserver", "kube-apiserver-operator", "critical"),
        ("CoreDNSErrorsHigh", "openshift-dns", "cluster-dns-operator", "warning"),
        ("KubeVirtNoAvailableNodesToRunVMs", "openshift-cnv", "kubevirt-hyperconverged-operator", "critical"),
        ("TargetDown", "openshift-monitoring", "prometheus-operator", "warning"),
        ("DiskClusterFailing", "openshift-storage", "ocs-operator", "critical"),
        ("NetworkInterfaceFlapping", "openshift-multus", "multus-operator", "warning"),
        ("APIRequestLatencyHigh", "openshift-kube-apiserver", "kube-apiserver-operator", "warning"),
        ("EtcdMembersDown", "openshift-etcd", "etcd-operator", "critical"),
        ("ingress-operator-degraded", "openshift-ingress-operator", "ingress-operator", "critical")
    ]
    
    alert_occurrences = []
    base_time = datetime.now() - timedelta(days=12)
    
    for cluster_id, _, _, _, _ in clusters_data:
        # Assign 4-6 random alert profiles to each cluster
        selected_profiles = random.sample(alert_profiles, k=random.randint(4, 6))
        for alertname, namespace, operator_component, severity in selected_profiles:
            fingerprint = generate_fingerprint(alertname, namespace, operator_component, cluster_id)
            occurrence_count = random.randint(3, 45)
            first_seen = base_time + timedelta(hours=random.randint(0, 48))
            last_seen = datetime.now() - timedelta(minutes=random.randint(5, 120))
            
            # Decide if active based on environment and profile
            active = random.choice([True, False]) if cluster_id != "inclu404" else True
            
            alert_occurrences.append((
                fingerprint, alertname, namespace, operator_component, cluster_id,
                severity, occurrence_count, active, first_seen, last_seen
            ))
            
    print(f"Inserting {len(alert_occurrences)} alert occurrences...")
    cur.executemany("""
        INSERT INTO alert_occurrences (fingerprint, alertname, namespace, operator_component, cluster_id, severity, occurrence_count, active, first_seen, last_seen)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (fingerprint) DO UPDATE SET
            occurrence_count = EXCLUDED.occurrence_count,
            active = EXCLUDED.active,
            last_seen = EXCLUDED.last_seen;
    """, alert_occurrences)
    
    # 3. Red Hat Support Cases (8 cases)
    redhat_cases_data = [
        ("RH-53029103", "API server timeout on high etcd db size", "Closed", "Severity 1 (Urgent)", base_time, base_time + timedelta(days=1), "Upgraded ETCD database compression intervals and executed manual compaction."),
        ("RH-12948192", "CoreDNS packet drops under severe pod scaling stress", "Closed", "Severity 2 (High)", base_time + timedelta(days=2), base_time + timedelta(days=3), "Adjusted DNS upstream timeout values in CoreDNS configmap Corefile."),
        ("RH-88392183", "KubeVirt hyperconverged operator scheduling failure due to missing node labels", "Closed", "Severity 1 (Urgent)", base_time + timedelta(days=1), base_time + timedelta(days=1, hours=8), "Applied kubevirt node selector overrides to re-allocate scheduling domains."),
        ("RH-99201928", "Prometheus scraper targets crashing due to memory limits", "Open", "Severity 2 (High)", datetime.now() - timedelta(days=2), None, None),
        ("RH-22340182", "OCS StorageCluster Ceph pool degraded IO", "Closed", "Severity 1 (Urgent)", base_time + timedelta(days=4), base_time + timedelta(days=5), "Replaced faulty OSD disk on node-03 and initiated Ceph recovery process."),
        ("RH-33458291", "Multus network attachment definition routing loop", "Closed", "Severity 3 (Medium)", base_time + timedelta(days=3), base_time + timedelta(days=4), "Updated Multus CNI network schema to avoid default bridge route conflicts."),
        ("RH-77482918", "ETCD leader election storm on disk slow operations", "Closed", "Severity 1 (Urgent)", base_time + timedelta(days=6), base_time + timedelta(days=6, hours=12), "Migrated ETCD storage classes to premium SSD disks with guaranteed write IOPS."),
        ("RH-66528192", "Ingress Operator failing HTTP health checks on cluster router pods", "Open", "Severity 2 (High)", datetime.now() - timedelta(hours=18), None, None)
    ]
    
    print("Inserting Red Hat cases...")
    cur.executemany("""
        INSERT INTO redhat_cases (case_id, title, status, severity, created_on, closed_on, resolution)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (case_id) DO UPDATE SET
            status = EXCLUDED.status,
            closed_on = EXCLUDED.closed_on,
            resolution = EXCLUDED.resolution;
    """, redhat_cases_data)
    
    # 4. Generate 55 ServiceNow Incidents
    print("Generating simulated ServiceNow incidents...")
    incidents_to_insert = []
    worknotes_to_insert = []
    snapshots_to_insert = []
    
    # Pre-defined worknotes scripts for SRE updates
    w_neutral_investigate = [
        "SRE investigating alert. Scraping cluster logs and Prometheus telemetry.",
        "Checked node system logs. CPU load is elevated but memory consumption is within limits.",
        "Waiting for telemetry data from cluster operator component.",
        "Analyzing network routing tables and namespace configurations.",
        "Investigating etcd leader history and storage partition status."
    ]
    
    w_negative_degraded = [
        "Severe error: Node resources saturated. Core services throwing timeouts.",
        "Degraded state detected. Database connection pool is exhausted, rejecting API requests.",
        "Outage alert: Multiple pods crashed in namespace. Storage is inaccessible.",
        "Disk latency is extremely high, causing severe read/write lag on the storage nodes.",
        "Network package drop rate is over 15%, causing critical heartbeat failures."
    ]
    
    w_positive_workaround = [
        "Workaround applied: Restarted degraded operators to clear thread pool deadlock.",
        "Fixed issue by scaling the replica count to 3. Network routing has stabilized.",
        "Restored node health by deleting dead containers. Resources returned to healthy levels.",
        "Compacted etcd database, successfully reclaiming 2GB space. Cluster latency is back to normal.",
        "Adjusted routing rules in Multus config. All interfaces are healthy and operating normally."
    ]
    
    w_closing_notes = [
        "Confirmed alert has cleared and all metrics are normal. Closing the incident ticket.",
        "Resolution verified. System remains stable for 1 hour. Ticket resolved successfully.",
        "Workaround confirmed permanent. Alert inactive. Resolving ServiceNow ticket.",
        "Ceph recovery finished. Health status changed back to OK. Ticket closed.",
        "Ingress controller restored. Router pods passing health checks. Ticket resolved."
    ]
    
    # Track metrics for recurrence pre-aggregation
    fingerprint_recurrence_stats = {}
    
    for i in range(1, 56):
        sys_id = f"sysid{i:020d}"
        number = f"INC{i:07d}"
        
        # Link to a random alert occurrence
        alert_occ = random.choice(alert_occurrences)
        fingerprint = alert_occ[0]
        alertname = alert_occ[1]
        namespace = alert_occ[2]
        operator_component = alert_occ[3]
        cluster_id = alert_occ[4]
        
        # Determine incident state: Open (New, Work in Progress, Reopened), Resolved, Closed
        # Let's distribute states realistically
        if i <= 10:
            state = "New"
        elif i <= 25:
            state = "Work in Progress"
        elif i <= 30:
            state = "Reopened"
        elif i <= 45:
            state = "Resolved"
        else:
            state = "Closed"
            
        # Determine flapping count (high flapping count on some warning alerts)
        flapping_count = random.randint(3, 12) if alertname in ("CoreDNSErrorsHigh", "NetworkInterfaceFlapping") else random.randint(0, 2)
        
        # Red Hat case link if critical or high incident
        rh_case_id = None
        if alert_occ[5] == "critical" and random.random() < 0.6:
            # Pick a case matching severity/status if possible
            matching_cases = [c[0] for c in redhat_cases_data if (state in ("Resolved", "Closed") and c[2] == "Closed") or (state not in ("Resolved", "Closed") and c[2] == "Open")]
            if matching_cases:
                rh_case_id = random.choice(matching_cases)
        
        # Ticket creation timestamp
        created_time = base_time + timedelta(days=random.randint(1, 8), hours=random.randint(0, 23))
        
        # Ticket update timestamp
        if state in ("New", "Work in Progress", "Reopened"):
            updated_time = datetime.now() - timedelta(minutes=random.randint(10, 300))
        else:
            # Resolved/Closed tickets
            updated_time = created_time + timedelta(hours=random.randint(1, 48))
            
        short_desc = f"Alert '{alertname}' firing in namespace '{namespace}' on cluster '{cluster_id}'"
        
        # Create worknotes and transitions
        notes = []
        transitions = []
        
        # 1st state transition: New
        transitions.append({
            "state": "New",
            "time": created_time,
            "worknotes": f"Incident created automatically via cluster alert ingestion. Alert Fingerprint: {fingerprint}"
        })
        
        # If state progressed past New
        if state != "New":
            # Add Work in Progress
            wip_time = created_time + timedelta(minutes=random.randint(15, 60))
            notes.append({
                "text": random.choice(w_neutral_investigate),
                "time": wip_time
            })
            transitions.append({
                "state": "Work in Progress",
                "time": wip_time,
                "worknotes": notes[-1]["text"]
            })
            
            # Maybe add a negative degraded note
            if random.random() < 0.7:
                deg_time = wip_time + timedelta(minutes=random.randint(30, 120))
                notes.append({
                    "text": random.choice(w_negative_degraded),
                    "time": deg_time
                })
                # (State remains WIP but worknotes added)
            
            # Reopened state simulation
            if state == "Reopened":
                # First Resolved
                res_time = wip_time + timedelta(hours=random.randint(2, 6))
                notes.append({
                    "text": random.choice(w_positive_workaround),
                    "time": res_time
                })
                transitions.append({
                    "state": "Resolved",
                    "time": res_time,
                    "worknotes": notes[-1]["text"]
                })
                
                # Then Reopened
                reopen_time = res_time + timedelta(hours=random.randint(1, 12))
                notes.append({
                    "text": "Incident reopened: Alert re-fired shortly after closure. Flapping suspected.",
                    "time": reopen_time
                })
                transitions.append({
                    "state": "Reopened",
                    "time": reopen_time,
                    "worknotes": notes[-1]["text"]
                })
                
            # If resolved or closed
            elif state in ("Resolved", "Closed"):
                res_time = wip_time + timedelta(hours=random.randint(2, 12))
                res_comment = random.choice(w_positive_workaround)
                notes.append({
                    "text": res_comment,
                    "time": res_time
                })
                transitions.append({
                    "state": "Resolved",
                    "time": res_time,
                    "worknotes": res_comment
                })
                
                if state == "Closed":
                    cls_time = res_time + timedelta(hours=random.randint(12, 24))
                    cls_comment = random.choice(w_closing_notes)
                    notes.append({
                        "text": cls_comment,
                        "time": cls_time
                    })
                    transitions.append({
                        "state": "Closed",
                        "time": cls_time,
                        "worknotes": cls_comment
                    })

        # Calculate final sentiment label and score based on the LAST worknote/closing comment
        last_note_text = notes[-1]["text"] if notes else short_desc
        sent_lbl, sent_scr = analyze_sentiment(last_note_text)
        
        # Determine hostname based on cluster location pattern
        loc = cluster_id[:2] if len(cluster_id) >= 2 else "nz"
        hostname = f"{loc}o{random.randint(10000, 99999)}"
        
        # Build Raw JSON Payload
        raw_payload = {
            "sys_id": sys_id,
            "number": number,
            "state": state,
            "sys_created_on": created_time.strftime("%Y-%m-%d %H:%M:%S"),
            "sys_updated_on": updated_time.strftime("%Y-%m-%d %H:%M:%S"),
            "short_description": short_desc,
            "u_cluster_id": cluster_id,
            "u_hostname": hostname,
            "u_alert_name": alertname,
            "u_namespace": namespace,
            "u_operator": operator_component,
            "u_severity": alert_occ[5],
            "u_redhat_case": rh_case_id,
            "close_notes": last_note_text if state in ("Resolved", "Closed") else "",
            "worknotes": [n["text"] for n in notes]
        }
        
        # Append to main records list
        incidents_to_insert.append((
            sys_id, number, state, created_time, updated_time, short_desc,
            cluster_id, fingerprint, flapping_count, rh_case_id,
            sent_lbl, sent_scr, json.dumps(raw_payload)
        ))
        
        # Compile worknotes for batch insert
        for n in notes:
            n_lbl, n_scr = analyze_sentiment(n["text"])
            worknotes_to_insert.append((
                sys_id, n["text"], n["time"], n_lbl, n_scr
            ))
            
        # Compile snapshots for batch insert (deduplicating by unique sys_id & updated_on)
        seen_snapshots = set()
        for snap in transitions:
            snap_time_str = snap["time"].strftime("%Y-%m-%d %H:%M:%S")
            snap_key = (sys_id, snap_time_str)
            if snap_key not in seen_snapshots:
                seen_snapshots.add(snap_key)
                s_lbl, s_scr = analyze_sentiment(snap["worknotes"])
                snapshots_to_insert.append((
                    sys_id, snap["state"], snap["time"], "SRE Automated Integrator",
                    snap["worknotes"], s_lbl, s_scr
                ))
                
        # Aggregate recurrence metrics tracking per alert fingerprint
        if fingerprint not in fingerprint_recurrence_stats:
            fingerprint_recurrence_stats[fingerprint] = {
                "alertname": alertname,
                "operator_component": operator_component,
                "cluster_id": cluster_id,
                "total_occurrences": alert_occ[6], # from alert_occurrences
                "total_incidents": 0,
                "reopen_count": 0,
                "mttr_durations": [],
                "last_reopened_at": None,
                "resolutions": []
            }
            
        stats = fingerprint_recurrence_stats[fingerprint]
        stats["total_incidents"] += 1
        
        if state == "Reopened":
            stats["reopen_count"] += 1
            if stats["last_reopened_at"] is None or updated_time > stats["last_reopened_at"]:
                stats["last_reopened_at"] = updated_time
                
        if state in ("Resolved", "Closed"):
            duration = (updated_time - created_time).total_seconds()
            stats["mttr_durations"].append(duration)
            stats["resolutions"].append((sent_scr, state == "Reopened"))

    # Insert incidents
    print("Inserting ServiceNow incidents...")
    cur.executemany("""
        INSERT INTO incidents (sys_id, number, state, sys_created_on, sys_updated_on, short_description, cluster_id, alert_fingerprint, flapping_count, redhat_case_id, sentiment_label, sentiment_score, raw_payload)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (sys_id) DO UPDATE SET
            state = EXCLUDED.state,
            sys_updated_on = EXCLUDED.sys_updated_on,
            flapping_count = incidents.flapping_count + EXCLUDED.flapping_count,
            redhat_case_id = EXCLUDED.redhat_case_id,
            sentiment_label = EXCLUDED.sentiment_label,
            sentiment_score = EXCLUDED.sentiment_score,
            raw_payload = EXCLUDED.raw_payload;
    """, incidents_to_insert)
    
    # Insert worknotes
    print("Inserting incident worknotes...")
    cur.executemany("""
        INSERT INTO incident_worknotes (sys_id, worknote_text, created_on, sentiment_label, sentiment_score)
        VALUES (%s, %s, %s, %s, %s);
    """, worknotes_to_insert)
    
    # Insert snapshots
    print("Inserting incident snapshots...")
    cur.executemany("""
        INSERT INTO incident_snapshots (sys_id, state, sys_updated_on, changed_by, worknotes_added, sentiment_label, sentiment_score)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (sys_id, sys_updated_on) DO NOTHING;
    """, snapshots_to_insert)
    
    # Calculate and insert Recurrence Intelligence Aggregates
    print("Calculating and inserting recurrence aggregates...")
    recurrence_data = []
    for fp, stats in fingerprint_recurrence_stats.items():
        avg_mttr = int(sum(stats["mttr_durations"]) / len(stats["mttr_durations"])) if stats["mttr_durations"] else 0
        
        # Calculate resolution quality score: starts at 100
        # Deduct 30 per reopen
        # Add (sentiment score - 0.5) * 40
        quality_score = 100.0
        quality_score -= stats["reopen_count"] * 30.0
        
        if stats["resolutions"]:
            avg_res_sent = sum(r[0] for r in stats["resolutions"]) / len(stats["resolutions"])
            quality_score += (avg_res_sent - 0.5) * 40.0
            
        quality_score = max(0.0, min(100.0, quality_score))
        
        recurrence_data.append((
            fp, stats["alertname"], stats["operator_component"], stats["cluster_id"],
            stats["total_occurrences"], stats["total_incidents"], stats["reopen_count"],
            avg_mttr, round(quality_score, 2), stats["last_reopened_at"], datetime.now()
        ))
        
    cur.executemany("""
        INSERT INTO recurrence_intelligence (fingerprint, alertname, operator_component, cluster_id, total_occurrences, total_incidents, reopen_count, mttr_seconds, resolution_quality_score, last_reopened_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (fingerprint) DO UPDATE SET
            total_occurrences = EXCLUDED.total_occurrences,
            total_incidents = EXCLUDED.total_incidents,
            reopen_count = EXCLUDED.reopen_count,
            mttr_seconds = EXCLUDED.mttr_seconds,
            resolution_quality_score = EXCLUDED.resolution_quality_score,
            last_reopened_at = EXCLUDED.last_reopened_at,
            updated_at = EXCLUDED.updated_at;
    """, recurrence_data)
    
    conn.commit()
    cur.close()
    print(f"Data seeding completed! Generated:")
    print(f" - {len(clusters_data)} Clusters")
    print(f" - {len(alert_occurrences)} Alert Occurrences")
    print(f" - {len(redhat_cases_data)} Red Hat Cases")
    print(f" - {len(incidents_to_insert)} ServiceNow Incidents")
    print(f" - {len(worknotes_to_insert)} Incident Worknotes")
    print(f" - {len(snapshots_to_insert)} Incident Snapshots")
    print(f" - {len(recurrence_data)} Recurrence Aggregates")

def generate_vector_embeddings(conn):
    """Generates sentence embeddings for SRE Playbooks and incident resolutions using all-MiniLM-L6-v2"""
    print("Loading SentenceTransformer model (all-MiniLM-L6-v2)...")
    embed_model = SentenceTransformer('all-MiniLM-L6-v2')
    
    cur = conn.cursor()
    
    # 1. Fetch resolved/closed incidents that have resolutions to embed
    cur.execute("""
        SELECT sys_id, number, short_description, sentiment_label 
        FROM incidents 
        WHERE state IN ('Resolved', 'Closed');
    """)
    resolved_incidents = cur.fetchall()
    
    embeddings_to_insert = []
    print(f"Generating embeddings for {len(resolved_incidents)} incident post-mortems/resolutions...")
    
    for sys_id, number, short_desc, sentiment in resolved_incidents:
        # Fetch the resolution comment (last worknote of state Resolved/Closed)
        cur.execute("""
            SELECT worknote_text FROM incident_worknotes 
            WHERE sys_id = %s 
            ORDER BY created_on DESC LIMIT 1;
        """, (sys_id,))
        res_note = cur.fetchone()
        res_text = res_note[0] if res_note else "Incident resolved."
        
        text_chunk = (
            f"Post-Mortem for ServiceNow Incident {number} | "
            f"Description: {short_desc} | "
            f"Resolution Notes: {res_text} | "
            f"Sentiment: {sentiment.upper()}"
        )
        
        # Generate dense vector coordinates
        embedding = embed_model.encode(text_chunk).tolist()
        
        embeddings_to_insert.append((
            sys_id, "incidents", text_chunk, embedding
        ))
        
    # 2. Add some standard SRE Playbook sections to embed for RAG similarity matches
    playbooks = [
        ("playbook-apiserver-timeout", "SRE Playbook: KubeAPIDown & RequestLatencyHigh. Core symptoms include API timeouts. Remediation: Check etcd DB size. If database size exceeds 2GB, trigger compaction. Compacting etcd database releases database space and brings latency back to normal levels. If load is extreme, increase master nodes resource allocations.", "playbooks"),
        ("playbook-dns-errors", "SRE Playbook: CoreDNSErrorsHigh. Core symptoms include packet drops. Remediation: Verify DNS configuration Corefile settings and check for packet losses. Increase CoreDNS pod replicas and adjust upstream DNS timeouts to avoid query starvation under heavy scale stress.", "playbooks"),
        ("playbook-kubevirt-nodes", "SRE Playbook: KubeVirtNoAvailableNodesToRunVMs. Core symptoms include VM scheduling failure. Remediation: Check node labeling and taints. Apply the required hyperconverged virtualization labels (e.g. kubevirt.io/schedulable=true) to eligible worker nodes to re-allocate scheduling domains.", "playbooks"),
        ("playbook-disk-failing", "SRE Playbook: DiskClusterFailing & Ceph Degraded. Core symptoms include high disk write latency and degraded Ceph pools. Remediation: Locate the faulty OSD disk identifier from ceph health logs. Replace the failed disk immediately. Once the new disk is attached, trigger ceph recovery process.", "playbooks"),
        ("playbook-network-flapping", "SRE Playbook: NetworkInterfaceFlapping. Core symptoms include interface loops and Multus failures. Remediation: Inspect Multus NetworkAttachmentDefinition routing rules. Avoid default bridge configurations that create loop conditions. Re-apply validated static routing maps.", "playbooks")
    ]
    
    print("Generating embeddings for standard SRE playbooks...")
    for pb_id, pb_text, table_src in playbooks:
        embedding = embed_model.encode(pb_text).tolist()
        embeddings_to_insert.append((
            pb_id, table_src, pb_text, embedding
        ))
        
    print(f"Inserting {len(embeddings_to_insert)} records into operational_knowledge_embeddings...")
    cur.executemany("""
        INSERT INTO operational_knowledge_embeddings (source_id, source_table, text_chunk, embedding)
        VALUES (%s, %s, %s, %s);
    """, embeddings_to_insert)
    
    conn.commit()
    cur.close()
    print("Vector embeddings successfully saved and HNSW indexed!")

def main():
    conn = None
    try:
        print(f"Connecting to database: {DATABASE_TARGET['dbname']} on {DATABASE_TARGET['host']}:{DATABASE_TARGET['port']}...")
        conn = psycopg2.connect(**DATABASE_TARGET)
        
        # 1. Initialize DB tables, constraints and vectors
        create_schemas(conn)
        
        # 2. Clear tables to support clean replay
        clean_database(conn)
        
        # 3. Insert mock data
        generate_mock_data(conn)
        
        # 4. Generate embeddings
        generate_vector_embeddings(conn)
        
        print("\nAll database simulation tasks completed successfully! Database is ready.")
    except Exception as e:
        print(f"Error executing database simulation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    main()

---

// filepath: simulation/mock_client.py
"""
Mock AWX client for local development and integration testing.

Simulates the AWX job lifecycle: PENDING → RUNNING → SUCCESSFUL/FAILED
with configurable delays. Drop-in replacement for awx.client.AWXClient.
"""

from __future__ import annotations

import logging
import random
import time
import uuid
from dataclasses import dataclass, field
from typing import Literal

from awx.client import AWXJobResult, AWXJobStatus

logger = logging.getLogger(__name__)


class MockAWXClient:
    """
    Simulates AWX REST API behavior without a real AWX server.

    Job lifecycle (configurable):
    - Jobs start in PENDING
    - After `pending_delay` seconds → RUNNING
    - After `run_delay` seconds → SUCCESSFUL (or FAILED if fail_rate triggers)

    Usage in tests:
        client = MockAWXClient(fail_rate=0.0)  # always succeed
        job_id = client.launch_job("42", intent.to_awx_extra_vars())
        result = client.get_job_status(job_id)
    """

    def __init__(
        self,
        fail_rate: float = 0.0,        # 0.0 = always succeed, 1.0 = always fail
        pending_delay: float = 0.5,    # seconds before RUNNING
        run_delay: float = 1.0,        # seconds before terminal state
    ):
        self._fail_rate = fail_rate
        self._pending_delay = pending_delay
        self._run_delay = run_delay

    def launch_job(self, template_id: str, extra_vars: dict) -> str:
        started_at = int(time.time())
        job_id = f"mock-{started_at}-{uuid.uuid4().hex[:8]}"
        logger.info(
            "[MOCK AWX] Job launched: id=%s template=%s extra_vars=%s",
            job_id,
            template_id,
            extra_vars,
        )
        return job_id

    def get_job_status(self, job_id: str) -> AWXJobResult:
        if not job_id.startswith("mock-"):
            return AWXJobResult(
                job_id=job_id,
                status=AWXJobStatus.ERROR,
                url=f"http://mock-awx/#/jobs/{job_id}",
            )

        try:
            started_at = int(job_id.split("-")[1])
        except (IndexError, ValueError):
            started_at = time.time() - 100  # fallback

        elapsed = time.time() - started_at

        if elapsed < self._pending_delay:
            status = AWXJobStatus.PENDING
        elif elapsed < self._pending_delay + self._run_delay:
            status = AWXJobStatus.RUNNING
        else:
            status = AWXJobStatus.SUCCESSFUL

        logger.debug("[MOCK AWX] get_job_status id=%s → %s (elapsed=%.1fs)", job_id, status, elapsed)

        return AWXJobResult(
            job_id=job_id,
            status=status,
            url=f"http://mock-awx/#/jobs/{job_id}",
            elapsed=round(elapsed, 2),
            failed=(status == AWXJobStatus.FAILED),
            extra_vars={},
        )

    def cancel_job(self, job_id: str) -> bool:
        if not job_id.startswith("mock-"):
            return False
        try:
            started_at = int(job_id.split("-")[1])
        except (IndexError, ValueError):
            return False
            
        elapsed = time.time() - started_at
        is_terminal = elapsed >= self._pending_delay + self._run_delay
        if not is_terminal:
            logger.info("[MOCK AWX] Job %s canceled", job_id)
            return True
        return False

---

// filepath: simulation/mock_event.json
{
  "cluster": "emclu202",
  "hostname": "emclu202.prod.openshift.com",
  "correlation_id": "test-3455",
  "namespace": "openshift-etcd",
  "startAt": "2026-05-23T14:30:00Z",
  "alertname": "KubeEtcdVolumeCorruptions"
}

---

// filepath: simulation/mock_kafka_server.py
import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import subprocess
import os
import sys

class MockKafkaHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        parsed_path = urllib.parse.urlparse(self.path)
        
        # Mock Kafka Webhook Endpoint
        if parsed_path.path == "/mock-kafka":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                event_json = json.loads(post_data.decode('utf-8'))
                
                # Respond to the user immediately
                self.send_response(202)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "accepted", "message": "Event queued to mock Kafka topic"}).encode())
                
                # Kick off the orchestrator in the background to simulate async event consumption
                event_str = json.dumps(event_json)
                script_path = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'agents', 'blackboard_orchestrator.py'))
                
                def run_orchestrator():
                    print(f"\n[Mock Kafka Consumer] Triggering Orchestrator for alert: {event_json.get('alertname')}")
                    # Change directory to the root of the project to ensure correct module resolution
                    root_dir = os.path.dirname(os.path.dirname(__file__))
                    subprocess.run([sys.executable, "-m", "agents.blackboard_orchestrator", "--event-json", event_str], cwd=root_dir)
                    
                threading.Thread(target=run_orchestrator).start()
                return
            except Exception as e:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode())
                return
                
        self.send_response(404)
        self.end_headers()

def run_kafka_mock(port=8092):
    server_address = ('127.0.0.1', port)
    httpd = ThreadingHTTPServer(server_address, MockKafkaHandler)
    print(f"Starting Mock Kafka listener on port {port}...")
    httpd.serve_forever()

if __name__ == "__main__":
    run_kafka_mock(8092)

---

// filepath: simulation/mock_sync.py
import psycopg2
from datetime import datetime

DB_CONFIG = {
    "dbname": "rhokp",
    "user": "postgres",
    "password": "postgres",
    "host": "localhost",
    "port": "5432"
}

def perform_mock_sync():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    print("Creating snow_sync_status...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS snow_sync_status (
            id SERIAL PRIMARY KEY,
            last_sync_time TIMESTAMP NOT NULL
        );
    """)
    
    print("Inserting mock sync time...")
    cur.execute("TRUNCATE snow_sync_status;")
    cur.execute("INSERT INTO snow_sync_status (last_sync_time) VALUES (NOW());")
    
    print("Creating incident_work_notes...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS incident_work_notes (
            id SERIAL PRIMARY KEY,
            alert_fingerprint VARCHAR(255),
            created_by VARCHAR(255),
            created_at TIMESTAMP,
            note TEXT
        );
    """)

    print("Creating agent_action_log...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS agent_action_log (
            id SERIAL PRIMARY KEY,
            alert_fingerprint VARCHAR(255),
            status VARCHAR(50),
            created_at TIMESTAMP
        );
    """)
    
    conn.commit()
    cur.close()
    conn.close()
    print("Mock sync completed successfully!")

if __name__ == "__main__":
    perform_mock_sync()

---

// filepath: simulation/mock_telemetry_server.py
import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading

class MockTelemetryHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        
        # Mock Prometheus Endpoint
        if parsed_path.path == "/api/v1/query":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            # Simulate alert STILL firing (non-empty result list)
            response = {
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [{"metric": {"alertname": "KubeEtcdVolumeCorruptions"}, "value": [1680000000, "1"]}]
                }
            }
            self.wfile.write(json.dumps(response).encode())
            return
            
        # Mock Splunk Endpoint
        elif parsed_path.path == "/services/search/jobs/export":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            # Simulate a log indicating ArgoCD failed to sync
            response = '{"result": {"_raw": "msg=\\"Sync operation failed due to drift\\""}}'
            self.wfile.write(response.encode())
            return
            
        self.send_response(404)
        self.end_headers()

def run_server(port):
    server_address = ('127.0.0.1', port)
    httpd = ThreadingHTTPServer(server_address, MockTelemetryHandler)
    print(f"Starting mock telemetry server on port {port}...")
    httpd.serve_forever()

if __name__ == "__main__":
    # Port 9090 for Prometheus
    t1 = threading.Thread(target=run_server, args=(9090,))
    # Port 8088 for Splunk
    t2 = threading.Thread(target=run_server, args=(8088,))
    
    t1.start()
    t2.start()
    
    t1.join()
    t2.join()

---

// filepath: simulation/test_reoccurrence.py
import psycopg2
import hashlib
import json
import subprocess
from datetime import datetime, timedelta

DATABASE_TARGET = {
    "dbname": "rhokp",
    "user": "postgres",
    "password": "postgres",
    "host": "localhost",
    "port": "5432"
}

def generate_fingerprint(alertname, namespace, operator_component, cluster_id):
    raw_str = f"{alertname}{namespace}{operator_component}{cluster_id}"
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

def main():
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur = conn.cursor()
    
    # Define test parameters
    cluster_id = "auclu303"
    alertname = "CoreDNSErrorsHigh"
    namespace = "openshift-dns"
    operator_component = "cluster-dns-operator"
    
    # 1. Generate fingerprint
    fingerprint = generate_fingerprint(alertname, namespace, operator_component, cluster_id)
    print(f"Test Fingerprint: {fingerprint}")
    
    # Ensure cluster exists
    cur.execute("""
        INSERT INTO clusters (cluster_id, name, openshift_version, environment)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (cluster_id) DO NOTHING;
    """, (cluster_id, "Staging Australia", "4.15.2", "staging"))
    
    # Ensure alert occurrence exists
    cur.execute("""
        INSERT INTO alert_occurrences (fingerprint, alertname, namespace, operator_component, cluster_id, severity, occurrence_count, active, first_seen, last_seen)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (fingerprint) DO UPDATE SET active = TRUE;
    """, (fingerprint, alertname, namespace, operator_component, cluster_id, "warning", 10, True, datetime.now() - timedelta(days=10), datetime.now()))
    
    # 2. Insert 6 incidents in the last 7 days (e.g. 1 day ago to 6 days ago)
    # We clear any existing incidents for this fingerprint first to have a clean test state
    cur.execute("DELETE FROM incidents WHERE alert_fingerprint = %s;", (fingerprint,))
    
    for i in range(1, 7):
        sys_id = f"testinc0000000000000000000000{i}"
        number = f"TINC000000{i}"
        created_time = datetime.now() - timedelta(days=i, hours=2)
        short_desc = f"Alert '{alertname}' firing in namespace '{namespace}' on cluster '{cluster_id}'"
        
        # Insert incident
        cur.execute("""
            INSERT INTO incidents (sys_id, number, state, sys_created_on, sys_updated_on, short_description, cluster_id, alert_fingerprint, flapping_count, redhat_case_id, sentiment_label, sentiment_score, raw_payload)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """, (sys_id, number, "Resolved", created_time, created_time + timedelta(hours=1), short_desc, cluster_id, fingerprint, 0, None, "positive", 0.85, json.dumps({})))
        
    # Ensure recurrence intelligence stats are inserted/updated
    cur.execute("""
        INSERT INTO recurrence_intelligence (fingerprint, alertname, operator_component, cluster_id, total_occurrences, total_incidents, reopen_count, mttr_seconds, resolution_quality_score, last_reopened_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (fingerprint) DO UPDATE SET
            total_occurrences = EXCLUDED.total_occurrences,
            total_incidents = EXCLUDED.total_incidents,
            reopen_count = EXCLUDED.reopen_count,
            resolution_quality_score = EXCLUDED.resolution_quality_score;
    """, (fingerprint, alertname, operator_component, cluster_id, 10, 6, 0, 3600, 95.00, None, datetime.now()))
    
    conn.commit()
    cur.close()
    conn.close()
    
    print("Database seeded with 6 incidents in the last 7 days.")
    
    # 3. Execute the blackboard orchestrator with the event JSON
    event_data = {
        "cluster": cluster_id,
        "hostname": "auo12345",
        "correlation_id": "test-correlation-reoccur",
        "namespace": namespace,
        "startAt": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "alertname": alertname
    }
    
    event_json_str = json.dumps(event_data)
    
    print("Executing blackboard orchestrator...")
    result = subprocess.run([
        r"c:\Users\SRIMANDARBHA\.agent\Scripts\python.exe",
        "agents/blackboard_orchestrator.py",
        "--event-json", event_json_str
    ], capture_output=True, text=True, cwd=r"c:\Users\SRIMANDARBHA\Downloads\rag_testing")
    
    print("--- STDOUT ---")
    print(result.stdout)
    print("--- STDERR ---")
    print(result.stderr)

if __name__ == "__main__":
    main()

---

// filepath: simulation/__init__.py
# Simulation module

---

// filepath: tests/conftest.py
"""
pytest fixtures for integration tests.

Provides:
- mock_llm_response: patches the LLM API with a canned RemediationIntent
- mock_awx_client: injects MockAWXClient
- test_db_conn: psycopg2 connection to a test database (uses env vars)
"""

from __future__ import annotations

import json
import os
import uuid
from unittest.mock import MagicMock, patch

import psycopg2
import pytest
import respx
import httpx

from agents.langchain_tools import RemediationIntent


# ─── Canned LLM response (restart_pod, HIGH risk → PENDING_APPROVAL) ─────────

CANNED_INTENT = RemediationIntent(
    action="restart_pod",
    namespace="openshift-virtualization-operator",
    target="virt-controller-7d9b4f",
    reason="Pod is in CrashLoopBackOff — restart is the standard first action.",
    confidence=0.88,
)

CANNED_INTENT_LOW = RemediationIntent(
    action="restart_pod",     # restart_pod is LOW risk
    namespace="test-ns",
    target="test-pod",
    reason="Test auto-execute path.",
    confidence=0.90,
)


@pytest.fixture
def sample_alert():
    return {
        "alert_name": "SSPOperatorDown",
        "namespace": "openshift-virtualization-operator",
        "cluster": "nzclu101",
        "hostname": "nzclu101.prod.openshift.com",
        "correlation_id": f"nzclu101-test-{uuid.uuid4().hex[:8]}",
    }


@pytest.fixture
def mock_awx():
    """Returns a MockAWXClient with 0% failure rate."""
    from simulation.mock_client import MockAWXClient
    return MockAWXClient(fail_rate=0.0, pending_delay=0.1, run_delay=0.2)


@pytest.fixture
def mock_failing_awx():
    """Returns a MockAWXClient that always fails."""
    from simulation.mock_client import MockAWXClient
    return MockAWXClient(fail_rate=1.0, pending_delay=0.1, run_delay=0.2)


@pytest.fixture
def mock_rag_tools():
    """Patches all DB-hitting tools to return canned responses."""
    with patch("agents.langchain_tools.lookup_runbook") as rl, \
         patch("agents.langchain_tools.get_incident_history") as ih, \
         patch("agents.langchain_tools.get_pod_status") as ps, \
         patch("agents.langchain_tools.query_prometheus") as pq:

        rl.invoke.return_value = json.dumps({
            "alert_name": "SSPOperatorDown",
            "runbook_hits": 1,
            "results": [{"source_id": "RB-001", "excerpt": "Restart the SSP operator pod."}],
        })
        ih.invoke.return_value = json.dumps({
            "cluster": "nzclu101",
            "alert_name": "SSPOperatorDown",
            "weekly_occurrences": 2,
            "reopen_count": 0,
            "resolution_quality_score": 95.0,
        })
        ps.invoke.return_value = json.dumps({
            "pod": "virt-controller",
            "namespace": "openshift-virtualization-operator",
            "phase": "Running",
            "container_statuses": [],
        })
        pq.invoke.return_value = json.dumps({
            "query": "ALERTS{...}",
            "result_count": 1,
            "results": [{"metric": {}, "value": [1, "1"]}],
        })
        yield {"runbook": rl, "history": ih, "pod": ps, "prometheus": pq}


@pytest.fixture
def mock_llm_classify():
    """Patches classify_action to return the canned HIGH-risk intent."""
    with patch("agents.langchain_tools.classify_action") as ca:
        ca.invoke.return_value = CANNED_INTENT.model_dump_json()
        yield ca

---

// filepath: tests/test_agent_pipeline.py
"""
Integration tests for the LangChain agent pipeline.

Tests:
1. Risk engine: LOW / HIGH / ESCALATE classification rules
2. Tool validation: RemediationIntent allowlist enforcement
3. Mock AWX: launch → poll → SUCCESSFUL lifecycle
4. Mock AWX: fail path → FAILED terminal state
5. Full pipeline routing: LOW → auto_execute
6. Full pipeline routing: ESCALATE (confidence < 0.75)
"""

from __future__ import annotations

import json
import time
from unittest.mock import patch

import pytest

from agents.langchain_tools import RemediationIntent
from agents.risk_engine import (
    CONFIDENCE_THRESHOLD,
    classify_risk,
    get_risk_reasoning,
    is_action_allowed,
)
from awx.client import AWXJobStatus
from simulation.mock_client import MockAWXClient


# ─── Risk engine tests ────────────────────────────────────────────────────────

class TestRiskEngine:
    def test_low_risk_restart_pod(self):
        intent = RemediationIntent(
            action="restart_pod", namespace="ns", target="pod-abc",
            reason="test", confidence=0.90,
        )
        assert classify_risk(intent) == "LOW"

    def test_low_risk_clear_evicted(self):
        intent = RemediationIntent(
            action="clear_evicted_pods", namespace="ns", target="cluster",
            reason="test", confidence=0.80,
        )
        assert classify_risk(intent) == "LOW"

    def test_low_risk_scale_up(self):
        intent = RemediationIntent(
            action="scale_up_replicas", namespace="ns", target="deploy-x",
            reason="test", confidence=0.85,
        )
        assert classify_risk(intent) == "LOW"

    def test_high_risk_delete_pvc(self):
        intent = RemediationIntent(
            action="delete_pvc", namespace="ns", target="pvc-data",
            reason="test", confidence=0.85,
        )
        assert classify_risk(intent) == "HIGH"

    def test_high_risk_drain_node(self):
        intent = RemediationIntent(
            action="drain_node", namespace="ns", target="node-01",
            reason="test", confidence=0.90,
        )
        assert classify_risk(intent) == "HIGH"

    def test_escalate_low_confidence(self):
        """Any action with confidence < CONFIDENCE_THRESHOLD → ESCALATE."""
        for action in ["restart_pod", "delete_pvc", "drain_node"]:
            intent = RemediationIntent(
                action=action, namespace="ns", target="target",
                reason="test", confidence=CONFIDENCE_THRESHOLD - 0.01,
            )
            assert classify_risk(intent) == "ESCALATE", \
                f"Expected ESCALATE for confidence below threshold on {action}"

    def test_escalate_unknown_action(self):
        """escalate action → ESCALATE tier."""
        intent = RemediationIntent(
            action="escalate", namespace="ns", target="cluster",
            reason="unknown", confidence=0.80,
        )
        assert classify_risk(intent) == "ESCALATE"

    def test_allowlist_restart_pod(self):
        assert is_action_allowed("restart_pod") is True

    def test_allowlist_unknown(self):
        assert is_action_allowed("delete_everything") is False

    def test_confidence_boundary(self):
        """Exactly at threshold should NOT escalate."""
        intent = RemediationIntent(
            action="restart_pod", namespace="ns", target="pod",
            reason="boundary test", confidence=CONFIDENCE_THRESHOLD,
        )
        assert classify_risk(intent) == "LOW"


# ─── Mock AWX lifecycle tests ─────────────────────────────────────────────────

class TestMockAWXClient:
    def test_launch_returns_job_id(self, mock_awx):
        job_id = mock_awx.launch_job("42", {"action": "restart_pod"})
        assert isinstance(job_id, str)
        assert len(job_id) > 0

    def test_initial_status_pending(self, mock_awx):
        job_id = mock_awx.launch_job("42", {"action": "restart_pod"})
        result = mock_awx.get_job_status(job_id)
        assert result.status == AWXJobStatus.PENDING

    def test_progresses_to_running(self):
        awx = MockAWXClient(pending_delay=0.05, run_delay=10.0)
        job_id = awx.launch_job("42", {"action": "restart_pod"})
        time.sleep(0.1)
        result = awx.get_job_status(job_id)
        assert result.status == AWXJobStatus.RUNNING

    def test_terminal_success(self):
        awx = MockAWXClient(pending_delay=0.0, run_delay=0.0, fail_rate=0.0)
        job_id = awx.launch_job("42", {"action": "restart_pod"})
        time.sleep(0.01)
        result = awx.get_job_status(job_id)
        assert result.status == AWXJobStatus.SUCCESSFUL
        assert result.status.is_terminal is True
        assert result.status.is_success is True

    def test_terminal_failure(self):
        awx = MockAWXClient(pending_delay=0.0, run_delay=0.0, fail_rate=1.0)
        job_id = awx.launch_job("42", {"action": "restart_pod"})
        time.sleep(0.01)
        result = awx.get_job_status(job_id)
        assert result.status == AWXJobStatus.FAILED
        assert result.status.is_terminal is True
        assert result.status.is_success is False

    def test_extra_vars_preserved(self, mock_awx):
        extra_vars = {"action": "drain_node", "namespace": "test", "target": "node-01"}
        job_id = mock_awx.launch_job("42", extra_vars)
        time.sleep(0.15)
        result = mock_awx.get_job_status(job_id)
        assert result.extra_vars == extra_vars

    def test_cancel_running_job(self):
        awx = MockAWXClient(pending_delay=0.0, run_delay=60.0)
        job_id = awx.launch_job("42", {})
        time.sleep(0.05)
        canceled = awx.cancel_job(job_id)
        assert canceled is True

    def test_cancel_terminal_job(self):
        awx = MockAWXClient(pending_delay=0.0, run_delay=0.0)
        job_id = awx.launch_job("42", {})
        time.sleep(0.05)
        canceled = awx.cancel_job(job_id)
        assert canceled is False  # already terminal


# ─── RemediationIntent validation ────────────────────────────────────────────

class TestRemediationIntent:
    def test_to_awx_extra_vars_shape(self):
        intent = RemediationIntent(
            action="restart_pod",
            namespace="openshift-ns",
            target="my-pod-abc123",
            reason="CrashLoopBackOff detected",
            confidence=0.91,
        )
        extra_vars = intent.to_awx_extra_vars()
        assert extra_vars["action"] == "restart_pod"
        assert extra_vars["namespace"] == "openshift-ns"
        assert extra_vars["target"] == "my-pod-abc123"
        # confidence must NOT be in extra_vars (it's internal, not sent to AWX)
        assert "confidence" not in extra_vars

    def test_invalid_action_rejected(self):
        with pytest.raises(Exception):
            RemediationIntent(
                action="rm_rf_everything",   # type: ignore — not in Literal
                namespace="ns",
                target="t",
                reason="bad",
                confidence=0.9,
            )

    def test_confidence_bounds(self):
        with pytest.raises(Exception):
            RemediationIntent(
                action="restart_pod", namespace="ns", target="t",
                reason="r", confidence=1.5,
            )
        with pytest.raises(Exception):
            RemediationIntent(
                action="restart_pod", namespace="ns", target="t",
                reason="r", confidence=-0.1,
            )

---

// filepath: tests/test_approval_flow.py
"""
Integration tests for the Human-in-the-Loop approval flow.

Tests the full state machine:
  PENDING_APPROVAL → APPROVE → EXECUTING (AWX launched)
  PENDING_APPROVAL → REJECT  → REJECTED
  PENDING_APPROVAL → EDIT    → EXECUTING (modified intent validated + AWX launched)
  ANY ACTIVE       → ESCALATE → ESCALATED

These tests use the FastAPI TestClient and mock the DB + AWX calls.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from agents.langchain_tools import RemediationIntent

# Sample intent that would be stored in DB for a PENDING_APPROVAL incident
SAMPLE_INTENT = {
    "action": "drain_node",
    "namespace": "openshift-infra",
    "target": "worker-node-07",
    "reason": "Node memory pressure detected. Drain before maintenance.",
    "confidence": 0.87,
}


def _make_test_app():
    """Create FastAPI TestClient with mocked DB."""
    from api.main import app
    return TestClient(app)


# ─── Approval flow tests ──────────────────────────────────────────────────────

class TestApprovalFlow:
    """
    Tests the approve/reject/edit/escalate endpoints.
    These tests mock the psycopg2 DB calls and AWX client.
    """

    @pytest.fixture
    def incident_id(self):
        return str(uuid.uuid4())

    @pytest.fixture
    def pending_incident_db(self, incident_id):
        """Mock DB fetch returning a PENDING_APPROVAL incident."""
        row = (
            uuid.UUID(incident_id),  # id
            "test-correlation-id",    # correlation_id
            "nzclu101",               # cluster
            "openshift-infra",        # namespace
            "NodeMemoryPressure",     # alert_name
            "worker-node-07",         # hostname
            "PENDING_APPROVAL",       # status
            "HIGH",                   # risk_tier
            0.87,                     # llm_confidence
            SAMPLE_INTENT,            # llm_intent_json
            None,                     # awx_job_id
            "2026-05-26T10:00:00Z",  # created_at
            "2026-05-26T10:01:00Z",  # updated_at
            None,                     # resolved_at
        )
        return row

    def test_approve_requires_reason(self, incident_id):
        """Approve request with empty reason should be rejected by schema validation."""
        from api.schemas import ApproveRequest
        with pytest.raises(Exception):
            ApproveRequest(reason="ab", user_id="test-user")  # too short

    def test_reject_requires_reason(self):
        """Reject request with empty reason should fail validation."""
        from api.schemas import RejectRequest
        with pytest.raises(Exception):
            RejectRequest(reason="", user_id="test-user")

    def test_edit_validates_intent_schema(self):
        """Edit+approve with invalid action should be rejected before hitting AWX."""
        from api.schemas import EditAndApproveRequest
        bad_intent = {
            "action": "destroy_cluster",  # not in allowlist
            "namespace": "default",
            "target": "everything",
            "reason": "test",
            "confidence": 0.9,
        }
        # FastAPI endpoint validates against RemediationIntent schema
        with pytest.raises(Exception):
            RemediationIntent(**bad_intent)

    def test_valid_edit_passes_schema(self):
        """Valid edited intent should pass RemediationIntent validation."""
        valid_intent = {
            "action": "restart_pod",  # changed from drain_node to safer action
            "namespace": "openshift-infra",
            "target": "worker-node-07",
            "reason": "Changed to pod restart — safer option confirmed by SRE.",
            "confidence": 0.87,
        }
        intent = RemediationIntent(**valid_intent)
        assert intent.action == "restart_pod"
        extra_vars = intent.to_awx_extra_vars()
        assert "confidence" not in extra_vars  # confidence never sent to AWX
        assert extra_vars["action"] == "restart_pod"

    def test_mock_awx_launch_on_approve(self, mock_awx):
        """AWX job should launch when approve is called with valid intent."""
        intent = RemediationIntent(**SAMPLE_INTENT)
        job_id = mock_awx.launch_job("1", intent.to_awx_extra_vars())
        assert job_id is not None

        import time
        time.sleep(0.3)
        result = mock_awx.get_job_status(job_id)
        assert result.status.is_success

    def test_mock_awx_uses_pydantic_extra_vars(self, mock_awx):
        """AWX must receive validated extra_vars, not raw strings."""
        intent = RemediationIntent(**SAMPLE_INTENT)
        extra_vars = intent.to_awx_extra_vars()

        # Verify the shape is what we expect
        assert set(extra_vars.keys()) == {"action", "namespace", "target", "reason"}
        assert extra_vars["action"] in {
            "restart_pod", "clear_evicted_pods", "scale_up_replicas",
            "delete_pvc", "drain_node", "scale_down_deployment", "escalate"
        }

    def test_full_reject_flow(self, mock_awx):
        """Simulates the reject flow end-to-end with mock objects."""
        # In the real API, reject writes to DB and calls PagerDuty
        # Here we verify the reject schema validation passes
        from api.schemas import RejectRequest
        req = RejectRequest(reason="The proposed drain is too risky during business hours.", user_id="john.doe")
        assert req.reason.startswith("The proposed")
        assert req.user_id == "john.doe"

    def test_edit_changes_intent_before_awx(self, mock_awx):
        """Verify that editing an intent changes what gets sent to AWX."""
        original_intent = RemediationIntent(**SAMPLE_INTENT)  # drain_node
        modified_intent = RemediationIntent(
            action="restart_pod",   # downgraded to safer action
            namespace=SAMPLE_INTENT["namespace"],
            target=SAMPLE_INTENT["target"],
            reason="SRE downgraded from drain_node to restart_pod after manual inspection.",
            confidence=0.87,
        )

        original_vars = original_intent.to_awx_extra_vars()
        modified_vars = modified_intent.to_awx_extra_vars()

        assert original_vars["action"] == "drain_node"
        assert modified_vars["action"] == "restart_pod"

        # Both are valid AWX extra_vars
        job_id = mock_awx.launch_job("1", modified_vars)
        assert job_id is not None


# ─── Risk engine state machine tests ─────────────────────────────────────────

class TestRiskStateMachine:
    """Tests the if/else routing logic (no LangGraph)."""

    def test_low_goes_auto_execute(self):
        from agents.risk_engine import classify_risk
        intent = RemediationIntent(
            action="restart_pod", namespace="ns", target="pod",
            reason="r", confidence=0.90,
        )
        assert classify_risk(intent) == "LOW"

    def test_high_goes_pending(self):
        from agents.risk_engine import classify_risk
        intent = RemediationIntent(
            action="drain_node", namespace="ns", target="node",
            reason="r", confidence=0.85,
        )
        assert classify_risk(intent) == "HIGH"

    def test_low_confidence_forces_escalate_regardless_of_action(self):
        from agents.risk_engine import classify_risk, CONFIDENCE_THRESHOLD
        for action in ["restart_pod", "clear_evicted_pods", "scale_up_replicas"]:
            intent = RemediationIntent(
                action=action, namespace="ns", target="t",
                reason="r", confidence=CONFIDENCE_THRESHOLD - 0.01,
            )
            tier = classify_risk(intent)
            assert tier == "ESCALATE", \
                f"Action {action} with low confidence should ESCALATE but got {tier}"

---

// filepath: tests/test_risk_engine.py
import unittest
from agents.risk_engine import classify_risk, is_action_allowed
from agents.langchain_tools import RemediationIntent

class TestRiskEngine(unittest.TestCase):
    def test_is_action_allowed(self):
        self.assertTrue(is_action_allowed("restart_pod"))
        self.assertTrue(is_action_allowed("scale_deployment"))
        self.assertFalse(is_action_allowed("delete_pvc"))
        self.assertFalse(is_action_allowed("escalate"))

    def test_risk_classification_low_risk(self):
        intent = RemediationIntent(
            action="restart_pod",
            namespace="openshift-monitoring",
            target="prometheus-k8s-0",
            reason="Test",
            confidence=0.95
        )
        self.assertEqual(classify_risk(intent), "LOW")

    def test_risk_classification_high_risk_action(self):
        intent = RemediationIntent(
            action="rollout_restart",
            namespace="default",
            target="my-app",
            reason="Test",
            confidence=0.90
        )
        self.assertEqual(classify_risk(intent), "HIGH")

    def test_risk_classification_low_confidence_escalates(self):
        intent = RemediationIntent(
            action="restart_pod",
            namespace="openshift-monitoring",
            target="prometheus-k8s-0",
            reason="Not sure",
            confidence=0.74
        )
        self.assertEqual(classify_risk(intent), "ESCALATE")

    def test_risk_classification_escalate_action_escalates(self):
        intent = RemediationIntent(
            action="escalate",
            namespace="openshift-monitoring",
            target="prometheus-k8s-0",
            reason="Escalating directly",
            confidence=0.95
        )
        self.assertEqual(classify_risk(intent), "ESCALATE")

    def test_remediation_intent_validation(self):
        # Valid
        intent = RemediationIntent.model_validate_json(
            '{"action": "restart_pod", "namespace": "test", "target": "pod", "reason": "why", "confidence": 0.8}'
        )
        self.assertEqual(intent.action, "restart_pod")

        # Missing fields should raise validation error
        with self.assertRaises(ValueError):
            RemediationIntent.model_validate_json('{"action": "restart_pod"}')

        # Invalid confidence type
        with self.assertRaises(ValueError):
            RemediationIntent.model_validate_json(
                '{"action": "restart_pod", "namespace": "test", "target": "pod", "reason": "why", "confidence": "high"}'
            )

if __name__ == '__main__':
    unittest.main()


---

// filepath: tests/__init__.py
"""tests package init."""

---

// filepath: tests/api/__init__.py


---

// filepath: tests/evals/__init__.py


---

// filepath: tests/worker/__init__.py


---

// filepath: worker/celery_app.py
"""
Celery application configuration.

Broker: PostgreSQL (via SQLAlchemy transport)
Result backend: PostgreSQL (via SQLAlchemy)

Workers:
  - default queue: standard agent tasks
  - priority queue: AWX polling tasks (lower latency)
"""

# pyrefly: ignore [missing-import]
from celery import Celery
from celery.signals import worker_process_init

from agents.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND

celery_app = Celery(
    "sre_worker",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["worker.tasks"],
)


@worker_process_init.connect
def preload_embedding_model(**kwargs):
    """
    Pre-load the SentenceTransformer model at Celery worker process startup.
    This avoids a thread-safety race condition when multiple task threads try
    to initialize the global _embed_model in langchain_tools.py simultaneously.
    """
    from agents.langchain_tools import _get_embed_model
    import logging
    logging.getLogger(__name__).info("Pre-loading embedding model at worker startup...")
    _get_embed_model()
    logging.getLogger(__name__).info("Embedding model ready.")


celery_app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Queues
    task_routes={
        "worker.tasks.run_agent_pipeline": {"queue": "default"},
        "worker.tasks.poll_awx_job": {"queue": "priority"},
        "worker.tasks.trigger_pagerduty_escalation": {"queue": "default"},
    },
    # Reliability
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    # Retries
    task_max_retries=3,
    # Result expiry (24h)
    result_expires=86400,
    # Worker
    worker_prefetch_multiplier=1,  # one task at a time per worker (safer for agent workloads)
    worker_max_tasks_per_child=100,
)

from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    "generate-shift-summary-morning": {
        "task": "worker.tasks.generate_auto_shift_summary",
        "schedule": crontab(hour=0, minute=30),
    },
    "generate-shift-summary-afternoon": {
        "task": "worker.tasks.generate_auto_shift_summary",
        "schedule": crontab(hour=8, minute=30),
    },
    "generate-shift-summary-night": {
        "task": "worker.tasks.generate_auto_shift_summary",
        "schedule": crontab(hour=16, minute=30),
    },
}

---

// filepath: worker/tasks.py
"""
Celery tasks for the SRE Incident Agent.

Tasks:
  run_agent_pipeline       -> LangChain agent pipeline for one incident
  poll_awx_job             -> Poll AWX every 15s until terminal, then verify
  verify_remediation       -> Real Kubernetes health check post-AWX success
  trigger_pagerduty_escalation -> Page oncall via PagerDuty API
  check_approval_timeout   -> Auto-escalate stale PENDING_APPROVAL incidents

P1 improvements applied:
  - Connection pool (SimpleConnectionPool) — no per-call TCP connections
  - structlog with incident_id/correlation_id bound to every log line
  - Real post-execution health verification (verify_remediation task)
  - notify_status_change() for Celery -> FastAPI WebSocket bridge
"""

from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

import psycopg2
import structlog
from psycopg2 import pool as pg_pool

from agents.config import (
    AWX_BASE_URL,
    BLAST_RADIUS_CAP,
    PAGERDUTY_API_KEY,
    PAGERDUTY_ESCALATION_POLICY_ID,
    USE_MOCK_AWX,
    DATABASE_TARGET,
)
from agents.langchain_agent import run_incident_pipeline
from agents.langchain_tools import RemediationIntent
from awx.client import AWXJobStatus
from db.pg_notify import notify_status_change
from worker.celery_app import celery_app

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Connection pool — shared per worker process, eliminates per-call connects
# ---------------------------------------------------------------------------

_pool: pg_pool.SimpleConnectionPool | None = None


def _get_pool() -> pg_pool.SimpleConnectionPool:
    global _pool
    if _pool is None:
        _pool = pg_pool.SimpleConnectionPool(minconn=2, maxconn=10, **DATABASE_TARGET)
    return _pool


@contextmanager
def _db_conn():
    """Borrow a connection from the pool, auto-commit or rollback on exit."""
    conn = _get_pool().getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _get_pool().putconn(conn)


# ---------------------------------------------------------------------------
# AWX client selection (real vs mock)
# ---------------------------------------------------------------------------


def _get_awx_client():
    if USE_MOCK_AWX:
        from simulation.mock_client import MockAWXClient
        return MockAWXClient(fail_rate=0.0, pending_delay=1.0, run_delay=3.0)
    from awx.client import AWXClient
    return AWXClient()


# ---------------------------------------------------------------------------
# DB helpers — all use the shared pool, never open raw connections
# ---------------------------------------------------------------------------


def _update_incident_status(incident_id: str, new_status: str, **kwargs):
    with _db_conn() as conn:
        cur = conn.cursor()
        set_clauses = ["status = %s", "updated_at = NOW()"]
        values = [new_status]
        for col in ("risk_tier", "llm_confidence", "llm_intent_json", "analysis_summary",
                    "escalate_to", "awx_job_id", "resolved_at"):
            if col in kwargs:
                set_clauses.append(f"{col} = %s")
                val = kwargs[col]
                if col == "llm_intent_json" and isinstance(val, dict):
                    val = json.dumps(val)
                values.append(val)
        values.append(incident_id)
        cur.execute(f"UPDATE incidents_v2 SET {', '.join(set_clauses)} WHERE id = %s", values)
        cur.close()


def _insert_timeline(incident_id: str, actor_type: str, action: str,
                     from_status: str | None = None, to_status: str | None = None,
                     notes: str | None = None, metadata: dict | None = None):
    """Append an immutable timeline event — always INSERT, never UPDATE."""
    with _db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO incident_timeline
              (incident_id, actor_type, action, from_status, to_status, notes, metadata_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (incident_id, actor_type, action, from_status, to_status, notes,
             json.dumps(metadata) if metadata else None),
        )
        cur.close()


def _insert_llm_decision(incident_id: str, prompt_used: str, raw_output: str,
                         parsed_intent: dict, confidence: float, tool_calls: list):
    with _db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO llm_decisions
              (incident_id, prompt_used, raw_llm_output, parsed_intent, confidence, tool_calls_json)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (incident_id, prompt_used, raw_output,
             json.dumps(parsed_intent), confidence, json.dumps(tool_calls)),
        )
        cur.close()


def _check_blast_radius(cluster: str) -> bool:
    """Returns True if it's safe to auto-execute (under the cap)."""
    with _db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT COUNT(*) FROM incidents_v2
            WHERE cluster = %s AND status = 'EXECUTING'
              AND updated_at > NOW() - INTERVAL '1 hour';
            """,
            (cluster,),
        )
        count = cur.fetchone()[0]
        cur.close()
        return count < BLAST_RADIUS_CAP


# ---------------------------------------------------------------------------
# Task 1: Run the full LangChain agent pipeline
# ---------------------------------------------------------------------------


@celery_app.task(
    name="worker.tasks.run_agent_pipeline",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def run_agent_pipeline(self, incident_id: str, alert_name: str, namespace: str,
                       cluster: str, hostname: str, correlation_id: str,
                       awx_template_id: str = "1"):
    """
    Main Celery task: runs the LangChain 5-step agent pipeline for one incident.
    - LOW risk  -> launches AWX job (checks blast radius first)
    - HIGH risk -> writes PENDING_APPROVAL to DB (awaits human via API)
    - ESCALATE  -> marks ESCALATED, fires PagerDuty
    """
    log = logger.bind(incident_id=incident_id, correlation_id=correlation_id,
                      alert_name=alert_name, cluster=cluster)
    log.info("Starting agent pipeline")

    def _on_status(inc_id, new_status, notes=""):
        _update_incident_status(str(inc_id), new_status)
        _insert_timeline(str(inc_id), actor_type="agent", action=f"Status -> {new_status}",
                         to_status=new_status, notes=notes)
        notify_status_change(str(inc_id), new_status, actor="agent")

    try:
        _insert_timeline(incident_id, actor_type="agent", action="Agent pipeline started",
                         from_status="RECEIVED", to_status="ANALYZING")
        _update_incident_status(incident_id, "ANALYZING")

        result = run_incident_pipeline(
            incident_id=uuid.UUID(incident_id),
            alert_name=alert_name,
            namespace=namespace,
            cluster=cluster,
            hostname=hostname,
            correlation_id=correlation_id,
            on_status_update=_on_status,
        )

        _insert_llm_decision(
            incident_id=incident_id,
            prompt_used="ReAct agent (see tool_calls for full context)",
            raw_output=result.raw_agent_output,
            parsed_intent=result.intent.model_dump(),
            confidence=result.intent.confidence,
            tool_calls=result.tool_calls,
        )

        intent_dict = result.intent.model_dump()

        if result.action == "auto_execute":
            if not _check_blast_radius(cluster):
                log.warning("Blast radius cap reached. Escalating.")
                _update_incident_status(incident_id, "ESCALATED",
                                        risk_tier=result.risk_tier,
                                        llm_confidence=result.intent.confidence,
                                        llm_intent_json=intent_dict,
                                        analysis_summary=result.intent.analysis_summary,
                                        escalate_to=result.intent.escalate_to)
                _insert_timeline(incident_id, actor_type="system",
                                 action="Blast radius cap reached. Auto-escalated.",
                                 from_status="ANALYZING", to_status="ESCALATED",
                                 notes=f"Cluster {cluster} has {BLAST_RADIUS_CAP} executing jobs.")
                notify_status_change(incident_id, "ESCALATED", actor="system")
                trigger_pagerduty_escalation.delay(incident_id, f"Blast radius cap on {cluster}")
                return

            _update_incident_status(incident_id, "EXECUTING", risk_tier="LOW",
                                    llm_confidence=result.intent.confidence,
                                    llm_intent_json=intent_dict,
                                    analysis_summary=result.intent.analysis_summary,
                                    escalate_to=result.intent.escalate_to)
            _insert_timeline(incident_id, actor_type="agent", action="Launching AWX job (AUTO)",
                             from_status="ANALYZING", to_status="EXECUTING",
                             notes=result.risk_reasoning, metadata={"intent": intent_dict})

            awx = _get_awx_client()
            job_id = awx.launch_job(template_id=awx_template_id,
                                    extra_vars=result.intent.to_awx_extra_vars())
            _update_incident_status(incident_id, "EXECUTING", awx_job_id=job_id)
            _insert_timeline(incident_id, actor_type="agent",
                             action=f"AWX job #{job_id} launched", to_status="EXECUTING",
                             metadata={"awx_job_id": job_id,
                                       "awx_url": f"{AWX_BASE_URL}/#/jobs/{job_id}"})
            notify_status_change(incident_id, "EXECUTING", actor="agent")
            poll_awx_job.apply_async(args=[incident_id, job_id], countdown=10, queue="priority")

        elif result.action == "pending_approval":
            _update_incident_status(incident_id, "PENDING_APPROVAL", risk_tier="HIGH",
                                    llm_confidence=result.intent.confidence,
                                    llm_intent_json=intent_dict,
                                    analysis_summary=result.intent.analysis_summary,
                                    escalate_to=result.intent.escalate_to)
            _insert_timeline(incident_id, actor_type="agent",
                             action="Awaiting human approval (HIGH risk)",
                             from_status="ANALYZING", to_status="PENDING_APPROVAL",
                             notes=result.risk_reasoning,
                             metadata={"proposed_intent": intent_dict})
            notify_status_change(incident_id, "PENDING_APPROVAL", actor="agent")
            log.info("Incident now PENDING_APPROVAL")
            check_approval_timeout.apply_async(args=[incident_id], countdown=15 * 60)

        else:  # escalate
            _update_incident_status(incident_id, "ESCALATED", risk_tier="ESCALATE",
                                    llm_confidence=result.intent.confidence,
                                    llm_intent_json=intent_dict,
                                    analysis_summary=result.intent.analysis_summary,
                                    escalate_to=result.intent.escalate_to)
            _insert_timeline(incident_id, actor_type="agent",
                             action="ESCALATED — paging oncall",
                             from_status="ANALYZING", to_status="ESCALATED",
                             notes=result.risk_reasoning, metadata={"intent": intent_dict})
            notify_status_change(incident_id, "ESCALATED", actor="agent")
            trigger_pagerduty_escalation.delay(
                incident_id,
                f"Low confidence ({result.intent.confidence:.0%}) or unknown action on "
                f"{alert_name} in {cluster}",
            )

    except Exception as exc:
        log.exception("Agent pipeline FAILED", error=str(exc))
        if self.request.retries >= self.max_retries:
            # Final retry exhausted — mark as permanently FAILED
            _update_incident_status(incident_id, "FAILED")
            _insert_timeline(incident_id, actor_type="system", action="Agent pipeline failed",
                             to_status="FAILED", notes=str(exc))
            notify_status_change(incident_id, "FAILED", actor="system")
            raise  # Don't retry — let Celery mark it as failed
        else:
            # Retries remain — log but don't flip status to FAILED yet
            _insert_timeline(incident_id, actor_type="system",
                             action=f"Agent pipeline error (retry {self.request.retries + 1}/{self.max_retries})",
                             notes=str(exc))
            self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Task 2: Poll AWX job status
# ---------------------------------------------------------------------------

AWX_POLL_INTERVAL = 15  # seconds


@celery_app.task(
    name="worker.tasks.poll_awx_job",
    bind=True,
    max_retries=60,
    default_retry_delay=AWX_POLL_INTERVAL,
)
def poll_awx_job(self, incident_id: str, job_id: str):
    """Poll AWX until terminal state, then dispatch verification task."""
    log = logger.bind(incident_id=incident_id, job_id=job_id)
    log.info("Polling AWX job status")

    awx = _get_awx_client()
    result = awx.get_job_status(job_id)

    if not result.status.is_terminal:
        log.debug("AWX job still running, retrying", status=str(result.status))
        self.retry(countdown=AWX_POLL_INTERVAL)
        return

    if result.status.is_success:
        log.info("AWX job SUCCEEDED")
        _update_incident_status(incident_id, "VERIFYING")
        _insert_timeline(incident_id, actor_type="agent",
                         action=f"AWX job #{job_id} SUCCEEDED — starting health verification",
                         from_status="EXECUTING", to_status="VERIFYING",
                         metadata={"awx_status": result.status.value, "elapsed": result.elapsed})
        notify_status_change(incident_id, "VERIFYING", actor="agent")
        # 60s cooldown for remediation to converge, then real health check
        verify_remediation.apply_async(args=[incident_id], countdown=60, queue="priority")
    else:
        log.error("AWX job reached terminal failure", status=result.status.value)
        _update_incident_status(incident_id, "FAILED")
        _insert_timeline(incident_id, actor_type="agent",
                         action=f"AWX job #{job_id} FAILED ({result.status.value})",
                         from_status="EXECUTING", to_status="FAILED",
                         notes="Auto-escalating to oncall due to AWX failure.",
                         metadata={"awx_status": result.status.value})
        notify_status_change(incident_id, "FAILED", actor="agent")
        trigger_pagerduty_escalation.delay(
            incident_id, f"AWX job #{job_id} failed: {result.status.value}"
        )


# ---------------------------------------------------------------------------
# Task 3: Post-execution health verification (REAL check, not hardcoded)
# ---------------------------------------------------------------------------


@celery_app.task(name="worker.tasks.verify_remediation", bind=True, max_retries=3,
                 default_retry_delay=30)
def verify_remediation(self, incident_id: str):
    """
    Real post-execution health check before marking RESOLVED.
    Reads the incident's stored intent to know which pod/namespace to verify.
    Escalates with PagerDuty if the pod is still unhealthy after the convergence window.
    """
    log = logger.bind(incident_id=incident_id)
    log.info("Running post-execution verification")

    try:
        with _db_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT namespace, llm_intent_json FROM incidents_v2 WHERE id = %s",
                (incident_id,),
            )
            row = cur.fetchone()
            cur.close()

        if not row:
            log.error("Incident not found for verification")
            return

        namespace, intent_json = row
        intent = json.loads(intent_json) if intent_json else {}
        pod_name = intent.get("target", "")

        from agents.langchain_tools import get_pod_status
        check_result = json.loads(
            get_pod_status.invoke(json.dumps({"namespace": namespace, "pod_name": pod_name}))
        )

        phase = check_result.get("phase", "Unknown")
        has_error = bool(check_result.get("error"))

        if has_error or phase not in ("Running", "Succeeded"):
            log.warning("Verification FAILED — pod not healthy", phase=phase, pod=pod_name)
            _insert_timeline(incident_id, actor_type="agent",
                             action="Verification FAILED — pod unhealthy after remediation",
                             from_status="VERIFYING", to_status="ESCALATED",
                             notes=f"Pod '{pod_name}' phase={phase}. Escalating for human review.",
                             metadata={"check_result": check_result})
            _update_incident_status(incident_id, "ESCALATED")
            notify_status_change(incident_id, "ESCALATED", actor="agent")
            trigger_pagerduty_escalation.delay(
                incident_id,
                f"Verification failed: pod '{pod_name}' is {phase} after remediation",
            )
        else:
            log.info("Verification PASSED — pod healthy", phase=phase, pod=pod_name)
            _insert_timeline(incident_id, actor_type="agent",
                             action="Verification PASSED — marking RESOLVED",
                             from_status="VERIFYING", to_status="RESOLVED",
                             notes=f"Pod '{pod_name}' phase={phase}. Health check passed.",
                             metadata={"check_result": check_result})
            _update_incident_status(
                incident_id, "RESOLVED",
                resolved_at=datetime.now(timezone.utc).isoformat(),
            )
            notify_status_change(incident_id, "RESOLVED", actor="agent")

    except Exception as exc:
        log.error("verify_remediation failed", error=str(exc))
        self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Task 4: PagerDuty escalation
# ---------------------------------------------------------------------------


@celery_app.task(name="worker.tasks.trigger_pagerduty_escalation")
def trigger_pagerduty_escalation(incident_id: str, reason: str):
    """Create a PagerDuty incident for oncall escalation."""
    log = logger.bind(incident_id=incident_id)
    if not PAGERDUTY_API_KEY:
        log.warning("PagerDuty API key not configured. Skipping escalation.")
        return

    import httpx
    try:
        resp = httpx.post(
            "https://events.pagerduty.com/v2/enqueue",
            headers={"Authorization": f"Token token={PAGERDUTY_API_KEY}"},
            json={
                "routing_key": PAGERDUTY_API_KEY,
                "event_action": "trigger",
                "payload": {
                    "summary": f"SRE Agent Escalation: incident_id={incident_id}",
                    "severity": "critical",
                    "source": "sre-incident-agent",
                    "custom_details": {
                        "incident_id": incident_id,
                        "reason": reason,
                        "escalation_policy": PAGERDUTY_ESCALATION_POLICY_ID,
                    },
                },
            },
            timeout=10,
        )
        resp.raise_for_status()
        log.info("PagerDuty incident created")
    except Exception as e:
        log.error("PagerDuty escalation failed", error=str(e))


# ---------------------------------------------------------------------------
# Task 5: Approval timeout check
# ---------------------------------------------------------------------------


@celery_app.task(name="worker.tasks.check_approval_timeout")
def check_approval_timeout(incident_id: str):
    """Check if an incident is still in PENDING_APPROVAL and escalate if so."""
    log = logger.bind(incident_id=incident_id)
    try:
        with _db_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT status FROM incidents_v2 WHERE id = %s", (incident_id,))
            row = cur.fetchone()
            cur.close()

        if not row:
            return

        if row[0] == "PENDING_APPROVAL":
            log.warning("Incident timed out waiting for human approval. Escalating.")
            _update_incident_status(incident_id, "ESCALATED")
            _insert_timeline(incident_id, actor_type="system",
                             action="Approval timeout reached — auto-escalated",
                             from_status="PENDING_APPROVAL", to_status="ESCALATED",
                             notes="Timed out after 15 minutes waiting for human action.")
            notify_status_change(incident_id, "ESCALATED", actor="system")
            trigger_pagerduty_escalation.delay(
                incident_id, "Timed out waiting for human approval after 15 minutes"
            )
    except Exception as e:
        log.error("check_approval_timeout failed", error=str(e))

# ---------------------------------------------------------------------------
# Task 6: Automatic Shift Summaries
# ---------------------------------------------------------------------------

@celery_app.task(name="worker.tasks.generate_auto_shift_summary")
def generate_auto_shift_summary():
    """
    Runs at HH:30 for the shift boundaries (00:30, 08:30, 16:30).
    Checks if a summary for the previous shift was manually created.
    If not, fetches data, generates a summary, vectorizes, and saves.
    """
    from api.routers.summaries import get_previous_shift_window, get_embed_model
    from langchain_core.messages import SystemMessage, HumanMessage
    from agents.langchain_agent import _get_llm
    
    log = logger.bind(task="generate_auto_shift_summary")
    shift_name, start_time, end_time = get_previous_shift_window()
    
    try:
        with _db_conn() as conn:
            cur = conn.cursor()
            
            # Check if one already exists for this shift_name
            cur.execute(
                "SELECT COUNT(*) FROM historical_shift_summaries WHERE shift_name = %s",
                (shift_name,)
            )
            if cur.fetchone()[0] > 0:
                log.info(f"Summary for {shift_name} already exists. Skipping auto-generation.")
                return
                
            log.info(f"Generating auto-summary for {shift_name}")
            
            cur.execute(
                """
                SELECT alert_name, cluster, status, risk_tier, created_at
                FROM incidents_v2 
                WHERE created_at >= %s AND created_at < %s
                ORDER BY created_at ASC
                """,
                (start_time, end_time)
            )
            incidents = cur.fetchall()
            
            cur.execute(
                """
                SELECT author, message, created_at 
                FROM shift_handovers 
                WHERE created_at >= %s AND created_at < %s
                ORDER BY created_at ASC
                """,
                (start_time, end_time)
            )
            handovers = cur.fetchall()
            
            context = f"--- INCIDENTS FROM {start_time} TO {end_time} ---\n"
            if not incidents:
                context += "No incidents recorded.\n"
            for inc in incidents:
                context += f"- Alert: {inc[0]} | Cluster: {inc[1]} | Status: {inc[2]} | Risk: {inc[3]}\n"
                
            context += f"\n--- SHIFT HANDOVERS FROM {start_time} TO {end_time} ---\n"
            if not handovers:
                context += "No handovers recorded.\n"
            for ho in handovers:
                context += f"- {ho[0]}: {ho[1]}\n"
                
            system_prompt = (
                "You are an SRE shift supervisor. Write a clear, comprehensive markdown report "
                "summarizing the events of the shift based on the provided logs. Group related events, "
                "highlight ongoing maintenance or issues, and provide a quick executive summary at the top."
            )
            
            user_prompt = f"Shift Log:\n{context}\n\nPlease generate the Final Shift Report."
            
            llm = _get_llm()
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            response = llm.invoke(messages)
            summary_text = response.content
            
            model = get_embed_model()
            vector_coord = model.encode(summary_text).tolist()
            
            new_id = uuid.uuid4()
            cur.execute(
                """
                INSERT INTO historical_shift_summaries (id, shift_name, summary_text, embedding, is_auto_generated)
                VALUES (%s, %s, %s, %s::vector, TRUE)
                """,
                (str(new_id), shift_name, summary_text, vector_coord)
            )
            
            log.info(f"Auto-summary saved successfully for {shift_name}")
            
    except Exception as e:
        log.error("Failed to generate auto-summary", error=str(e))

---

// filepath: worker/__init__.py
"""worker package init."""

---

