from typing import Any

from core.task import TaskStatus

from .action_registry import ActionRegistry
from .models import ExecutionContext


class ExecutionEngine:
    """Core translation layer binding Contexts to the Action Registry."""
    
    def __init__(self, registry: ActionRegistry):
        self._registry = registry
        
    def execute_context(self, context: ExecutionContext) -> dict[str, Any]:
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

    def execute(self, task: Any) -> Any:
        """
        Backward compatibility wrapper for Agent.
        Executes a task directly in the current thread.
        """
        try:
            task.start()
            handler = self._registry.get(task.action)
            result = handler(None, **task.args) if hasattr(task, 'args') else handler(None, **task.parameters)
            task.complete(result)
        except Exception as e:  # noqa: BLE001
            # If task is still PENDING (start() failed or wasn't reached), force to RUNNING first
            if task.status == TaskStatus.PENDING:
                task.start()
            task.fail(str(e))
        return task
