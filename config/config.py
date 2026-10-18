"""
Configuration management for Jarvis.

Loads settings from environment variables with sensible defaults.
All configuration lives in a single immutable dataclass.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from config.providers import PROVIDER_CONFIG

_DEFAULT_MEMORY_DB = str(
    Path.home() / ".jarvis" / "memory.db"
)
_DEFAULT_KNOWLEDGE_DB = str(
    Path.home() / ".jarvis" / "knowledge.db"
)
_DEFAULT_AUTONOMY_DB = str(
    Path.home() / ".jarvis" / "autonomy.sqlite3"
)


@dataclass(frozen=True)
class JarvisConfig:
    """Immutable configuration for the Jarvis agent framework."""

    provider: str = "ollama"
    model: str = "qwen3:8b"
    ollama_host: str = "http://localhost:11434"
    max_retries: int = 3
    request_timeout: int = 30
    retry_backoff_seconds: float = 1.0
    memory_db_path: str = _DEFAULT_MEMORY_DB
    autonomy_persistence_backend: str = "sqlite"
    autonomy_db_path: str = _DEFAULT_AUTONOMY_DB
    
    # Specialized Model Roles
    model_general: str = "qwen3:8b"
    model_reasoning: str = "deepseek-r1:8b"
    model_coding: str = "qwen2.5-coder:7b"
    model_vision: str = "qwen2.5vl:7b"
    model_fast: str = "gemma4:e4b"

    # Knowledge / PKI
    embedding_model: str = "nomic-embed-text"
    knowledge_db_path: str = _DEFAULT_KNOWLEDGE_DB
    knowledge_scan_interval_seconds: int = 300

    # n8n Integration
    n8n_host: str = "http://localhost:5678"
    n8n_api_key: str = ""

    # Provider strategy fields appended to preserve older positional arguments.
    fallback_providers: tuple[str, ...] = ()
    reasoning_provider: str | None = None
    coding_provider: str | None = None
    vision_provider: str | None = None
    fast_provider: str | None = None

    def get_role_models(self) -> dict[str, str]:
        """Return dictionary mapping semantic roles to model tags."""
        return {
            "general": self.model_general or self.model,
            "reasoning": self.model_reasoning,
            "coding": self.model_coding,
            "vision": self.model_vision,
            "fast": self.model_fast,
        }



def _optional_provider_env(name: str) -> str | None:
    """Read and validate an optional provider override."""
    value = os.environ.get(name, "").strip().lower()
    if not value:
        return None
    if value not in PROVIDER_CONFIG:
        raise ValueError(
            f"Unknown provider in {name}: {value!r}; supported providers: "
            f"{', '.join(sorted(PROVIDER_CONFIG))}"
        )
    return value


def load_config() -> JarvisConfig:
    """Load configuration from environment variables with defaults.

    Environment variables:
        JARVIS_PROVIDER: AI provider name (default: ollama)
        JARVIS_MODEL: Provider-specific default model override.
        JARVIS_FALLBACK_PROVIDERS: Optional comma-separated fallback provider IDs.
        JARVIS_PROVIDER_REASONING/CODING/VISION/FAST: Optional role provider overrides.
        JARVIS_MODEL_GENERAL: General role model (default: qwen3:8b)
        JARVIS_MODEL_REASONING: Reasoning role model (default: deepseek-r1:8b)
        JARVIS_MODEL_CODING: Coding role model (default: qwen2.5-coder:7b)
        JARVIS_MODEL_VISION: Vision role model (default: qwen2.5vl:7b)
        JARVIS_MODEL_FAST: Fast role model (default: gemma4:e4b)
        OLLAMA_HOST: Ollama server URL (default: http://localhost:11434)
        JARVIS_MAX_RETRIES: Max LLM retry attempts (default: 3)
        JARVIS_TIMEOUT: Request timeout in seconds (default: 30)
        JARVIS_MEMORY_DB: Path to memory database (default: ~/.jarvis/memory.db)
        JARVIS_AUTONOMY_PERSISTENCE: Goal persistence backend, sqlite or memory
            (default: sqlite; in-memory remains useful for tests/development).
        JARVIS_AUTONOMY_DB: Path to the autonomy goal database
            (default: ~/.jarvis/autonomy.sqlite3)

    Returns:
        JarvisConfig: Frozen configuration instance.
    """
    provider = os.environ.get("JARVIS_PROVIDER", "ollama").strip().lower()
    if provider not in PROVIDER_CONFIG:
        raise ValueError(
            f"Unknown JARVIS_PROVIDER {provider!r}; supported providers: "
            f"{', '.join(sorted(PROVIDER_CONFIG))}"
        )

    provider_defaults = PROVIDER_CONFIG[provider]
    model = os.environ.get("JARVIS_MODEL", provider_defaults["default_model"]).strip()
    fallback_raw = os.environ.get("JARVIS_FALLBACK_PROVIDERS", "")
    fallback_providers = tuple(
        part.strip().lower()
        for part in fallback_raw.split(",")
        if part.strip()
    )
    if len(fallback_providers) != len(set(fallback_providers)):
        raise ValueError("JARVIS_FALLBACK_PROVIDERS contains duplicate provider IDs")
    unknown_fallbacks = sorted(set(fallback_providers) - set(PROVIDER_CONFIG))
    if unknown_fallbacks:
        raise ValueError(
            "Unknown fallback provider(s): " + ", ".join(unknown_fallbacks)
        )
    if provider in fallback_providers:
        raise ValueError("JARVIS_PROVIDER cannot also appear in JARVIS_FALLBACK_PROVIDERS")

    ollama_roles = PROVIDER_CONFIG["ollama"]["models"]
    role_defaults = {
        "general": model if provider == "ollama" else ollama_roles["general"],
        "reasoning": ollama_roles["reasoning"],
        "coding": ollama_roles["coding"],
        "vision": ollama_roles["vision"],
        "fast": ollama_roles["fast"],
    }
    role_provider_overrides = {
        "reasoning": _optional_provider_env("JARVIS_PROVIDER_REASONING"),
        "coding": _optional_provider_env("JARVIS_PROVIDER_CODING"),
        "vision": _optional_provider_env("JARVIS_PROVIDER_VISION"),
        "fast": _optional_provider_env("JARVIS_PROVIDER_FAST"),
    }
    allowed_providers = {provider, *fallback_providers}
    unavailable_role_overrides = {
        role: provider_id
        for role, provider_id in role_provider_overrides.items()
        if provider_id is not None and provider_id not in allowed_providers
    }
    if unavailable_role_overrides:
        details = ", ".join(
            f"{role}={provider_id}" for role, provider_id in sorted(unavailable_role_overrides.items())
        )
        raise ValueError(
            "Role provider override is not the primary or an explicitly configured fallback: "
            + details
        )

    return JarvisConfig(
        provider=provider,
        model=model,
        fallback_providers=fallback_providers,
        reasoning_provider=role_provider_overrides["reasoning"],
        coding_provider=role_provider_overrides["coding"],
        vision_provider=role_provider_overrides["vision"],
        fast_provider=role_provider_overrides["fast"],
        model_general=os.environ.get("JARVIS_MODEL_GENERAL", role_defaults["general"]).strip(),
        model_reasoning=os.environ.get("JARVIS_MODEL_REASONING", role_defaults["reasoning"]).strip(),
        model_coding=os.environ.get("JARVIS_MODEL_CODING", role_defaults["coding"]).strip(),
        model_vision=os.environ.get("JARVIS_MODEL_VISION", role_defaults["vision"]).strip(),
        model_fast=os.environ.get("JARVIS_MODEL_FAST", role_defaults["fast"]).strip(),
        ollama_host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
        max_retries=int(os.environ.get("JARVIS_MAX_RETRIES", "3")),
        request_timeout=int(os.environ.get("JARVIS_TIMEOUT", "30")),
        retry_backoff_seconds=float(
            os.environ.get("JARVIS_RETRY_BACKOFF_SECONDS", "1.0")
        ),
        memory_db_path=os.environ.get("JARVIS_MEMORY_DB", _DEFAULT_MEMORY_DB),
        autonomy_persistence_backend=os.environ.get("JARVIS_AUTONOMY_PERSISTENCE", "sqlite"),
        autonomy_db_path=os.environ.get("JARVIS_AUTONOMY_DB", _DEFAULT_AUTONOMY_DB),
        embedding_model=os.environ.get("JARVIS_EMBEDDING_MODEL", "nomic-embed-text"),
        knowledge_db_path=os.environ.get("JARVIS_KNOWLEDGE_DB", _DEFAULT_KNOWLEDGE_DB),
        knowledge_scan_interval_seconds=int(os.environ.get("JARVIS_KNOWLEDGE_SCAN_INTERVAL", "300")),
        n8n_host=os.environ.get("N8N_HOST", "http://localhost:5678"),
        n8n_api_key=os.environ.get("N8N_API_KEY", ""),
    )
