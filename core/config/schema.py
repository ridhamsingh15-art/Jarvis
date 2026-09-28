"""
Schema definitions for the Configuration module.
"""
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ConfigField:
    """
    Defines a single configuration field in the schema.
    
    Attributes:
        type_: The expected type of the configuration value (e.g., int, str, bool).
        default: The default value if not provided by any layer. If None, it must be provided unless required=False.
        required: Whether this field is mandatory. Defaults to True.
        is_secret: Whether this field contains sensitive information that should be masked. Defaults to False.
        description: Optional description of what this field configures.
    """
    type_: type
    default: Any = None
    required: bool = True
    is_secret: bool = False
    description: str = ""


class ConfigSchema:
    """
    Represents the full configuration schema.
    """
    
    def __init__(self, fields: dict[str, ConfigField]):
        """
        Initialize the configuration schema.
        
        Args:
            fields: A dictionary mapping configuration keys to their ConfigField definitions.
        """
        self.fields = fields

    def get_field(self, key: str) -> ConfigField | None:
        """
        Get the field definition for a given key.
        
        Args:
            key: The configuration key.
            
        Returns:
            The ConfigField definition, or None if the key is not in the schema.
        """
        return self.fields.get(key)
    
    def validate_and_coerce(self, key: str, value: Any) -> Any:
        """
        Validate and coerce a value according to the schema field definition.
        
        Args:
            key: The configuration key.
            value: The value to validate and coerce.
            
        Returns:
            The coerced value.
            
        Raises:
            ValueError: If coercion fails or value is invalid.
        """
        field = self.get_field(key)
        if not field:
            # If the field is not in schema, we might either ignore it or return as is.
            # For strictness, we just return as is, or you could raise an error if strict mode is desired.
            return value

        if value is None:
            return value

        # Perform type coercion
        if field.type_ == bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                lower_val = value.lower()
                if lower_val in ('true', '1', 'yes', 'y'):
                    return True
                if lower_val in ('false', '0', 'no', 'n'):
                    return False
            raise ValueError(f"Cannot coerce {value} to bool for key {key}")

        try:
            return field.type_(value)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Cannot coerce {value} to {field.type_.__name__} for key {key}: {e}")
