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
                # All executor tasks from the previous iteration have been awaited.
                # Any remaining PENDING/RUNNING node is therefore blocked or stale;
                # polling here would spin forever when an upstream dependency failed.
                unfinished = {
                    node_id: state
                    for node_id, state in graph.state.node_states.items()
                    if state in (NodeState.PENDING, NodeState.RUNNING)
                }
                if not unfinished:
                    break

                for node_id, state in unfinished.items():
                    if state == NodeState.PENDING:
                        blocked_by = sorted(
                            dependency
                            for dependency in graph.state.dependencies.get(node_id, set())
                            if graph.state.node_states.get(dependency) != NodeState.COMPLETED
                        )
                        reason = (
                            "Blocked by incomplete dependencies: " + ", ".join(blocked_by)
                            if blocked_by
                            else "No runnable node was available."
                        )
                    else:
                        reason = "Node remained RUNNING without an active executor task."
                    graph.state.node_states[node_id] = NodeState.FAILED
                    graph.state.results[node_id] = reason

                self.recovery.checkpoint(graph.state)
                await self.monitor.log_status(graph.state)
                continue

            # Execute ready nodes in parallel
            tasks = [self.executor.execute_node(n, graph.state) for n in ready]
            await asyncio.gather(*tasks)
            
            self.recovery.checkpoint(graph.state)
            await self.monitor.log_status(graph.state)
