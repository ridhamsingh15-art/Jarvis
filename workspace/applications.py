from dataclasses import dataclass


@dataclass
class ApplicationState:
    name: str
    pid: int

class AppManager:
    def get_apps(self) -> list[ApplicationState]:
        return [
            ApplicationState(name="VS Code", pid=1024),
            ApplicationState(name="Chrome", pid=2048)
        ]
