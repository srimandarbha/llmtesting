# Task: Advanced CVE Risk & Upgrade Advisor

- [x] 1. Update `ingestion/sync_rhokp_cve_to_postgres.py` with the new relational schema (`affected_versions`) and mock data.
- [x] 2. Update `api/routers/cve_advisor.py` to calculate Risk Percentages, evaluate targets, and determine the "Best Upgrade".
- [x] 3. Update `frontend/src/components/UpgradeAdvisor.tsx` to visualize Risk Gauges, 'Resolves' vs. 'Risks Waiting' sections, and the 'Best Choice' badge.
- [x] 4. Run ingestion script to seed Postgres and verify API outputs.
