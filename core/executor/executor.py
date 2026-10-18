import logging
import math
from numbers import Real
from typing import Any

from core.action_safety import (
    is_known_pre_side_effect_failure,
    is_known_read_only_action,
)
from core.task import TaskStatus

from .action_registry import ActionRegistry
from .exceptions import ActionNotFoundError
from .models import ExecutionContext

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """Core translation layer binding Contexts to the Action Registry."""
    
    def __init__(self, registry: ActionRegistry):
        self._registry = registry

    def registered_actions(self) -> list[str]:
        """Expose registered capabilities without leaking mutable registry internals."""
        return self._registry.list_actions()
        
    def timeout_for_task(self, task: Any, default_timeout: float | None) -> float | None:
        """Resolve a handler timeout without reducing an explicitly larger budget."""
        if default_timeout is not None and (
            not isinstance(default_timeout, Real)
            or isinstance(default_timeout, bool)
            or not math.isfinite(default_timeout)
            or default_timeout <= 0
        ):
            raise ValueError("default_timeout must be a finite positive number or None")

        try:
            handler = self._registry.get(task.action)
        except (AttributeError, ActionNotFoundError):
            return float(default_timeout) if default_timeout is not None else None

        timeout = getattr(handler, "execution_timeout_seconds", None)
        if (
            isinstance(timeout, Real)
            and not isinstance(timeout, bool)
            and math.isfinite(timeout)
            and timeout > 0
        ):
            return max(float(timeout), float(default_timeout or 0.0))
        return float(default_timeout) if default_timeout is not None else None

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
        Only PENDING/RETRYING tasks may claim execution; duplicate calls are no-ops.
        """
        # try_start() performs the state check and transition atomically. In particular,
        # a second caller must not execute the handler or fail the first caller's task.
        if not task.try_start():
            logger.warning(
                "Skipping duplicate task execution for %s.%s in state %s",
                getattr(task, "tool", "unknown"),
                getattr(task, "action", "unknown"),
                getattr(getattr(task, "status", None), "value", getattr(task, "status", None)),
            )
            return task

        try:
            handler = self._registry.get(task.action)
        except Exception as exc:
            # Registration lookup failed before any handler was invoked, so this is a
            # known non-execution failure rather than an uncertain external side effect.
            if getattr(task, "status", None) == TaskStatus.RUNNING:
                task.fail(f"NOT EXECUTED: handler lookup failed: {type(exc).__name__}: {exc}")
            logger.exception("Task handler lookup failed for %s.%s", task.tool, task.action)
            return task

        try:
            result = handler(None, **task.args) if hasattr(task, "args") else handler(None, **task.parameters)
            task.complete(result)
        except Exception as exc:
            # Read-only operations cannot mutate external state, so their failures can
            # safely return to bounded model recovery. All other actions remain uncertain.
            if getattr(task, "status", None) == TaskStatus.RUNNING:
                if is_known_read_only_action(task.tool, task.action) or is_known_pre_side_effect_failure(
                    task.tool, task.action, str(exc)
                ):
                    task.fail(f"Execution failed: {type(exc).__name__}: {exc}")
                else:
                    task.fail(
                        "OUTCOME UNKNOWN: execution handler raised "
                        f"{type(exc).__name__}: {exc}. The handler may have crossed a "
                        "side-effect boundary; do not automatically retry until external "
                        "state is reconciled."
                    )
            logger.exception("Task execution failed for %s.%s", task.tool, task.action)
        return task
