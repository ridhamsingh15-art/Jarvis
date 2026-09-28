"""
Critical Second-Pass Routing & Bug Regression Test Suite.
Tests:
1. "Hi" -> CHAT, 1 LLM call, ExecutiveBrain/ReasoningLoop/MissionControl NOT used.
2. "Why do people enjoy watching documentaries?" -> CHAT, ExecutiveBrain/ReasoningLoop/MissionControl NOT used.
3. "Remember that my favorite IDE is Antigravity." -> MEMORY, ExecutiveBrain/ReasoningLoop NOT used, fast fact storage.
4. "What did I just tell you?" -> MEMORY conversational context, ExecutiveBrain/ReasoningLoop NOT used.
5. "Open the calculator" -> TOOL, windows.open_app executed, ExecutiveBrain/ReasoningLoop/MissionControl NOT used.
6. "Open GitHub" -> TOOL, browser.open_site executed, site normalization works for 'github.com', 'Open GitHub', etc.
7. "Research the history of artificial intelligence and give me a detailed report" -> MISSION, ExecutiveBrain/ReasoningLoop/MissionControl used, but NOT to classify.
8. Malformed LLM JSON response -> Controlled failure, NEVER executes unintended tools.
9. Bug 1 Regression: KnowledgeSearchResult schema (document.path, chunk.text).
10. Bug 2 Regression: Browser normalization (github, github.com, https://github.com, etc.).
11. Bug 3 Regression: Multi-threaded SQLite access to SqliteMissionRepository without thread affinity error.
"""

import threading
import tempfile
import os
from unittest.mock import Mock, MagicMock, patch
import pytest

from core.agent import Agent
from core.routing.intent_classifier import IntentClassifier, IntentType
from core.task import Task
from core.cognition.conversation import ConversationEngine, ConversationResponse
from core.cognition.dialogue import DialogueState
from core.identity.manager import IdentityManager
from tools.browser import BrowserTool
from core.exceptions import ExecutionError
from core.mission.repository import SqliteMissionRepository
from core.mission.models import Mission
from core.cognition.retrieval import MemoryRetriever, RetrievedMemory
from core.knowledge.indexer.registry import KnowledgeDocument, KnowledgeChunk, KnowledgeSearchResult


