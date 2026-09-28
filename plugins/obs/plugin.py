"""
OBS Studio Integration Plugin for JARVIS.

Connects JARVIS to OBS Studio via the obs-websocket protocol,
enabling automatic scene switching, recording control, and stream
management during content production workflows.

Plugin lifecycle hooks:
    plugin_initialize(ctx)  — called once after loading
    plugin_start(ctx)       — called when the plugin is enabled
    plugin_stop(ctx)        — called when the plugin is disabled/stopped
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.plugins.sdk import PluginContext

logger = logging.getLogger("plugin.obs_studio")

_ctx: "PluginContext | None" = None
_PLUGIN_ID = "obs_studio"


# ---------------------------------------------------------------------------
# Lifecycle hooks — called by JARVIS DefaultPluginLifecycle
# ---------------------------------------------------------------------------

def plugin_initialize(ctx: "PluginContext") -> None:
    """Called once after the module is loaded. Set up the plugin context."""
    global _ctx
    _ctx = ctx
    ctx.log.info("OBS Studio plugin initializing...")

    # Register capabilities so the Capability Router can dispatch to us
    ctx.capabilities.register(
        name="obs_start_recording",
        description="Start OBS Studio recording.",
        capability_type="tool",
    )
    ctx.capabilities.register(
        name="obs_stop_recording",
        description="Stop OBS Studio recording.",
        capability_type="tool",
    )
    ctx.capabilities.register(
        name="obs_switch_scene",
        description="Switch the active OBS Studio scene.",
        capability_type="tool",
    )

    ctx.log.info("OBS Studio capabilities registered.")


def plugin_start(ctx: "PluginContext") -> None:
    """Called when the plugin transitions to RUNNING state."""
    ctx.assert_permission("network")
    ctx.assert_permission("automation")

    # Subscribe to publishing events to auto-start/stop recording
    ctx.events.subscribe("publishing.started", _on_publishing_started)
    ctx.events.subscribe("publishing.completed", _on_publishing_completed)

    ctx.log.info("OBS Studio plugin started. Listening for publishing events.")


def plugin_stop(ctx: "PluginContext") -> None:
    """Called when the plugin transitions to STOPPED state."""
    ctx.events.cleanup()
    ctx.log.info("OBS Studio plugin stopped.")


# ---------------------------------------------------------------------------
# Tool implementations — called by JARVIS tool routing
# ---------------------------------------------------------------------------

def obs_start_recording() -> dict:
    """Start OBS recording via websocket."""
    if _ctx:
        _ctx.assert_permission("network")
        _ctx.log.info("Starting OBS recording...")
    # In a real implementation: call obs-websocket StartRecord API
    return {"status": "recording_started"}


def obs_stop_recording() -> dict:
    """Stop OBS recording via websocket."""
    if _ctx:
        _ctx.assert_permission("network")
        _ctx.log.info("Stopping OBS recording...")
    # In a real implementation: call obs-websocket StopRecord API
    return {"status": "recording_stopped"}


def obs_switch_scene(scene_name: str) -> dict:
    """Switch to a named scene in OBS."""
    if _ctx:
        _ctx.assert_permission("network")
        _ctx.log.info(f"Switching OBS scene to: {scene_name}")
    # In a real implementation: call obs-websocket SetCurrentProgramScene API
    return {"status": "scene_switched", "scene": scene_name}


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------

def _on_publishing_started(event) -> None:
    logger.info("Publishing started — auto-triggering OBS recording.")
    obs_start_recording()


def _on_publishing_completed(event) -> None:
    logger.info("Publishing complete — stopping OBS recording.")
    obs_stop_recording()
