"""
Experience & Continuous Learning Engine — data models.

Captures the full context of a mission's execution so that JARVIS can
learn from it: what worked, what failed, how long it took, and what the
analytics said afterwards.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Optional

from core.models.primitives import Identifier, Timestamp


class ExperienceType(StrEnum):
    SUCCESSFUL_WORKFLOW = "successful_workflow"
    FAILED_WORKFLOW      = "failed_workflow"
    TOOL_FAILURE         = "tool_failure"
    PLUGIN_FAILURE       = "plugin_failure"
    PUBLISHING_OUTCOME   = "publishing_outcome"
    CONTENT_PERFORMANCE  = "content_performance"
    USER_PREFERENCE      = "user_preference"


class LessonCategory(StrEnum):
    TIMING        = "timing"
    TOOLING       = "tooling"
    WORKFLOW_ORDER = "workflow_order"
    CONTENT       = "content"
    ANALYTICS     = "analytics"
    USER_FEEDBACK = "user_feedback"
    RETRY_PATTERN = "retry_pattern"


@dataclass(frozen=True)
class StageOutcome:
    """Records the result of a single agent/workflow stage."""
    stage_id: str
    capability: str
    success: bool
    duration_ms: float = 0.0
    retries: int = 0
    error_summary: Optional[str] = None
    payload_keys: list[str] = field(default_factory=list)  # keys produced


@dataclass(frozen=True)
class AnalyticsSnapshot:
    """Content performance metrics captured post-publishing."""
    ctr: float = 0.0          # click-through rate
    retention: float = 0.0    # avg. watch-time %
    watch_time_s: float = 0.0 # total watch time seconds
    completion_rate: float = 0.0
    engagement_score: float = 0.0
    platform: str = "unknown"


@dataclass
class ExperienceRecord:
    """
    The complete learning record generated after a mission completes.
    Mutable so it can be enriched incrementally (e.g., analytics arrive later).
    """
    id: str = field(default_factory=lambda: f"exp_{uuid.uuid4().hex[:12]}")
    mission_id: str = ""
    mission_title: str = ""
    experience_type: ExperienceType = ExperienceType.SUCCESSFUL_WORKFLOW
    topic: str = ""
    format: str = "video"

    # Execution detail
    ordered_steps: list[str] = field(default_factory=list)
    stage_outcomes: list[StageOutcome] = field(default_factory=list)
    total_duration_ms: float = 0.0
    overall_success: bool = True
    failed_stages: list[str] = field(default_factory=list)
    retry_count: int = 0

    # Feedback
    user_feedback: Optional[str] = None
    user_rating: Optional[float] = None  # 1.0 – 5.0

    # Post-publish analytics
    analytics: Optional[AnalyticsSnapshot] = None

    # Timestamps
    created_at: str = field(default_factory=lambda: Timestamp().iso_value)


@dataclass(frozen=True)
class Lesson:
    """
    A distilled, reusable lesson extracted from one or more ExperienceRecords.
    Lessons are stored as immutable facts used to improve future planning.
    """
    id: str
    category: LessonCategory
    topic: str
    summary: str               # human-readable lesson
    recommendation: str        # actionable change for next plan
    confidence: float = 1.0   # 0.0–1.0; decays if contradicted
    source_experience_ids: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: Timestamp().iso_value)
