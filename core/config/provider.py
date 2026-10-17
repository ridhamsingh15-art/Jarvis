"""
Configuration Providers for layered configuration loading.
"""
import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class ConfigProvider(ABC):
    """
    Abstract base class for all configuration providers.
    """
    @abstractmethod
    def load(self) -> dict[str, Any]:
        """
        Load and return configuration values as a dictionary.
        
        Returns:
            Dictionary of configuration keys and values.
        """


class DefaultConfigProvider(ConfigProvider):
    """
    Provides default configuration values defined in the schema.
    """
    def __init__(self, defaults: dict[str, Any]):
        """
        Args:
            defaults: Dictionary of default configuration values.
        """
        self._defaults = defaults

    def load(self) -> dict[str, Any]:
        return self._defaults.copy()


class FileConfigProvider(ConfigProvider):
    """
    Loads configuration from a JSON file.
    """
    def __init__(self, file_path: str):
        """
        Args:
            file_path: Path to the JSON configuration file.
        """
        self._file_path = Path(file_path)

    def load(self) -> dict[str, Any]:
        if not self._file_path.exists():
            return {}
            
        try:
            with open(self._file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            # According to specs, fail-fast on startup errors
            from .exceptions import ConfigurationError
            raise ConfigurationError(f"Failed to parse config file {self._file_path}: {e}")
        except OSError as e:
            from .exceptions import ConfigurationError
            raise ConfigurationError(f"Failed to read config file {self._file_path}: {e}")


class EnvConfigProvider(ConfigProvider):
    """
    Loads configuration from Environment variables.
    
    Variables must be prefixed (e.g., JARVIS_) to avoid polluting the configuration
    with unrelated system environment variables.
    """
    def __init__(self, prefix: str = "JARVIS_"):
        """
        Args:
            prefix: Prefix for environment variables to include in configuration.
        """
        self._prefix = prefix

    def load(self) -> dict[str, Any]:
        config = {}
        for key, value in os.environ.items():
            if key.startswith(self._prefix):
                # Strip prefix and convert to lowercase for the config key
                config_key = key[len(self._prefix):].lower()
                config[config_key] = value
        return config
