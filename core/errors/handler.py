import sys
from typing import Optional, Type

from core.telemetry import AsyncLogger
from .base import JarvisError
from .hierarchy import FatalError


class ErrorHandler:
    """
    Manages global exception trapping and logger integration.
    """
    _logger: Optional[AsyncLogger] = None
    _original_excepthook = None

    @classmethod
    def setup(cls, logger: AsyncLogger) -> None:
        """
        Binds the global exception hook to capture unhandled panics,
        wrap them in a FatalError, and securely log them before exit.
        """
        cls._logger = logger
        cls._original_excepthook = sys.excepthook
        sys.excepthook = cls._unhandled_exception_handler

    @classmethod
    def _unhandled_exception_handler(
        cls, 
        exc_type: Type[BaseException], 
        exc_value: BaseException, 
        traceback_obj
    ) -> None:
        """
        The global hook for unhandled exceptions.
        """
        # If it's already a JarvisError, we just log it as Fatal.
        # Otherwise, we wrap it in a FatalError.
        if isinstance(exc_value, JarvisError):
            final_error = exc_value
            # Escalate severity for unhandled escapes
            final_error.severity = final_error.severity.CRITICAL
        else:
            final_error = FatalError(
                message=f"Unhandled exception: {exc_value}",
                root_cause=exc_value,
                metadata={"exc_type": exc_type.__name__}
            )

        if cls._logger:
            # Structurally log the fatal error payload
            # The async logger requires us to push it as metadata/kwargs,
            # but the masker will still safely sanitize it.
            cls._logger.fatal(
                message="Runtime Panic - Unhandled Exception",
                error=final_error.to_dict()
            )
            
            # Since the process is about to die, we MUST flush the queue synchronously
            cls._logger.shutdown()

        # Fallback to the original hook so standard stderr printing still works
        if cls._original_excepthook:
            cls._original_excepthook(exc_type, exc_value, traceback_obj)
