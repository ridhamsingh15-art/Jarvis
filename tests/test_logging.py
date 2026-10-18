import os
import threading

import pytest

from core.config import ConfigField, ConfigManager, ConfigSchema, DefaultConfigProvider
from core.telemetry import (
    JsonFormatter,
    LogLevel,
    LogMasker,
    TextFormatter,
    add_metadata,
    clear_context,
    create_logger,
    set_component_name,
    set_correlation_id,
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


@pytest.mark.parametrize(
    "secret_key",
    [
        "access_token",
        "accessToken",
        "refresh-token",
        "client_secret",
        "clientSecret",
        "apiKey",
        "api-key",
        "privateKey",
        "private_key",
        "authorization",
        "COOKIE",
        "db-password",
    ],
)
def test_secret_masking_covers_common_key_variants(sample_config, secret_key):
    masker = LogMasker(sample_config)
    payload = {
        secret_key: "must-not-leak",
        "nested": [{"sessionKey": "nested-secret", "ordinary": "visible"}],
        "tokenizer": "ordinary-language-tokenizer",
    }

    masked = masker.mask(payload)

    assert masked[secret_key] == "********"
    assert masked["nested"][0]["sessionKey"] == "********"
    assert masked["nested"][0]["ordinary"] == "visible"
    assert masked["tokenizer"] == "ordinary-language-tokenizer"
    assert "must-not-leak" not in repr(masked)
    assert "nested-secret" not in repr(masked)


def test_secret_masking_matches_configured_schema_keys_after_normalization(tmp_path):
    schema = ConfigSchema({
        "OAuthAccessToken": ConfigField(type_=str, is_secret=True, default="secret"),
    })
    config = ConfigManager(schema).load()
    masker = LogMasker(config)

    assert masker.mask({"oauth_access_token": "sensitive"})["oauth_access_token"] == "********"


def test_shutdown_does_not_close_sink_while_dispatch_is_writing(sample_config, monkeypatch):
    from core.telemetry.logger import AsyncLogger

    started = threading.Event()
    release = threading.Event()

    class BlockingSink:
        def __init__(self):
            self.closed = False
            self.closed_while_writing = False

        def write(self, _formatted):
            started.set()
            assert release.wait(timeout=2)
            self.closed_while_writing = self.closed

        def close(self):
            self.closed = True

    sink = BlockingSink()
    logger = AsyncLogger(LogLevel.DEBUG, LogMasker(sample_config), [(TextFormatter(), sink)])
    real_join = logger._thread.join
    # Simulate the documented bounded shutdown timeout without waiting two seconds.
    monkeypatch.setattr(logger._thread, "join", lambda timeout=None: real_join(timeout=0.01))
    logger.info("blocked sink record")
    assert started.wait(timeout=1)

    logger.shutdown()
    assert not sink.closed, "shutdown must not close a sink still owned by the dispatcher"

    release.set()
    real_join(timeout=1)
    assert not logger._thread.is_alive()
    assert sink.closed
    assert not sink.closed_while_writing


def test_dispatcher_accounts_for_records_when_a_sink_fails(sample_config):
    from core.telemetry.logger import AsyncLogger

    received = []

    class FlakySink:
        def __init__(self):
            self.calls = 0
            self.closed = False

        def write(self, formatted):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("expected sink failure")
            received.append(formatted)

        def close(self):
            self.closed = True

    sink = FlakySink()
    logger = AsyncLogger(LogLevel.DEBUG, LogMasker(sample_config), [(TextFormatter(), sink)])
    logger.info("first record")
    logger.info("second record")
    logger.shutdown()

    assert sink.calls == 2
    assert received and "second record" in received[0]
    assert sink.closed


def test_secret_masking_recurses_through_tuples(sample_config):
    masker = LogMasker(sample_config)
    payload = {
        "metadata": (
            {"password": "tuple-secret-marker"},
            [{"apiKey": "nested-tuple-secret-marker", "ordinary": "visible"}],
        )
    }

    masked = masker.mask(payload)

    assert masked["metadata"][0]["password"] == "********"
    assert masked["metadata"][1][0]["apiKey"] == "********"
    assert masked["metadata"][1][0]["ordinary"] == "visible"
    assert "tuple-secret-marker" not in repr(masked)
    assert "nested-tuple-secret-marker" not in repr(masked)
