"""Tests for the JARVIS Identity Layer subsystem."""

from unittest.mock import MagicMock

from core.cognition.dialogue import DialogueState
from core.identity.context import IdentityContextBuilder
from core.identity.guardrails import GuardrailEngine
from core.identity.manager import IdentityManager
from core.identity.models import IdentityContext, PersonaTrait
from core.identity.persona import Persona
from core.identity.prompt_builder import PromptBuilder

# ── Persona ──────────────────────────────────────────────────────


def test_persona_returns_all_traits() -> None:
    persona = Persona()
    traits = persona.get_traits()
    assert len(traits) == 9
    assert all(isinstance(t, PersonaTrait) for t in traits)


def test_persona_identity_statement_contains_jarvis() -> None:
    persona = Persona()
    statement = persona.get_identity_statement()
    assert "JARVIS" in statement
    assert "AI Operating System" in statement


def test_persona_rules_ordered_by_priority() -> None:
    persona = Persona()
    rules = persona.get_rules()
    priorities = [r.priority for r in rules]
    assert priorities == sorted(priorities, reverse=True)


# ── GuardrailEngine ─────────────────────────────────────────────


def test_guardrail_rewrites_qwen_disclosure() -> None:
    engine = GuardrailEngine()
    result = engine.apply("I am Qwen, a large language model.")
    assert "JARVIS" in result
    assert "Qwen" not in result


def test_guardrail_rewrites_gpt_disclosure() -> None:
    engine = GuardrailEngine()
    result = engine.apply("I'm GPT and I can help you.")
    assert "JARVIS" in result
    assert "GPT" not in result


def test_guardrail_rewrites_generic_ai_disclaimer() -> None:
    engine = GuardrailEngine()
    result = engine.apply("As an AI language model, I cannot do that.")
    assert "AI operating system" in result
    assert "AI language model" not in result


def test_guardrail_rewrites_preference_disclaimer() -> None:
    engine = GuardrailEngine()
    result = engine.apply("I don't have personal preferences but I can help.")
    assert "personal preferences" not in result
    assert "best approach" in result


def test_guardrail_preserves_clean_response() -> None:
    engine = GuardrailEngine()
    clean = "I'll open Notepad for you right away."
    assert engine.apply(clean) == clean


def test_guardrail_handles_empty_string() -> None:
    engine = GuardrailEngine()
    assert engine.apply("") == ""


# ── IdentityContextBuilder ───────────────────────────────────────


def test_context_builder_produces_valid_context() -> None:
    persona = Persona()
    builder = IdentityContextBuilder(persona, "qwen3:8b", "ollama")
    ctx = builder.build()
    assert isinstance(ctx, IdentityContext)
    assert ctx.active_model == "qwen3:8b"
    assert ctx.active_provider == "ollama"
    assert "JARVIS" in ctx.identity_statement
    assert len(ctx.traits) == 9
    assert len(ctx.rules) > 0


# ── PromptBuilder ────────────────────────────────────────────────


def test_prompt_builder_includes_persona_and_tools() -> None:
    persona = Persona()
    builder = IdentityContextBuilder(persona, "test-model", "test-provider")
    ctx = builder.build()
    pb = PromptBuilder(ctx)
    state = DialogueState()
    prompt = pb.build_conversation_prompt(state, "Tool: browser\n  - Action: open_site")
    assert "JARVIS" in prompt
    assert "browser" in prompt
    assert "open_site" in prompt


def test_prompt_builder_includes_model_disclosure_policy() -> None:
    persona = Persona()
    builder = IdentityContextBuilder(persona, "qwen3:8b", "ollama")
    ctx = builder.build()
    pb = PromptBuilder(ctx)
    state = DialogueState()
    prompt = pb.build_conversation_prompt(state, "")
    assert "qwen3:8b" in prompt
    assert "ollama" in prompt
    assert "Model Disclosure" in prompt


def test_prompt_builder_includes_behavioural_rules() -> None:
    persona = Persona()
    builder = IdentityContextBuilder(persona, "test", "test")
    ctx = builder.build()
    pb = PromptBuilder(ctx)
    state = DialogueState()
    prompt = pb.build_conversation_prompt(state, "")
    assert "Behavioural Rules" in prompt
    assert "Never identify as Qwen" in prompt


def test_prompt_builder_planner_prompt() -> None:
    persona = Persona()
    builder = IdentityContextBuilder(persona, "test", "test")
    ctx = builder.build()
    pb = PromptBuilder(ctx)
    prompt = pb.build_planner_prompt("Tool: windows\n  - open_app", "context here")
    assert "JARVIS" in prompt
    assert "windows" in prompt
    assert "context here" in prompt
    assert "JSON" in prompt


# ── IdentityManager ──────────────────────────────────────────────


def test_identity_manager_build_system_prompt() -> None:
    mgr = IdentityManager(active_model="llama3", active_provider="ollama")
    state = DialogueState()
    prompt = mgr.build_system_prompt(state, "Tool: file\n  - Action: create_file")
    assert "JARVIS" in prompt
    assert "file" in prompt
    assert "llama3" in prompt
    assert "Behavioural Rules" in prompt


def test_identity_manager_build_planner_prompt() -> None:
    mgr = IdentityManager(active_model="gpt-4", active_provider="openai")
    prompt = mgr.build_planner_prompt("Tool: browser\n  - open_site", "")
    assert "JARVIS" in prompt
    assert "browser" in prompt
    assert "JSON" in prompt


def test_identity_manager_apply_guardrails() -> None:
    mgr = IdentityManager(active_model="test", active_provider="test")
    result = mgr.apply_guardrails("I am Qwen and I can help.")
    assert "JARVIS" in result
    assert "Qwen" not in result


def test_identity_manager_preserves_clean_text() -> None:
    mgr = IdentityManager(active_model="test", active_provider="test")
    clean = "Here is your file listing."
    assert mgr.apply_guardrails(clean) == clean


def test_identity_manager_get_context() -> None:
    mgr = IdentityManager(active_model="qwen3:8b", active_provider="ollama")
    ctx = mgr.get_identity_context()
    assert isinstance(ctx, IdentityContext)
    assert ctx.active_model == "qwen3:8b"


# ── Integration with ConversationEngine ──────────────────────────


def test_conversation_engine_uses_identity_manager() -> None:
    """Verify ConversationEngine delegates to IdentityManager and
    that guardrails are applied to the response message."""
    from core.cognition.context import ShortTermContext
    from core.cognition.conversation import ConversationEngine
    from providers.provider_models import ModelResponse, TokenUsage

    identity = IdentityManager(active_model="test-model", active_provider="test")
    router = MagicMock()
    registry = MagicMock()
    registry.list_tools.return_value = []

    # Simulate LLM returning a response that includes "I am Qwen"
    router.generate.return_value = ModelResponse(
        text='{"type": "RESPONSE", "message": "I am Qwen and I can help you."}',
        provider_id="test",
        model_id="test-model",
        latency_ms=100,
        token_usage=TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30),
        cost=0.0,
    )

    engine = ConversationEngine(router, registry, identity=identity)
    context = ShortTermContext()
    state = DialogueState()

    response = engine.process("hello", context, state)

    # Guardrail should have rewritten "I am Qwen" to "I am JARVIS"
    assert "JARVIS" in response.message
    assert "Qwen" not in response.message
    assert response.type == "RESPONSE"
