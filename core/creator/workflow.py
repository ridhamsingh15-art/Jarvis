from typing import List
from .models import DependencyGraph, WorkflowNode

class WorkflowCompiler:
    """Compiles a DependencyGraph into an ordered execution sequence."""

    def compile(self, graph: DependencyGraph) -> List[WorkflowNode]:
        """
        Performs a topological sort on the DependencyGraph to yield a linear 
        execution sequence where all dependencies are satisfied.
        """
        ordered: List[WorkflowNode] = []
        visited = set()
        
        # We need to visit nodes only after all their dependencies are visited
        def visit(node_id: str):
            if node_id in visited:
                return
                
            node = graph.nodes[node_id]
            for dep in node.dependencies:
                if dep not in visited:
                    visit(dep)
                    
            visited.add(node_id)
            ordered.append(node)
            
        # Iterate over all nodes to ensure disconnected components are captured
        for node_id in sorted(graph.nodes.keys()):
            if node_id not in visited:
                visit(node_id)
                
        return ordered
