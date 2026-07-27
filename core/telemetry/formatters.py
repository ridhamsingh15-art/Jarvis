import json
from abc import ABC, abstractmethod
from typing import Any, Dict


class LogFormatter(ABC):
    """
    Abstract interface for log formatters.
    Converts a structured log dictionary into a string.
    """
    @abstractmethod
    def format(self, log_record: Dict[str, Any]) -> str:
        pass


class JsonFormatter(LogFormatter):
    """
    Formats log records as JSON strings. Highly suitable for parsing and indexing.
    """
    def format(self, log_record: Dict[str, Any]) -> str:
        try:
            return json.dumps(log_record, default=str)
        except Exception as e:
            # Fallback for un-serializable objects (fail-safe)
            return json.dumps({"error": "Failed to serialize log record", "reason": str(e)})


class TextFormatter(LogFormatter):
    """
    Formats log records as human-readable text. Suitable for local console output.
    Format: [TIMESTAMP] [LEVEL] [COMPONENT] (CorrID: X) Message | Metadata
    """
    def format(self, log_record: Dict[str, Any]) -> str:
        timestamp = log_record.get("timestamp", "")
        level = log_record.get("level", "UNKNOWN")
        component = log_record.get("component", "System")
        message = log_record.get("message", "")
        corr_id = log_record.get("correlation_id")
        
        corr_str = f"(CorrID: {corr_id}) " if corr_id else ""
        
        metadata = log_record.get("metadata", {})
        meta_str = ""
        if metadata:
            meta_str = " | " + " ".join(f"{k}={v}" for k, v in metadata.items())
            
        return f"[{timestamp}] [{level:5}] [{component}] {corr_str}{message}{meta_str}"
