from enum import Enum


class ErrorCategory(str, Enum):
    """
    Standardized categorizations for all JARVIS AIOS faults.
    """
    VALIDATION = "VALIDATION"
    CONFIGURATION = "CONFIGURATION"
    SECURITY = "SECURITY"
    PERMISSION = "PERMISSION"
    NETWORK = "NETWORK"
    PROVIDER = "PROVIDER"
    TIMEOUT = "TIMEOUT"
    WORKFLOW = "WORKFLOW"
    MEMORY = "MEMORY"
    TOOL = "TOOL"
    PLUGIN = "PLUGIN"
    INTERNAL = "INTERNAL"
    FATAL = "FATAL"
    TRANSIENT = "TRANSIENT"
    PERMANENT = "PERMANENT"
    UNKNOWN = "UNKNOWN"


class ErrorSeverity(str, Enum):
    """
    Severity levels governing failure responses.
    """
    CRITICAL = "CRITICAL"   # Requires immediate termination or global fallback
    HIGH = "HIGH"           # Subsystem failure, workflow termination
    MEDIUM = "MEDIUM"       # Task failure, possible retry
    LOW = "LOW"             # Degradation of service, recoverable
