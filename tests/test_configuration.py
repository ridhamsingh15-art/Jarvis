import os
import json
import pytest

from core.config import (
    ConfigSchema,
    ConfigField,
    DefaultConfigProvider,
    FileConfigProvider,
    EnvConfigProvider,
    ConfigManager,
    ConfigurationError,
    SchemaValidationError,
    MissingConfigurationError
)

@pytest.fixture
def sample_schema():
    return ConfigSchema({
        "host": ConfigField(type_=str, default="localhost"),
        "port": ConfigField(type_=int, default=8080),
        "debug": ConfigField(type_=bool, default=False),
        "api_key": ConfigField(type_=str, required=True, is_secret=True),
        "timeout": ConfigField(type_=int, required=False)
    })


def test_schema_validation_and_coercion(sample_schema):
    assert sample_schema.validate_and_coerce("port", "9090") == 9090
    assert sample_schema.validate_and_coerce("debug", "true") is True
    assert sample_schema.validate_and_coerce("debug", "0") is False
    assert sample_schema.validate_and_coerce("host", "0.0.0.0") == "0.0.0.0"

    with pytest.raises(ValueError):
        sample_schema.validate_and_coerce("port", "not_a_number")


def test_default_provider(sample_schema):
    manager = ConfigManager(sample_schema)
    # Default provider is implicitly added by Manager if default is in schema
    # But let's add a dummy api_key so it doesn't fail on required
    manager.add_provider(DefaultConfigProvider({"api_key": "secret"}))
    
    config = manager.load()
    assert config.host == "localhost"
    assert config.port == 8080
    assert config.debug is False
    assert config.api_key == "secret"


def test_file_provider(sample_schema, tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({
        "port": 9000,
        "api_key": "file_secret"
    }))
    
    manager = ConfigManager(sample_schema)
    manager.add_provider(FileConfigProvider(str(config_file)))
    
    config = manager.load()
    assert config.port == 9000
    assert config.api_key == "file_secret"
    assert config.host == "localhost" # from defaults


def test_env_provider(sample_schema, monkeypatch):
    monkeypatch.setenv("JARVIS_PORT", "9999")
    monkeypatch.setenv("JARVIS_DEBUG", "1")
    monkeypatch.setenv("JARVIS_API_KEY", "env_secret")
    
    manager = ConfigManager(sample_schema)
    manager.add_provider(EnvConfigProvider("JARVIS_"))
    
    config = manager.load()
    assert config.port == 9999
    assert config.debug is True
    assert config.api_key == "env_secret"


def test_layered_configuration(sample_schema, tmp_path, monkeypatch):
    # 1. Defaults are in schema
    
    # 2. File config overrides defaults
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({
        "port": 9000,
        "api_key": "file_secret",
        "timeout": 30
    }))
    
    # 3. Env config overrides file
    monkeypatch.setenv("JARVIS_API_KEY", "super_secret_env")
    monkeypatch.setenv("JARVIS_DEBUG", "True")
    
    manager = ConfigManager(sample_schema)
    manager.add_provider(FileConfigProvider(str(config_file)))
    manager.add_provider(EnvConfigProvider("JARVIS_"))
    
    config = manager.load()
    assert config.host == "localhost" # from default
    assert config.port == 9000 # from file
    assert config.timeout == 30 # from file
    assert config.debug is True # from env
    assert config.api_key == "super_secret_env" # from env


def test_missing_required_key(sample_schema):
    manager = ConfigManager(sample_schema)
    # api_key is required and has no default
    with pytest.raises(MissingConfigurationError):
        manager.load()


def test_invalid_coercion_fails_fast(sample_schema, monkeypatch):
    monkeypatch.setenv("JARVIS_API_KEY", "secret")
    monkeypatch.setenv("JARVIS_PORT", "not_an_int")
    
    manager = ConfigManager(sample_schema)
    manager.add_provider(EnvConfigProvider())
    
    with pytest.raises(SchemaValidationError):
        manager.load()


def test_secret_masking(sample_schema):
    manager = ConfigManager(sample_schema)
    manager.add_provider(DefaultConfigProvider({"api_key": "super_secret_key"}))
    
    config = manager.load()
    
    # Value is accessible directly
    assert config.api_key == "super_secret_key"
    
    # But masked in string representation
    config_str = str(config)
    assert "super_secret_key" not in config_str
    assert "'api_key': '********'" in config_str
    
def test_immutable_snapshot(sample_schema):
    manager = ConfigManager(sample_schema)
    manager.add_provider(DefaultConfigProvider({"api_key": "secret"}))
    config = manager.load()
    
    with pytest.raises(AttributeError):
        # Should not be able to set attributes
        config.host = "new_host"

def test_o1_lookup(sample_schema):
    manager = ConfigManager(sample_schema)
    manager.add_provider(DefaultConfigProvider({"api_key": "secret"}))
    config = manager.load()
    
    # Property access (O(1))
    assert config.host == "localhost"
    # Dictionary access (O(1))
    assert config["host"] == "localhost"
    assert config.get("host") == "localhost"
