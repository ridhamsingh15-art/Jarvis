from dataclasses import dataclass, field
from typing import Any


@dataclass
class Task:
    tool: str
    action: str
    args: dict = field(default_factory=dict)

    status: str = "pending"

    result: Any = None
    error: str = ""

    def execute(self):
        self.status = "running"

    def complete(self, result=None):
        self.status = "completed"
        self.result = result

    def fail(self, error):
        self.status = "failed"
        self.error = str(error)