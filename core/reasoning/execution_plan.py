from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class ExecutionPlan:
    """A strongly typed plan containing the ordered steps and required resources."""
    ordered_steps: List[str] = field(default_factory=list)
    required_context: List[str] = field(default_factory=list)
    required_tools: List[str] = field(default_factory=list)
    required_models: List[str] = field(default_factory=list)
    required_missions: List[str] = field(default_factory=list)
    fallback_strategy: str = ""
    requires_clarification: bool = False
    clarification_question: Optional[str] = None
    
    # Flags added for backwards compatibility with earlier systems and CognitiveManager routing
    requires_memory: bool = False
    requires_knowledge: bool = False
    requires_project: bool = False
