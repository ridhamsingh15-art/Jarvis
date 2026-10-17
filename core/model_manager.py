"""
Model Manager & Health Check Subsystem for JARVIS.

Provides:
- Health checking of the Ollama server and configured models
- Model inventory and role inspection table
- Graceful error reporting for missing or unavailable models
- CLI inspection command integration
"""

from __future__ import annotations

import logging
from typing import Any

import requests

from config.config import JarvisConfig, load_config

logger = logging.getLogger(__name__)


class ModelManager:
    """Manages model health checks, inventories, and role status."""

    def __init__(self, config: JarvisConfig | None = None) -> None:
        self._config = config or load_config()
        self._host = self._config.ollama_host

    def check_ollama_running(self) -> bool:
        """Check if local Ollama server is responding."""
        try:
            resp = requests.get(f"{self._host}/api/tags", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False

    def get_installed_models(self) -> list[dict[str, Any]]:
        """Retrieve installed models list from Ollama."""
        try:
            resp = requests.get(f"{self._host}/api/tags", timeout=5)
            if resp.status_code == 200:
                return resp.json().get("models", [])
            return []
        except Exception as exc:
            logger.debug("Failed to query Ollama models: %s", exc)
            return []

    def get_status(self) -> dict[str, Any]:
        """Compile complete health and configuration status."""
        is_running = self.check_ollama_running()
        installed_raw = self.get_installed_models() if is_running else []

        installed_map: dict[str, dict[str, Any]] = {}
        for m in installed_raw:
            name = m.get("name", "")
            # normalize name and strip latest tag if present
            base_name = name.split(":")[0] if ":" in name else name
            installed_map[name] = m
            if base_name not in installed_map:
                installed_map[base_name] = m

        role_models = self._config.get_role_models()
        missing_models: dict[str, str] = {}
        configured_status: dict[str, dict[str, Any]] = {}

        for role, model_tag in role_models.items():
            base_tag = model_tag.split(":")[0] if ":" in model_tag else model_tag
            found_key = None
            if model_tag in installed_map:
                found_key = model_tag
            elif base_tag in installed_map:
                found_key = base_tag

            if found_key and is_running:
                m_info = installed_map[found_key]
                size_bytes = m_info.get("size", 0)
                size_gb = f"{size_bytes / (1024**3):.1f} GB" if size_bytes else "Unknown"
                configured_status[role] = {
                    "model": model_tag,
                    "status": "AVAILABLE",
                    "size": size_gb,
                }
            else:
                status = "OFFLINE" if not is_running else "MISSING"
                configured_status[role] = {
                    "model": model_tag,
                    "status": status,
                    "size": "N/A",
                }
                if is_running:
                    missing_models[role] = model_tag

        return {
            "ollama_running": is_running,
            "host": self._host,
            "active_default_model": self._config.model,
            "configured_roles": configured_status,
            "missing_models": missing_models,
            "all_installed": [m.get("name", "") for m in installed_raw],
        }

    def format_models_table(self) -> str:
        """Format the model status into an ASCII table."""
        status = self.get_status()
        is_running = status["ollama_running"]

        lines = [
            "=" * 74,
            f"  JARVIS AIOS -- Model Registry & Health Status",
            f"  Ollama Server: {'ONLINE (' + self._host + ')' if is_running else 'OFFLINE (Cannot reach ' + self._host + ')'}",
            f"  Active Default: {status['active_default_model']}",
            "=" * 74,
            f"  {'ROLE':<12} {'MODEL TAG':<26} {'STATUS':<14} {'SIZE':<10}",
            "-" * 74,
        ]

        for role, info in status["configured_roles"].items():
            role_disp = role.upper()
            model_disp = info["model"]
            stat_disp = info["status"]
            size_disp = info["size"]
            lines.append(f"  {role_disp:<12} {model_disp:<26} {stat_disp:<14} {size_disp:<10}")

        lines.append("-" * 74)

        if status["all_installed"]:
            other_models = [
                m for m in status["all_installed"]
                if not any(m == cfg["model"] or m.startswith(cfg["model"] + ":") for cfg in status["configured_roles"].values())
            ]
            if other_models:
                lines.append("  Other Installed Models:")
                for om in other_models[:10]:
                    lines.append(f"    * {om}")
                lines.append("-" * 74)

        if status["missing_models"]:
            lines.append("  [WARNING] The following configured models are not installed:")
            for role, tag in status["missing_models"].items():
                lines.append(f"    - Role '{role.upper()}': {tag} (Run: ollama pull {tag})")
            lines.append("=" * 74)
        else:
            lines.append("  All configured role models are verified and ready.")
            lines.append("=" * 74)

        return "\n".join(lines)

    def startup_health_check(self) -> bool:
        """Run health check at startup and log diagnostic output."""
        logger.info("Performing JARVIS model health check...")
        status = self.get_status()

        if not status["ollama_running"]:
            logger.warning(
                "Ollama server is not running or unreachable at %s. Local AI models will not respond until Ollama is started.",
                self._host,
            )
            return False

        if status["missing_models"]:
            logger.warning(
                "Some configured models are missing: %s. Requests to these roles will fall back to default model.",
                status["missing_models"],
            )
        else:
            logger.info("All configured role models are available on %s.", self._host)

        return True


def display_model_status() -> None:
    """Entry point helper to print model status to stdout."""
    manager = ModelManager()
    print(manager.format_models_table())


if __name__ == "__main__":
    display_model_status()
