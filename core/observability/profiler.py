from .tracing import TraceContext


class ExecutionProfiler:
    def profile(self, trace: TraceContext) -> dict[str, float]:
        slow_spans = {}
        for s in trace.spans:
            if s.duration and s.duration > 0.05: # Mock threshold
                slow_spans[s.name] = s.duration
        return slow_spans
