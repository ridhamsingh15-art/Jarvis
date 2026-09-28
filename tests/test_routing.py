"""
Tests for Fast Intent Router and optimized execution pipeline.
"""
import pytest
from unittest.mock import Mock, patch

from core.routing.intent_classifier import IntentClassifier, IntentType
from core.agent import Agent
from core.task import Task

class TestIntentClassifier:
    
    def test_deterministic_chat(self):
        classifier = IntentClassifier()
        assert classifier.classify("Hi") == IntentType.CHAT
        assert classifier.classify("Hello!!") == IntentType.CHAT
        assert classifier.classify("Who are you?") == IntentType.CHAT
        
    def test_deterministic_memory(self):
        classifier = IntentClassifier()
        assert classifier.classify("Remember that my name is Ridham") == IntentType.MEMORY
        assert classifier.classify("Do you remember my project?") == IntentType.MEMORY
        
    def test_deterministic_tool(self):
        classifier = IntentClassifier()
        assert classifier.classify("Open notepad") == IntentType.TOOL
        assert classifier.classify("Create folder C:/test") == IntentType.TOOL
        assert classifier.classify("delete file.txt") == IntentType.TOOL
        
    def test_deterministic_mission(self):
        classifier = IntentClassifier()
        assert classifier.classify("Create a SaaS application") == IntentType.MISSION
        assert classifier.classify("Build a game") == IntentType.MISSION
        assert classifier.classify("Generate a documentary") == IntentType.MISSION
        
    def test_llm_fallback(self):
        """Ambiguous inputs invoke Stage 2 LLM classification."""
        mock_llm = Mock()
        # Simulate the LLM returning "CHAT" for an ambiguous query
        mock_llm.generate.return_value = Mock(text="CHAT")
        classifier = IntentClassifier(llm_client=mock_llm)

        # Ambiguous input not covered by regex — should trigger Stage 2
        result = classifier.classify("Why is the sky blue?")
        assert result == IntentType.CHAT
        # Stage 2 was invoked
        mock_llm.generate.assert_called_once()

