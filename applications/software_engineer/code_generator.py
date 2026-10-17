"""Generate code from architecture designs without manufacturing success claims."""
import logging
from typing import Any

from .models import ArchitectureDesign, ImplementationResult

logger = logging.getLogger(__name__)


class CodeGenerator:
    """Agent that should write production code based on an architectural design."""

    def __init__(self, llm_client: Any, workspace_path: str):
        self._llm_client = llm_client
        self._workspace_path = workspace_path

    def generate(self, design: ArchitectureDesign) -> ImplementationResult:
        """Return an explicit failure until actual model-backed generation is available."""
        logger.info("Code generation requested for %d design components", len(design.components))
        return ImplementationResult(
            diffs=[],
            files_touched=[],
            compile_success=False,
            errors=[
                "Automated code generation is not implemented; no files were generated or modified."
            ],
        )
