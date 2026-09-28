"""
JARVIS AIOS Identity Layer.

Single source of truth for JARVIS identity, persona, behavioural rules,
model disclosure, and response guardrails.
"""

from core.identity.manager import IdentityManager

__all__ = ["IdentityManager"]
