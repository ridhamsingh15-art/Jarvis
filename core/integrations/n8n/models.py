"""
Domain models for n8n workflows and executions.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class N8nWorkflow:
    """Represents a registered n8n workflow accessible to JARVIS."""
    id: str  # The physical n8n workflow ID (e.g., "1", "2")
    name: str  # JARVIS-friendly name (e.g., "CreateYouTubeVideo")
    description: str
    required_inputs: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    estimated_duration_sec: int = 60


@dataclass
class N8nExecutionResult:
    """Represents the result of an n8n workflow execution."""
    execution_id: str
    status: str  # "running", "waiting", "completed", "error", "canceled"
    data: dict[str, Any] | None = None
    error_message: str | None = None
