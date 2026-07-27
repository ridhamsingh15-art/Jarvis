from typing import Dict, Any

from .action_registry import ActionRegistry
from .models import ExecutionContext
from .exceptions import ActionNotFoundError

class ExecutionEngine:
    """Core translation layer binding Contexts to the Action Registry."""
    
    def __init__(self, registry: ActionRegistry):
        self._registry = registry
        
    def execute_context(self, context: ExecutionContext) -> Dict[str, Any]:
        """
        Locates the action in the registry and invokes it.
        Called entirely from within the isolated try/except block of a WorkerThread.
        """
        action_name = context.task.action
        handler = self._registry.get(action_name)
        
        # The handler is expected to return a dictionary (output payload)
        # It is also expected to check context.token.is_cancelled internally if long-running
        result = handler(context, **context.task.parameters)
        
        if result is None:
            return {}
        if not isinstance(result, dict):
            raise TypeError(f"Action '{action_name}' returned a non-dict payload.")
            
        return result
