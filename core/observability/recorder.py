import json

from .tracing import TraceContext


class ExecutionRecorder:
    def __init__(self) -> None:
        self.records: dict[str, str] = {}

    def record(self, trace: TraceContext) -> None:
        data = []
        for s in trace.spans:
            data.append({
                "id": s.id, "name": s.name, 
                "duration": s.duration, "errors": s.errors
            })
        self.records[trace.trace_id] = json.dumps(data)
