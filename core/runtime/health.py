from typing import List, Dict, Any
from core.models import Timestamp
from .registry import RuntimeRegistry
from .models import HealthReport

class HealthMonitor:
    """Aggregates and monitors health across the Runtime."""
    
    def __init__(self, registry: RuntimeRegistry):
        self._registry = registry

    def check_health(self) -> HealthReport:
        components = self._registry.list_components()
        all_healthy = True
        component_reports = {}
        
        for comp in components:
            try:
                report = comp.health()
                component_reports[comp.metadata().name] = report.to_dict()
                if not report.is_healthy:
                    all_healthy = False
            except Exception as e:
                all_healthy = False
                component_reports[comp.metadata().name] = {
                    "is_healthy": False,
                    "status": "ERROR",
                    "details": {"exception": str(e)}
                }

        status = "HEALTHY" if all_healthy else "DEGRADED"
        
        return HealthReport(
            is_healthy=all_healthy,
            status=status,
            component_name="JARVIS_RUNTIME",
            details={"components": component_reports}
        )