class TestAgentRouting:
    
    @patch("core.agent.IntentClassifier")
    def test_chat_bypasses_planning(self, mock_classifier_class):
        mock_classifier = mock_classifier_class.return_value
        mock_classifier.classify.return_value = IntentType.CHAT
        
        mock_cognitive = Mock()
        mock_cognitive.process_fast.return_value = Mock(message="I am JARVIS.", type="RESPONSE")
        
        mock_planner = Mock()
        mock_executor = Mock()
        mock_validator = Mock()
        
        agent = Agent(
            planner=mock_planner,
            validator=mock_validator,
            executor=mock_executor,
            cognitive_manager=mock_cognitive
        )
        
        # We need to mock _process_task to avoid deep execution of system tasks
        agent._process_task = lambda t: t
        
        tasks = agent.run("Who are you?")
        
        mock_planner.plan.assert_not_called()
        mock_cognitive.process_fast.assert_called_once_with("Who are you?", intent="chat")
        assert tasks[0].action == "respond"
        
    @patch("core.agent.IntentClassifier")
    def test_tool_bypasses_mission_loop(self, mock_classifier_class):
        mock_classifier = mock_classifier_class.return_value
        mock_classifier.classify.return_value = IntentType.TOOL
        
        mock_planner = Mock()
        mock_planner.plan.return_value = [Task(tool="windows", action="open_app")]
        
        agent = Agent(
            planner=mock_planner,
            validator=Mock(),
            executor=Mock(),
        )
        
        # We need to mock _process_task
        agent._process_task = lambda t: t
        
        # If no capability_manager, it falls back to planner directly, bypassing ExecutiveBrain
        tasks = agent.run("Open notepad")
        
        mock_planner.plan.assert_called_once()

    def test_scenario_1_hi_chat(self):
        """User: 'Hi' -> CHAT, ConversationEngine USED, ExecutiveBrain/ReasoningLoop/MissionControl NOT USED."""
        mock_cognitive = Mock()
        mock_cognitive.process_fast.return_value = Mock(type="RESPONSE", message="Hello! How can I assist you today?", tool=None, action=None)
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
        assert tasks[0].args["message"] == "Hello! How can I assist you today?"
        mock_cognitive.process_fast.assert_called_once_with("Hi", intent="chat")
        # Ensure heavy stages were NOT invoked
        mock_planner.plan.assert_not_called()
        assert not hasattr(mock_cognitive, "plan") or mock_cognitive.plan.call_count == 0

    def test_scenario_2_who_are_you(self):
        """User: 'Who are you?' -> CHAT, ConversationEngine USED, no mission reasoning."""
        mock_cognitive = Mock()
        mock_cognitive.process_fast.return_value = Mock(type="RESPONSE", message="I am JARVIS, your AI operating system.", tool=None, action=None)
        mock_planner = Mock()

        agent = Agent(
            planner=mock_planner,
            validator=Mock(),
            executor=Mock(),
            cognitive_manager=mock_cognitive,
        )
        agent._process_task = lambda t: t

        tasks = agent.run("Who are you?")

        assert len(tasks) == 1
        assert tasks[0].args["message"] == "I am JARVIS, your AI operating system."
        mock_cognitive.process_fast.assert_called_once_with("Who are you?", intent="chat")
        mock_planner.plan.assert_not_called()

    def test_scenario_3_remember_my_ide(self):
        """User: 'Remember my IDE is Antigravity.' -> MEMORY, Memory subsystem used, no ExecutiveBrain."""
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

        tasks = agent.run("Remember that my IDE is Antigravity.")

        assert len(tasks) == 1
        assert "Antigravity" in tasks[0].args["message"]
        mock_memory.remember_fact.assert_called_once_with("ide", "Antigravity")
        mock_planner.plan.assert_not_called()
        mock_cognitive.process.assert_not_called()

    def test_scenario_4_open_notepad(self):
        """User: 'Open Notepad.' -> TOOL, windows.open_app selected, validation occurs, executor runs."""
        mock_cognitive = Mock()
        mock_cognitive.process_fast.return_value = Mock(
            type="ACTION",
            message="Opening Notepad for you.",
            tool="windows",
            action="open_app",
            parameters={"app": "notepad"}
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

        tasks = agent.run("Open Notepad.")

        assert len(tasks) == 2
        assert tasks[0].args["message"] == "Opening Notepad for you."
        assert tasks[1].tool == "windows"
        assert tasks[1].action == "open_app"
        assert tasks[1].args["app"] == "notepad"
        mock_validator.validate.assert_called_once()
        mock_executor.execute.assert_called_once()

    def test_scenario_5_open_github(self):
        """User: 'Open GitHub.' -> TOOL, browser.open_site resolved dynamically, not hard-coded."""
        mock_cognitive = Mock()
        mock_cognitive.process_fast.return_value = Mock(
            type="ACTION",
            message="Opening GitHub in your browser.",
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

        tasks = agent.run("Open GitHub.")

        assert len(tasks) == 2
        assert tasks[1].tool == "browser"
        assert tasks[1].action == "open_site"
        assert tasks[1].args["site"] == "github"
        mock_validator.validate.assert_called_once()
        mock_executor.execute.assert_called_once()

    def test_scenario_6_generate_documentary(self):
        """User: 'Generate a documentary.' -> MISSION, ExecutiveBrain / Mission handled."""
        mock_planner = Mock()
        mock_planner.plan.return_value = [Task(tool="system", action="respond", args={"message": "Documentary planned"})]

        agent = Agent(
            planner=mock_planner,
            validator=Mock(),
            executor=Mock(),
        )
        agent._process_task = lambda t: t

        tasks = agent.run("Generate a documentary about climate change.")

        # MISSION route taken
        assert len(tasks) >= 1
        mock_planner.plan.assert_called_once()

    def test_scenario_7_arbitrary_chat_input(self):
        """Arbitrary conversational input: 'Why do people enjoy watching documentaries?' -> CHAT."""
        classifier = IntentClassifier()
        assert classifier.classify("Why do people enjoy watching documentaries?") == IntentType.CHAT

        mock_cognitive = Mock()
        mock_cognitive.process_fast.return_value = Mock(
            type="RESPONSE",
            message="People enjoy documentaries because they offer insight into real-world events.",
            tool=None,
            action=None
        )

        agent = Agent(
            planner=Mock(),
            validator=Mock(),
            executor=Mock(),
            cognitive_manager=mock_cognitive,
        )
        agent._process_task = lambda t: t

        tasks = agent.run("Why do people enjoy watching documentaries?")

        assert len(tasks) == 1
        assert "documentaries" in tasks[0].args["message"]
        mock_cognitive.process_fast.assert_called_once_with("Why do people enjoy watching documentaries?", intent="chat")

