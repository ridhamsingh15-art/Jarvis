"""
Fast Intent Router for JARVIS AIOS.

Two-stage classification:
  Stage 1 — deterministic regex (sub-millisecond, 0 LLM calls)
  Stage 2 — lightweight LLM call for genuinely ambiguous inputs

The classifier MUST NEVER invoke ExecutiveBrain, ReasoningLoop, or Planner.
It is a pure router — once it returns an IntentType, exactly one pipeline owns the request.
"""
import re
import logging
from enum import StrEnum
from typing import Optional, Any

logger = logging.getLogger(__name__)


class IntentType(StrEnum):
    CHAT = "chat"
    MEMORY = "memory"
    TOOL = "tool"
    MISSION = "mission"


class IntentClassifier:
    """Classifies user requests into distinct intent channels.

    Stage 1 (deterministic):
      - Fast regex patterns for obvious MEMORY, TOOL, MISSION, and CHAT intents.
      - Returns immediately when confidence is high.

    Stage 2 (LLM fallback):
      - Only used for ambiguous inputs that don't clearly match Stage 1.
      - A single minimal LLM call returning CHAT/MEMORY/TOOL/MISSION.
      - Falls back to CHAT on timeout or failure.
    """

    # ── MEMORY: remember/recall patterns ──────────────────────────────────────
    _MEMORY_PATTERN = re.compile(
        r"^(?:please\s+)?"
        r"(?:remember(?:\s+that)?|save(?:\s+that)?"
        r"|what\s+is\s+my|what'?s\s+my|do\s+you\s+remember|recall"
        r"|what\s+did\s+i(?:\s+just)?\s+tell\s+you|what\s+was\s+that"
        r").*",
        re.IGNORECASE,
    )

    # ── TOOL: direct OS/app commands ───────────────────────────────────────────
    _TOOL_PATTERN = re.compile(
        r"^(?:please\s+|can\s+you\s+|could\s+you\s+|would\s+you\s+)?"
        r"(?:open|launch|run|start|close|search|create|delete|execute)\s+.*"
        r"|.*?\b(?:open|launch|start)\s+(?:the\s+)?(?:calculator|calc|notepad|browser|github|terminal|cmd|chrome|app)\b.*",
        re.IGNORECASE,
    )

    # ── MISSION: complex autonomous tasks ──────────────────────────────────────
    # Stage 1 MISSION signals — each is a strong indicator of deep work
    _MISSION_SIGNALS = re.compile(
        r"""
        # Direct mission keywords
        (?:plan\s+and\s+execute|autonomous\s+mission|start\s+mission)
        |
        # "research/investigate/analyze/explore/study X and produce Y"
        (?:research|investigate|analyze|explore|study)\s+.+?
        (?:and\s+(?:give|write|provide|produce|generate|create)\s+.+?(?:report|summary|document|analysis)|in\s+detail|in\s+depth)
        |
        # "create/build/generate/write/produce [a/an/the] [complete/full/detailed] [big artifact]"
        (?:create|build|generate|refactor|write|produce)\s+
        (?:a\s+|an\s+|the\s+)?(?:complete\s+|full\s+|detailed\s+|comprehensive\s+)?
        (?:documentary|saas(?:\s+app)?|animation|business\s+plan|game|video|repository|repo|report|codebase|website|app(?:lication)?)
        |
        # "deeply/thoroughly/comprehensively do X and Y"
        (?:deeply|thoroughly|comprehensively|extensively)\s+
        (?:research|analyze|investigate|study|explore|review)\s+.+?
        (?:and\s+(?:produce|write|create|generate|provide)\s+.+?(?:report|analysis|document|summary))?
        |
        # "produce/write a detailed/comprehensive report/analysis"
        (?:produce|write|create|generate)\s+a\s+
        (?:detailed|comprehensive|complete|in-depth)\s+
        (?:report|analysis|document|summary)
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    # ── CHAT: obvious greetings and smalltalk ─────────────────────────────────
    _CHAT_PATTERN = re.compile(
        r"^(?:hi|hello|hey|who\s+are\s+you|thank(?:\s+you|s)?|how\s+are\s+you"
        r"|tell\s+me\s+a\s+joke|what\s+can\s+you\s+do|good\s+(?:morning|afternoon|evening)"
        r"|what'?s\s+up|howdy)[\\s\\?\\!\\.]*$",
        re.IGNORECASE,
    )

    # ── CLASSIFIER LLM PROMPT ─────────────────────────────────────────────────
    _CLASSIFY_SYSTEM = (
        "You are a request classifier for an AI assistant. "
        "Classify the user input into exactly one of: CHAT, MEMORY, TOOL, MISSION. "
        "CHAT = conversation/questions. "
        "MEMORY = storing or recalling personal facts. "
        "TOOL = direct OS/app command (open, search, create file). "
        "MISSION = complex multi-step research, analysis, content creation, or autonomous goal. "
        "Reply with ONLY the single word category, nothing else."
    )

    def __init__(self, llm_client: Optional[Any] = None):
        """
        Args:
            llm_client: Optional LLMClient for Stage 2 ambiguous classification.
                        If None, ambiguous inputs fall back to CHAT.
        """
        self._llm = llm_client

    def classify(self, user_input: str) -> IntentType:
        """Classify the intent of the user input.

        Stage 1: deterministic regex (always runs first, always fast).
        Stage 2: LLM call only for inputs that don't match any Stage 1 rule.

        MUST NEVER invoke ExecutiveBrain, ReasoningLoop, or MissionControl.
        """
        cleaned = user_input.strip()

        # ── Stage 1: deterministic rules ──────────────────────────────────────
        # Ordering matters: MEMORY before TOOL to avoid "remember" matching tool pattern
        if self._MEMORY_PATTERN.match(cleaned):
            logger.debug("[CLASSIFIER] Stage1 → MEMORY")
            return IntentType.MEMORY

        if self._MISSION_SIGNALS.search(cleaned):
            logger.debug("[CLASSIFIER] Stage1 → MISSION")
            return IntentType.MISSION

        if self._TOOL_PATTERN.match(cleaned):
            logger.debug("[CLASSIFIER] Stage1 → TOOL")
            return IntentType.TOOL

        if self._CHAT_PATTERN.match(cleaned):
            logger.debug("[CLASSIFIER] Stage1 → CHAT (greeting)")
            return IntentType.CHAT

        # ── Stage 2: LLM disambiguation ───────────────────────────────────────
        # Only for genuinely ambiguous inputs. Falls back to CHAT on any failure.
        if self._llm is not None:
            try:
                response = self._llm.generate(
                    self._CLASSIFY_SYSTEM,
                    f'Classify: "{cleaned}"',
                )
                text = (response.text if hasattr(response, "text") else str(response)).strip().upper()
                for candidate in ("MISSION", "MEMORY", "TOOL", "CHAT"):
                    if candidate in text:
                        logger.info("[CLASSIFIER] Stage2 → %s (LLM)", candidate)
                        return IntentType(candidate.lower())
            except Exception as exc:
                logger.warning("[CLASSIFIER] Stage2 LLM failed (%s). Defaulting to CHAT.", exc)

        # ── Default: CHAT ──────────────────────────────────────────────────────
        # ConversationEngine handles arbitrary natural language gracefully.
        logger.debug("[CLASSIFIER] Default → CHAT")
        return IntentType.CHAT
