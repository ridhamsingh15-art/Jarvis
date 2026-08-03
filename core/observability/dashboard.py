from .metrics import MetricsRegistry


class ObservabilityDashboard:
    def __init__(self, registry: MetricsRegistry):
        self.registry = registry

    def render(self) -> dict[str, float]:
        return {
            name: gauge.value for name, gauge in self.registry.gauges.items()
        }
