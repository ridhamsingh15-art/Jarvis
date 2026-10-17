import asyncio
import builtins
import copy

from .enums import TaskState
from .interfaces import IAgent
from .models import AgentResult, AgentTask, SharedContext


class TaskDispatcher:
    """Encapsulates parallel dispatching logic and robust timeouts."""

    @staticmethod
    async def dispatch(agent: IAgent, task: AgentTask, context: SharedContext) -> AgentResult:
        """Executes a single agent task wrapping retry and timeout constraints."""
        for attempt in range(task.max_retries):
            try:
                # Wrap inside asyncio.wait_for for bounded execution
                result = await asyncio.wait_for(agent.execute(task, context), timeout=float(task.timeout))
                return result
            except asyncio.TimeoutError:
                if attempt == task.max_retries - 1:
                    return AgentResult(
                        task_id=task.id,
                        status=TaskState.FAILED,
                        metrics={"error": "ExecutionTimeoutError"}
                    )
            except Exception as e:  # noqa: BLE001
                if attempt == task.max_retries - 1:
                    return AgentResult(
                        task_id=task.id,
                        status=TaskState.FAILED,
                        metrics={"error": str(e)}
                    )
                    
        return AgentResult(
            task_id=task.id,
            status=TaskState.FAILED,
            metrics={"error": "Max retries exceeded"}
        )

    @staticmethod
    async def dispatch_parallel(
        agents: builtins.list[IAgent], 
        tasks: builtins.list[AgentTask], 
        context: SharedContext
    ) -> builtins.list[AgentResult]:
        """Executes multiple tasks concurrently."""
        if len(agents) != len(tasks):
            raise ValueError("Number of agents must match number of tasks for parallel dispatch.")
            
        coroutines = []
        for agent, task in zip(agents, tasks):
            # Give each parallel agent a copy of the immutable context snapshot to avoid ref leaks
            snapshot = copy.deepcopy(context)
            coroutines.append(TaskDispatcher.dispatch(agent, task, snapshot))
            
        results = await asyncio.gather(*coroutines, return_exceptions=True)
        
        final_results = []
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                final_results.append(AgentResult(
                    task_id=tasks[i].id,
                    status=TaskState.FAILED,
                    metrics={"error": str(res)}
                ))
            else:
                final_results.append(res)  # type: ignore
                
        return final_results
