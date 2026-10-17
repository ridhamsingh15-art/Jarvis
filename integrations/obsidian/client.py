from integrations.base.stub_client import StubIntegrationClient


class ObsidianClient(StubIntegrationClient):
    def __init__(self) -> None:
        super().__init__("obsidian", ["create_note", "search_notes", "open_note"])
