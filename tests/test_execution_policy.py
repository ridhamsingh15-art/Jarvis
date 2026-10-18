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
    CapabilitySource,
    ExecutionPolicy,
    PolicyConfirmationRequired,
    PolicyContext,
    PolicyDeniedError,
    PolicyVerdict,
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

    def test_skill_high_risk_action_denied(self):
        policy = ExecutionPolicy(allow_destructive_from_core=True)
        result = policy.check(_ctx("file", "delete_file", source=CapabilitySource.SKILL, source_id="skill-file"))
        assert result.verdict == PolicyVerdict.DENY


class TestExecutionPolicyPackageInstallVariants:
    @pytest.mark.parametrize(
        "command",
        [
            "pip3 install example-package",
            "python -m pip install example-package",
            "npm ci",
            "pnpm add example-package",
            "yarn add example-package",
            "uv add example-package",
        ],
    )
    def test_package_install_variants_are_high_risk(self, command):
        result = ExecutionPolicy().check(
            _ctx("shell", "run", args={"command": command})
        )
        assert result.verdict == PolicyVerdict.DENY
        assert "high-risk shell command" in result.reason.lower()


class TestExecutionPolicyShellArgumentNormalization:
    def test_cmd_and_args_alias_cannot_hide_high_risk_install(self):
        policy = ExecutionPolicy()
        result = policy.check(
            _ctx(
                "shell",
                "run",
                args={"cmd": "pip", "args": ["install", "example-package"]},
            )
        )
        assert result.verdict == PolicyVerdict.DENY
        assert "high-risk shell command" in result.reason.lower()


class TestExecutionPolicyShellConfirmationBoundary:
    @pytest.mark.parametrize("source", [CapabilitySource.PLUGIN, CapabilitySource.MCP])
    def test_untrusted_high_risk_shell_command_denied_even_when_confirmed(self, source):
        policy = ExecutionPolicy(
            allow_destructive_from_core=True,
            restricted_plugin_tools=frozenset({"shell"}),
            restricted_mcp_tools=frozenset({"shell"}),
        )
        result = policy.check(
            _ctx(
                "shell",
                "shell_run",
                source=source,
                source_id="external-source",
                user_confirmed=True,
                args={"command": "pip install example-package"},
            )
        )
        assert result.verdict == PolicyVerdict.DENY
        assert "not permitted" in result.reason.lower() or "denied" in result.reason.lower()


class TestExecutionPolicyEmptyAllowlists:
    def test_explicitly_empty_plugin_allowlist_denies_every_tool(self):
        policy = ExecutionPolicy(restricted_plugin_tools=frozenset())
        result = policy.check(_ctx("browser", "open_url", source=CapabilitySource.PLUGIN))
        assert result.verdict == PolicyVerdict.DENY

    def test_explicitly_empty_mcp_allowlist_denies_every_tool(self):
        policy = ExecutionPolicy(restricted_mcp_tools=frozenset())
        result = policy.check(_ctx("browser", "open_url", source=CapabilitySource.MCP))
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

    def test_enforce_blocks_when_confirmation_is_required(self):
        policy = ExecutionPolicy(allow_destructive_from_core=True)
        with pytest.raises(PolicyConfirmationRequired, match="requires user confirmation"):
            policy.enforce(_ctx("file", "delete_file", user_confirmed=False))

    def test_enforce_allows_destructive_action_after_explicit_confirmation(self):
        policy = ExecutionPolicy(allow_destructive_from_core=True)
        policy.enforce(_ctx("file", "delete_file", user_confirmed=True))

    def test_enforce_passes_on_allow(self):
        policy = ExecutionPolicy()
        policy.enforce(_ctx("windows", "open_app"))  # must not raise


class TestExecutionPolicyUnknownSource:
    def test_unknown_source_cannot_use_high_risk_action(self):
        policy = ExecutionPolicy(allow_destructive_from_core=True)
        result = policy.check(_ctx("file", "delete_file", source="unregistered-source"))
        assert result.verdict == PolicyVerdict.DENY
        assert "Unknown capability source" in result.reason


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


@pytest.mark.parametrize(
    "action",
    ["patch_file", "edit_file", "rename", "move", "copy", "append_line", "delete"],
)
def test_destructive_file_mutations_require_explicit_core_approval(action):
    policy = ExecutionPolicy(allow_destructive_from_core=True)
    result = policy.check(_ctx("file", action, args={"path": "inside-workspace.txt", "content": "x"}))
    assert result.verdict == PolicyVerdict.REQUIRE_CONFIRMATION


