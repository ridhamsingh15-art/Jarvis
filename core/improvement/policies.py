import builtins
import datetime

from .enums import PolicyAction
from .interfaces import IPolicyEngine
from .models import OptimizationRecommendation


class SafetyPolicyEngine(IPolicyEngine):
    """Validates recommendations against unsafe bounds or rapid oscillation."""

    def evaluate_recommendation(
        self, 
        recommendation: OptimizationRecommendation, 
        history: builtins.list[OptimizationRecommendation]
    ) -> PolicyAction:
        
        # Check for rapid oscillation (same target and category within short window)
        now = datetime.datetime.now(datetime.UTC)
        for past_rec in reversed(history):
            if past_rec.category == recommendation.category and past_rec.target == recommendation.target:
                # Basic mock check: if last recommendation was recent and values differ
                # In real prod this would evaluate precise oscillation deltas.
                past_time = datetime.datetime.fromisoformat(past_rec.timestamp.iso_value)
                delta = now - past_time
                if delta.total_seconds() < 60:
                    return PolicyAction.BLOCK_OSCILLATION
                break # Only check the most recent one for this target
                
        # Mock checking for completely unsafe negative values for weights
        if recommendation.suggested_value < 0:
            return PolicyAction.BLOCK_UNSAFE

        return PolicyAction.ALLOW
