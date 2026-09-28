"""
Cognition subsystem unit tests.

Covers: ConversationEngine, ContextBuilder, ContextOrchestrator,
        MemoryRetriever, and CognitiveManager.

All external dependencies (LLM, memory, providers) are mocked so tests
run fast with zero network calls.
"""

import json
import pytest
from unittest.mock import MagicMock, patch, call

from providers.provider_models import ModelResponse
from core.cognition.conversation import ConversationEngine, ConversationResponse
from core.cognition.context_builder import ContextBuilder
from core.cognition.context_models import ProviderType, ContextPackage
from core.cognition.context_orchestrator import ContextOrchestrator
from core.cognition.context import ShortTermContext
from core.cognition.retrieval import MemoryRetriever
from core.cognition.manager import CognitiveManager
from core.cognition.dialogue import DialogueState


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_model_response(text: str) -> ModelResponse:
    return ModelResponse(text=text, provider_id="mock", model_id="mock", latency_ms=1)


def _make_router(text: str):
    """Return a ModelRouter mock that produces `text` on generate()."""
    router = MagicMock()
    router.generate.return_value = _make_model_response(text)
    return router


def _make_identity():
    identity = MagicMock()
    identity.build_system_prompt.return_value = "SYS"
    identity.apply_guardrails.side_effect = lambda x: x
    return identity


def _make_registry():
    registry = MagicMock()
    registry.describe.return_value = "Tool: browser\n  - open_url: opens URL"
    return registry


# ─── ConversationEngine tests ─────────────────────────────────────────────────

class TestConversationEngine:

    def _engine(self, llm_text: str) -> ConversationEngine:
        return ConversationEngine(
            model_router=_make_router(llm_text),
            registry=_make_registry(),
            identity=_make_identity(),
        )

    def test_chat_response_returns_response_type(self):
        """A conversational JSON response maps to RESPONSE type."""
        payload = json.dumps({"type": "RESPONSE", "message": "Hello, human!"})
        engine = self._engine(payload)
        resp = engine.process("Hi", DialogueState())
        assert resp.type == "RESPONSE"
        assert resp.message == "Hello, human!"
        assert resp.tool is None

    def test_action_response_includes_tool_and_action(self):
        """An ACTION JSON response carries tool, action, and parameters."""
        payload = json.dumps({
            "type": "ACTION",
            "message": "Opening calculator.",
            "tool": "windows",
            "action": "open_app",
            "parameters": {"app": "calculator"},
        })
        engine = self._engine(payload)
        resp = engine.process("Open calculator", DialogueState())
        assert resp.type == "ACTION"
        assert resp.tool == "windows"
        assert resp.action == "open_app"
        assert resp.parameters == {"app": "calculator"}

    def test_malformed_json_falls_back_to_response(self):
        """Completely invalid JSON never raises — returns safe RESPONSE."""
        engine = self._engine("this is not json at all !!!")
        resp = engine.process("anything", DialogueState())
        assert resp.type == "RESPONSE"
        assert isinstance(resp.message, str)
        assert len(resp.message) > 0

    def test_partial_json_with_message_key_extracted(self):
        """Partial JSON with a message key is salvaged."""
        engine = self._engine('{"message": "Here is the answer", "type": "RESPONSE"}')
        resp = engine.process("What is 2+2?", DialogueState())
        assert resp.type == "RESPONSE"
        assert "answer" in resp.message

    def test_action_with_missing_tool_demoted_to_response(self):
        """ACTION payload missing tool string is safely demoted to RESPONSE."""
        payload = json.dumps({
            "type": "ACTION",
            "message": "Let me help.",
            "tool": None,
            "action": None,
            "parameters": {},
        })
        engine = self._engine(payload)
        resp = engine.process("Do something", DialogueState())
        assert resp.type == "RESPONSE"
        assert resp.tool is None

    def test_llm_failure_returns_graceful_response(self):
        """If the LLM raises an exception, a graceful RESPONSE is returned."""
        router = MagicMock()
        router.generate.side_effect = RuntimeError("LLM is down")
        engine = ConversationEngine(router, _make_registry(), _make_identity())
        resp = engine.process("Hello", DialogueState())
        assert resp.type == "RESPONSE"
        assert isinstance(resp.message, str)


