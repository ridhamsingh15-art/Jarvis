from .dependency_graph import DependencyGraph
from .workflow_builder import WorkflowBuilder


class OrchestratorPlanner:
    def plan(self, goal: str) -> DependencyGraph:
        builder = WorkflowBuilder(workflow_id="auto_plan")
        # Generate mock workflow for a goal
        n1 = builder.add_task("research")
        n2 = builder.add_task("code", deps=[n1])
        builder.add_task("test", deps=[n2])
        return builder.build()
