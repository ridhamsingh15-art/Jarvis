from integrations.base.stub_client import StubIntegrationClient


class GithubClient(StubIntegrationClient):
    def __init__(self) -> None:
        super().__init__("github", ["create_repo", "list_repos", "create_issue", "create_pr"])
