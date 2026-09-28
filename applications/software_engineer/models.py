"""
Data models for the Autonomous Software Engineering Framework.

Immutable records that pass between specialized agents (e.g., Analysis -> Design -> Gen -> Review).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Optional


class EngineeringPhase(StrEnum):
    ANALYSIS      = "analysis"
    DESIGN        = "design"
    GENERATION    = "generation"
    REVIEW        = "review"
    TESTING       = "testing"
    DEBUGGING     = "debugging"
    REFACTORING   = "refactoring"
    DOCUMENTATION = "documentation"
    RELEASE       = "release"


@dataclass(frozen=True, kw_only=True)
class EngineeringMissionContext:
    """Context shared across the engineering workflow."""
    mission_id: str = field(default_factory=lambda: f"eng_miss_{uuid.uuid4().hex[:8]}")
    workspace_path: str
    goal: str
    active_branch: str = "main"


@dataclass(frozen=True, kw_only=True)
class DependencyGraph:
    """Representation of project structure and dependencies."""
    modules: list[str]
    imports: dict[str, list[str]]  # module_name -> list of imported module names
    external_packages: list[str] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class RepositoryAnalysis:
    """Output from the Repository Analyzer agent."""
    dependency_graph: DependencyGraph
    primary_language: str
    detected_frameworks: list[str]
    entry_points: list[str]
    relevant_files: list[str]


@dataclass(frozen=True, kw_only=True)
class ComponentDesign:
    """A proposed component or modification."""
    component_name: str
    purpose: str
    dependencies: list[str]
    files_to_modify: list[str]
    files_to_create: list[str]


@dataclass(frozen=True, kw_only=True)
class ArchitectureDesign:
    """Output from the Architecture Designer agent."""
    components: list[ComponentDesign]
    architectural_patterns: list[str]
    potential_conflicts: list[str] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class CodeDiff:
    """A change proposed or applied to a file."""
    file_path: str
    change_type: str  # 'create', 'modify', 'delete'
    content: Optional[str] = None  # Full new content, or diff hunk
    lines_added: int = 0
    lines_removed: int = 0


@dataclass(frozen=True, kw_only=True)
class ImplementationResult:
    """Output from the Code Generator."""
    diffs: list[CodeDiff]
    files_touched: list[str]
    compile_success: bool = True
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class CodeReviewReport:
    """Output from the Code Reviewer agent."""
    approved: bool
    comments: list[str]
    duplication_detected: list[str] = field(default_factory=list)
    dead_code_detected: list[str] = field(default_factory=list)
    architecture_violations: list[str] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class TestResult:
    """Output from the Test Engineer."""
    passed: bool
    total_tests: int
    passed_tests: int
    failed_tests: int
    coverage_percent: float = 0.0
    failure_messages: list[str] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class DebugReport:
    """Output from the Debugger."""
    root_cause_analysis: str
    proposed_fix: Optional[ImplementationResult] = None
    confidence: float = 0.0


@dataclass(frozen=True, kw_only=True)
class SecurityReviewReport:
    """Output from the Security Reviewer."""
    approved: bool
    vulnerabilities: list[str]
    unsafe_operations: list[str]


@dataclass(frozen=True, kw_only=True)
class ReleaseSummary:
    """Output from the Release Manager."""
    version: str
    changelog: str
    breaking_changes: list[str] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class EngineeringReport:
    """Final output of the complete workflow."""
    mission_id: str
    success: bool
    phases_executed: list[EngineeringPhase]
    files_modified: list[str]
    final_commit_hash: Optional[str] = None
    summary: str = ""
