"""
JARVIS AIOS Configuration Module

Provides a robust, layered, fail-fast configuration system complying
with the Foundation Specification.
"""

from .exceptions import (
    ConfigurationError,
    MissingConfigurationError,
    SchemaValidationError,
)
from .manager import ConfigManager, ConfigSnapshot
from .provider import (
    ConfigProvider,
    DefaultConfigProvider,
    EnvConfigProvider,
    FileConfigProvider,
)
from .schema import ConfigField, ConfigSchema

__all__ = [
    "ConfigField",
    "ConfigManager",
    "ConfigProvider",
    "ConfigSchema",
    "ConfigSnapshot",
    "ConfigurationError",
    "DefaultConfigProvider",
    "EnvConfigProvider",
    "FileConfigProvider",
    "MissingConfigurationError",
    "SchemaValidationError"
]
