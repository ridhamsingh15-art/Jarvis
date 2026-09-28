from integrations.base.stub_client import StubIntegrationClient


class BrowserClient(StubIntegrationClient):
    def __init__(self) -> None:
        super().__init__("browser", ["open_url", "screenshot", "scroll"])
