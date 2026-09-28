"""
MCP Architecture — Phase G implementation.

Minimal MCP (Model Context Protocol) client adapter for JARVIS.

Security-first design:
    MCP tools NEVER execute directly. They enter JARVIS as registered capabilities
    and must pass ExecutionPolicy → Validator → Executor.

    MCP Server
        ↓
    MCPAdapter          (schema normalization + trust boundary)
        ↓
    CapabilityRegistry  (MCP tools become JARVIS capabilities)
        ↓
    ExecutionPolicy     (MCP source treated as untrusted)
        ↓
    Validator
        ↓
    Executor
        ↓
    Telemetry

NOT implemented:
  - Remote marketplace
  - Automatic trust elevation
  - Plugin installation

This module implements:
  - MCPServerConfig     — server registration
  - MCPToolDescriptor   — tool metadata model
  - MCPAdapter          — normalizes MCP tools into JARVIS capabilities
  - MCPRegistry         — tracks registered MCP servers and their tools
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# MCP requests that exceed this timeout are aborted
DEFAULT_MCP_TIMEOUT_SECONDS: float = 30.0


# ---------------------------------------------------------------------------
# MCP Models
# ---------------------------------------------------------------------------


@dataclass
class MCPServerConfig:
    """Registration descriptor for an MCP server."""
    server_id: str
    name: str
    uri: str                    # e.g. "http://localhost:3000" or "stdio://mcp-server"
    transport: str = "http"     # "http" | "stdio" | "websocket"
    timeout_seconds: float = DEFAULT_MCP_TIMEOUT_SECONDS
    trusted: bool = False       # False by default — untrusted until explicit approval
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPToolDescriptor:
    """Normalized descriptor for a single tool advertised by an MCP server."""
    tool_id: str
    name: str
    description: str
    server_id: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    # Risk classification assigned by the adapter, never by the MCP server
    risk_level: str = "unknown"   # "safe" | "moderate" | "high" | "unknown"


@dataclass
class MCPToolResult:
    """Result from an MCP tool invocation."""
    tool_id: str
    success: bool
    output: Any
    error: str = ""
    latency_ms: float = 0.0


# ---------------------------------------------------------------------------
# MCPAdapter — normalizes MCP responses
# ---------------------------------------------------------------------------


# Keywords in tool names/descriptions that trigger high-risk classification
_HIGH_RISK_KEYWORDS: frozenset[str] = frozenset({
    "delete", "remove", "destroy", "drop", "truncate",
    "execute", "run", "shell", "command", "script",
    "write", "overwrite", "format", "install", "uninstall",
    "credential", "password", "secret", "token", "key",
    "shutdown", "reboot", "restart",
})

_MODERATE_RISK_KEYWORDS: frozenset[str] = frozenset({
    "create", "update", "modify", "edit", "post", "send", "publish",
    "upload", "commit", "push",
})


class MCPAdapter:
    """
    Normalizes raw MCP tool listings into MCPToolDescriptors.

    Assigns risk classifications based on tool name/description analysis.
    The MCP server CANNOT self-declare its own risk level.
    """

    def normalize_tools(
        self,
        raw_tools: list[dict[str, Any]],
        server_id: str,
    ) -> list[MCPToolDescriptor]:
        """
        Convert raw MCP tool definitions to normalized MCPToolDescriptors.

        Args:
            raw_tools: List of tool dicts from MCP server's tool listing.
            server_id: The ID of the MCP server that provided these tools.

        Returns:
            List of validated MCPToolDescriptors.
        """
        descriptors = []
        for raw in raw_tools:
            try:
                descriptor = self._normalize_one(raw, server_id)
                if descriptor is not None:
                    descriptors.append(descriptor)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[MCP] Failed to normalize tool from server '%s': %s | raw=%s",
                    server_id, exc, str(raw)[:120],
                )
        logger.info("[MCP] Normalized %d tool(s) from server '%s'", len(descriptors), server_id)
        return descriptors

    def _normalize_one(self, raw: dict[str, Any], server_id: str) -> MCPToolDescriptor | None:
        """Normalize a single raw tool definition."""
        if not isinstance(raw, dict):
            logger.warning("[MCP] Skipping non-dict tool definition: %s", type(raw))
            return None

        tool_id = str(raw.get("name") or raw.get("id") or "")
        if not tool_id:
            logger.warning("[MCP] Skipping tool with no name/id: %s", str(raw)[:80])
            return None

        name = str(raw.get("name", tool_id))
        description = str(raw.get("description", ""))
        input_schema = raw.get("inputSchema") or raw.get("input_schema") or {}
        output_schema = raw.get("outputSchema") or raw.get("output_schema") or {}

        if not isinstance(input_schema, dict):
            input_schema = {}
        if not isinstance(output_schema, dict):
            output_schema = {}

        risk_level = self._classify_risk(name, description)

        return MCPToolDescriptor(
            tool_id=f"{server_id}.{tool_id}",
            name=name,
            description=description[:500],
            server_id=server_id,
            input_schema=input_schema,
            output_schema=output_schema,
            risk_level=risk_level,
        )

    @staticmethod
    def _classify_risk(name: str, description: str) -> str:
        """
        Classify tool risk based on name and description analysis.
        Risk is always assigned by JARVIS, never accepted from the MCP server.
        """
        text = (name + " " + description).lower()
        if any(kw in text for kw in _HIGH_RISK_KEYWORDS):
            return "high"
        if any(kw in text for kw in _MODERATE_RISK_KEYWORDS):
            return "moderate"
        return "safe"


# ---------------------------------------------------------------------------
# MCPRegistry — tracks servers and their tools
# ---------------------------------------------------------------------------


class MCPRegistry:
    """
    In-memory registry of MCP servers and their advertised tools.

    Does NOT automatically trust any server.
    Does NOT automatically execute any tool.
    """

    def __init__(self) -> None:
        self._servers: dict[str, MCPServerConfig] = {}
        self._tools: dict[str, MCPToolDescriptor] = {}   # keyed by tool_id
        self._adapter = MCPAdapter()

    def register_server(self, config: MCPServerConfig) -> None:
        """Register an MCP server (does not connect or trust automatically)."""
        self._servers[config.server_id] = config
        logger.info(
            "[MCP] Registered server '%s' uri=%s trusted=%s",
            config.server_id, config.uri, config.trusted,
        )

    def unregister_server(self, server_id: str) -> bool:
        """Remove an MCP server and all its tools."""
        if server_id not in self._servers:
            return False
        self._servers.pop(server_id)
        # Remove tools from this server
        to_remove = [tid for tid, t in self._tools.items() if t.server_id == server_id]
        for tid in to_remove:
            self._tools.pop(tid)
        logger.info("[MCP] Unregistered server '%s' and %d tool(s)", server_id, len(to_remove))
        return True

    def register_tools(self, raw_tools: list[dict[str, Any]], server_id: str) -> list[MCPToolDescriptor]:
        """
        Normalize and register tools from an MCP server's tool listing.

        Args:
            raw_tools: Raw tool definitions from MCP server.
            server_id: Must already be registered via register_server().

        Returns:
            List of registered MCPToolDescriptors.
        """
        if server_id not in self._servers:
            raise ValueError(f"MCP server '{server_id}' is not registered. Call register_server() first.")

        descriptors = self._adapter.normalize_tools(raw_tools, server_id)
        for d in descriptors:
            self._tools[d.tool_id] = d
        return descriptors

    def get_tool(self, tool_id: str) -> MCPToolDescriptor | None:
        return self._tools.get(tool_id)

    def list_tools(self, server_id: str | None = None) -> list[MCPToolDescriptor]:
        if server_id is None:
            return list(self._tools.values())
        return [t for t in self._tools.values() if t.server_id == server_id]

    def list_servers(self) -> list[MCPServerConfig]:
        return list(self._servers.values())

    def get_server(self, server_id: str) -> MCPServerConfig | None:
        return self._servers.get(server_id)

    def is_trusted(self, server_id: str) -> bool:
        """Returns True only if the server was explicitly registered as trusted."""
        server = self._servers.get(server_id)
        return server is not None and server.trusted
