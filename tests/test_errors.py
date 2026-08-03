import sys

from core.errors import (
    ErrorCategory,
    ErrorHandler,
    ErrorSeverity,
    FatalError,
    JarvisError,
    NetworkError,
    ValidationError,
)
from core.telemetry.context import clear_context, set_component_name, set_correlation_id


def test_jarvis_error_base():
    clear_context()
    set_correlation_id("test-corr-1")
    set_component_name("TestComponent")
    
    err = JarvisError("Something went wrong", metadata={"user": "admin"})
    
    # Defaults
    assert err.category == ErrorCategory.UNKNOWN
    assert err.severity == ErrorSeverity.MEDIUM
    
    # Injected context
    assert err.correlation_id == "test-corr-1"
    assert err.component == "TestComponent"
    assert err.metadata == {"user": "admin"}
    
    # Stack Trace
    assert "test_jarvis_error_base" in err.stack_trace
    
    # Dict representation
    payload = err.to_dict()
    assert payload["error_id"] == err.error_id
    assert payload["correlation_id"] == "test-corr-1"


def test_error_hierarchy_defaults():
    val_err = ValidationError("Bad input")
    assert val_err.category == ErrorCategory.VALIDATION
    assert val_err.severity == ErrorSeverity.MEDIUM
    assert val_err.recoverable is True
    assert val_err.retryable is False
    
    net_err = NetworkError("Connection lost")
    assert net_err.category == ErrorCategory.NETWORK
    assert net_err.retryable is True
    assert net_err.recoverable is True


def test_nested_errors():
    try:
        _ = 1 / 0
    except ZeroDivisionError as e:
        root_cause = e
        
    err = FatalError("Computation failed", root_cause=root_cause)
    
    # The traceback of the inner exception should be appended
    assert "ZeroDivisionError" in err.stack_trace
    
    payload = err.to_dict()
    assert payload["root_cause"]["type"] == "ZeroDivisionError"


def test_nested_jarvis_errors():
    err1 = ValidationError("Missing field")
    err2 = FatalError("Cannot start", root_cause=err1)
    
    payload = err2.to_dict()
    assert "root_cause" in payload
    assert payload["root_cause"]["category"] == ErrorCategory.VALIDATION.value


def test_handler_integration():
    class DummyLogger:
        def __init__(self):
            self.logged_fatal = None
            self.shutdown_called = False
            
        def fatal(self, message, error):
            self.logged_fatal = error
            
        def shutdown(self):
            self.shutdown_called = True
            
    logger = DummyLogger()
    ErrorHandler.setup(logger)
    
    # Trigger unhandled
    try:
        raise ValueError("Hidden failure")
    except ValueError as e:
        ErrorHandler._unhandled_exception_handler(type(e), e, e.__traceback__)
        
    assert logger.shutdown_called is True
    assert logger.logged_fatal is not None
    assert logger.logged_fatal["category"] == ErrorCategory.FATAL.value
    assert logger.logged_fatal["root_cause"]["type"] == "ValueError"
    
    # Cleanup sys hook so we don't break pytest natively
    sys.excepthook = sys.__excepthook__
