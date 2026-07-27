from .base import JarvisError
from .enums import ErrorCategory, ErrorSeverity


class ValidationError(JarvisError):
    category = ErrorCategory.VALIDATION
    severity = ErrorSeverity.MEDIUM
    retryable = False
    recoverable = True


class ConfigurationError(JarvisError):
    category = ErrorCategory.CONFIGURATION
    severity = ErrorSeverity.CRITICAL
    retryable = False
    recoverable = False


class SecurityError(JarvisError):
    category = ErrorCategory.SECURITY
    severity = ErrorSeverity.HIGH
    retryable = False
    recoverable = False


class PermissionError(JarvisError):
    category = ErrorCategory.PERMISSION
    severity = ErrorSeverity.MEDIUM
    retryable = False
    recoverable = True


class NetworkError(JarvisError):
    category = ErrorCategory.NETWORK
    severity = ErrorSeverity.MEDIUM
    retryable = True
    recoverable = True


class ProviderError(JarvisError):
    category = ErrorCategory.PROVIDER
    severity = ErrorSeverity.HIGH
    retryable = True
    recoverable = True


class TimeoutError(JarvisError):
    category = ErrorCategory.TIMEOUT
    severity = ErrorSeverity.MEDIUM
    retryable = True
    recoverable = True


class WorkflowError(JarvisError):
    category = ErrorCategory.WORKFLOW
    severity = ErrorSeverity.HIGH
    retryable = False
    recoverable = False


class MemoryError(JarvisError):
    category = ErrorCategory.MEMORY
    severity = ErrorSeverity.HIGH
    retryable = False
    recoverable = False


class ToolError(JarvisError):
    category = ErrorCategory.TOOL
    severity = ErrorSeverity.MEDIUM
    retryable = False
    recoverable = True


class PluginError(JarvisError):
    category = ErrorCategory.PLUGIN
    severity = ErrorSeverity.HIGH
    retryable = False
    recoverable = True


class InternalError(JarvisError):
    category = ErrorCategory.INTERNAL
    severity = ErrorSeverity.CRITICAL
    retryable = False
    recoverable = False


class FatalError(JarvisError):
    category = ErrorCategory.FATAL
    severity = ErrorSeverity.CRITICAL
    retryable = False
    recoverable = False


class TransientError(JarvisError):
    category = ErrorCategory.TRANSIENT
    severity = ErrorSeverity.LOW
    retryable = True
    recoverable = True
