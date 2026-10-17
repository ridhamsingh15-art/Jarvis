import dataclasses
from typing import Any


@dataclasses.dataclass
class DialogueState:
    """Tracks the state of the conversation across turns."""
    
    # If the system asked a question, what was it? (e.g. 'user_name')
    pending_question: str | None = None
    
    # What tool was invoked last in the conversation?
    last_tool_invoked: str | None = None
    
    # What is the current long-term goal of the conversation?
    conversation_goal: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)
    
    def clear_pending(self) -> None:
        self.pending_question = None

