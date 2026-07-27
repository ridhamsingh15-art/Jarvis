import time
from typing import Dict, Any, Optional

from core.models import ExecutionResult
from core.tasks import TaskDefinition

class ExecutionResultBuilder:
    """Utility to safely construct ExecutionResult models capturing runtime limits."""
    
    @staticmethod
    def success(task: TaskDefinition, output: Dict[str, Any], start_time: float) -> ExecutionResult:
        return ExecutionResult(
            success=True,
            output=output,
            error_message=None,
            execution_time_ms=int((time.time() - start_time) * 1000)
        )
        
    @staticmethod
    def failure(task: TaskDefinition, error_msg: str, start_time: float) -> ExecutionResult:
        return ExecutionResult(
            success=False,
            output={},
            error_message=error_msg,
            execution_time_ms=int((time.time() - start_time) * 1000)
        )
