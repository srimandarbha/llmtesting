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
