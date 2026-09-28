"""
Data models for the ComfyUI Integration.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(frozen=True, kw_only=True)
class ComfyUIWorkflow:
    """Represents a parsed ComfyUI workflow JSON payload."""
    nodes: Dict[str, Any]


@dataclass(frozen=True, kw_only=True)
class PromptResponse:
    """Response returned from the /prompt endpoint."""
    prompt_id: str
    number: int
    node_errors: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class QueueHistory:
    """A record of a completed prompt's history."""
    prompt_id: str
    outputs: Dict[str, Any]
    status: Dict[str, Any]


@dataclass(frozen=True, kw_only=True)
class ImageOutput:
    """Represents a downloaded image or video from ComfyUI."""
    filename: str
    subfolder: str
    type: str
    data: bytes
