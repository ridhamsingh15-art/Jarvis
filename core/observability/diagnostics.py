from .metrics import MetricsRegistry


class DiagnosticScanner:
    def __init__(self, registry: MetricsRegistry):
        self.registry = registry

    def scan(self) -> list[str]:
        issues = []
        ram = self.registry.get_gauge("system.ram.usage").value
        if ram > 90.0:
            issues.append("High RAM usage detected.")
        return issues
