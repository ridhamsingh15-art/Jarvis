"""
Data models for the JARVIS Self-Evolution Framework.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Optional


class Priority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    TECHNICAL_DEBT = "technical_debt"
    FUTURE_FEATURE = "future_feature"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ProposalState(StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    REJECTED = "rejected"
    IMPLEMENTED = "implemented"


@dataclass(frozen=True, kw_only=True)
class SystemMetrics:
    """Metrics collected across the system."""
    latency_ms: float
    failure_rate: float
    retry_rate: float
    memory_usage_mb: float
    expensive_models_usage_count: int
    most_failed_plugins: list[str] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class EvolutionProposal:
    """A structured improvement proposal."""
    id: str = field(default_factory=lambda: f"prop_{uuid.uuid4().hex[:8]}")
    problem: str
    evidence: str
    impact: str
    recommended_solution: str
    affected_modules: list[str]
    estimated_complexity: str
    estimated_risk: RiskLevel
    priority: Priority
    state: ProposalState = ProposalState.DRAFT
    duplicate_of: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class EvolutionRoadmap:
    """An evolving roadmap of proposals."""
    proposals: list[EvolutionProposal] = field(default_factory=list)
    last_updated: float = 0.0
