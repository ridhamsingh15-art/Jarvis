from integrations.base.stub_client import StubIntegrationClient


class BlenderClient(StubIntegrationClient):
    def __init__(self) -> None:
        super().__init__("blender", ["open_scene", "render", "animation"])