class TestSecondPassAcceptance:

    def test_acceptance_1_hi(self):
        """1. 'Hi' -> ROUTE=CHAT, ExecutiveBrain=NO, ReasoningLoop=NO, MissionControl=NO, LLM calls ≈ 1."""
        mock_cognitive = Mock()
        mock_cognitive.process_fast.return_value = ConversationResponse(type="RESPONSE", message="Hello! How can I help you today?")
        mock_planner = Mock()
        mock_validator = Mock()
        mock_executor = Mock()

        agent = Agent(
            planner=mock_planner,
            validator=mock_validator,
            executor=mock_executor,
            cognitive_manager=mock_cognitive,
        )
        agent._process_task = lambda t: t

        tasks = agent.run("Hi")

        assert len(tasks) == 1
        assert tasks[0].action == "respond"
        assert tasks[0].args["message"] == "Hello! How can I help you today?"
        mock_cognitive.process_fast.assert_called_once_with("Hi", intent="chat")
        # Ensure heavy engines were NOT used
        mock_planner.plan.assert_not_called()

    def test_acceptance_2_documentary_chat(self):
        """2. 'Why do people enjoy watching documentaries?' -> ROUTE=CHAT, ExecutiveBrain=NO, ReasoningLoop=NO, MissionControl=NO."""
        mock_cognitive = Mock()
        mock_cognitive.process_fast.return_value = ConversationResponse(
            type="RESPONSE",
            message="People enjoy documentaries because they provide deep insights into real-world events and knowledge."
        )
        mock_planner = Mock()

        agent = Agent(
            planner=mock_planner,
            validator=Mock(),
            executor=Mock(),
            cognitive_manager=mock_cognitive,
        )
        agent._process_task = lambda t: t

        tasks = agent.run("Why do people enjoy watching documentaries?")

        assert len(tasks) == 1
        assert tasks[0].action == "respond"
        mock_cognitive.process_fast.assert_called_once_with("Why do people enjoy watching documentaries?", intent="chat")
        mock_planner.plan.assert_not_called()

    def test_acceptance_3_remember_favorite_ide(self):
        """3. 'Remember that my favorite IDE is Antigravity.' -> ROUTE=MEMORY, ExecutiveBrain=NO, ReasoningLoop=NO, Fast execution."""
        mock_memory = Mock()
        mock_cognitive = Mock()
        mock_planner = Mock()

        agent = Agent(
            planner=mock_planner,
            validator=Mock(),
            executor=Mock(),
            memory=mock_memory,
            cognitive_manager=mock_cognitive,
        )
        agent._process_task = lambda t: t

        tasks = agent.run("Remember that my favorite IDE is Antigravity.")

        assert len(tasks) == 1
        assert "Antigravity" in tasks[0].args["message"]
        mock_memory.remember_fact.assert_called_once_with("favorite ide", "Antigravity")
        mock_planner.plan.assert_not_called()
        mock_cognitive.process.assert_not_called()

    def test_acceptance_4_what_did_i_just_tell_you(self):
        """4. 'What did I just tell you?' -> ROUTE=MEMORY, ExecutiveBrain=NO, ReasoningLoop=NO."""
        mock_memory = Mock()
        mock_cognitive = Mock()
        mock_cognitive.process_fast.return_value = ConversationResponse(
            type="RESPONSE",
            message="You just told me that your favorite IDE is Antigravity."
        )
        mock_planner = Mock()

        agent = Agent(
            planner=mock_planner,
            validator=Mock(),
            executor=Mock(),
            memory=mock_memory,
            cognitive_manager=mock_cognitive,
        )
        agent._process_task = lambda t: t

        tasks = agent.run("What did I just tell you?")

        assert len(tasks) == 1
        assert "Antigravity" in tasks[0].args["message"]
        mock_cognitive.process_fast.assert_called_once()
        mock_planner.plan.assert_not_called()

    def test_acceptance_5_open_the_calculator(self):
        """5. 'Open the calculator' -> ROUTE=TOOL, ExecutiveBrain=NO, ReasoningLoop=NO, MissionControl=NO, windows.open_app executes."""
        mock_cognitive = Mock()
        mock_cognitive.process_fast.return_value = ConversationResponse(
            type="ACTION",
            message="Opening the calculator.",
            tool="windows",
            action="open_app",
            parameters={"app": "calculator"}
        )
        mock_validator = Mock()
        mock_executor = Mock()
        mock_executor.execute.side_effect = lambda t: t

        agent = Agent(
            planner=Mock(),
            validator=mock_validator,
            executor=mock_executor,
            cognitive_manager=mock_cognitive,
        )

        tasks = agent.run("Open the calculator")

        assert len(tasks) == 2
        assert tasks[0].args["message"] == "Opening the calculator."
        assert tasks[1].tool == "windows"
        assert tasks[1].action == "open_app"
        mock_validator.validate.assert_called_once()
        mock_executor.execute.assert_called_once()

    def test_acceptance_6_open_github(self):
        """6. 'Open GitHub' -> ROUTE=TOOL, ExecutiveBrain=NO, ReasoningLoop=NO, browser.open_site executes."""
        mock_cognitive = Mock()
        mock_cognitive.process_fast.return_value = ConversationResponse(
            type="ACTION",
            message="Opening GitHub.",
            tool="browser",
            action="open_site",
            parameters={"site": "github"}
        )
        mock_validator = Mock()
        mock_executor = Mock()
        mock_executor.execute.side_effect = lambda t: t

        agent = Agent(
            planner=Mock(),
            validator=mock_validator,
            executor=mock_executor,
            cognitive_manager=mock_cognitive,
        )

        tasks = agent.run("Open GitHub")

        assert len(tasks) == 2
        assert tasks[1].tool == "browser"
        assert tasks[1].action == "open_site"
        assert tasks[1].args["site"] == "github"
        mock_validator.validate.assert_called_once()
        mock_executor.execute.assert_called_once()

    def test_acceptance_7_research_mission(self):
        """7. 'Research the history of artificial intelligence and give me a detailed report' -> ROUTE=MISSION.
        ExecutiveBrain / Mission path used, but initial route classification does NOT invoke ExecutiveBrain."""
        classifier = IntentClassifier()
        # Initial routing must be MISSION without any LLM/ExecutiveBrain
        assert classifier.classify("Research the history of artificial intelligence and give me a detailed report") == IntentType.MISSION

    def test_acceptance_8_malformed_llm_json_never_executes_tool(self):
        """8. Malformed LLM JSON response -> Controlled failure, NEVER executes unintended tools."""
        mock_router = Mock()
        # Malformed JSON with delimiter error
        mock_router.generate.return_value = Mock(text='{"type": "ACTION", "tool": "windows", "action": "delete_all", "parameters": }')
        identity = IdentityManager(active_model="qwen2.5:7b", active_provider="ollama")
        engine = ConversationEngine(model_router=mock_router, registry=Mock(), identity=identity)

        response = engine.process("Run dangerous command", DialogueState(), context_package=None)

        # Must NOT be an ACTION
        assert response.type == "RESPONSE"
        assert response.tool is None
        assert response.action is None
        assert any(word in response.message.lower() for word in ["trouble", "rephrase", "again", "formatting"])


