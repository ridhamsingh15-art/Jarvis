"""
Security Reviewer Agent.

Detects unsafe operations, reviews permission usage and plugin isolation.
"""
import logging
from typing import Any
from .models import CodeDiff, SecurityReviewReport

logger = logging.getLogger(__name__)

class SecurityReviewer:
    def __init__(self, llm_client: Any):
        self._llm_client = llm_client

    def review(self, diffs: list[CodeDiff]) -> SecurityReviewReport:
        logger.info("Performing security review...")
        # Stub
        return SecurityReviewReport(
            approved=True,
            vulnerabilities=[],
            unsafe_operations=[]
        )
