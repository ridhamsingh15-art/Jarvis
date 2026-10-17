from .tracing import TraceContext


class PerformanceAnalyzer:
    def __init__(self) -> None:
        pass

    def evaluate_latency(self, trace: TraceContext) -> dict[str, str]:
        results = {}
        for s in trace.spans:
            if "llm" in s.name.lower() and s.duration and s.duration > 1.0:
                results[s.name] = "SLOW_LLM"
            elif "vision" in s.name.lower() and s.duration and s.duration > 0.5:
                results[s.name] = "SLOW_VISION"
        return results
