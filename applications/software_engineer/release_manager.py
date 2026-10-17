"""Release management entry point."""
import logging
from typing import Any

from .models import ReleaseSummary

logger = logging.getLogger(__name__)


class ReleaseManager:
    def __init__(self, llm_client: Any):
        self._llm_client = llm_client

    def generate_release(self, from_commit: str, to_commit: str) -> ReleaseSummary:
        """Refuse to fabricate release versions or changelog entries."""
        logger.info("Release summary requested for %s..%s", from_commit, to_commit)
        raise NotImplementedError(
            "Release summary generation is not implemented; no release data was fabricated."
        )
