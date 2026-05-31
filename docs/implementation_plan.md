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
