"""Refactoring agent entry point."""
import logging
from typing import Any

from .models import ImplementationResult, RepositoryAnalysis

logger = logging.getLogger(__name__)


class RefactoringEngine:
    def __init__(self, llm_client: Any, workspace_path: str):
        self._llm_client = llm_client
        self._workspace_path = workspace_path

    def refactor(self, target_module: str, analysis: RepositoryAnalysis) -> ImplementationResult:
        """Return a failed result until code transformations are actually implemented."""
        logger.info("Refactoring requested for module %s", target_module)
        return ImplementationResult(
            diffs=[],
            files_touched=[],
            compile_success=False,
            errors=[
                f"Automated refactoring is not implemented; '{target_module}' was not changed."
            ],
        )
