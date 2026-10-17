import time
import uuid
from contextlib import contextmanager


class Span:
    def __init__(self, name: str, trace_id: str, parent_id: str | None = None):
        self.id = uuid.uuid4().hex
        self.trace_id = trace_id
        self.parent_id = parent_id
        self.name = name
        self.start_time = time.time()
        self.end_time: float | None = None
        self.duration: float | None = None
        self.errors: list[str] = []

    def end(self) -> None:
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time

class TraceContext:
    def __init__(self) -> None:
        self.trace_id = uuid.uuid4().hex
        self.spans: list[Span] = []
        self._current_span: Span | None = None

    @contextmanager
    def span(self, name: str):
        parent = self._current_span
        s = Span(name, self.trace_id, parent.id if parent else None)
        self.spans.append(s)
        self._current_span = s
        try:
            yield s
        except Exception as e:
            s.errors.append(str(e))
            raise
        finally:
            s.end()
            self._current_span = parent
