from .tracing import TraceContext


class TelemetryAnalyzer:
    def analyze(self, trace: TraceContext) -> dict[str, int]:
        errors = sum(len(s.errors) for s in trace.spans)
        return {"total_spans": len(trace.spans), "total_errors": errors}
