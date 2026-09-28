from integrations.base.stub_client import StubIntegrationClient


class VscodeClient(StubIntegrationClient):
    def __init__(self) -> None:
        super().__init__("vscode", ["open_file", "run_task", "get_extensions"])
