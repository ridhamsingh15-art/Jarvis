from integrations.base.stub_client import StubIntegrationClient


class EmailClient(StubIntegrationClient):
    def __init__(self) -> None:
        super().__init__("email", ["send_email", "read_emails", "search_emails"])
