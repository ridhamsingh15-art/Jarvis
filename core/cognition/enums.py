from enum import Enum, auto


class IntentType(Enum):
    CHAT = auto()
    QUESTION = auto()
    SIMPLE_ACTION = auto()
    COMPLEX_GOAL = auto()
    LEARN = auto()
    UNKNOWN = auto()

class DecisionType(Enum):
    DIRECT_RESPONSE = auto()
    EXECUTE_ACTION = auto()
    CREATE_PLAN = auto()
    ASK_CLARIFICATION = auto()
