"""
Core Logger implementation.
Provides an AsyncLogger that queues log events and processes them in a background thread
to guarantee <1ms overhead on application threads.
"""
import time
import queue
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .levels import LogLevel
from .context import get_correlation_id, get_component_name, get_metadata
from .masker import LogMasker
from .formatters import LogFormatter
from .sinks import LogSink


class AsyncLogger:
    """
    Non-blocking, thread-safe logger.
    """
    def __init__(self, 
                 level: LogLevel, 
                 masker: LogMasker, 
                 outputs: List[Tuple[LogFormatter, LogSink]],
                 max_queue_size: int = 10000):
        self.level = level
        self._masker = masker
        self._outputs = outputs
        
        # Bounded queue to prevent OOM in catastrophic scenarios
        self._queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self._shutdown_event = threading.Event()
        
        # Start the background dispatcher thread
        self._thread = threading.Thread(target=self._dispatch_loop, name="Jarvis-Logger-Thread", daemon=True)
        self._thread.start()

    def debug(self, message: str, **kwargs: Any) -> None:
        self._log(LogLevel.DEBUG, message, kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        self._log(LogLevel.INFO, message, kwargs)

    def warn(self, message: str, **kwargs: Any) -> None:
        self._log(LogLevel.WARN, message, kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        self._log(LogLevel.ERROR, message, kwargs)

    def fatal(self, message: str, **kwargs: Any) -> None:
        self._log(LogLevel.FATAL, message, kwargs)

    def _log(self, level: LogLevel, message: str, kwargs: Dict[str, Any]) -> None:
        """
        Constructs the log record and queues it.
        Execution must remain strictly <1ms.
        """
        if level.value < self.level.value:
            return

        # Capture context immediately
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level.name,
            "component": get_component_name(),
            "correlation_id": get_correlation_id(),
            "message": message,
            "metadata": {**get_metadata(), **kwargs}
        }

        try:
            # Non-blocking put. If full, we drop the log (Fail Safe philosophy).
            self._queue.put_nowait(record)
        except queue.Full:
            # We cannot log that the queue is full without blocking or recurring, 
            # so we silently drop. In a real system, we might increment an atomic counter.
            pass

    def _dispatch_loop(self) -> None:
        """
        Background loop running on a dedicated thread.
        Pulls logs, formats, masks, and writes them to sinks.
        """
        while not self._shutdown_event.is_set() or not self._queue.empty():
            try:
                # 100ms timeout allows the loop to check shutdown_event periodically
                record = self._queue.get(timeout=0.1)
                
                # Apply secret masking
                masked_record = self._masker.mask(record)
                
                # Write to all outputs
                for formatter, sink in self._outputs:
                    formatted_msg = formatter.format(masked_record)
                    sink.write(formatted_msg)
                    
                self._queue.task_done()
            except queue.Empty:
                continue
            except Exception:
                # Catch-all to prevent the dispatcher thread from ever crashing
                pass

    def shutdown(self) -> None:
        """
        Gracefully shuts down the logger, flushing remaining queued items.
        """
        self._shutdown_event.set()
        # Wait up to 2 seconds for the queue to flush
        self._thread.join(timeout=2.0)
        
        # Close all sinks
        for _, sink in self._outputs:
            sink.close()
