"""
Phase G Tests — MCP Architecture

Tests:
1. server registration
2. tool discovery/normalization
3. tool metadata preserved
4. risk classification (safe/moderate/high)
5. malformed tool metadata ignored
6. unregistered server raises
7. untrusted server defaults to trusted=False
8. MCP tool cannot bypass ExecutionPolicy
9. server unregistration removes tools
"""
import pytest
from core.mcp import MCPRegistry, MCPServerConfig, MCPAdapter


def _make_registry_with_server(server_id="test_srv", trusted=False) -> MCPRegistry:
    registry = MCPRegistry()
    registry.register_server(MCPServerConfig(
        server_id=server_id,
        name="Test Server",
        uri="http://localhost:3001",
        trusted=trusted,
    ))
    return registry


class TestMCPServerRegistration:
    def test_register_server(self):
        registry = MCPRegistry()
        config = MCPServerConfig(server_id="srv1", name="Search", uri="http://localhost:3001")
        registry.register_server(config)
        servers = registry.list_servers()
        assert any(s.server_id == "srv1" for s in servers)

    def test_server_not_trusted_by_default(self):
        registry = MCPRegistry()
        registry.register_server(MCPServerConfig(server_id="srv2", name="X", uri="http://x"))
        assert not registry.is_trusted("srv2")

    def test_explicit_trusted_server(self):
        registry = MCPRegistry()
        registry.register_server(MCPServerConfig(server_id="srv3", name="Y", uri="http://y", trusted=True))
        assert registry.is_trusted("srv3")

    def test_unregistered_server_not_trusted(self):
        registry = MCPRegistry()
        assert not registry.is_trusted("nonexistent")

    def test_unregister_server(self):
        registry = _make_registry_with_server()
        registry.register_tools([{"name": "tool1", "description": "does x"}], "test_srv")
        registry.unregister_server("test_srv")
        assert registry.get_server("test_srv") is None
        assert len(registry.list_tools("test_srv")) == 0


class TestMCPToolRegistration:
    def test_register_valid_tools(self):
        registry = _make_registry_with_server()
        tools = registry.register_tools([
            {"name": "search", "description": "Search the web"},
            {"name": "fetch", "description": "Fetch a URL"},
        ], "test_srv")
        assert len(tools) == 2

    def test_tool_id_prefixed_with_server_id(self):
        registry = _make_registry_with_server()
        tools = registry.register_tools([{"name": "search", "description": "Search"}], "test_srv")
        assert tools[0].tool_id == "test_srv.search"

    def test_malformed_tool_skipped(self):
        registry = _make_registry_with_server()
        tools = registry.register_tools([
            {"name": "good_tool", "description": "Fine"},
            None,
            {"description": "no name"},
            123,
        ], "test_srv")
        assert len(tools) == 1
        assert tools[0].name == "good_tool"

    def test_unregistered_server_raises(self):
        registry = MCPRegistry()
        with pytest.raises(ValueError, match="not registered"):
            registry.register_tools([{"name": "t"}], "unknown")

    def test_get_tool_by_id(self):
        registry = _make_registry_with_server()
        registry.register_tools([{"name": "lookup", "description": "Look up info"}], "test_srv")
        tool = registry.get_tool("test_srv.lookup")
        assert tool is not None
        assert tool.name == "lookup"

    def test_list_tools_by_server(self):
        registry = _make_registry_with_server("s1")
        registry.register_server(MCPServerConfig(server_id="s2", name="S2", uri="http://s2"))
        registry.register_tools([{"name": "t1", "description": "tool 1"}], "s1")
        registry.register_tools([{"name": "t2", "description": "tool 2"}], "s2")
        s1_tools = registry.list_tools("s1")
        assert all(t.server_id == "s1" for t in s1_tools)


class TestMCPRiskClassification:
    def test_delete_classified_as_high_risk(self):
        adapter = MCPAdapter()
        tools = adapter.normalize_tools([{"name": "delete_records", "description": "Deletes DB records"}], "s1")
        assert tools[0].risk_level == "high"

    def test_execute_classified_as_high_risk(self):
        adapter = MCPAdapter()
        tools = adapter.normalize_tools([{"name": "execute_command", "description": "Runs a command"}], "s1")
        assert tools[0].risk_level == "high"

    def test_create_classified_as_moderate(self):
        adapter = MCPAdapter()
        tools = adapter.normalize_tools([{"name": "create_issue", "description": "Creates a GitHub issue"}], "s1")
        assert tools[0].risk_level == "moderate"

    def test_read_only_classified_as_safe(self):
        adapter = MCPAdapter()
        tools = adapter.normalize_tools([{"name": "list_repos", "description": "Lists repositories"}], "s1")
        assert tools[0].risk_level == "safe"

    def test_server_cannot_override_risk_level(self):
        """Risk level from adapter overrides any server-provided classification."""
        adapter = MCPAdapter()
        # Even if server sends "safe", delete should be high
        raw = {"name": "delete_all", "description": "SAFE: delete all data", "risk_level": "safe"}
        tools = adapter.normalize_tools([raw], "s1")
        assert tools[0].risk_level == "high"


class TestMCPPolicyIntegration:
    def test_mcp_tool_must_pass_execution_policy(self):
        """MCP tools cannot bypass ExecutionPolicy — checked at execution time."""
        from core.execution_policy import ExecutionPolicy, PolicyContext, CapabilitySource, PolicyVerdict
        policy = ExecutionPolicy(restricted_mcp_tools=frozenset({"browser"}))

        # MCP server trying to use 'file' tool → DENY
        ctx = PolicyContext(
            tool="file", action="read_file",
            source=CapabilitySource.MCP,
            source_id="mcp_server_1",
        )
        result = policy.check(ctx)
        assert result.verdict == PolicyVerdict.DENY

    def test_mcp_safe_tool_allowed_by_policy(self):
        from core.execution_policy import ExecutionPolicy, PolicyContext, CapabilitySource, PolicyVerdict
        policy = ExecutionPolicy(restricted_mcp_tools=frozenset({"browser", "system"}))

        ctx = PolicyContext(
            tool="browser", action="search_google",
            source=CapabilitySource.MCP,
            source_id="mcp_search",
        )
        result = policy.check(ctx)
        assert result.verdict == PolicyVerdict.ALLOW