# ─── ContextBuilder tests ────────────────────────────────────────────────────

class TestContextBuilder:

    def _builder(self):
        return ContextBuilder()

    def test_chat_intent_returns_conversation_and_tool(self):
        providers = self._builder().determine_providers(intent="chat")
        assert ProviderType.CONVERSATION in providers
        assert ProviderType.TOOL in providers
        # CHAT should NOT pull memory by default
        assert ProviderType.MEMORY not in providers

    def test_memory_intent_includes_memory_and_pki(self):
        providers = self._builder().determine_providers(intent="memory")
        assert ProviderType.MEMORY in providers
        assert ProviderType.PKI in providers
        assert ProviderType.CONVERSATION in providers

    def test_tool_intent_returns_tool_and_conversation(self):
        providers = self._builder().determine_providers(intent="tool")
        assert ProviderType.TOOL in providers
        assert ProviderType.CONVERSATION in providers

    def test_mission_intent_returns_full_set(self):
        providers = self._builder().determine_providers(intent="mission")
        expected = {
            ProviderType.MEMORY, ProviderType.PKI, ProviderType.MISSION,
            ProviderType.PROJECT, ProviderType.WORKSPACE,
            ProviderType.TOOL, ProviderType.CONVERSATION,
        }
        assert expected.issubset(providers)

    def test_plan_flags_override_intent(self):
        """A plan with requires_knowledge=True forces PKI regardless of intent."""
        plan = MagicMock()
        plan.requires_knowledge = True
        plan.required_missions = []
        plan.required_tools = []
        plan.requires_project = False
        providers = self._builder().determine_providers(plan=plan, intent="chat")
        assert ProviderType.PKI in providers

    def test_no_llm_call_ever_made(self):
        """ContextBuilder must never call an LLM (no llm attribute)."""
        builder = ContextBuilder()
        assert not hasattr(builder, "_llm") or getattr(builder, "_llm", None) is None
        # Call it multiple times — no LLM interaction expected
        for intent in ("chat", "tool", "memory", "mission"):
            builder.determine_providers(intent=intent)


# ─── ContextOrchestrator tests ───────────────────────────────────────────────

class TestContextOrchestrator:

    def _orchestrator(self, memory_results=None):
        wp = MagicMock()
        wp.gather.return_value = []
        mp = MagicMock()
        mp.gather.return_value = []
        pp = MagicMock()
        pp.gather.return_value = []
        tp = MagicMock()
        tp.gather.return_value = []
        mr = MagicMock()
        mr.retrieve.return_value = memory_results or []
        return ContextOrchestrator(
            workspace_provider=wp,
            mission_provider=mp,
            project_provider=pp,
            tool_provider=tp,
            memory_retriever=mr,
        )

    def _context(self):
        ctx = ShortTermContext()
        ctx.add_message("user", "test")
        return ctx

    def test_builds_context_package_for_chat(self):
        orch = self._orchestrator()
        pkg = orch.build("Hello", self._context(), intent="chat")
        assert isinstance(pkg, ContextPackage)

    def test_memory_retriever_not_called_for_chat(self):
        """For CHAT intent, memory retriever should NOT be invoked (no MEMORY provider)."""
        wp = MagicMock(); wp.gather.return_value = []
        mp = MagicMock(); mp.gather.return_value = []
        pp = MagicMock(); pp.gather.return_value = []
        tp = MagicMock(); tp.gather.return_value = []
        mr = MagicMock(); mr.retrieve.return_value = []

        orch = ContextOrchestrator(
            workspace_provider=wp, mission_provider=mp,
            project_provider=pp, tool_provider=tp, memory_retriever=mr,
        )
        orch.build("Hello", self._context(), intent="chat")
        mr.retrieve.assert_not_called()

    def test_memory_retriever_called_for_memory_intent(self):
        """For MEMORY intent, memory retriever MUST be invoked."""
        mr = MagicMock()
        mr.retrieve.return_value = []
        orch = self._orchestrator()
        orch._memory_retriever = mr
        orch.build("What is my name?", self._context(), intent="memory")
        mr.retrieve.assert_called_once()

    def test_provider_failure_returns_empty_package(self):
        """If a provider throws, orchestrator returns an empty ContextPackage."""
        tp = MagicMock()
        tp.gather.side_effect = RuntimeError("tool provider crashed")
        mr = MagicMock(); mr.retrieve.return_value = []
        orch = ContextOrchestrator(
            workspace_provider=MagicMock(gather=MagicMock(return_value=[])),
            mission_provider=MagicMock(gather=MagicMock(return_value=[])),
            project_provider=MagicMock(gather=MagicMock(return_value=[])),
            tool_provider=tp,
            memory_retriever=mr,
        )
        pkg = orch.build("Hello", self._context(), intent="chat")
        assert isinstance(pkg, ContextPackage)


