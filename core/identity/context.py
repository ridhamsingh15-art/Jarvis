"""
Identity context builder — constructs runtime identity context.

Aggregates persona information with runtime model/provider details
so prompt builders can produce contextually accurate prompts.
"""

from core.identity.models import IdentityContext
from core.identity.persona import Persona


class IdentityContextBuilder:
    """Builds an IdentityContext from a Persona and runtime model info.

    The active model and provider names are injected at construction
    time to avoid coupling identity to the provider subsystem.
    """

    def __init__(self, persona: Persona, active_model: str, active_provider: str) -> None:
        self._persona = persona
        self._active_model = active_model
        self._active_provider = active_provider

    def build(self) -> IdentityContext:
        """Construct a complete IdentityContext snapshot."""
        return IdentityContext(
            identity_statement=self._persona.get_identity_statement(),
            traits=self._persona.get_traits(),
            rules=self._persona.get_rules(),
            active_model=self._active_model,
            active_provider=self._active_provider,
        )
