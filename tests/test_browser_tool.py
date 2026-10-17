"""
Tests for BrowserTool action registration and executor resolution.

Verifies:
- BrowserTool registers all expected actions
- Registry resolves browser actions correctly
- ExecutionEngine can execute browser actions through the bridging pattern
"""

from unittest.mock import patch

from core.executor.action_registry import ActionRegistry
from core.registry import Registry
from tools.base_tool import BaseTool
from tools.browser import BrowserTool


class TestBrowserToolActions:
    """Verify BrowserTool defines the correct action set."""

    def setup_method(self):
        self.tool = BrowserTool()

    def test_has_search_google_action(self):
        actions = self.tool.get_actions()
        assert "search_google" in actions

    def test_has_open_url_action(self):
        actions = self.tool.get_actions()
        assert "open_url" in actions

    def test_has_open_site_action(self):
        actions = self.tool.get_actions()
        assert "open_site" in actions

    def test_action_definitions_have_names(self):
        actions = self.tool.get_actions()
        for action_name, definition in actions.items():
            assert definition.name == action_name

    def test_search_google_has_query_param(self):
        actions = self.tool.get_actions()
        defn = actions["search_google"]
        assert "query" in defn.required_args


class TestRegistryBrowserResolution:
    """Verify Registry can look up BrowserTool and its actions."""

    def setup_method(self):
        self.registry = Registry()
        self.tool = BrowserTool()
        self.registry.register(self.tool)

    def test_registry_has_browser(self):
        assert self.registry.has_tool("browser")

    def test_registry_get_returns_browser(self):
        tool = self.registry.get("browser")
        assert tool is not None
        assert tool.name == "browser"

    def test_registry_get_actions(self):
        actions = self.registry.get_actions("browser")
        assert "search_google" in actions
        assert "open_url" in actions
        assert "open_site" in actions


class TestExecutorActionBridge:
    """Verify the tool-to-ActionRegistry bridging pattern works."""

    def setup_method(self):
        self.registry = Registry()
        self.browser = BrowserTool()
        self.registry.register(self.browser)

        self.action_registry = ActionRegistry()

        # Bridge — same pattern used in main.py
        for tool_name in self.registry.list_tools():
            tool = self.registry.get(tool_name)
            if tool is not None:
                for action_name in tool.get_actions():
                    def _make_handler(t: BaseTool, a: str):
                        def handler(_context, **kwargs):
                            return t.execute(a, kwargs)
                        return handler
                    self.action_registry.register(
                        action_name, _make_handler(tool, action_name)
                    )

    def test_action_registry_has_search_google(self):
        handler = self.action_registry.get("search_google")
        assert handler is not None

    def test_action_registry_has_open_url(self):
        handler = self.action_registry.get("open_url")
        assert handler is not None

    def test_action_registry_has_open_site(self):
        handler = self.action_registry.get("open_site")
        assert handler is not None

    @patch("webbrowser.open")
    def test_search_google_handler_executes(self, mock_open):
        handler = self.action_registry.get("search_google")
        result = handler(None, query="cats")
        assert "cats" in result
        mock_open.assert_called_once()

    @patch("webbrowser.open")
    def test_open_url_handler_executes(self, mock_open):
        handler = self.action_registry.get("open_url")
        result = handler(None, url="https://example.com")
        assert "example.com" in result
        mock_open.assert_called_once()

    @patch("webbrowser.open")
    def test_open_site_handler_executes(self, mock_open):
        handler = self.action_registry.get("open_site")
        result = handler(None, site="google")
        assert "google" in result
        mock_open.assert_called_once()
