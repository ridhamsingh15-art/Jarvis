import asyncio

from .dependency_graph import DependencyGraph
from .executor import WorkflowExecutor
from .monitoring import WorkflowMonitor
from .recovery import WorkflowRecovery
from .state import NodeState


class WorkflowScheduler:
    def __init__(self, executor: WorkflowExecutor, recovery: WorkflowRecovery, monitor: WorkflowMonitor):
        self.executor = executor
        self.recovery = recovery
        self.monitor = monitor

    async def run_graph(self, graph: DependencyGraph) -> None:
        while True:
            ready = graph.get_ready_nodes()
            
            # Check if done
            if not ready:
                # If any are still running or pending, we are stuck or waiting
                in_progress = any(
                    s in (NodeState.PENDING, NodeState.RUNNING) 
                    for s in graph.state.node_states.values()
                )
                if not in_progress:
                    break
                else:
                    await asyncio.sleep(0.01)
                    continue

            # Execute ready nodes in parallel
            tasks = [self.executor.execute_node(n, graph.state) for n in ready]
            await asyncio.gather(*tasks)
            
            self.recovery.checkpoint(graph.state)
            await self.monitor.log_status(graph.state)
