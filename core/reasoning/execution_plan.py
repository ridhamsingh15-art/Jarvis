from dataclasses import dataclass, field


@dataclass
class ExecutionPlan:
    """A strongly typed plan containing the ordered steps and required resources."""
    ordered_steps: list[str] = field(default_factory=list)
    required_context: list[str] = field(default_factory=list)
    required_tools: list[str] = field(default_factory=list)
    required_models: list[str] = field(default_factory=list)
    required_missions: list[str] = field(default_factory=list)
    fallback_strategy: str = ""
    requires_clarification: bool = False
    clarification_question: str | None = None
    
    # Flags added for backwards compatibility with earlier systems and CognitiveManager routing
    requires_memory: bool = False
    requires_knowledge: bool = False
    requires_project: bool = False
