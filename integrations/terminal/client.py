from integrations.base.stub_client import StubIntegrationClient


class TerminalClient(StubIntegrationClient):
    def __init__(self) -> None:
        super().__init__("terminal", ["run_command", "list_processes", "kill_process"])
