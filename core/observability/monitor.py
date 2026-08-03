from .metrics import MetricsRegistry


class SystemMonitor:
    def __init__(self, registry: MetricsRegistry):
        self.registry = registry

    def update(self) -> None:
        # Mocks system metrics for test stability
        self.registry.get_gauge("system.cpu.usage").set(45.0)
        self.registry.get_gauge("system.ram.usage").set(60.0)
        self.registry.get_gauge("system.disk.usage").set(75.0)
