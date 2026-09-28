from integrations.base.stub_client import StubIntegrationClient


class DockerClient(StubIntegrationClient):
    def __init__(self) -> None:
        super().__init__("docker", ["run_container", "stop_container", "list_containers"])
