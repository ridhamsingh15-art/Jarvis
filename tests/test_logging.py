import os
import json
import time
import pytest
import threading

from core.config import ConfigSchema, ConfigField, ConfigManager, DefaultConfigProvider
from core.telemetry import (
    LogLevel, 
    set_correlation_id, set_component_name, add_metadata, clear_context,
    JsonFormatter, TextFormatter,
    LogMasker,
    create_logger
)

@pytest.fixture
def sample_config(tmp_path):
    schema = ConfigSchema({
        "log_level": ConfigField(type_=str, default="DEBUG"),
        "log_sinks": ConfigField(type_=list, default=["file"]),
        "log_file_path": ConfigField(type_=str, default=str(tmp_path / "test.log")),
        "db_password": ConfigField(type_=str, is_secret=True, default="supersecret")
    })
    manager = ConfigManager(schema)
    manager.add_provider(DefaultConfigProvider({}))
    return manager.load()


def test_levels_and_formatters():
    # Test level parsing
    assert LogLevel.from_string("debug") == LogLevel.DEBUG
    assert LogLevel.from_string("UNKNOWN") == LogLevel.INFO
    
    record = {
        "timestamp": "2023-01-01T00:00:00Z",
        "level": "INFO",
        "component": "Test",
        "message": "Hello World",
        "metadata": {"user_id": 123}
    }
    
    jf = JsonFormatter()
    res_json = jf.format(record)
    assert '"message": "Hello World"' in res_json
    assert '"user_id": 123' in res_json
    
    tf = TextFormatter()
    res_text = tf.format(record)
    assert "[2023-01-01T00:00:00Z] [INFO ] [Test] Hello World | user_id=123" in res_text


def test_context_propagation():
    clear_context()
    
    set_correlation_id("corr-123")
    set_component_name("AuthModule")
    add_metadata("tenant", "acme")
    
    # Simulate another thread/context
    def worker():
        set_correlation_id("corr-456")
        assert core.telemetry.context.get_correlation_id() == "corr-456"
        
    import core.telemetry.context
    
    assert core.telemetry.context.get_correlation_id() == "corr-123"
    assert core.telemetry.context.get_component_name() == "AuthModule"
    assert core.telemetry.context.get_metadata() == {"tenant": "acme"}


def test_secret_masking(sample_config):
    masker = LogMasker(sample_config)
    payload = {
        "safe_key": "safe_value",
        "db_password": "my_real_password",
        "token": "api_token_123", # 'token' is always masked by default
        "nested": {
            "db_password": "nested_password",
            "other": "value"
        }
    }
    
    masked = masker.mask(payload)
    assert masked["safe_key"] == "safe_value"
    assert masked["db_password"] == "********"
    assert masked["token"] == "********"
    assert masked["nested"]["db_password"] == "********"
    assert masked["nested"]["other"] == "value"


def test_async_logger_e2e(sample_config, tmp_path):
    clear_context()
    logger = create_logger(sample_config)
    
    log_file = sample_config.get("log_file_path")
    
    set_correlation_id("test-e2e")
    logger.info("Test message", additional="data", db_password="secret")
    
    # Wait for background thread to flush
    logger.shutdown()
    
    assert os.path.exists(log_file)
    with open(log_file, "r") as f:
        content = f.read()
        
    assert "Test message" in content
    assert "test-e2e" in content
    assert "additional" in content
    assert "********" in content  # password was masked
    assert "secret" not in content # unmasked password not in log


def test_concurrent_logging(sample_config, tmp_path):
    logger = create_logger(sample_config)
    
    def worker(thread_id):
        for i in range(100):
            logger.info(f"Message from thread {thread_id} - {i}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    
    logger.shutdown()
    
    log_file = sample_config.get("log_file_path")
    with open(log_file, "r") as f:
        lines = f.readlines()
        
    assert len(lines) == 1000
