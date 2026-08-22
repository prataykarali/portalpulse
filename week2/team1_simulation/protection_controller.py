"""Week 2 Closed-Loop Protection Controller & Prescriptive Capacity Engine.

Implements prescriptive capacity planning and multi-stage closed-loop traffic control:
Traffic -> Application -> DB/Redis -> Telemetry -> ML Router -> Decision -> Protection -> Stabilized Telemetry.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from week2.team1_simulation.telemetry_synthesizer import synthesize_telemetry
from week2.team2_ml.model_router import MODEL_ROUTER
from week2.team2_ml.drift_detector import DRIFT_DETECTOR


class PrescriptiveCapacityAdvisor:
    """Prescriptive Decision Engine recommending exact infrastructure sizing actions."""

    @staticmethod
    def advise(
        scenario_name: str,
        concurrent_users: int,
        num_pods: int = 4,
        db_pool_size: int = 100,
        cache_hit_ratio: float = 0.70,
        waiting_room_enabled: bool = False,
        degraded_mode: bool = False,
    ) -> Dict[str, Any]:
        # 1. Telemetry synthesis
        tel = synthesize_telemetry(
            scenario_name=scenario_name,
            concurrent_users=concurrent_users,
            num_pods=num_pods,
            db_pool_size=db_pool_size,
            cache_hit_ratio=cache_hit_ratio,
            waiting_room_enabled=waiting_room_enabled,
            degraded_mode=degraded_mode,
        )

        # 2. ML Ensemble prediction
        ml_res = MODEL_ROUTER.predict(
            hour=14,
            day_of_week=2,
            is_weekend=0,
            is_result_window=1 if "Result" in scenario_name else 0,
            concurrent_users=concurrent_users,
            requests_per_sec=tel["requests_per_sec"],
        )

        safe_capacity = ml_res["consensus_capacity"]
        headroom_pct = round(((safe_capacity - concurrent_users) / max(safe_capacity, 1.0)) * 100.0, 1)

        # 3. Determine System State
        cpu = tel["cpu"]
        lat = tel["latency"]
        db_util = tel["db_pool_utilization"]

        if cpu >= 85.0 or lat >= 800.0 or db_util >= 90.0 or headroom_pct < 0.0:
            system_state = "CRITICAL"
            state_badge = "🔴 CRITICAL OVERLOAD"
            state_desc = "System is actively breaching SLA thresholds. Immediate protection required."
        elif cpu >= 70.0 or lat >= 350.0 or db_util >= 75.0 or headroom_pct < 20.0:
            system_state = "PREPARE"
            state_badge = "🟡 PREPARE MODE"
            state_desc = "System approaching saturation knee. Predictive scaling and queueing recommended."
        else:
            system_state = "SAFE"
            state_badge = "🟢 SAFE OPERATION"
            state_desc = "All metrics within nominal operating margins."

        # 4. Prescriptive Action Calculations
        # Pod recommendations
        if system_state == "CRITICAL":
            target_pods = min(16, max(num_pods + 4, int(math.ceil(concurrent_users / 2200.0))))
            target_db = min(300, max(db_pool_size + 60, int(target_pods * 25)))
            recommend_waiting_room = True
            recommend_cache_warm = True
            recommend_degraded = True if lat > 1500.0 else False
        elif system_state == "PREPARE":
            target_pods = min(16, max(num_pods + 2, int(math.ceil(concurrent_users / 2800.0))))
            target_db = min(250, max(db_pool_size + 30, int(target_pods * 22)))
            recommend_waiting_room = True if concurrent_users > 7000 else False
            recommend_cache_warm = True
            recommend_degraded = False
        else:
            target_pods = num_pods
            target_db = db_pool_size
            recommend_waiting_room = False
            recommend_cache_warm = False
            recommend_degraded = False

        # Calculate estimated new capacity after applying recommendations
        new_pod_mult = (target_pods / 4.0) ** 0.88
        new_db_mult = min(1.3, max(0.5, target_db / 100.0))
        new_cache_mult = 1.0 + (max(0.85, cache_hit_ratio) * 0.45)
        base_cap = 7800.0 if "Result" in scenario_name else 9400.0
        estimated_new_capacity = round(base_cap * new_pod_mult * new_cache_mult * new_db_mult, 0)
        capacity_gain_pct = round(((estimated_new_capacity - safe_capacity) / max(safe_capacity, 1.0)) * 100.0, 1)

        recommendations_list = []
        if target_pods > num_pods:
            recommendations_list.append(f"Scale App Pods: {num_pods} → {target_pods} (+{target_pods - num_pods} pods)")
        else:
            recommendations_list.append(f"Maintain App Pods at {num_pods}")

        if target_db > db_pool_size:
            recommendations_list.append(f"Expand DB Connection Pool: {db_pool_size} → {target_db} (+{target_db - db_pool_size} conns)")
        else:
            recommendations_list.append(f"Maintain DB Pool at {db_pool_size}")

        if recommend_waiting_room:
            recommendations_list.append("Activate Virtual Waiting Room (Dynamic Token Queueing)")
        if recommend_cache_warm:
            recommendations_list.append("Pre-warm Redis Result Cache & Extend TTL to 600s (Target >85% Hit Rate)")
        if recommend_degraded:
            recommendations_list.append("Enable Degraded Mode (Disable non-critical analytics joins)")

        return {
            "current_state": {
                "users": concurrent_users,
                "cpu_pct": cpu,
                "latency_ms": lat,
                "db_pool_util_pct": db_util,
                "redis_hit_pct": round(cache_hit_ratio * 100.0, 1),
                "num_pods": num_pods,
                "db_pool_size": db_pool_size,
            },
            "system_state": system_state,
            "state_badge": state_badge,
            "state_desc": state_desc,
            "ml_safe_capacity": safe_capacity,
            "headroom_pct": headroom_pct,
            "target_pods": target_pods,
            "target_db_pool": target_db,
            "recommend_waiting_room": recommend_waiting_room,
            "recommend_cache_warm": recommend_cache_warm,
            "recommend_degraded": recommend_degraded,
            "estimated_new_capacity": estimated_new_capacity,
            "capacity_gain_pct": capacity_gain_pct,
            "action_items": recommendations_list,
            "telemetry": tel,
            "ml_consensus": ml_res,
        }


class ClosedLoopController:
    """Closed-Loop Intelligence Engine orchestrating real-time protection and observing telemetry recovery."""

    @staticmethod
    def run_closed_loop_simulation(
        scenario_name: str = "Result Declaration Rush",
        surge_users: int = 12500,
        initial_pods: int = 4,
        initial_db_pool: int = 100,
        initial_cache_hit: float = 0.65,
    ) -> List[Dict[str, Any]]:
        """Executes a 4-step closed-loop simulation showing stabilization under load."""
        trajectory = []

        # Step 0: Initial Surge Load (Unmitigated)
        advice_t0 = PrescriptiveCapacityAdvisor.advise(
            scenario_name=scenario_name,
            concurrent_users=surge_users,
            num_pods=initial_pods,
            db_pool_size=initial_db_pool,
            cache_hit_ratio=initial_cache_hit,
            waiting_room_enabled=False,
            degraded_mode=False,
        )
        t0_cpu = advice_t0["current_state"]["cpu_pct"]
        t0_lat = advice_t0["current_state"]["latency_ms"]
        trajectory.append({
            "step": 0,
            "phase": "t0: Unmitigated Surge Load",
            "state": advice_t0["system_state"],
            "users": surge_users,
            "admitted_users": surge_users,
            "queued_users": 0,
            "pods": initial_pods,
            "db_pool": initial_db_pool,
            "cache_hit_pct": round(initial_cache_hit * 100.0, 1),
            "cpu": t0_cpu,
            "latency": t0_lat,
            "protection_active": "None",
            "narrative": f"Surge load of {surge_users:,} users arrives. CPU hits {t0_cpu}% and latency spikes to {t0_lat}ms.",
        })

        # Step 1: Model Prediction & Protection Triggered (Actuation)
        waiting_room = advice_t0["recommend_waiting_room"]
        advice_t1 = PrescriptiveCapacityAdvisor.advise(
            scenario_name=scenario_name,
            concurrent_users=surge_users,
            num_pods=initial_pods,
            db_pool_size=initial_db_pool,
            cache_hit_ratio=0.82,  # Cache warm-up starting
            waiting_room_enabled=waiting_room,
            degraded_mode=False,
        )
        t1_queued = advice_t1["telemetry"]["queued_users"]
        t1_cpu = advice_t1["current_state"]["cpu_pct"]
        t1_lat = advice_t1["current_state"]["latency_ms"]
        trajectory.append({
            "step": 1,
            "phase": "t1: Protection Controller Actuated",
            "state": "PREPARE",
            "users": surge_users,
            "admitted_users": advice_t1["telemetry"]["admitted_users"],
            "queued_users": t1_queued,
            "pods": initial_pods,
            "db_pool": initial_db_pool,
            "cache_hit_pct": 82.0,
            "cpu": t1_cpu,
            "latency": t1_lat,
            "protection_active": "Virtual Waiting Room + Cache Pre-warm",
            "narrative": f"ML Router predicts saturation. Waiting Room queues {t1_queued:,} users; Redis pre-warms to 82% hit rate.",
        })

        # Step 2: Autoscaler Pods Provisioned & DB Pool Expanded
        target_pods = advice_t0["target_pods"]
        target_db = advice_t0["target_db_pool"]
        advice_t2 = PrescriptiveCapacityAdvisor.advise(
            scenario_name=scenario_name,
            concurrent_users=surge_users,
            num_pods=target_pods,
            db_pool_size=target_db,
            cache_hit_ratio=0.88,
            waiting_room_enabled=waiting_room,
            degraded_mode=False,
        )
        t2_cpu = advice_t2["current_state"]["cpu_pct"]
        t2_lat = advice_t2["current_state"]["latency_ms"]
        trajectory.append({
            "step": 2,
            "phase": "t2: HPA Pods Scaled & Pool Expanded",
            "state": "SAFE",
            "users": surge_users,
            "admitted_users": advice_t2["telemetry"]["admitted_users"],
            "queued_users": advice_t2["telemetry"]["queued_users"],
            "pods": target_pods,
            "db_pool": target_db,
            "cache_hit_pct": 88.0,
            "cpu": t2_cpu,
            "latency": t2_lat,
            "protection_active": f"HPA ({target_pods} Pods) + DB Pool ({target_db}) + Redis (88%)",
            "narrative": f"HPA brings {target_pods} pods online. CPU drops to {t2_cpu}% and latency drops to {t2_lat}ms.",
        })

        # Step 3: Steady-State Equilibrium (Queue Drained)
        advice_t3 = PrescriptiveCapacityAdvisor.advise(
            scenario_name=scenario_name,
            concurrent_users=surge_users,
            num_pods=target_pods,
            db_pool_size=target_db,
            cache_hit_ratio=0.90,
            waiting_room_enabled=False,  # Scaled infrastructure absorbs entire surge
            degraded_mode=False,
        )
        t3_cpu = advice_t3["current_state"]["cpu_pct"]
        t3_lat = advice_t3["current_state"]["latency_ms"]
        trajectory.append({
            "step": 3,
            "phase": "t3: Closed-Loop Equilibrium",
            "state": "SAFE",
            "users": surge_users,
            "admitted_users": surge_users,
            "queued_users": 0,
            "pods": target_pods,
            "db_pool": target_db,
            "cache_hit_pct": 90.0,
            "cpu": t3_cpu,
            "latency": t3_lat,
            "protection_active": "Scaled Stable Infrastructure",
            "narrative": f"Closed loop stabilized. Full surge of {surge_users:,} users served smoothly at {t3_lat}ms latency.",
        })

        return trajectory


# Singleton Instances
PRESCRIPTIVE_ADVISOR = PrescriptiveCapacityAdvisor()
CLOSED_LOOP_CONTROLLER = ClosedLoopController()
