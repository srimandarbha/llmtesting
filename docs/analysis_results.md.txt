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
