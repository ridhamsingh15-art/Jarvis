from integrations.base.stub_client import StubIntegrationClient


class NotionClient(StubIntegrationClient):
    def __init__(self) -> None:
        super().__init__("notion", ["create_page", "update_page", "list_pages"])
