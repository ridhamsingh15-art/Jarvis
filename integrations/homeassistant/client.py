from integrations.base.stub_client import StubIntegrationClient


class HomeassistantClient(StubIntegrationClient):
    def __init__(self) -> None:
        super().__init__("homeassistant", ["get_state", "set_state", "list_entities"])
