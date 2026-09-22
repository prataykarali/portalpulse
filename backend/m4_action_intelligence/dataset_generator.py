"""Synthetic state-action dataset generation for PortalPulse Action Intelligence.

Synthesizes 25,000 realistic state-action tuples grounded in SRE domain playbooks,
queueing theory, and secure_action.md strategies with calibrated noise and edge cases.
"""

from __future__ import annotations

from typing import Tuple

import numpy as np
import pandas as pd

from backend.m4_action_intelligence.schema import (
    ACTION_INDEX_MAP,
    STATE_FEATURE_NAMES,
    SREAction,
)


def generate_action_dataset(
    n_samples: int = 25000,
    random_state: int = 42,
) -> Tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    """Generate balanced synthetic training samples across all 11 tactical SRE actions.

    Args:
        n_samples: Total number of samples to synthesize (divided evenly across 11 actions).
        random_state: RNG seed for reproducible generation.

    Returns:
        Tuple of:
            - X: np.ndarray of shape (n_samples, 13)
            - y: np.ndarray of shape (n_samples,) with integer action labels [0-10]
            - df: pd.DataFrame containing feature columns, label_id, and action_name
    """
    rng = np.random.default_rng(random_state)
    n_classes = len(ACTION_INDEX_MAP)
    samples_per_class = n_samples // n_classes

    all_features = []
    all_labels = []

    for action_id, action_enum in ACTION_INDEX_MAP.items():
        k = samples_per_class

        if action_enum == SREAction.NO_OP:
            # Nominal operating parameters
            cpu = rng.uniform(18.0, 52.0, k)
            ram = rng.uniform(28.0, 58.0, k)
            rps = rng.uniform(200.0, 1400.0, k)
            lat = rng.uniform(35.0, 160.0, k)
            err = rng.uniform(0.0001, 0.004, k)
            fut_rps = rps * rng.uniform(0.92, 1.08, k)
            fut_cpu = cpu * rng.uniform(0.92, 1.08, k)
            fut_lat = lat * rng.uniform(0.92, 1.08, k)
            anom = rng.uniform(0.02, 0.28, k)
            rca_c = rng.uniform(0.05, 0.30, k)
            db_conn = rng.uniform(15.0, 48.0, k)
            queue = rng.uniform(0.0, 20.0, k)
            inst = rng.integers(4, 9, k).astype(float)

        elif action_enum == SREAction.SCALE_OUT_WORKERS:
            # Worker CPU compute exhaustion
            cpu = rng.uniform(84.0, 99.0, k)
            ram = rng.uniform(50.0, 78.0, k)
            rps = rng.uniform(1800.0, 4200.0, k)
            lat = rng.uniform(450.0, 1800.0, k)
            err = rng.uniform(0.006, 0.045, k)
            fut_rps = rps * rng.uniform(1.05, 1.30, k)
            fut_cpu = np.clip(cpu * rng.uniform(1.02, 1.15, k), 85.0, 100.0)
            fut_lat = lat * rng.uniform(1.05, 1.25, k)
            anom = rng.uniform(0.68, 0.96, k)
            rca_c = rng.uniform(0.70, 0.98, k)
            db_conn = rng.uniform(25.0, 62.0, k)
            queue = rng.uniform(40.0, 380.0, k)
            inst = rng.integers(2, 7, k).astype(float)

        elif action_enum == SREAction.SCALE_IN_WORKERS:
            # Over-provisioned during night or lull
            cpu = rng.uniform(6.0, 24.0, k)
            ram = rng.uniform(18.0, 34.0, k)
            rps = rng.uniform(40.0, 380.0, k)
            lat = rng.uniform(18.0, 55.0, k)
            err = rng.uniform(0.0, 0.001, k)
            fut_rps = rps * rng.uniform(0.85, 1.05, k)
            fut_cpu = cpu * rng.uniform(0.85, 1.05, k)
            fut_lat = lat * rng.uniform(0.90, 1.05, k)
            anom = rng.uniform(0.01, 0.18, k)
            rca_c = rng.uniform(0.05, 0.25, k)
            db_conn = rng.uniform(8.0, 25.0, k)
            queue = np.zeros(k)
            inst = rng.integers(9, 17, k).astype(float)

        elif action_enum == SREAction.ACTIVATE_RATE_LIMIT:
            # Ingress rate exceeding safe thresholds
            cpu = rng.uniform(70.0, 88.0, k)
            ram = rng.uniform(55.0, 75.0, k)
            rps = rng.uniform(4200.0, 7200.0, k)
            lat = rng.uniform(320.0, 1100.0, k)
            err = rng.uniform(0.012, 0.055, k)
            fut_rps = rps * rng.uniform(1.08, 1.35, k)
            fut_cpu = np.clip(cpu * rng.uniform(1.04, 1.18, k), 75.0, 98.0)
            fut_lat = lat * rng.uniform(1.08, 1.30, k)
            anom = rng.uniform(0.72, 0.94, k)
            rca_c = rng.uniform(0.68, 0.92, k)
            db_conn = rng.uniform(45.0, 78.0, k)
            queue = rng.uniform(220.0, 850.0, k)
            inst = rng.integers(6, 12, k).astype(float)

        elif action_enum == SREAction.INCREASE_DB_POOL:
            # PostgreSQL pool exhaustion
            cpu = rng.uniform(38.0, 68.0, k)
            ram = rng.uniform(45.0, 70.0, k)
            rps = rng.uniform(1400.0, 3200.0, k)
            lat = rng.uniform(650.0, 2600.0, k)
            err = rng.uniform(0.025, 0.085, k)
            fut_rps = rps * rng.uniform(0.95, 1.12, k)
            fut_cpu = cpu * rng.uniform(0.95, 1.08, k)
            fut_lat = lat * rng.uniform(1.05, 1.35, k)
            anom = rng.uniform(0.76, 0.98, k)
            rca_c = rng.uniform(0.78, 0.99, k)
            db_conn = rng.uniform(88.0, 99.5, k)  # Pegged DB pool
            queue = rng.uniform(80.0, 500.0, k)
            inst = rng.integers(4, 9, k).astype(float)

        elif action_enum == SREAction.PURGE_REDIS_CACHE:
            # Cache pollution / miss-rate spike
            cpu = rng.uniform(45.0, 72.0, k)
            ram = rng.uniform(40.0, 68.0, k)
            rps = rng.uniform(1200.0, 2800.0, k)
            lat = rng.uniform(280.0, 750.0, k)
            err = rng.uniform(0.008, 0.035, k)
            fut_rps = rps * rng.uniform(0.98, 1.10, k)
            fut_cpu = cpu * rng.uniform(0.98, 1.10, k)
            fut_lat = lat * rng.uniform(1.02, 1.20, k)
            anom = rng.uniform(0.48, 0.75, k)
            rca_c = rng.uniform(0.62, 0.88, k)
            db_conn = rng.uniform(55.0, 78.0, k)
            queue = rng.uniform(25.0, 180.0, k)
            inst = rng.integers(4, 8, k).astype(float)

        elif action_enum == SREAction.DRAIN_REQUEST_QUEUE:
            # Queue buffer overload / worker backpressure
            cpu = rng.uniform(72.0, 94.0, k)
            ram = rng.uniform(60.0, 85.0, k)
            rps = rng.uniform(2500.0, 4800.0, k)
            lat = rng.uniform(1100.0, 3600.0, k)
            err = rng.uniform(0.035, 0.110, k)
            fut_rps = rps * rng.uniform(0.95, 1.15, k)
            fut_cpu = cpu * rng.uniform(0.98, 1.08, k)
            fut_lat = lat * rng.uniform(1.05, 1.30, k)
            anom = rng.uniform(0.80, 0.98, k)
            rca_c = rng.uniform(0.75, 0.96, k)
            db_conn = rng.uniform(50.0, 80.0, k)
            queue = rng.uniform(920.0, 2600.0, k)  # Massive queue
            inst = rng.integers(4, 9, k).astype(float)

        elif action_enum == SREAction.ENGAGE_CIRCUIT_BREAKER:
            # Third-party / downstream dependency failure
            cpu = rng.uniform(40.0, 72.0, k)
            ram = rng.uniform(42.0, 68.0, k)
            rps = rng.uniform(800.0, 2500.0, k)
            lat = rng.uniform(1600.0, 4800.0, k)
            err = rng.uniform(0.095, 0.420, k)  # Extreme 5xx error rate
            fut_rps = rps * rng.uniform(0.90, 1.05, k)
            fut_cpu = cpu * rng.uniform(0.95, 1.05, k)
            fut_lat = lat * rng.uniform(1.05, 1.25, k)
            anom = rng.uniform(0.86, 0.99, k)
            rca_c = rng.uniform(0.82, 0.99, k)
            db_conn = rng.uniform(30.0, 65.0, k)
            queue = rng.uniform(50.0, 350.0, k)
            inst = rng.integers(4, 8, k).astype(float)

        elif action_enum == SREAction.RESTART_DEGRADED_PODS:
            # Memory leak / container degradation
            cpu = rng.uniform(42.0, 78.0, k)
            ram = rng.uniform(89.0, 99.5, k)  # Memory saturation
            rps = rng.uniform(1000.0, 2600.0, k)
            lat = rng.uniform(520.0, 1750.0, k)
            err = rng.uniform(0.018, 0.065, k)
            fut_rps = rps * rng.uniform(0.95, 1.05, k)
            fut_cpu = cpu * rng.uniform(0.98, 1.08, k)
            fut_lat = lat * rng.uniform(1.02, 1.20, k)
            anom = rng.uniform(0.74, 0.97, k)
            rca_c = rng.uniform(0.72, 0.94, k)
            db_conn = rng.uniform(35.0, 68.0, k)
            queue = rng.uniform(40.0, 280.0, k)
            inst = rng.integers(3, 8, k).astype(float)

        elif action_enum == SREAction.DIVERT_READS_TO_REPLICA:
            # Primary DB read contention
            cpu = rng.uniform(42.0, 65.0, k)
            ram = rng.uniform(45.0, 68.0, k)
            rps = rng.uniform(1600.0, 3600.0, k)
            lat = rng.uniform(720.0, 2100.0, k)
            err = rng.uniform(0.015, 0.050, k)
            fut_rps = rps * rng.uniform(0.98, 1.15, k)
            fut_cpu = cpu * rng.uniform(0.98, 1.08, k)
            fut_lat = lat * rng.uniform(1.05, 1.25, k)
            anom = rng.uniform(0.72, 0.92, k)
            rca_c = rng.uniform(0.70, 0.94, k)
            db_conn = rng.uniform(74.0, 87.0, k)  # High DB load but not fully pegged
            queue = rng.uniform(60.0, 320.0, k)
            inst = rng.integers(4, 9, k).astype(float)

        elif action_enum == SREAction.ENABLE_WAITING_ROOM:
            # Massive flash crowd surge (e.g. 10k+ RPS)
            cpu = rng.uniform(85.0, 99.0, k)
            ram = rng.uniform(68.0, 88.0, k)
            rps = rng.uniform(7800.0, 14500.0, k)  # Enormous ingress
            lat = rng.uniform(900.0, 3200.0, k)
            err = rng.uniform(0.035, 0.120, k)
            fut_rps = rps * rng.uniform(1.10, 1.40, k)
            fut_cpu = np.clip(cpu * rng.uniform(1.02, 1.12, k), 90.0, 100.0)
            fut_lat = lat * rng.uniform(1.10, 1.35, k)
            anom = rng.uniform(0.88, 0.99, k)
            rca_c = rng.uniform(0.82, 0.98, k)
            db_conn = rng.uniform(60.0, 90.0, k)
            queue = rng.uniform(750.0, 2200.0, k)
            inst = rng.integers(6, 14, k).astype(float)

        # Stack into matrix of shape (k, 13)
        class_matrix = np.column_stack([
            cpu, ram, rps, lat, err,
            fut_rps, fut_cpu, fut_lat,
            anom, rca_c, db_conn, queue, inst
        ])

        # Add slight Gaussian noise to simulate sensor jitter
        noise = rng.normal(0.0, 0.015, class_matrix.shape)
        class_matrix = np.maximum(0.0, class_matrix + class_matrix * noise)

        all_features.append(class_matrix)
        all_labels.append(np.full(k, action_id, dtype=np.int64))

    X = np.vstack(all_features).astype(np.float32)
    y = np.concatenate(all_labels).astype(np.int64)

    # Shuffle the dataset
    indices = rng.permutation(len(X))
    X = X[indices]
    y = y[indices]

    # Build DataFrame for inspectability
    df = pd.DataFrame(X, columns=STATE_FEATURE_NAMES)
    df["action_id"] = y
    df["action_name"] = [ACTION_INDEX_MAP[idx].value for idx in y]

    return X, y, df
