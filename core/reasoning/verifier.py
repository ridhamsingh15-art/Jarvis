import logging
from core.reasoning.models import VerificationResult
from core.reasoning.execution_plan import ExecutionPlan
from core.registry import Registry

logger = logging.getLogger(__name__)

class ReasoningVerifier:
    """Verifies that the ExecutionPlan is actionable (e.g. tools exist)."""
    
    def __init__(self, registry: Registry):
        self._registry = registry
        
    def verify(self, plan: ExecutionPlan) -> VerificationResult:
        """Verifies tool availability and other dependencies."""
        errors = []
        
        # Verify Tools
        available_tools = set(self._registry.list_tools())
        for req_tool in plan.required_tools:
            # Check if the requested tool exists in the registry
            if req_tool not in available_tools:
                errors.append(f"Tool '{req_tool}' is required but not available.")
                
        # (Mocking) Verify Missions
        # We would inject MissionManager here, but for now we just allow them
        
        is_valid = len(errors) == 0
        return VerificationResult(is_valid=is_valid, errors=errors)
