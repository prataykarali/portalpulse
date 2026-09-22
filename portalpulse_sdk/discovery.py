"""Host and Container Resource Discovery for PortalPulse SDK.

Inspects host physical capacity, container/cgroup quota limits (cgroups v1 & v2),
and process allocations to establish the portal's true resource envelope.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional, Tuple

import psutil

from portalpulse_sdk.schema import ResourceProfile

logger = logging.getLogger("portalpulse.sdk.discovery")


def detect_cgroup_limits() -> Tuple[Optional[str], Optional[float], Optional[float]]:
    """Inspect Linux cgroups to discover effective container CPU and RAM limits.

    Returns:
        (cgroup_version, effective_cpu_limit_cores, effective_ram_limit_mb)
    """
    cgroup_v2_cpu = Path("/sys/fs/cgroup/cpu.max")
    cgroup_v2_mem = Path("/sys/fs/cgroup/memory.max")

    cgroup_v1_quota = Path("/sys/fs/cgroup/cpu/cpu.cfs_quota_us")
    cgroup_v1_period = Path("/sys/fs/cgroup/cpu/cpu.cfs_period_us")
    cgroup_v1_mem = Path("/sys/fs/cgroup/memory/memory.limit_in_bytes")

    cgroup_version: Optional[str] = None
    effective_cpu: Optional[float] = None
    effective_ram: Optional[float] = None

    # Check cgroup v2
    if cgroup_v2_cpu.exists() and cgroup_v2_mem.exists():
        cgroup_version = "v2"
        try:
            cpu_content = cgroup_v2_cpu.read_text().strip().split()
            if len(cpu_content) >= 2 and cpu_content[0] != "max":
                quota = float(cpu_content[0])
                period = float(cpu_content[1])
                if period > 0:
                    effective_cpu = round(quota / period, 2)
        except Exception as e:
            logger.debug("Failed reading cgroup v2 cpu.max: %s", e)

        try:
            mem_content = cgroup_v2_mem.read_text().strip()
            if mem_content != "max":
                mem_bytes = float(mem_content)
                effective_ram = round(mem_bytes / (1024 * 1024), 1)
        except Exception as e:
            logger.debug("Failed reading cgroup v2 memory.max: %s", e)

    # Check cgroup v1 if v2 wasn't found or unconstrained
    elif cgroup_v1_quota.exists() and cgroup_v1_period.exists():
        cgroup_version = "v1"
        try:
            quota = float(cgroup_v1_quota.read_text().strip())
            period = float(cgroup_v1_period.read_text().strip())
            if quota > 0 and period > 0:
                effective_cpu = round(quota / period, 2)
        except Exception as e:
            logger.debug("Failed reading cgroup v1 cpu quota: %s", e)

        try:
            if cgroup_v1_mem.exists():
                mem_bytes = float(cgroup_v1_mem.read_text().strip())
                # cgroup v1 uses a very large 64-bit int (~9e18) when unconstrained
                if mem_bytes < 1e15:
                    effective_ram = round(mem_bytes / (1024 * 1024), 1)
        except Exception as e:
            logger.debug("Failed reading cgroup v1 memory limit: %s", e)

    return cgroup_version, effective_cpu, effective_ram


def discover_resource_envelope(
    portal_id: str,
    worker_count: Optional[int] = None,
    worker_concurrency: Optional[int] = None,
    db_pool_size: Optional[int] = None,
    db_connection_limit: Optional[int] = None,
    service_instances: int = 1,
    max_service_instances: int = 32,
) -> ResourceProfile:
    """Discover host hardware, cgroup container constraints, and configured process limits.

    Args:
        portal_id: Identifier of the target portal.
        worker_count: Declared or detected worker process count.
        worker_concurrency: Concurrency per worker.
        db_pool_size: Configured DB connection pool size.
        db_connection_limit: Maximum DB connections allowed.
        service_instances: Number of running replicas / instances.
        max_service_instances: Maximum allowed autoscaling limit.

    Returns:
        Populated ResourceProfile.
    """
    # 1. Host CPU
    logical_cores = psutil.cpu_count(logical=True) or 4
    physical_cores = psutil.cpu_count(logical=False)

    # 2. Host RAM
    vmem = psutil.virtual_memory()
    host_ram_mb = round(vmem.total / (1024 * 1024), 1)

    # 3. Disk
    try:
        disk = psutil.disk_usage("/")
        disk_total_gb = round(disk.total / (1024 * 1024 * 1024), 1)
        disk_free_gb = round(disk.free / (1024 * 1024 * 1024), 1)
    except Exception:
        disk_total_gb = 100.0
        disk_free_gb = 50.0

    # 4. Container / Cgroup quotas
    cgroup_ver, eff_cpu, eff_ram = detect_cgroup_limits()

    # 5. Process Allocations
    if worker_count is None:
        try:
            current_proc = psutil.Process()
            worker_count = max(1, len(current_proc.children()) + 1)
        except Exception:
            worker_count = int(os.environ.get("PORTAL_WORKERS", "1"))

    if worker_concurrency is None:
        worker_concurrency = int(os.environ.get("PORTAL_WORKER_CONCURRENCY", "32"))

    return ResourceProfile(
        portal_id=portal_id,
        host_cpu_cores=logical_cores,
        cpu_cores_physical=physical_cores,
        effective_cpu_limit=eff_cpu,
        host_ram_mb=host_ram_mb,
        effective_ram_limit_mb=eff_ram,
        disk_total_gb=disk_total_gb,
        disk_free_gb=disk_free_gb,
        network_bandwidth_mbps=1000.0,
        worker_count=worker_count,
        worker_concurrency=worker_concurrency,
        db_pool_size=db_pool_size,
        db_connection_limit=db_connection_limit,
        service_instances=service_instances,
        max_service_instances=max_service_instances,
        cgroup_version=cgroup_ver,
    )
