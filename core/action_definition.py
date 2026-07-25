"""
Structured metadata for tool actions.

Replaces string-based descriptions with a strongly-typed schema,
allowing the Validator and Planner to consume explicit argument requirements.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ActionDefinition:
    """Immutable definition of a tool action and its schema.

    Attributes:
        name: The name of the action (e.g. 'open_url').
        description: Human-readable description of what the action does.
        required_args: List of argument names that must be provided.
        optional_args: List of optional argument names (defaults to empty).
    """

    name: str
    description: str
    required_args: list[str]
    optional_args: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        """Backward compatibility for GUI and Registry string formatting.
        
        Renders a human-readable summary combining the description
        and the expected arguments.
        """
        desc = self.description
        if self.required_args:
            args_fmt = ", ".join(f"'{arg}'" for arg in self.required_args)
            desc += f" Requires {args_fmt} argument{'s' if len(self.required_args) > 1 else ''}."
        if self.optional_args:
            args_fmt = ", ".join(f"'{arg}'" for arg in self.optional_args)
            desc += f" Optional: {args_fmt} argument{'s' if len(self.optional_args) > 1 else ''}."
        return desc
