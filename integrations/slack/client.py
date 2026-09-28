from integrations.base.stub_client import StubIntegrationClient


class SlackClient(StubIntegrationClient):
    def __init__(self) -> None:
        super().__init__("slack", ["send_message", "list_channels", "create_channel"])