def test_write_file_requires_approval_only_when_overwriting_existing_file(tmp_path):
    policy = ExecutionPolicy(allow_destructive_from_core=True)
    target = tmp_path / "write.txt"
    new_file = policy.check(_ctx("file", "write_file", args={"path": str(target), "content": "new"}))
    assert new_file.verdict == PolicyVerdict.ALLOW
    target.write_text("old", encoding="utf-8")
    overwrite = policy.check(_ctx("file", "write_file", args={"path": str(target), "content": "new"}))
    assert overwrite.verdict == PolicyVerdict.REQUIRE_CONFIRMATION


def test_inline_python_execution_requires_explicit_approval():
    policy = ExecutionPolicy(allow_destructive_from_core=True)
    result = policy.check(_ctx("shell", "run", args={"command": 'python -c "print(1)"'}))
    assert result.verdict == PolicyVerdict.REQUIRE_CONFIRMATION

@pytest.mark.parametrize(
    "command",
    [
        '"C:\\Python312\\python.exe" -c "print(1)"',
        r'C:\Python312\python.exe -c "print(1)"',
        '"py.exe" -e "print(1)"',
    ],
)
def test_quoted_or_path_qualified_inline_python_requires_approval(command):
    policy = ExecutionPolicy(allow_destructive_from_core=True)
    result = policy.check(_ctx("shell", "run", args={"command": command}))
    assert result.verdict == PolicyVerdict.REQUIRE_CONFIRMATION


def test_relative_write_path_uses_configured_workspace_for_overwrite_check(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "existing.txt"
    target.write_text("original", encoding="utf-8")
    policy = ExecutionPolicy(allow_destructive_from_core=True, workspace_root=workspace)

    overwrite = policy.check(
        _ctx("file", "write_file", args={"path": "existing.txt", "content": "replacement"})
    )
    new_file = policy.check(
        _ctx("file", "write_file", args={"path": "new.txt", "content": "new"})
    )

    assert overwrite.verdict == PolicyVerdict.REQUIRE_CONFIRMATION
    assert new_file.verdict == PolicyVerdict.ALLOW
    assert target.read_text(encoding="utf-8") == "original"


def test_registered_tool_policy_copy_preserves_workspace_overwrite_boundary(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "existing.txt").write_text("original", encoding="utf-8")
    policy = ExecutionPolicy(
        allow_destructive_from_core=True,
        workspace_root=workspace,
    ).with_registered_tools(frozenset({"extra_tool"}))

    result = policy.check(
        _ctx("file", "write_file", args={"path": "existing.txt", "content": "replacement"})
    )

    assert result.verdict == PolicyVerdict.REQUIRE_CONFIRMATION

@pytest.mark.parametrize("invalid", ["false", "true", 0, 1, None, [], {}])
def test_non_boolean_confirmation_never_authorizes_a_destructive_action(invalid):
    policy = ExecutionPolicy(allow_destructive_from_core=True)
    result = policy.check(
        _ctx("file", "delete_file", user_confirmed=invalid)
    )
    assert result.verdict == PolicyVerdict.DENY
    assert "user_confirmed must be a boolean" in result.reason


@pytest.mark.parametrize("invalid_tool", [None, "", "  ", [], {}])
def test_malformed_tool_name_fails_closed_without_raising(invalid_tool):
    result = ExecutionPolicy().check(
        PolicyContext(tool=invalid_tool, action="read_file")
    )
    assert result.verdict == PolicyVerdict.DENY
    assert "tool must be a non-empty string" in result.reason


@pytest.mark.parametrize("invalid_action", [None, "", "  ", [], {}])
def test_malformed_action_name_fails_closed_without_raising(invalid_action):
    result = ExecutionPolicy().check(
        PolicyContext(tool="file", action=invalid_action)
    )
    assert result.verdict == PolicyVerdict.DENY
    assert "action must be a non-empty string" in result.reason


@pytest.mark.parametrize("invalid_source", ["core", "plugin", "mcp", None, []])
def test_source_must_be_trusted_enum_not_a_string_or_arbitrary_object(invalid_source):
    result = ExecutionPolicy(allow_destructive_from_core=True).check(
        _ctx("file", "delete_file", source=invalid_source, user_confirmed=True)
    )
    assert result.verdict == PolicyVerdict.DENY
    assert "source must be a CapabilitySource" in result.reason


@pytest.mark.parametrize("invalid_args", [None, [], "{}", 1])
def test_non_dictionary_policy_arguments_fail_closed(invalid_args):
    result = ExecutionPolicy().check(
        _ctx("file", "write_file", args=invalid_args)
    )
    assert result.verdict == PolicyVerdict.DENY
    assert "args must be a dictionary" in result.reason
