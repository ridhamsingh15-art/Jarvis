"""
Repository Analyzer Agent.

Understands repository structure, builds dependency graphs, and locates relevant modules.
"""
import ast
import os
import logging
from typing import Optional
from .models import RepositoryAnalysis, DependencyGraph

logger = logging.getLogger(__name__)

class RepositoryAnalyzer:
    """Agent that analyzes the repository structure and dependencies."""

    def __init__(self, workspace_path: str):
        self._workspace_path = workspace_path

    def analyze(self) -> RepositoryAnalysis:
        """Perform a full analysis of the repository."""
        logger.info(f"Analyzing repository at {self._workspace_path}...")
        
        modules = []
        imports = {}
        entry_points = []
        
        # Simple walk to find python files
        for root, _, files in os.walk(self._workspace_path):
            if ".git" in root or ".venv" in root or "__pycache__" in root:
                continue
                
            for file in files:
                if file.endswith(".py"):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, self._workspace_path)
                    modules.append(rel_path)
                    
                    # Parse AST for imports
                    try:
                        with open(full_path, "r", encoding="utf-8") as f:
                            content = f.read()
                        
                        tree = ast.parse(content, filename=rel_path)
                        file_imports = []
                        for node in ast.walk(tree):
                            if isinstance(node, ast.Import):
                                for alias in node.names:
                                    file_imports.append(alias.name)
                            elif isinstance(node, ast.ImportFrom) and node.module:
                                file_imports.append(node.module)
                        
                        imports[rel_path] = file_imports
                        
                        # Detect entry points (if __name__ == "__main__")
                        if 'if __name__ == "__main__":' in content or 'if __name__ == \'__main__\':' in content:
                            entry_points.append(rel_path)
                            
                    except SyntaxError:
                        logger.warning(f"Syntax error while parsing {rel_path}")
                    except Exception as e:
                        logger.warning(f"Error parsing {rel_path}: {e}")

        graph = DependencyGraph(
            modules=modules,
            imports=imports,
            external_packages=self._detect_external_packages()
        )
        
        return RepositoryAnalysis(
            dependency_graph=graph,
            primary_language="Python", # Hardcoded heuristic for now
            detected_frameworks=[],
            entry_points=entry_points,
            relevant_files=modules[:10] # For a real agent, this would be filtered by the specific goal
        )

    def _detect_external_packages(self) -> list[str]:
        req_path = os.path.join(self._workspace_path, "requirements.txt")
        if os.path.exists(req_path):
            try:
                with open(req_path, "r", encoding="utf-8") as f:
                    return [line.strip().split("==")[0] for line in f if line.strip() and not line.startswith("#")]
            except Exception:
                pass
        return []
