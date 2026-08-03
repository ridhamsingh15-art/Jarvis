from dataclasses import dataclass, field


@dataclass
class WorkspaceState:
    running_applications: list[str] = field(default_factory=list)
    open_windows: list[str] = field(default_factory=list)
    active_project: str | None = None
    active_repository: str | None = None
    browser_tabs: list[str] = field(default_factory=list)
    clipboard_content: str | None = None
    
    def to_dict(self) -> dict:
        return {
            "applications": self.running_applications,
            "windows": self.open_windows,
            "project": self.active_project,
            "repository": self.active_repository,
            "browser_tabs": self.browser_tabs,
            "clipboard": self.clipboard_content
        }
