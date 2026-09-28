from dataclasses import dataclass, field
from enum import Enum
from typing import List

class ProviderType(Enum):
    MEMORY = "memory"
    PKI = "pki"
    WORKSPACE = "workspace"
    MISSION = "mission"
    PROJECT = "project"
    TOOL = "tool"
    CONVERSATION = "conversation"
    IDENTITY = "identity"

@dataclass
class ContextChunk:
    """A single piece of context retrieved from a provider."""
    content: str
    provider: ProviderType
    relevance_score: float = 0.0
    recency_score: float = 0.0
    importance_score: float = 0.0
    
    @property
    def total_score(self) -> float:
        """Calculate overall ranking score."""
        return (self.relevance_score * 0.5) + (self.recency_score * 0.3) + (self.importance_score * 0.2)

@dataclass
class ContextPackage:
    """The complete context payload ready for injection."""
    identity_context: str = ""
    memory_facts: List[str] = field(default_factory=list)
    pki_knowledge: List[str] = field(default_factory=list)
    active_projects: List[str] = field(default_factory=list)
    workspace_state: List[str] = field(default_factory=list)
    mission_status: List[str] = field(default_factory=list)
    tool_state: List[str] = field(default_factory=list)
    recent_conversation: List[str] = field(default_factory=list)
