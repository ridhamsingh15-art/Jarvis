from integrations.base.stub_client import StubIntegrationClient


class GitClient(StubIntegrationClient):
    def __init__(self) -> None:
        super().__init__("git", ["clone", "commit", "push", "pull", "status"])
