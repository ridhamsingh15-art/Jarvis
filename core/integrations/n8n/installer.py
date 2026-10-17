"""
Dependency Management and Installer for n8n.
"""

import logging
import shutil
import subprocess

import requests

from config.config import JarvisConfig
from core.events.bus import EventBus
from core.models import Event

logger = logging.getLogger(__name__)


class N8nInstaller:
    """Manages prerequisites, health checks, and installation for n8n."""

    def __init__(self, config: JarvisConfig, event_bus: EventBus) -> None:
        self._config = config
        self._event_bus = event_bus

    def check_prerequisites(self) -> tuple[bool, str]:
        """Detect if Node (npm) or Docker is available."""
        if shutil.which("npm") is not None:
            return True, "npm"
        if shutil.which("docker") is not None:
            return True, "docker"
        return False, "Neither npm nor docker was found on the system."

    def check_health(self) -> bool:
        """Pings the n8n host to check if it's already running."""
        try:
            # We hit the health endpoint if it exists, or just root
            resp = requests.get(f"{self._config.n8n_host.rstrip('/')}/healthz", timeout=3.0)
            return resp.status_code == 200
        except requests.RequestException:
            pass
            
        try:
            # Fallback to checking root
            resp = requests.get(self._config.n8n_host, timeout=3.0)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def request_installation(self) -> None:
        """Emits an event indicating installation is required."""
        self._event_bus.publish(Event(
            topic="N8nInstallRequested",
            payload={"message": "n8n is not installed or unreachable."},
            source="n8n.installer"
        ))

    def install(self) -> None:
        """Runs the installation using the detected package manager."""
        has_prereqs, method = self.check_prerequisites()
        if not has_prereqs:
            raise RuntimeError(f"Cannot install n8n: {method}")
            
        logger.info("Installing n8n using %s...", method)
        
        try:
            if method == "npm":
                subprocess.run(["npm", "install", "-g", "n8n"], check=True, capture_output=True)
            elif method == "docker":
                # Typically we wouldn't just run it directly without user volume config,
                # but this is a simplified example.
                subprocess.run(["docker", "pull", "docker.n8n.io/n8nio/n8n"], check=True, capture_output=True)
                
            self._event_bus.publish(Event(
                topic="N8nInstalled",
                payload={"method": method},
                source="n8n.installer"
            ))
        except subprocess.CalledProcessError as e:
            logger.error("Failed to install n8n: %s", e.stderr.decode() if e.stderr else str(e))
            raise RuntimeError("Installation command failed.") from e
