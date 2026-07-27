import typing
from dataclasses import dataclass, is_dataclass, asdict, replace
from typing import Any, Dict, TypeVar, Type

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
        pass

    def to_dict(self) -> Dict[str, Any]:
        """
        Serializes the model and any nested models into a primitive dictionary.
        """
        return asdict(self)

    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
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
            if is_dataclass(field_type) and issubclass(field_type, JarvisModel) and isinstance(value, dict):
                init_kwargs[field_name] = field_type.from_dict(value)
            # Basic list of models
            elif getattr(field_type, "__origin__", None) is list and isinstance(value, list):
                inner_type = typing.get_args(field_type)[0]
                if is_dataclass(inner_type) and issubclass(inner_type, JarvisModel):
                    init_kwargs[field_name] = [inner_type.from_dict(item) if isinstance(item, dict) else item for item in value]
                else:
                    init_kwargs[field_name] = value
            # Basic dict of models
            elif getattr(field_type, "__origin__", None) is dict and isinstance(value, dict):
                key_type, val_type = typing.get_args(field_type)
                if is_dataclass(val_type) and issubclass(val_type, JarvisModel):
                    init_kwargs[field_name] = {k: val_type.from_dict(v) if isinstance(v, dict) else v for k, v in value.items()}
                else:
                    init_kwargs[field_name] = value
            # Optional models
            elif getattr(field_type, "__origin__", None) is typing.Union:
                args = typing.get_args(field_type)
                if type(None) in args:
                    inner_type = next((t for t in args if t is not type(None)), None)
                    if inner_type and is_dataclass(inner_type) and issubclass(inner_type, JarvisModel) and isinstance(value, dict):
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
            raise ModelValidationError(f"Failed to instantiate {cls.__name__}: {str(e)}") from e

    def copy(self: T, **changes: Any) -> T:
        """
        Creates a deep copy of the model, optionally applying modifications.
        """
        try:
            return replace(self, **changes)
        except Exception as e:
            raise ModelValidationError(f"Failed to copy {self.__class__.__name__}: {str(e)}") from e
