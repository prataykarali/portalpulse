"""Action Masker for PortalPulse Control Plane.

Translates declared portal infrastructure capabilities into an Action Mask over
the 11 discrete SREAction mitigation types, ensuring the neural network policy
never recommends or executes an infrastructure operation unsupported by the host.
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np

from backend.control_plane.schema import ActionMask, MaskedRecommendation
from backend.m4_action_intelligence.schema import ACTION_INDEX_MAP, SREAction
from portalpulse_sdk.schema import PortalCapabilities


class ActionMasker:
    """Computes and applies capability masks to AI action policy predictions."""

    @staticmethod
    def get_action_mask(capabilities: PortalCapabilities, portal_id: str) -> ActionMask:
        """Construct a boolean mask vector corresponding to the 11 discrete SRE actions."""
        mask_vector: List[bool] = []
        permitted: List[str] = []
        masked: List[str] = []

        for idx in range(len(ACTION_INDEX_MAP)):
            action = ACTION_INDEX_MAP[idx]
            allowed = ActionMasker.is_action_permitted(action, capabilities)
            mask_vector.append(allowed)
            if allowed:
                permitted.append(action.value)
            else:
                masked.append(action.value)

        return ActionMask(
            portal_id=portal_id,
            mask_vector=mask_vector,
            permitted_actions=permitted,
            masked_actions=masked,
        )

    @staticmethod
    def is_action_permitted(action: SREAction, caps: PortalCapabilities) -> bool:
        """Check if a single SRE action is supported by the portal capabilities."""
        if action == SREAction.NO_OP:
            return True
        elif action in (SREAction.SCALE_OUT_WORKERS, SREAction.SCALE_IN_WORKERS):
            return caps.horizontal_scaling
        elif action == SREAction.ACTIVATE_RATE_LIMIT:
            return caps.rate_limiting
        elif action == SREAction.INCREASE_DB_POOL:
            return caps.database_pool_scaling
        elif action == SREAction.PURGE_REDIS_CACHE:
            return caps.caching
        elif action == SREAction.DRAIN_REQUEST_QUEUE:
            return caps.request_queue
        elif action == SREAction.ENGAGE_CIRCUIT_BREAKER:
            return caps.circuit_breaker or caps.static_fallback
        elif action == SREAction.RESTART_DEGRADED_PODS:
            return caps.pod_restart
        elif action == SREAction.DIVERT_READS_TO_REPLICA:
            return caps.database_replica
        elif action == SREAction.ENABLE_WAITING_ROOM:
            return caps.waiting_room or caps.request_queue
        return False

    @staticmethod
    def apply_mask(
        portal_id: str,
        raw_probabilities: Dict[str, float],
        capabilities: PortalCapabilities,
    ) -> MaskedRecommendation:
        """Apply capability mask to neural network policy softmax probabilities.

        Zeros out forbidden actions, re-normalizes the distribution across permitted
        actions, and selects the highest-scoring permitted action.
        """
        mask = ActionMasker.get_action_mask(capabilities, portal_id)
        raw_best_action = max(raw_probabilities, key=raw_probabilities.get)  # type: ignore[arg-type]
        raw_confidence = float(raw_probabilities[raw_best_action])

        # Convert to numpy array in canonical action index order
        probs = np.zeros(len(ACTION_INDEX_MAP), dtype=np.float32)
        for idx, act in ACTION_INDEX_MAP.items():
            probs[idx] = float(raw_probabilities.get(act.value, 0.0))

        # Apply boolean mask
        mask_arr = np.array(mask.mask_vector, dtype=bool)
        masked_probs = np.where(mask_arr, probs, 0.0)

        # Re-normalize across permitted actions
        total_mass = float(np.sum(masked_probs))
        if total_mass > 1e-6:
            effective_probs = masked_probs / total_mass
        else:
            # Fallback to NO_OP if all allowed probabilities sum to zero
            effective_probs = np.zeros_like(masked_probs)
            effective_probs[0] = 1.0  # NO_OP

        effective_best_idx = int(np.argmax(effective_probs))
        effective_action = ACTION_INDEX_MAP[effective_best_idx].value
        effective_confidence = round(float(effective_probs[effective_best_idx]), 4)

        was_masked = bool(raw_best_action != effective_action)
        if was_masked:
            rationale = (
                f"Raw recommended action '{raw_best_action}' was masked out because host portal "
                f"'{portal_id}' declared the corresponding capability as unsupported. "
                f"Diverted to next highest permitted action: '{effective_action}' "
                f"(effective confidence: {effective_confidence:.1%})."
            )
        else:
            rationale = (
                f"Action '{effective_action}' is permitted by host portal '{portal_id}' "
                f"infrastructure capabilities."
            )

        prob_dict: Dict[str, float] = {
            ACTION_INDEX_MAP[i].value: round(float(effective_probs[i]), 4)
            for i in range(len(ACTION_INDEX_MAP))
        }

        return MaskedRecommendation(
            portal_id=portal_id,
            raw_action=raw_best_action,
            raw_confidence=round(raw_confidence, 4),
            effective_action=effective_action,
            effective_confidence=effective_confidence,
            was_masked=was_masked,
            masking_rationale=rationale,
            masked_actions=mask.masked_actions,
            effective_probabilities=prob_dict,
        )


# Global singleton
ACTION_MASKER = ActionMasker()
