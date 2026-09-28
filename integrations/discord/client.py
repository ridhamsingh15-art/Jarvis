from integrations.base.stub_client import StubIntegrationClient


class DiscordClient(StubIntegrationClient):
    def __init__(self) -> None:
        super().__init__("discord", ["send_message", "list_channels", "join_server"])
