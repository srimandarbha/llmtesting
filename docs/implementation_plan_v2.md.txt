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