class TestBugRegressions:

    def test_bug_1_knowledge_search_result_schema(self):
        """Bug 1 Regression: Retrieval must access pki.document.path and pki.chunk.text, not pki.filepath."""
        mock_km = Mock()
        doc = KnowledgeDocument(
            id="doc-1",
            path="C:/docs/ai_history.txt",
            filename="ai_history.txt",
            extension=".txt",
            file_type="text",
            size_bytes=100,
            last_modified=0.0,
            last_indexed=0.0,
            metadata={}
        )
        chunk = KnowledgeChunk(id="c-1", document_id="doc-1", text="AI was founded as an academic discipline in 1956.")
        search_result = KnowledgeSearchResult(document=doc, chunk=chunk, score=0.95)
        mock_km.search.return_value = [search_result]

        retriever = MemoryRetriever(
            memory_manager=Mock(search=Mock(return_value=[])),
            knowledge_manager=mock_km,
            llm_client=Mock(generate=Mock(return_value=Mock(text='["history of artificial intelligence"]')))
        )

        results = retriever.retrieve("search my document for history of artificial intelligence")
        pki_results = [r for r in results if r.source == "pki"]

        assert len(pki_results) == 1
        assert "Document (C:/docs/ai_history.txt): AI was founded as an academic discipline in 1956." in pki_results[0].content

    @pytest.mark.parametrize("site_input,expected_url", [
        ("github", "https://github.com"),
        ("github.com", "https://github.com"),
        ("GitHub", "https://github.com"),
        ("open github.com", "https://github.com"),
        ("https://github.com", "https://github.com"),
        ("www.github.com", "https://github.com"),
        ("google", "https://www.google.com"),
        ("youtube.com", "https://www.youtube.com"),
    ])
    def test_bug_2_browser_site_normalization(self, site_input, expected_url):
        """Bug 2 Regression: BrowserTool._open_site must normalize sites and domains cleanly."""
        with patch("webbrowser.open") as mock_open:
            result = BrowserTool._open_site({"site": site_input})
            assert "Opened" in result
            mock_open.assert_called_once_with(expected_url)

    def test_bug_2_browser_unknown_site_still_raises(self):
        """Bug 2 Regression: Truly unknown site without domain raises ExecutionError."""
        with pytest.raises(ExecutionError) as exc_info:
            BrowserTool._open_site({"site": "completely_unknown_site_name"})
        assert "Unknown site" in str(exc_info.value)

    def test_bug_3_sqlite_thread_safety(self):
        """Bug 3 Regression: SqliteMissionRepository must support multi-threaded access without thread affinity error."""
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            repo = SqliteMissionRepository(db_path)
            errors = []

            def worker(thread_id: int):
                try:
                    for i in range(5):
                        m = Mission(title=f"Task from thread {thread_id} step {i}")
                        repo.save(m)
                        loaded = repo.get(m.mission_id.value)
                        assert loaded.title == m.title
                        assert repo.exists(m.mission_id.value)
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=worker, args=(t,)) for t in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(errors) == 0, f"Thread errors encountered: {errors}"
            missions = repo.list()
            assert len(missions) == 25
        finally:
            try:
                os.remove(db_path)
            except Exception:
                pass
