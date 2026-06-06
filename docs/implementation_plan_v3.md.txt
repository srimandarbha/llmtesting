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
