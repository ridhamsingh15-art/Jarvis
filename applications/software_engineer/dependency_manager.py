"""Manage validated Python requirements in a workspace manifest."""
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)
_REQUIREMENT = re.compile(
    r"^(?P<name>[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)"
    r"(?P<extras>\[[A-Za-z0-9._-]+(?:,[A-Za-z0-9._-]+)*\])?"
    r"(?P<specifiers>(?:\s*(?:===|==|~=|!=|<=|>=|<|>)\s*"
    r"[A-Za-z0-9][A-Za-z0-9.*+!_-]*(?:\s*,\s*(?:===|==|~=|!=|<=|>=|<|>)\s*"
    r"[A-Za-z0-9][A-Za-z0-9.*+!_-]*)*)?)$"
)


def _normalized_requirement(value: str) -> tuple[str, str] | None:
    """Validate a simple requirement and normalize package names/specifier spacing."""
    match = _REQUIREMENT.fullmatch(value.strip())
    if match is None:
        return None
    name = re.sub(r"[-_.]+", "-", match.group("name").casefold())
    extras_raw = match.group("extras")
    extras = ""
    if extras_raw:
        names = sorted(
            re.sub(r"[-_.]+", "-", item.casefold())
            for item in extras_raw[1:-1].split(",")
        )
        extras = "[" + ",".join(names) + "]"
    specifiers = re.sub(r"\s+", "", match.group("specifiers"))
    canonical = name + extras + specifiers
    return name, canonical


class DependencyManager:
    def __init__(self, workspace_path: str):
        self._workspace_path = workspace_path

    def add_dependency(self, package_name: str) -> bool:
        """Record a simple package requirement without executing an installer.

        Returns True if the exact requirement is already present or is written.
        Conflicts, unsafe paths, malformed requirements, and missing manifests fail
        explicitly with False and leave the workspace unchanged.
        """
        if not isinstance(package_name, str):
            logger.warning("Refusing non-string dependency requirement")
            return False
        requested = _normalized_requirement(package_name)
        if requested is None:
            logger.warning("Refusing invalid or unsupported dependency requirement: %r", package_name)
            return False

        workspace = Path(self._workspace_path).expanduser().resolve()
        manifest = workspace / "requirements.txt"
        if not workspace.is_dir() or manifest.is_symlink() or not manifest.is_file():
            logger.warning("No safe existing requirements.txt in workspace %s", workspace)
            return False
        if manifest.resolve().parent != workspace:
            logger.warning("Refusing requirements manifest outside workspace: %s", manifest)
            return False

        try:
            original = manifest.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            logger.warning("Cannot read dependency manifest %s: %s", manifest, exc)
            return False

        requested_name, requested_canonical = requested
        for raw_line in original.splitlines():
            line = raw_line.split("#", 1)[0].strip()
            if not line or line.startswith(("#", "-")):
                continue
            existing = _normalized_requirement(line)
            if existing is None or existing[0] != requested_name:
                continue
            if existing[1] == requested_canonical:
                return True
            logger.warning("Conflicting requirement for %s already exists: %s", requested_name, line)
            return False

        separator = "" if not original or original.endswith(("\n", "\r")) else "\n"
        updated = f"{original}{separator}{requested_canonical}\n"
        try:
            manifest.write_text(updated, encoding="utf-8", newline="")
        except (OSError, UnicodeError) as exc:
            logger.warning("Cannot update dependency manifest %s: %s", manifest, exc)
            return False

        logger.info("Added requirement %s to %s", requested_canonical, manifest)
        return True
