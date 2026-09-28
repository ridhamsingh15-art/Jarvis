"""
Data models for the AI Application Runtime.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Optional


class AppState(StrEnum):
    INSTALLED = "installed"
    STARTING = "starting"
    RUNNING = "running"
    SUSPENDED = "suspended"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass(frozen=True, kw_only=True)
class AppDependency:
    """A dependency required by an application."""
    name: str
    version_range: str
    type: str  # 'plugin', 'model', 'application', 'system'


@dataclass(frozen=True, kw_only=True)
class AppManifest:
    """The declared configuration of an AI application."""
    id: str
    name: str
    version: str
    description: str
    entry_point: str
    capabilities: list[str] = field(default_factory=list)
    dependencies: list[AppDependency] = field(default_factory=list)
    required_permissions: list[str] = field(default_factory=list)
    storage_requirements: dict[str, Any] = field(default_factory=dict)
    configuration_schema: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class AppStatus:
    """The runtime state of an application."""
    app_id: str
    state: AppState
    version: str
    uptime_seconds: float = 0.0
    error_message: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class InstallResult:
    """Result of an installation attempt."""
    success: bool
    app_id: Optional[str] = None
    version: Optional[str] = None
    errors: list[str] = field(default_factory=list)
    resolved_dependencies: list[str] = field(default_factory=list)
