from dataclasses import dataclass, field
from typing import Any

from core.models import JarvisModel
from core.tasks import CancellationToken, TaskDefinition


@dataclass(frozen=True, slots=True)
class ExecutionContext(JarvisModel):
    """
    Immutable representation of an active execution.
    Carries the definition, active cancellation token, and a shared scratchpad.
    """
    task: TaskDefinition
    token: CancellationToken = field(default_factory=CancellationToken)
    scratchpad: dict[str, Any] = field(default_factory=dict)
