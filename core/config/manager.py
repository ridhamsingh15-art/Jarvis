"""
Configuration Manager for resolving, validating, and serving configuration.
"""
from typing import Any, Dict, List, Optional
from .schema import ConfigSchema
from .provider import ConfigProvider
from .exceptions import SchemaValidationError, MissingConfigurationError


class ConfigSnapshot:
    """
    Immutable dictionary-like object that holds the final validated configuration.
    Provides O(1) property and dictionary-like access.
    """
    def __init__(self, data: Dict[str, Any], schema: ConfigSchema):
        # We store the internal data privately to prevent mutation
        super().__setattr__('_data', data)
        super().__setattr__('_schema', schema)

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("ConfigSnapshot is immutable")

    def __getattr__(self, name: str) -> Any:
        if name in self._data:
            return self._data[name]
        raise AttributeError(f"Configuration has no attribute '{name}'")

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)
        
    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __str__(self) -> str:
        """
        String representation with secret masking.
        """
        masked = {}
        for k, v in self._data.items():
            field = self._schema.get_field(k)
            if field and field.is_secret:
                masked[k] = "********"
            else:
                masked[k] = v
        return str(masked)

    def __repr__(self) -> str:
        return f"ConfigSnapshot({self.__str__()})"


class ConfigManager:
    """
    Manages the lifecycle of configuration: Loading from providers, validating, and sealing.
    """
    def __init__(self, schema: ConfigSchema):
        """
        Args:
            schema: The schema definition to validate against.
        """
        self._schema = schema
        self._providers: List[ConfigProvider] = []
        self._snapshot: Optional[ConfigSnapshot] = None

    def add_provider(self, provider: ConfigProvider) -> None:
        """
        Add a configuration provider. 
        Providers added later will override values from earlier providers.
        
        Args:
            provider: The ConfigProvider to add.
        """
        self._providers.append(provider)

    def load(self) -> ConfigSnapshot:
        """
        Load configuration from all registered providers in order, validate against
        the schema, and return an immutable snapshot.
        
        Returns:
            ConfigSnapshot: The final frozen configuration.
            
        Raises:
            ConfigurationError: If any validation or coercion fails (fail-fast).
        """
        raw_config: Dict[str, Any] = {}
        
        # Load defaults from schema first
        for key, field in self._schema.fields.items():
            if field.default is not None:
                raw_config[key] = field.default

        # Layer providers
        for provider in self._providers:
            provider_config = provider.load()
            for k, v in provider_config.items():
                if self._schema.get_field(k):
                    raw_config[k] = v

        # Validate and Coerce
        validated_config: Dict[str, Any] = {}
        for key, field in self._schema.fields.items():
            if key not in raw_config:
                if field.required:
                    raise MissingConfigurationError(f"Missing required configuration key: {key}")
                continue

            try:
                validated_config[key] = self._schema.validate_and_coerce(key, raw_config[key])
            except ValueError as e:
                raise SchemaValidationError(str(e))
                
        # Seal into immutable snapshot
        self._snapshot = ConfigSnapshot(validated_config, self._schema)
        return self._snapshot

    @property
    def config(self) -> ConfigSnapshot:
        """
        Get the loaded configuration snapshot.
        Must call `load()` before accessing.
        """
        if not self._snapshot:
            raise RuntimeError("Configuration has not been loaded yet.")
        return self._snapshot
