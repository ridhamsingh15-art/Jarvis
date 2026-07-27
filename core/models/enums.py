from enum import Enum, auto

class ExecutionState(str, Enum):
    """Lifecycle state of a task, command, or execution unit."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class Capability(str, Enum):
    """Broad capabilities granted to or required by subsystems."""
    READ = "READ"
    WRITE = "WRITE"
    EXECUTE = "EXECUTE"
    NETWORK_ACCESS = "NETWORK_ACCESS"
    FILE_ACCESS = "FILE_ACCESS"

class Permission(str, Enum):
    """Specific permission boundaries."""
    ADMIN = "ADMIN"
    USER = "USER"
    GUEST = "GUEST"
    SYSTEM = "SYSTEM"
