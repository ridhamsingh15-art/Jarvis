"""
ExecutionPolicy — mandatory gate between any capability source and the Executor.

Architecture:
    LLM / Plugin / MCP / Skill
        ↓
    ExecutionPolicy.check()   ← enforcement lives here
        ↓
    Validator
        ↓
    Executor

Rules:
  - UNKNOWN capability → DENY
  - Destructive capability → DENY (or require explicit confirmation)
  - Untrusted source (plugin/MCP) → restricted set only
  - All denials are logged with reason

This module intentionally has NO dependency on the LLM or any network call.
Security boundaries must be structural, not prompt-based.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Source trust levels
# ---------------------------------------------------------------------------


class CapabilitySource(StrEnum):
    """Where the capability request originated from."""
    CORE = "core"           # First-party JARVIS routing
    PLUGIN = "plugin"       # Third-party plugin
    MCP = "mcp"             # External MCP tool server
    SKILL = "skill"         # JARVIS skill file


class PolicyVerdict(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_CONFIRMATION = "require_confirmation"


# ---------------------------------------------------------------------------
# Capability risk classification
# ---------------------------------------------------------------------------

# Tools that are always safe to execute without extra scrutiny.
_SAFE_TOOLS: frozenset[str] = frozenset({
    "system",
    "browser",
    "windows",
    "file",
    "shell",   # shell is allowed but only through safe command allowlist
})

# Actions (tool.action) that are classified as HIGH RISK.
# These require DENY for untrusted sources; REQUIRE_CONFIRMATION for core.
_HIGH_RISK_ACTIONS: frozenset[str] = frozenset({
    # File destruction
    "delete_file",
    "delete_dir",
    "overwrite_file",
    "format_disk",
    # System
    "shutdown",
    "reboot",
    "restart",
    # Registry / credentials
    "write_registry",
    "read_credentials",
    "escalate_privilege",
    # Shell high-risk
    "shell_run",       # only the restricted ShellTool.run is safe
    # Downloads / arbitrary execution
    "download_and_execute",
    "install_package",
})


# ---------------------------------------------------------------------------
# Policy context
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PolicyContext:
    """Carries information about the execution request for policy evaluation."""
    tool: str
    action: str
    source: CapabilitySource = CapabilitySource.CORE
    source_id: str = "jarvis"    # plugin_id / mcp_server_id / skill_id
    user_confirmed: bool = False  # True when the user explicitly approved


# ---------------------------------------------------------------------------
# PolicyResult
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PolicyResult:
    verdict: PolicyVerdict
    reason: str
    context: PolicyContext


# ---------------------------------------------------------------------------
# ExecutionPolicy
# ---------------------------------------------------------------------------


class ExecutionPolicy:
    """
    Enforces execution policy for all capability sources.

    Usage::

        policy = ExecutionPolicy()
        result = policy.check(PolicyContext(tool="file", action="delete_file", source=CapabilitySource.PLUGIN))
        if result.verdict != PolicyVerdict.ALLOW:
            raise PolicyDeniedError(result.reason)
    """

    def __init__(
        self,
        allow_destructive_from_core: bool = False,
        restricted_plugin_tools: frozenset[str] | None = None,
        restricted_mcp_tools: frozenset[str] | None = None,
    ) -> None:
        """
        Args:
            allow_destructive_from_core: If True, destructive actions from CORE
                source emit REQUIRE_CONFIRMATION instead of DENY. Disabled by
                default (safest posture).
            restricted_plugin_tools: Set of tool names plugins are allowed to invoke.
                Defaults to {"system", "browser"}.
            restricted_mcp_tools: Set of tool names MCP servers are allowed to invoke.
                Defaults to {"system", "browser"}.
        """
        self._allow_destructive_from_core = allow_destructive_from_core
        self._restricted_plugin_tools: frozenset[str] = restricted_plugin_tools or frozenset({"system", "browser"})
        self._restricted_mcp_tools: frozenset[str] = restricted_mcp_tools or frozenset({"system", "browser"})

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self, ctx: PolicyContext) -> PolicyResult:
        """
        Evaluate whether the requested capability should be allowed.

        Returns:
            PolicyResult with verdict ALLOW, DENY, or REQUIRE_CONFIRMATION.
        """
        tool_action = f"{ctx.tool}.{ctx.action}"

        # 1. Unknown tool → DENY
        if ctx.tool not in _SAFE_TOOLS:
            return self._deny(ctx, f"Unknown tool '{ctx.tool}' — only registered tools are permitted")

        # 2. Source-specific restrictions
        if ctx.source == CapabilitySource.PLUGIN:
            if ctx.tool not in self._restricted_plugin_tools:
                return self._deny(
                    ctx,
                    f"Plugin '{ctx.source_id}' may not invoke tool '{ctx.tool}'. "
                    f"Permitted plugin tools: {sorted(self._restricted_plugin_tools)}",
                )

        if ctx.source == CapabilitySource.MCP:
            if ctx.tool not in self._restricted_mcp_tools:
                return self._deny(
                    ctx,
                    f"MCP server '{ctx.source_id}' may not invoke tool '{ctx.tool}'. "
                    f"Permitted MCP tools: {sorted(self._restricted_mcp_tools)}",
                )

        # 3. High-risk action check
        if ctx.action in _HIGH_RISK_ACTIONS:
            # Untrusted source always denied
            if ctx.source in (CapabilitySource.PLUGIN, CapabilitySource.MCP):
                return self._deny(
                    ctx,
                    f"High-risk action '{ctx.action}' is not permitted from source '{ctx.source}'",
                )
            # Core source: confirmation required unless pre-confirmed or policy allows
            if ctx.source == CapabilitySource.CORE:
                if ctx.user_confirmed:
                    return self._allow(ctx, f"High-risk action '{ctx.action}' approved by user")
                if self._allow_destructive_from_core:
                    return PolicyResult(
                        verdict=PolicyVerdict.REQUIRE_CONFIRMATION,
                        reason=f"High-risk action '{ctx.action}' requires user confirmation",
                        context=ctx,
                    )
                return self._deny(
                    ctx,
                    f"High-risk action '{ctx.action}' is denied. "
                    "Set allow_destructive_from_core=True and obtain user_confirmed=True to proceed.",
                )

        # 4. All other checks pass → ALLOW
        return self._allow(ctx, f"Capability '{tool_action}' allowed from source '{ctx.source}'")

    def enforce(self, ctx: PolicyContext) -> None:
        """
        Like check() but raises PolicyDeniedError on DENY.

        Raises:
            PolicyDeniedError: If the policy verdict is DENY.
        """
        result = self.check(ctx)
        if result.verdict == PolicyVerdict.DENY:
            raise PolicyDeniedError(result.reason, context=ctx)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _allow(ctx: PolicyContext, reason: str) -> PolicyResult:
        logger.debug("[POLICY] ALLOW %s.%s (source=%s): %s", ctx.tool, ctx.action, ctx.source, reason)
        return PolicyResult(verdict=PolicyVerdict.ALLOW, reason=reason, context=ctx)

    @staticmethod
    def _deny(ctx: PolicyContext, reason: str) -> PolicyResult:
        logger.warning("[POLICY] DENY %s.%s (source=%s id=%s): %s", ctx.tool, ctx.action, ctx.source, ctx.source_id, reason)
        return PolicyResult(verdict=PolicyVerdict.DENY, reason=reason, context=ctx)


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class PolicyDeniedError(Exception):
    """Raised when ExecutionPolicy.enforce() produces a DENY verdict."""

    def __init__(self, reason: str, context: PolicyContext | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.context = context
