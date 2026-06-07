# Task: Dynamic Errata Sync & Live Cluster Integration

- [x] 1. Run SQL updates to modify `clusters` table with realistic `4.19.x` and `4.20.x` OpenShift versions.
- [x] 2. Refactor `api/routers/cve_advisor.py` to query `clusters` instead of `cluster_inventory`.
- [x] 3. Rewrite `ingestion/sync_rhokp_cve_to_postgres.py` to dynamically fetch active versions from `clusters` and generate target Errata mapping logic.
- [x] 4. Run the ingestion script and manually verify API outputs against the UI.
