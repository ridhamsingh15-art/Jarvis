"""
Model Profiles for the Capability Router.
"""

from dataclasses import dataclass
from enum import Enum


class CostTier(Enum):
    """Cost tiers for models."""
    FREE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3


class LatencyTier(Enum):
    """Latency tiers for models."""
    FAST = 1
    MEDIUM = 2
    SLOW = 3


@dataclass(frozen=True)
class ModelProfile:
    """Metadata describing a reasoning model's capabilities."""
    
    name: str           # e.g. "qwen3:8b", "gemini-2.5-pro"
    provider: str       # e.g. "ollama", "google"
    
    reasoning: int      # 1-10
    coding: int         # 1-10
    vision: bool
    voice: bool
    multimodal: bool
    
    context_length: int
    cost: CostTier
    latency: LatencyTier
    privacy_local: bool # True if the model runs completely locally
