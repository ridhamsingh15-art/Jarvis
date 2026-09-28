"""
Provides robust secret masking capabilities for log payloads.
Extracts secret keys from the ConfigSnapshot and redacts them deep in dictionaries.
"""
from typing import Any

from core.config import ConfigSnapshot

_MASK = "********"

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
                    self._secret_keys.add(key.lower())
        
        # Also add common dangerous keys explicitly just to be safe (Zero Trust)
        self._secret_keys.update({"password", "token", "api_key", "secret", "authorization"})

    def mask(self, payload: Any) -> Any:
        """
        Deeply traverses the payload and masks any dictionaries containing secret keys.
        """
        if isinstance(payload, dict):
            masked_dict = {}
            for k, v in payload.items():
                if str(k).lower() in self._secret_keys:
                    masked_dict[k] = _MASK
                else:
                    masked_dict[k] = self.mask(v)
            return masked_dict
        elif isinstance(payload, list):
            return [self.mask(item) for item in payload]
        else:
            return payload
