from .models import CreatorObjective, DependencyGraph, WorkflowNode, ProductionState
from .exceptions import WorkflowResolutionError

class GraphBuilder:
    """Builds a DependencyGraph from a CreatorObjective."""

    def build(self, objective: CreatorObjective) -> DependencyGraph:
        graph = DependencyGraph()
        
        # Define the nodes based on capabilities
        # We enforce a standard content factory DAG:
        # Research -> Script -> Storyboard -> Image -> Animation
        #                                  -> Voice -> 
        # (Animation & Voice) -> Editor -> Publisher -> Analytics
        
        caps = objective.required_capabilities
        
        # 1. Research
        if "web_search" in caps:
            graph.add_node(WorkflowNode(id="research", capability="web_search", description=f"Research topic: {objective.topic}"))
            
        # 2. Script
        if "script_writing" in caps:
            node = WorkflowNode(id="script", capability="script_writing", description="Write video script")
            if "web_search" in caps:
                node.dependencies.add("research")
            graph.add_node(node)
            
        # 3. Storyboard
        if "storyboarding" in caps:
            node = WorkflowNode(id="storyboard", capability="storyboarding", description="Generate storyboard panels")
            if "script_writing" in caps:
                node.dependencies.add("script")
            graph.add_node(node)
            
        # 4. Images
        if "image_generation" in caps:
            node = WorkflowNode(id="images", capability="image_generation", description="Generate visual assets")
            if "storyboarding" in caps:
                node.dependencies.add("storyboard")
            graph.add_node(node)
            
        # 5. Animation
        if "animation" in caps:
            node = WorkflowNode(id="animation", capability="animation", description="Animate visual assets")
            if "image_generation" in caps:
                node.dependencies.add("images")
            graph.add_node(node)
            
        # 6. Voice
        if "voice_generation" in caps:
            node = WorkflowNode(id="voice", capability="voice_generation", description="Generate voiceovers")
            if "script_writing" in caps:
                node.dependencies.add("script")
            graph.add_node(node)
            
        # 7. Edit
        if "video_assembly" in caps:
            node = WorkflowNode(id="edit", capability="video_assembly", description="Assemble video components")
            if "animation" in caps:
                node.dependencies.add("animation")
            if "voice_generation" in caps:
                node.dependencies.add("voice")
            graph.add_node(node)
            
        # 8. Publish
        if "publishing" in caps:
            node = WorkflowNode(id="publish", capability="publishing", description="Publish to channels")
            if "video_assembly" in caps:
                node.dependencies.add("edit")
            graph.add_node(node)
            
        # 9. Analytics
        if "analytics" in caps:
            node = WorkflowNode(id="analytics", capability="analytics", description="Track performance metrics")
            if "publishing" in caps:
                node.dependencies.add("publish")
            graph.add_node(node)
            
        # Validate graph for cycles or missing dependencies
        self._validate_graph(graph)
        
        return graph

    def _validate_graph(self, graph: DependencyGraph) -> None:
        """Ensures the DAG is valid (no cycles, all dependencies exist)."""
        for node_id, node in graph.nodes.items():
            for dep in node.dependencies:
                if dep not in graph.nodes:
                    raise WorkflowResolutionError(f"Node '{node_id}' depends on non-existent node '{dep}'")
        
        # Simple cycle check using topological sort approach
        visited = set()
        path = set()
        
        def visit(n: str):
            if n in path:
                raise WorkflowResolutionError(f"Cycle detected in workflow at node '{n}'")
            if n in visited:
                return
            path.add(n)
            for d in graph.nodes[n].dependencies:
                visit(d)
            path.remove(n)
            visited.add(n)
            
        for node_id in graph.nodes:
            visit(node_id)
