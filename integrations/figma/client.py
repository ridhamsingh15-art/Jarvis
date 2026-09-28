from integrations.base.stub_client import StubIntegrationClient


class FigmaClient(StubIntegrationClient):
    def __init__(self) -> None:
        super().__init__("figma", ["get_design", "export_assets", "list_projects"])
