"""
Phase B Tests — Execution Policy Boundary

Tests:
1. allowed capability
2. denied capability (unknown tool)
3. unknown tool → DENY
4. destructive capability → DENY / REQUIRE_CONFIRMATION
5. plugin capability — restricted tool set
6. plugin attempting high-risk action → DENY
7. MCP capability — restricted tool set
8. core source + user_confirmed → ALLOW destructive
9. enforce() raises PolicyDeniedError on DENY
"""
import pytest
from core.execution_policy import (
    ExecutionPolicy,
    PolicyContext,
    PolicyVerdict,
    CapabilitySource,
    PolicyDeniedError,
)


def _ctx(tool: str, action: str, source: CapabilitySource = CapabilitySource.CORE, **kwargs) -> PolicyContext:
    return PolicyContext(tool=tool, action=action, source=source, **kwargs)


class TestExecutionPolicyAllowed:
    def test_safe_tool_core_allowed(self):
        policy = ExecutionPolicy()
        result = policy.check(_ctx("windows", "open_app"))
        assert result.verdict == PolicyVerdict.ALLOW

    def test_browser_core_allowed(self):
        policy = ExecutionPolicy()
        result = policy.check(_ctx("browser", "open_url"))
        assert result.verdict == PolicyVerdict.ALLOW

    def test_file_core_allowed(self):
        policy = ExecutionPolicy()
        result = policy.check(_ctx("file", "read_file"))
        assert result.verdict == PolicyVerdict.ALLOW

    def test_system_tool_allowed(self):
        policy = ExecutionPolicy()
        result = policy.check(_ctx("system", "respond"))
        assert result.verdict == PolicyVerdict.ALLOW


class TestExecutionPolicyDenied:
    def test_unknown_tool_denied(self):
        policy = ExecutionPolicy()
        result = policy.check(_ctx("rogue_tool", "do_thing"))
        assert result.verdict == PolicyVerdict.DENY

    def test_destructive_action_denied_by_default(self):
        policy = ExecutionPolicy()
        result = policy.check(_ctx("file", "delete_file"))
        assert result.verdict == PolicyVerdict.DENY

    def test_shutdown_denied(self):
        policy = ExecutionPolicy()
        result = policy.check(_ctx("windows", "shutdown"))
        assert result.verdict == PolicyVerdict.DENY

    def test_registry_write_denied(self):
        policy = ExecutionPolicy()
        result = policy.check(_ctx("windows", "write_registry"))
        assert result.verdict == PolicyVerdict.DENY


class TestExecutionPolicyPluginSource:
    def test_plugin_allowed_tool_allowed(self):
        policy = ExecutionPolicy(restricted_plugin_tools=frozenset({"browser", "system"}))
        result = policy.check(_ctx("browser", "open_url", source=CapabilitySource.PLUGIN, source_id="my_plugin"))
        assert result.verdict == PolicyVerdict.ALLOW

    def test_plugin_disallowed_tool_denied(self):
        policy = ExecutionPolicy(restricted_plugin_tools=frozenset({"browser"}))
        result = policy.check(_ctx("windows", "open_app", source=CapabilitySource.PLUGIN, source_id="my_plugin"))
        assert result.verdict == PolicyVerdict.DENY

    def test_plugin_high_risk_action_denied(self):
        policy = ExecutionPolicy(restricted_plugin_tools=frozenset({"file"}))
        result = policy.check(_ctx("file", "delete_file", source=CapabilitySource.PLUGIN, source_id="evil_plugin"))
        assert result.verdict == PolicyVerdict.DENY


class TestExecutionPolicyMCPSource:
    def test_mcp_allowed_tool_allowed(self):
        policy = ExecutionPolicy(restricted_mcp_tools=frozenset({"browser", "system"}))
        result = policy.check(_ctx("browser", "search_google", source=CapabilitySource.MCP, source_id="mcp_search"))
        assert result.verdict == PolicyVerdict.ALLOW

    def test_mcp_disallowed_tool_denied(self):
        policy = ExecutionPolicy(restricted_mcp_tools=frozenset({"browser"}))
        result = policy.check(_ctx("file", "read_file", source=CapabilitySource.MCP, source_id="mcp_files"))
        assert result.verdict == PolicyVerdict.DENY

    def test_mcp_high_risk_always_denied(self):
        policy = ExecutionPolicy(restricted_mcp_tools=frozenset({"file"}))
        result = policy.check(_ctx("file", "delete_file", source=CapabilitySource.MCP, source_id="mcp_evil"))
        assert result.verdict == PolicyVerdict.DENY


class TestExecutionPolicyConfirmation:
    def test_destructive_with_user_confirmed_allowed(self):
        policy = ExecutionPolicy(allow_destructive_from_core=True)
        result = policy.check(_ctx("file", "delete_file", user_confirmed=True))
        assert result.verdict == PolicyVerdict.ALLOW

    def test_destructive_without_confirmation_requires_confirmation(self):
        policy = ExecutionPolicy(allow_destructive_from_core=True)
        result = policy.check(_ctx("file", "delete_file", user_confirmed=False))
        assert result.verdict == PolicyVerdict.REQUIRE_CONFIRMATION

    def test_enforce_raises_on_deny(self):
        policy = ExecutionPolicy()
        with pytest.raises(PolicyDeniedError):
            policy.enforce(_ctx("unknown_tool", "do_thing"))

    def test_enforce_passes_on_allow(self):
        policy = ExecutionPolicy()
        policy.enforce(_ctx("windows", "open_app"))  # must not raise


class TestExecutionPolicyDefaultSafety:
    def test_default_policy_safe_posture(self):
        """Out-of-the-box policy: unknown → DENY, destructive → DENY."""
        policy = ExecutionPolicy()
        dangerous = [
            ("file", "delete_file"),
            ("windows", "shutdown"),
            ("windows", "reboot"),
            ("windows", "write_registry"),
            ("shell", "shell_run"),
        ]
        for tool, action in dangerous:
            result = policy.check(_ctx(tool, action))
            assert result.verdict == PolicyVerdict.DENY, f"{tool}.{action} should be DENY"
