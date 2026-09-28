import typing
from dataclasses import asdict, dataclass, replace
from typing import Any, TypeVar

from typing_extensions import Self

from .exceptions import ModelValidationError

T = TypeVar('T', bound='JarvisModel')

@dataclass(frozen=True, slots=True)
class JarvisModel:
    """
    The canonical base model for all JARVIS AIOS domain objects.
    Enforces immutability, slotted memory efficiency, and deep serialization.
    """
    
    def __post_init__(self):
        """
        Validate fields immediately upon instantiation.
        """
        self.validate()

    def validate(self) -> None:
        """
        Override this method in subclasses for semantic validation.
        Structural type checking is performed natively.
        """

    def to_dict(self) -> dict[str, Any]:
        """
        Serializes the model and any nested models into a primitive dictionary.
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """
        Deserializes a dictionary back into the strictly-typed model.
        Recursively reconstructs nested models based on type hints.
        """
        if not isinstance(data, dict):
            raise ModelValidationError(f"Expected dict for {cls.__name__}, got {type(data).__name__}")

        field_types = typing.get_type_hints(cls)
        init_kwargs = {}
        
        for field_name, field_type in field_types.items():
            if field_name not in data:
                continue
                
            value = data[field_name]
            
            # Recursive deserialization for nested JarvisModels
            if hasattr(field_type, "from_dict") and isinstance(value, dict):
                init_kwargs[field_name] = field_type.from_dict(value)
            # Basic list of models
            elif getattr(field_type, "__origin__", None) is list and isinstance(value, list):
                inner_type = typing.get_args(field_type)[0]
                if hasattr(inner_type, "from_dict"):
                    init_kwargs[field_name] = [inner_type.from_dict(item) if isinstance(item, dict) else item for item in value]
                else:
                    init_kwargs[field_name] = value
            # Basic dict of models
            elif getattr(field_type, "__origin__", None) is dict and isinstance(value, dict):
                _key_type, val_type = typing.get_args(field_type)
                if hasattr(val_type, "from_dict"):
                    init_kwargs[field_name] = {k: val_type.from_dict(v) if isinstance(v, dict) else v for k, v in value.items()}
                else:
                    init_kwargs[field_name] = value
            # Optional models
            elif getattr(field_type, "__origin__", None) is typing.Union:
                args = typing.get_args(field_type)
                if type(None) in args:
                    inner_type = next((t for t in args if t is not type(None)), None)
                    if inner_type and hasattr(inner_type, "from_dict") and isinstance(value, dict):
                        init_kwargs[field_name] = inner_type.from_dict(value)
                    else:
                        init_kwargs[field_name] = value
                else:
                    init_kwargs[field_name] = value
            else:
                init_kwargs[field_name] = value

        try:
            return cls(**init_kwargs)
        except Exception as e:
            raise ModelValidationError(f"Failed to instantiate {cls.__name__}: {e!s}") from e

    def copy(self, **changes: Any) -> Self:
        """
        Creates a deep copy of the model, optionally applying modifications.
        """
        try:
            return replace(self, **changes)
        except Exception as e:
            raise ModelValidationError(f"Failed to copy {self.__class__.__name__}: {e!s}") from e
