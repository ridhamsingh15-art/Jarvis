"""
Tests for ModelManager health checks, role mapping, and table formatting.
"""
from unittest.mock import patch, MagicMock
from config.config import JarvisConfig
from core.model_manager import ModelManager


def test_model_manager_status():
    config = JarvisConfig(
        model="qwen3:8b",
        model_general="qwen3:8b",
        model_reasoning="deepseek-r1:8b",
        model_coding="qwen2.5-coder:7b",
        model_vision="qwen2.5vl:7b",
        model_fast="gemma4:e4b",
    )
    manager = ModelManager(config)

    fake_tags = {
        "models": [
            {"name": "qwen3:8b", "size": 5200000000},
            {"name": "deepseek-r1:8b", "size": 5200000000},
            {"name": "qwen2.5-coder:7b", "size": 4700000000},
            {"name": "qwen2.5vl:7b", "size": 6000000000},
            {"name": "gemma4:e4b", "size": 9600000000},
        ]
    }

    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = fake_tags
        mock_get.return_value = mock_resp

        status = manager.get_status()
        assert status["ollama_running"] is True
        assert len(status["missing_models"]) == 0
        assert status["configured_roles"]["coding"]["status"] == "AVAILABLE"
        assert status["configured_roles"]["reasoning"]["status"] == "AVAILABLE"
        assert status["configured_roles"]["vision"]["status"] == "AVAILABLE"

        table = manager.format_models_table()
        assert "CODING" in table
        assert "REASONING" in table
        assert "VISION" in table
        assert "AVAILABLE" in table


def test_model_manager_missing_model():
    config = JarvisConfig(
        model="qwen3:8b",
        model_coding="non-existent-coder:latest",
    )
    manager = ModelManager(config)

    fake_tags = {
        "models": [
            {"name": "qwen3:8b", "size": 5200000000},
        ]
    }

    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = fake_tags
        mock_get.return_value = mock_resp

        status = manager.get_status()
        assert "coding" in status["missing_models"]
        table = manager.format_models_table()
        assert "MISSING" in table


def test_model_manager_offline():
    manager = ModelManager()

    with patch("requests.get", side_effect=Exception("Connection refused")):
        status = manager.get_status()
        assert status["ollama_running"] is False
        table = manager.format_models_table()
        assert "OFFLINE" in table