# ─── MemoryRetriever tests ───────────────────────────────────────────────────

class TestMemoryRetriever:

    def _retriever(self, llm_response="[]"):
        llm = MagicMock()
        llm.generate.return_value = _make_model_response(llm_response)
        mm = MagicMock()
        mm._memory = MagicMock()
        mm._memory.get_all_facts.return_value = {}
        mm._memory.search.return_value = []
        km = MagicMock()
        km.search.return_value = []
        return MemoryRetriever(llm, mm, km)

    def test_greeting_returns_empty_without_llm(self):
        """Greetings skip retrieval entirely — no LLM call for search queries."""
        r = self._retriever()
        results = r.retrieve("hi")
        assert results == []
        r._llm.generate.assert_not_called()

    def test_memory_keyword_triggers_retrieval_path(self):
        """A memory keyword causes the retrieval path to run."""
        r = self._retriever(llm_response='["my name"]')
        r.retrieve("what is my name?")
        # LLM should have been called for query generation
        r._llm.generate.assert_called_once()

    def test_llm_failure_returns_user_input_as_query(self):
        """If LLM fails, we fall back to using user_input as the search query."""
        r = self._retriever()
        r._llm.generate.side_effect = RuntimeError("LLM down")
        # Should not raise; returns either [] or results from fallback
        try:
            results = r.retrieve("remember my password")
            assert isinstance(results, list)
        except Exception as exc:
            pytest.fail(f"retrieve() should not raise: {exc}")


# ─── CognitiveManager tests ──────────────────────────────────────────────────

class TestCognitiveManager:

    def _manager(self, llm_text: str):
        engine = MagicMock()
        engine.process.return_value = ConversationResponse(
            type="RESPONSE", message=llm_text
        )
        orch = MagicMock()
        orch.build.return_value = ContextPackage()
        reflection = MagicMock()
        event_bus = MagicMock()
        event_bus.publish.return_value = None
        context = ShortTermContext()

        return CognitiveManager(
            conversation_engine=engine,
            reflection=reflection,
            context_orchestrator=orch,
            context=context,
            event_bus=event_bus,
        ), engine, orch, reflection

    def test_process_fast_calls_engine_once(self):
        mgr, engine, orch, refl = self._manager("Hello!")
        resp = mgr.process_fast("Hi")
        assert resp.type == "RESPONSE"
        engine.process.assert_called_once()

    def test_process_fast_passes_chat_intent_to_orchestrator(self):
        mgr, engine, orch, refl = self._manager("Hello!")
        mgr.process_fast("Hi", intent="chat")
        call_kwargs = orch.build.call_args
        assert call_kwargs.kwargs.get("intent") == "chat"

    def test_process_passes_tool_intent_to_orchestrator(self):
        mgr, engine, orch, refl = self._manager("Opening calc.")
        mgr.process("Open calculator", intent="tool")
        call_kwargs = orch.build.call_args
        assert call_kwargs.kwargs.get("intent") == "tool"

    def test_reflect_is_separate_from_process(self):
        """reflect() must not be called inside process_fast() automatically."""
        mgr, engine, orch, refl = self._manager("Hi!")
        mgr.process_fast("Hi")
        # reflect is called by Agent.run(), not by CognitiveManager itself
        refl.reflect_on_conversation.assert_not_called()
