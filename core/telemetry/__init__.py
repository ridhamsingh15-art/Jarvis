"""
JARVIS AIOS Logging Module

A high-performance, non-blocking, structured logging system with correlation IDs
and automated secret masking, compliant with the Foundation Specification.
"""

from .levels import LogLevel
from .context import (
    set_correlation_id, get_correlation_id,
    set_component_name, get_component_name,
    add_metadata, get_metadata,
    clear_context
)
from .formatters import LogFormatter, JsonFormatter, TextFormatter
from .sinks import LogSink, ConsoleSink, FileSink
from .masker import LogMasker
from .logger import AsyncLogger
from .factory import create_logger

__all__ = [
    "LogLevel",
    "set_correlation_id", "get_correlation_id",
    "set_component_name", "get_component_name",
    "add_metadata", "get_metadata", "clear_context",
    "LogFormatter", "JsonFormatter", "TextFormatter",
    "LogSink", "ConsoleSink", "FileSink",
    "LogMasker",
    "AsyncLogger",
    "create_logger"
]
