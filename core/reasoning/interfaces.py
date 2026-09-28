from abc import ABC, abstractmethod
from typing import Any

from .models import Inference


class IReasoner(ABC):
    @abstractmethod
    def reason(self, context: dict[str, Any]) -> list[Inference]:
        pass
