from dataclasses import dataclass, field
from enum import Enum
from typing import Any

class GoalType(Enum):
    QUESTION = "question"
    CONVERSATION = "conversation"
    TASK = "task"
    RESEARCH = "research"
    CODING = "coding"
    AUTOMATION = "automation"
    CREATIVE = "creative"
    LONG_RUNNING_PROJECT = "long_running_project"

class Complexity(Enum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"
    VERY_COMPLEX = "very_complex"

@dataclass
class ExecutionStrategy:
    """The master plan for how JARVIS will handle a user request."""
    goal: GoalType
    complexity: Complexity
    selected_model: str | None = None
    requires_memory: bool = False
    requires_knowledge: bool = False
    requires_tools: bool = False
    requires_mission: bool = False
    requires_planning: bool = False
    requires_clarification: bool = False
    clarification_question: str | None = None
    response_mode: str = "immediate"  # "immediate" or "background"
    inference_requirements: Any = None
