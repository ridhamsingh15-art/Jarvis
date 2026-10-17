"""
JARVIS AIOS Logging Module

A high-performance, non-blocking, structured logging system with correlation IDs
and automated secret masking, compliant with the Foundation Specification.
"""

from .context import (
    add_metadata,
    clear_context,
    get_component_name,
    get_correlation_id,
    get_metadata,
    set_component_name,
    set_correlation_id,
)
from .factory import create_logger
from .formatters import JsonFormatter, LogFormatter, TextFormatter
from .levels import LogLevel
from .logger import AsyncLogger
from .masker import LogMasker
from .sinks import ConsoleSink, FileSink, LogSink

__all__ = [
    "AsyncLogger",
    "ConsoleSink",
    "FileSink",
    "JsonFormatter",
    "LogFormatter",
    "LogLevel",
    "LogMasker",
    "LogSink",
    "TextFormatter",
    "add_metadata",
    "clear_context",
    "create_logger",
    "get_component_name",
    "get_correlation_id",
    "get_metadata",
    "set_component_name",
    "set_correlation_id"
]
