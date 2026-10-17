"""
Configuration definition for the Model Router.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ModelRouterConfig:
    """Immutable configuration for the Model Router subsystem.
    
    Contains default preferences and thresholds used during the routing lifecycle.
    """
    
    # Provider preferences
    default_chat_provider: str | None = None
    default_reasoning_provider: str | None = None
    prefer_local: bool = True
    
    # Fallback and routing mechanics
    max_fallback_attempts: int = 3
    routing_policy: str = "weighted_score"
    request_timeout_seconds: int = 30
    
    # Future extensibility flags
    future_extension_flags: dict[str, Any] = field(default_factory=dict)
