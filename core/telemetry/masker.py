"""
Provides robust secret masking capabilities for log payloads.
Extracts secret keys from the ConfigSnapshot and redacts them deep in dictionaries.
"""
import re
from typing import Any

from core.config import ConfigSnapshot

_MASK = "********"

# Exact credential-name variants are always masked even when a config schema
# does not know about a third-party payload. Tokens are matched as key segments,
# not arbitrary substrings (so a harmless key such as "tokenizer" stays visible).
_SENSITIVE_KEY_SEGMENTS = frozenset({
    "password", "passwd", "pwd", "token", "secret", "authorization",
    "credential", "credentials", "cookie", "cookies", "private_key",
    "privatekey", "client_secret", "clientsecret", "api_key", "apikey",
    "access_key", "accesskey", "refresh_key", "refreshkey", "signing_key",
    "signingkey", "encryption_key", "encryptionkey", "session_key",
    "sessionkey", "bearer",
})


def _normalize_key(key: Any) -> str:
    """Normalize snake/camel/kebab/space-separated keys consistently."""
    raw = str(key)
    raw = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", raw)
    return re.sub(r"[^a-zA-Z0-9]+", "_", raw).strip("_").lower()


def _is_sensitive_key(key: Any, configured_keys: set[str]) -> bool:
    normalized = _normalize_key(key)
    if normalized in configured_keys or normalized in _SENSITIVE_KEY_SEGMENTS:
        return True
    segments = set(normalized.split("_"))
    if segments & {"password", "passwd", "pwd", "token", "secret", "authorization",
                   "credential", "credentials", "cookie", "cookies", "bearer"}:
        return True
    return bool(
        {"api", "private", "client", "access", "refresh", "signing", "encryption", "session"}
        & segments
        and "key" in segments
    )

class LogMasker:
    """
    Masks sensitive information in log payloads based on configuration schema.
    """
    def __init__(self, config: ConfigSnapshot):
        self._secret_keys: set[str] = set()
        
        # Traverse the config schema to find fields marked as secrets
        if hasattr(config, "_schema"):
            schema = config._schema
            for key, field in schema.fields.items():
                if field.is_secret:
                    self._secret_keys.add(_normalize_key(key))

        # These built-ins augment the config schema; third-party records often use
        # credential naming conventions that are absent from the application's schema.
        self._secret_keys.update(_SENSITIVE_KEY_SEGMENTS)

    def mask(self, payload: Any) -> Any:
        """
        Deeply traverses the payload and masks any dictionaries containing secret keys.
        """
        if isinstance(payload, dict):
            masked_dict = {}
            for k, v in payload.items():
                if _is_sensitive_key(k, self._secret_keys):
                    masked_dict[k] = _MASK
                else:
                    masked_dict[k] = self.mask(v)
            return masked_dict
        elif isinstance(payload, list):
            return [self.mask(item) for item in payload]
        elif isinstance(payload, tuple):
            return tuple(self.mask(item) for item in payload)
        else:
            return payload
