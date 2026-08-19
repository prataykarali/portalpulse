# SRE Incident Response Runbook for Academic Portal Outages

## Incident Severity Matrix
- **SEV-1 (CRITICAL)**: P95 Latency > 800ms OR CPU > 85% OR DB Pool Saturation > 90%.
- **SEV-2 (WARNING)**: Utilization > 70% during approaching result declaration window.
- **SEV-3 (NOMINAL)**: Operating inside baseline SLA parameters.

## Automated & Manual Remediation Steps
1. **Enable Virtual Waiting Room**: Directs all traffic above safe capacity into a FIFO queue.
2. **Engage Degraded Query Mode**: Temporarily disables un-indexed grade analytics and audit logs.
3. **Scale Backend Pods**: Trigger Kubernetes HPA scaling from 4 to 16 pods.
4. **Purge Expired Redis Keys**: Flush cold cached queries to free up buffer pool memory.
