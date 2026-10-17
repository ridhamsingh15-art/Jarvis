import json

from .recorder import ExecutionRecorder


class ExecutionReplay:
    def __init__(self, recorder: ExecutionRecorder):
        self.recorder = recorder

    def replay(self, trace_id: str) -> list[dict]:
        data = self.recorder.records.get(trace_id)
        if not data:
            return []
        return json.loads(data)
