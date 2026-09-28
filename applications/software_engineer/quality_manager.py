"""
Quality Manager.

Enforces rules: never overwrite silently, always create checkpoints, always produce a review.
"""
import logging
from .exceptions import QualityGateError

logger = logging.getLogger(__name__)

class QualityManager:
    def __init__(self):
        self._checkpoints_created = 0

    def record_checkpoint(self) -> None:
        self._checkpoints_created += 1

    def check_quality_gate(self) -> None:
        """Ensure that proper workflow rules were followed before completion."""
        if self._checkpoints_created == 0:
            raise QualityGateError("Quality Gate Failed: No git checkpoint was created before making changes.")
        logger.info("Quality gate passed.")
