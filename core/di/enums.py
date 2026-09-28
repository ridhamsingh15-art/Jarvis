from enum import Enum, auto


class ServiceLifetime(Enum):
    """
    Defines the lifetime of a registered service in the DI Container.
    """
    SINGLETON = auto()  # One instance per container
    SCOPED = auto()     # One instance per scope
    TRANSIENT = auto()  # New instance per resolution
