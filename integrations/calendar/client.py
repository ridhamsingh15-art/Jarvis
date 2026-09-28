from integrations.base.stub_client import StubIntegrationClient


class CalendarClient(StubIntegrationClient):
    def __init__(self) -> None:
        super().__init__("calendar", ["create_event", "list_events", "delete_event"])
