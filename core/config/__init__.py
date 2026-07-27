"""
JARVIS AIOS Configuration Module

Provides a robust, layered, fail-fast configuration system complying
with the Foundation Specification.
"""

from .exceptions import (
    ConfigurationError, 
    SchemaValidationError, 
    MissingConfigurationError
)
from .schema import ConfigSchema, ConfigField
from .provider import ConfigProvider, DefaultConfigProvider, FileConfigProvider, EnvConfigProvider
from .manager import ConfigManager, ConfigSnapshot

__all__ = [
    "ConfigurationError",
    "SchemaValidationError",
    "MissingConfigurationError",
    "ConfigSchema",
    "ConfigField",
    "ConfigProvider",
    "DefaultConfigProvider",
    "FileConfigProvider",
    "EnvConfigProvider",
    "ConfigManager",
    "ConfigSnapshot"
]
