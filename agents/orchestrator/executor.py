import asyncio

from .state import NodeState, WorkflowNode, WorkflowState


class WorkflowExecutor:
    async def execute_node(self, node: WorkflowNode, state: WorkflowState) -> None:
        state.node_states[node.id] = NodeState.RUNNING
        
        for attempt in range(node.retries):
            try:
                # Simulate work
                await asyncio.sleep(0.01)
                
                # Mock failure logic based on payload for testing
                if node.payload.get("simulate_fail"):
                    raise RuntimeError("Simulated failure")
                    
                state.results[node.id] = f"Result of {node.action}"
                state.node_states[node.id] = NodeState.COMPLETED
                return
            except (RuntimeError, ValueError, TypeError) as e:
                if attempt == node.retries - 1:
                    state.node_states[node.id] = NodeState.FAILED
                    state.results[node.id] = str(e)
