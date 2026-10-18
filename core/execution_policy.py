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
import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
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
    "shell",        # shell is allowed but only through safe command allowlist
    "automation",   # automation integration
    "publishing",   # publishing integration
    "codex_desktop",  # guarded visual desktop agent; its own MCP layer prompts for each state-changing action
})

# Actions (tool.action) that are classified as HIGH RISK.
# These require DENY for untrusted sources; REQUIRE_CONFIRMATION for core.
_HIGH_RISK_ACTIONS: frozenset[str] = frozenset({
    # File destruction
    "delete",
    "delete_file",
    "delete_dir",
    "overwrite_file",
    "patch_file",
    "edit_file",
    "rename",
    "move",
    "copy",
    "append_line",      # durable filesystem side effect; explicit approval required
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
    # Automation & external publishing
    "execute_workflow",
    "publish",
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
    request_id: str = ""
    args: dict[str, Any] = field(default_factory=dict)


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
        registered_tools: frozenset[str] | None = None,
        workspace_root: str | Path | None = None,
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
            registered_tools: Additional explicitly registered core tool names. Actions from
                these tools require per-mission user confirmation by default; the registry alone
                does not make their side effects trusted.
            workspace_root: The same filesystem boundary used by the configured FileTool.
                Relative write paths are resolved against this root before checking whether a
                write would overwrite an existing file. This value must come from trusted
                runtime configuration, never from model-controlled tool arguments.
        """
        self._allow_destructive_from_core = allow_destructive_from_core
        self._workspace_root = (
            Path(workspace_root).expanduser().resolve()
            if workspace_root is not None
            else None
        )
        self._restricted_plugin_tools: frozenset[str] = (
            restricted_plugin_tools
            if restricted_plugin_tools is not None
            else frozenset({"system", "browser"})
        )
        self._restricted_mcp_tools: frozenset[str] = (
            restricted_mcp_tools
            if restricted_mcp_tools is not None
            else frozenset({"system", "browser"})
        )
        self._registered_tools: frozenset[str] = registered_tools or frozenset()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def with_registered_tools(self, tool_names: frozenset[str]) -> ExecutionPolicy:
        """Return a policy copy that recognizes explicit registry additions but confirmation-gates them."""
        return ExecutionPolicy(
            allow_destructive_from_core=self._allow_destructive_from_core,
            restricted_plugin_tools=self._restricted_plugin_tools,
            restricted_mcp_tools=self._restricted_mcp_tools,
            registered_tools=self._registered_tools | frozenset(tool_names),
            workspace_root=self._workspace_root,
        )

    def check(self, ctx: PolicyContext) -> PolicyResult:
        """
        Evaluate whether the requested capability should be allowed.

        Returns:
            PolicyResult with verdict ALLOW, DENY, or REQUIRE_CONFIRMATION.
        """
        if not isinstance(ctx, PolicyContext):
            raise TypeError("ctx must be a PolicyContext")

        # Dataclass annotations are not runtime validation. Reject malformed trust
        # fields before set membership, command parsing, or any authorization branch.
        if not isinstance(ctx.tool, str) or not ctx.tool.strip():
            return self._deny(ctx, "Invalid policy context: tool must be a non-empty string")
        if not isinstance(ctx.action, str) or not ctx.action.strip():
            return self._deny(ctx, "Invalid policy context: action must be a non-empty string")
        if not isinstance(ctx.source, CapabilitySource):
            return self._deny(
                ctx,
                f"Unknown capability source '{ctx.source}' - source must be a CapabilitySource",
            )
        if not isinstance(ctx.source_id, str):
            return self._deny(ctx, "Invalid policy context: source_id must be a string")
        if type(ctx.user_confirmed) is not bool:
            return self._deny(ctx, "Invalid policy context: user_confirmed must be a boolean")
        if type(ctx.args) is not dict:
            return self._deny(ctx, "Invalid policy context: args must be a dictionary")
        if not isinstance(ctx.request_id, str):
            return self._deny(ctx, "Invalid policy context: request_id must be a string")

        tool_action = f"{ctx.tool}.{ctx.action}"

        # Unknown sources must be denied before any tool/action allow logic.
        if ctx.source not in tuple(CapabilitySource):
            return self._deny(
                ctx,
                f"Unknown capability source '{ctx.source}' - only registered sources are permitted",
            )

        # 1. Unknown tool → DENY. Additional core tools must be explicitly supplied by
        # the application's trusted registry, and are confirmation-gated below.
        if ctx.tool not in _SAFE_TOOLS and ctx.tool not in self._registered_tools:
            return self._deny(ctx, f"Unknown tool '{ctx.tool}' — only registered tools are permitted")

        # 2. Source-specific restrictions
        if ctx.source == CapabilitySource.PLUGIN and ctx.tool not in self._restricted_plugin_tools:
            return self._deny(
                ctx,
                f"Plugin '{ctx.source_id}' may not invoke tool '{ctx.tool}'. "
                f"Permitted plugin tools: {sorted(self._restricted_plugin_tools)}",
            )

        if ctx.source == CapabilitySource.MCP and ctx.tool not in self._restricted_mcp_tools:
            return self._deny(
                ctx,
                f"MCP server '{ctx.source_id}' may not invoke tool '{ctx.tool}'. "
                f"Permitted MCP tools: {sorted(self._restricted_mcp_tools)}",
            )

        if ctx.tool in self._registered_tools and ctx.tool not in _SAFE_TOOLS:
            if ctx.source != CapabilitySource.CORE:
                return self._deny(ctx, f"Additional registered tool '{ctx.tool}' is available to core routing only")
            if not ctx.user_confirmed:
                reason = f"Newly registered tool action '{tool_action}' requires explicit user confirmation"
                result = PolicyResult(PolicyVerdict.REQUIRE_CONFIRMATION, reason, ctx)
                self._record_trace(ctx, result.verdict.value, result.reason)
                return result

        # 3. Shell-specific execution policy
        if ctx.tool == "shell":
            cmd = ""
            if isinstance(ctx.args, dict):
                def _command_part(value: Any) -> str:
                    if isinstance(value, (list, tuple)):
                        return " ".join(str(part) for part in value)
                    return str(value or "").strip()

                command_value = next(
                    (ctx.args[key] for key in ("command", "cmd", "executable") if ctx.args.get(key)),
                    "",
                )
                cmd = _command_part(command_value)
                extra_value = next(
                    (ctx.args[key] for key in ("args", "arguments", "params", "parameters") if ctx.args.get(key)),
                    "",
                )
                if extra_value:
                    cmd = f"{cmd} {_command_part(extra_value)}".strip()

            from tools.shell import ShellTool
            blocked_reason = ShellTool.check_high_risk(cmd)
            if blocked_reason:
                return self._deny(ctx, f"Execution policy denied high-risk shell command: {blocked_reason}")

            # Check for high-risk system commands
            package_install = re.search(
                r"\b(?:pip(?:\d+(?:\.\d+)?)?\s+install|"
                r"(?:python(?:\d+(?:\.\d+)?)?|py)\s+-m\s+pip\s+install|"
                r"npm\s+(?:install|i|ci)|pnpm\s+(?:add|install)|"
                r"yarn\s+(?:add|install)|uv\s+(?:add|pip\s+install))\b",
                cmd,
                re.IGNORECASE,
            )
            inline_interpreter = bool(re.search(
                r"\b(?:python(?:\d+(?:\.\d+)?)?(?:\.exe)?|py(?:\.exe)?)\s+-(?:c|e)\b",
                cmd, re.IGNORECASE,
            )) or ShellTool.is_inline_interpreter_command(cmd)
            is_high_risk_cmd = bool(package_install or inline_interpreter) or any(
                k in cmd.lower()
                for k in ("taskkill", "kill -9", "net stop", "sc stop", "icacls")
            )
            if is_high_risk_cmd:
                # A confirmation flag from an untrusted source is not user authorization.
                if ctx.source != CapabilitySource.CORE:
                    return self._deny(
                        ctx,
                        f"High-risk shell command is not permitted from source '{ctx.source}'",
                    )
                if ctx.user_confirmed:
                    return self._allow(ctx, f"High-risk shell command approved by user: {cmd[:60]}")
                if self._allow_destructive_from_core:
                    res = PolicyResult(
                        verdict=PolicyVerdict.REQUIRE_CONFIRMATION,
                        reason=f"High-risk shell command requires user confirmation: {cmd[:60]}",
                        context=ctx,
                    )
                    self._record_trace(ctx, res.verdict.value, res.reason)
                    return res
                return self._deny(ctx, f"High-risk shell command denied: {cmd[:60]}")

        # Creating a new file/folder within the configured workspace is a normal
        # capability. Replacing an existing file is high-risk and requires approval.
        existing_file_write = False
        if ctx.tool == "file" and ctx.action == "write_file" and isinstance(ctx.args, dict):
            raw_path = ctx.args.get("path")
            if isinstance(raw_path, (str, Path)) and str(raw_path).strip():
                try:
                    candidate = Path(raw_path).expanduser()
                    if not candidate.is_absolute() and self._workspace_root is not None:
                        candidate = self._workspace_root / candidate
                    # Match FileTool's relative-path semantics. An uninspectable target
                    # must fail closed instead of being mistaken for a new file.
                    existing_file_write = candidate.resolve(strict=False).exists()
                except (OSError, RuntimeError, TypeError, ValueError):
                    existing_file_write = True  # malformed/uninspectable path fails closed

        # 4. High-risk action check
        if ctx.action in _HIGH_RISK_ACTIONS or existing_file_write:
            # Non-core sources cannot use a high-risk action to bypass confirmation.
            if ctx.source in (CapabilitySource.PLUGIN, CapabilitySource.MCP, CapabilitySource.SKILL):
                return self._deny(
                    ctx,
                    f"High-risk action '{ctx.action}' is not permitted from source '{ctx.source}'",
                )
            # Core source: confirmation required unless pre-confirmed or policy allows
            if ctx.source == CapabilitySource.CORE:
                if ctx.user_confirmed:
                    return self._allow(ctx, f"High-risk action '{ctx.action}' approved by user")
                if self._allow_destructive_from_core:
                    res = PolicyResult(
                        verdict=PolicyVerdict.REQUIRE_CONFIRMATION,
                        reason=f"High-risk action '{ctx.action}' requires user confirmation",
                        context=ctx,
                    )
                    self._record_trace(ctx, res.verdict.value, res.reason)
                    return res
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
        if result.verdict == PolicyVerdict.REQUIRE_CONFIRMATION:
            raise PolicyConfirmationRequired(result.reason, context=ctx)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @classmethod
    def _record_trace(cls, ctx: PolicyContext, verdict: str, reason: str) -> None:
        try:
            from core.runtime_trace import get_current_trace
            trace = get_current_trace()
            if trace is not None:
                trace.record_policy_decision(
                    tool=ctx.tool,
                    action=ctx.action,
                    source=str(ctx.source),
                    verdict=verdict,
                    reason=reason,
                )
        except Exception as exc:  # noqa: BLE001 - policy decisions must not depend on telemetry
            logger.debug("Could not record policy trace (%s)", type(exc).__name__)

    @classmethod
    def _allow(cls, ctx: PolicyContext, reason: str) -> PolicyResult:
        logger.debug("[POLICY] ALLOW %s.%s (source=%s): %s", ctx.tool, ctx.action, ctx.source, reason)
        cls._record_trace(ctx, PolicyVerdict.ALLOW.value, reason)
        return PolicyResult(verdict=PolicyVerdict.ALLOW, reason=reason, context=ctx)

    @classmethod
    def _deny(cls, ctx: PolicyContext, reason: str) -> PolicyResult:
        logger.warning("[POLICY] DENY %s.%s (source=%s id=%s): %s", ctx.tool, ctx.action, ctx.source, ctx.source_id, reason)
        cls._record_trace(ctx, PolicyVerdict.DENY.value, reason)
        return PolicyResult(verdict=PolicyVerdict.DENY, reason=reason, context=ctx)


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class PolicyDeniedError(Exception):
    """Raised when ExecutionPolicy.enforce() refuses a capability request."""

    def __init__(self, reason: str, context: PolicyContext | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.context = context


class PolicyConfirmationRequired(PolicyDeniedError):
    """Raised when a capability cannot proceed until explicit user approval."""
