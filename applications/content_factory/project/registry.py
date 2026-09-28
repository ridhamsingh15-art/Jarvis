"""
Project Registry for indexing and searching available Project Bundles.
"""


from .models import ProjectBundleMetadata
from .storage import ProjectStorage


class ProjectRegistry:
    """In-memory index of available project bundles for quick searching."""

    def __init__(self, storage: ProjectStorage) -> None:
        self._storage = storage
        self._projects: dict[str, ProjectBundleMetadata] = {}

    def scan(self) -> None:
        """Scans the storage directory and rebuilds the registry."""
        self._projects.clear()
        
        if not self._storage.root_dir.exists():
            return
            
        for child in self._storage.root_dir.iterdir():
            if child.is_dir():
                project_id = child.name
                # We attempt to load it
                bundle = self._storage.load_bundle(project_id)
                if bundle:
                    self._projects[project_id] = bundle.metadata

    def register(self, metadata: ProjectBundleMetadata) -> None:
        self._projects[metadata.project_id] = metadata

    def unregister(self, project_id: str) -> None:
        if project_id in self._projects:
            del self._projects[project_id]

    def list_all(self) -> list[ProjectBundleMetadata]:
        return list(self._projects.values())

    def find_by_id(self, project_id: str) -> ProjectBundleMetadata | None:
        return self._projects.get(project_id)

    def find_by_title(self, title_query: str) -> list[ProjectBundleMetadata]:
        query = title_query.lower()
        return [m for m in self._projects.values() if query in m.title.lower()]

    def find_by_tag(self, tag: str) -> list[ProjectBundleMetadata]:
        query = tag.lower()
        return [m for m in self._projects.values() if any(query == t.lower() for t in m.tags)]
