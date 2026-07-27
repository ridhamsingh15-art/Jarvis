from typing import Dict, List, Set
from collections import defaultdict, deque
import threading

from .exceptions import CyclicDependencyError

class DependencyGraph:
    """Thread-safe DAG implementation for tracking Task dependencies within a Workflow."""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._nodes: Set[str] = set()
        self._adj: Dict[str, Set[str]] = defaultdict(set) # task -> tasks it depends on (outgoing edges to prerequisites)
        self._rev_adj: Dict[str, Set[str]] = defaultdict(set) # prerequisite -> tasks depending on it
        
    def add_task(self, task_id: str) -> None:
        with self._lock:
            self._nodes.add(task_id)
            
    def remove_task(self, task_id: str) -> None:
        with self._lock:
            if task_id in self._nodes:
                self._nodes.remove(task_id)
            if task_id in self._adj:
                for prereq in self._adj[task_id]:
                    self._rev_adj[prereq].discard(task_id)
                del self._adj[task_id]
            if task_id in self._rev_adj:
                for dependent in self._rev_adj[task_id]:
                    self._adj[dependent].discard(task_id)
                del self._rev_adj[task_id]

    def add_dependency(self, task_id: str, depends_on_id: str) -> None:
        """Adds a dependency where task_id cannot run until depends_on_id completes."""
        with self._lock:
            self._nodes.add(task_id)
            self._nodes.add(depends_on_id)
            self._adj[task_id].add(depends_on_id)
            self._rev_adj[depends_on_id].add(task_id)
            
        # Optional: could check cycle immediately here, but keeping it explicit below
            
    def remove_dependency(self, task_id: str, depends_on_id: str) -> None:
        with self._lock:
            if task_id in self._adj:
                self._adj[task_id].discard(depends_on_id)
            if depends_on_id in self._rev_adj:
                self._rev_adj[depends_on_id].discard(task_id)
                
    def detect_cycles(self) -> bool:
        """Returns True if a cycle is detected, False otherwise."""
        with self._lock:
            # We use Kahn's algorithm or DFS for cycle detection. Kahn's is easy.
            in_degree = {node: 0 for node in self._nodes}
            for node in self._nodes:
                in_degree[node] = len(self._adj[node])
                
            queue = deque([n for n in self._nodes if in_degree[n] == 0])
            visited_count = 0
            
            while queue:
                current = queue.popleft()
                visited_count += 1
                
                # For every node that depends on current
                for dependent in self._rev_adj.get(current, set()):
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)
                        
            return visited_count != len(self._nodes)
            
    def topological_sort(self) -> List[str]:
        """Returns a valid execution order. Raises CyclicDependencyError if graph has a cycle."""
        with self._lock:
            in_degree = {node: 0 for node in self._nodes}
            for node in self._nodes:
                in_degree[node] = len(self._adj[node])
                
            queue = deque([n for n in self._nodes if in_degree[n] == 0])
            order = []
            
            # Sort queue strings just to make output deterministic for tests if there's a tie
            while queue:
                # To ensure determinism, we sort the available queue items
                available = sorted(list(queue))
                queue.clear()
                
                for current in available:
                    order.append(current)
                    for dependent in self._rev_adj.get(current, set()):
                        in_degree[dependent] -= 1
                        if in_degree[dependent] == 0:
                            queue.append(dependent)
                            
            if len(order) != len(self._nodes):
                raise CyclicDependencyError("Cyclic dependency detected, topological sort not possible.")
                
            return order
