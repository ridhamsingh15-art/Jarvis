"""Documentation agent entry point."""
import logging
from typing import Any

from .models import ImplementationResult, RepositoryAnalysis

logger = logging.getLogger(__name__)


class DocumentationEngine:
    def __init__(self, llm_client: Any, workspace_path: str):
        self._llm_client = llm_client
        self._workspace_path = workspace_path

    def document_changes(self, implementation: ImplementationResult, analysis: RepositoryAnalysis) -> None:
        """Refuse to imply documentation was updated until the writer is implemented."""
        logger.info("Documentation requested for %d code changes", len(implementation.diffs))
        raise NotImplementedError(
            "Automated documentation updates are not implemented; no documentation was changed."
        )
