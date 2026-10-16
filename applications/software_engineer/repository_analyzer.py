"""Repository Analyzer Agent.

Understands repository structure, builds dependency graphs, and locates relevant modules.
"""
from __future__ import annotations

import ast
import logging
import os
import re
from pathlib import Path

from .models import DependencyGraph, RepositoryAnalysis

logger = logging.getLogger(__name__)
_SKIPPED_DIRECTORY_NAMES = frozenset(
    {".git", ".venv", "venv", "env", "__pycache__", ".pytest_cache", ".mypy_cache"}
)
_REQUIREMENT_NAME = re.compile(r"^([A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)")


class RepositoryAnalyzer:
    """Agent that analyzes the repository structure and dependencies."""

    def __init__(self, workspace_path: str):
        self._workspace_path = str(Path(workspace_path).expanduser().resolve())

    def analyze(self) -> RepositoryAnalysis:
        """Perform a repository analysis; skip only known generated/environment trees."""
        logger.info("Analyzing repository at %s", self._workspace_path)

        modules: list[str] = []
        imports: dict[str, list[str]] = {}
        entry_points: list[str] = []

        for root, directories, files in os.walk(self._workspace_path):
            # Compare individual directory names: a substring check for '.git'
            # accidentally excluded the normal '.github' directory too.
            directories[:] = [
                name for name in directories if name.casefold() not in _SKIPPED_DIRECTORY_NAMES
            ]

            for filename in files:
                if not filename.endswith(".py"):
                    continue
                full_path = Path(root) / filename
                relative_path = os.path.relpath(full_path, self._workspace_path)
                modules.append(relative_path)

                try:
                    content = full_path.read_text(encoding="utf-8")
                    tree = ast.parse(content, filename=relative_path)
                except SyntaxError as exc:
                    logger.warning(
                        "Syntax error while parsing %s at line %s",
                        relative_path,
                        exc.lineno or "unknown",
                    )
                    continue
                except (OSError, UnicodeError, ValueError, RecursionError) as exc:
                    # Skip the affected source file, but leave an actionable diagnostic.
                    logger.warning(
                        "Could not analyze repository file %s (%s)",
                        relative_path,
                        type(exc).__name__,
                    )
                    continue

                file_imports: list[str] = []
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        file_imports.extend(alias.name for alias in node.names)
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        file_imports.append(node.module)
                imports[relative_path] = file_imports

                if any(
                    isinstance(node, ast.If)
                    and isinstance(node.test, ast.Compare)
                    and isinstance(node.test.left, ast.Name)
                    and node.test.left.id == "__name__"
                    and node.test.ops
                    and isinstance(node.test.ops[0], ast.Eq)
                    and any(
                        isinstance(comparator, ast.Constant)
                        and comparator.value == "__main__"
                        for comparator in node.test.comparators
                    )
                    for node in ast.walk(tree)
                ):
                    entry_points.append(relative_path)

        graph = DependencyGraph(
            modules=modules,
            imports=imports,
            external_packages=self._detect_external_packages(),
        )
        return RepositoryAnalysis(
            dependency_graph=graph,
            primary_language="Python",
            detected_frameworks=[],
            entry_points=entry_points,
            relevant_files=modules[:10],
        )

    def _detect_external_packages(self) -> list[str]:
        """Read package names from requirements.txt without treating options as packages."""
        requirements_path = Path(self._workspace_path) / "requirements.txt"
        if not requirements_path.is_file():
            return []

        packages: list[str] = []
        try:
            with requirements_path.open("r", encoding="utf-8") as requirements_file:
                for line_number, raw_line in enumerate(requirements_file, start=1):
                    line = raw_line.split("#", maxsplit=1)[0].strip()
                    if not line or line.startswith("-"):
                        continue
                    if line.casefold().startswith(("git+", "http://", "https://", "file:")):
                        continue
                    # Reject malformed names rather than reporting a prefix such as
                    # 'invalid' from the invalid requirement 'invalid package name'.
                    if re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]*\s+\S", line):
                        logger.warning("Ignoring malformed requirement entry at line %d", line_number)
                        continue
                    match = _REQUIREMENT_NAME.match(line)
                    if match is None:
                        logger.warning(
                            "Ignoring malformed requirement entry at line %d",
                            line_number,
                        )
                        continue
                    packages.append(match.group(1))
        except (OSError, UnicodeError) as exc:
            logger.warning(
                "Could not read requirements.txt (%s)",
                type(exc).__name__,
            )
            return []

        return packages
