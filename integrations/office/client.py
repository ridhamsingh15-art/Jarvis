from integrations.base.stub_client import StubIntegrationClient


class OfficeClient(StubIntegrationClient):
    def __init__(self) -> None:
        super().__init__("office", ["open_word", "open_excel", "open_powerpoint"])
