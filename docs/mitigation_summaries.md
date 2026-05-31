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
