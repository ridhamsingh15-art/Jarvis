"""
Factory for initializing the logging subsystem from the Configuration module.
"""
from typing import List, Tuple
from core.config import ConfigSnapshot
from .levels import LogLevel
from .masker import LogMasker
from .formatters import LogFormatter, JsonFormatter, TextFormatter
from .sinks import LogSink, ConsoleSink, FileSink
from .logger import AsyncLogger

def create_logger(config: ConfigSnapshot) -> AsyncLogger:
    """
    Creates and configures an AsyncLogger using the provided Configuration Snapshot.
    No hardcoded values are allowed here per Foundation specifications; everything
    is driven by the config.
    """
    
    # 1. Determine log level (default to INFO if not configured)
    level_str = config.get("log_level", "INFO")
    level = LogLevel.from_string(level_str)
    
    # 2. Setup Masker (it extracts secrets from config schema automatically)
    masker = LogMasker(config)
    
    # 3. Setup outputs (Formatters + Sinks)
    outputs: List[Tuple[LogFormatter, LogSink]] = []
    
    active_sinks = config.get("log_sinks", ["console"])
    
    if "console" in active_sinks:
        # We use TextFormatter for console by default for readability unless specified
        console_format = config.get("log_console_format", "text")
        formatter = JsonFormatter() if console_format.lower() == "json" else TextFormatter()
        outputs.append((formatter, ConsoleSink()))
        
    if "file" in active_sinks:
        # We always use JsonFormatter for files for indexing
        file_path = config.get("log_file_path", "jarvis.log")
        outputs.append((JsonFormatter(), FileSink(file_path)))
        
    # 4. Initialize the AsyncLogger
    return AsyncLogger(level, masker, outputs)
