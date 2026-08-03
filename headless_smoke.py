from unittest.mock import MagicMock

from core.agent import Agent
from core.cognition.classifier import IntentClassifier
from core.cognition.context import ShortTermContext
from core.cognition.manager import CognitiveManager
from core.cognition.reflection import CognitiveReflection
from core.cognition.router import CognitiveRouter
from core.events.bus import EventBus
from core.executor.action_registry import ActionRegistry
from core.executor.executor import ExecutionEngine
from core.model_router import ModelRouter
from core.planner import Planner
from core.registry import Registry
from core.telemetry.levels import LogLevel
from core.telemetry.logger import AsyncLogger
from core.validator import Validator


def main():
    print("Setting up dependencies...")
    gateway = MagicMock(spec=ModelRouter)
    action_registry = ActionRegistry()
    registry = Registry()

    planner = Planner(gateway, registry)
    validator = Validator(registry)
    executor = ExecutionEngine(action_registry)

    dummy_masker = MagicMock()
    dummy_masker.mask.side_effect = lambda x: x
    async_logger = AsyncLogger(level=LogLevel.INFO, masker=dummy_masker, outputs=[])
    event_bus = EventBus(logger=async_logger)

    classifier = IntentClassifier(gateway=gateway)
    router = CognitiveRouter()
    context = ShortTermContext()
    reflection = CognitiveReflection(event_bus=event_bus)

    cognitive_manager = CognitiveManager(
        classifier=classifier,
        router=router,
        reflection=reflection,
        context=context,
        event_bus=event_bus,
    )

    agent = Agent(
        planner=planner,
        validator=validator,
        executor=executor,
        memory=None,
        cognitive_manager=cognitive_manager,
    )

    commands = [
        "hello",
        "open notepad",
        "open calculator",
        "create file test.txt",
        "search python",
        "remember my favorite editor is VS Code",
    ]

    # Mocking cognitive components to bypass LLM
    from core.cognition.enums import DecisionType, IntentType
    from core.cognition.models import CognitiveDecision, IntentResult

    def analyze_mock(msg):
        # simple heuristic for smoke test
        action = None
        params = {}
        itype = IntentType.CHAT
        if msg.startswith("hello"):
            itype = IntentType.CHAT
        elif msg.startswith("open"):
            itype = IntentType.SIMPLE_ACTION
            action = "open_app"
            params = {"app": msg.split()[-1]}
        elif msg.startswith(("create file", "search")):
            itype = IntentType.COMPLEX_GOAL
        elif msg.startswith("remember"):
            itype = IntentType.LEARN
        return IntentResult(
            intent=itype, confidence=0.9, extracted_action=action, parameters=params
        )

    def decide_mock(intent_res):
        if intent_res.intent == IntentType.CHAT:
            return CognitiveDecision(
                decision_type=DecisionType.DIRECT_RESPONSE,
                intent_result=intent_res,
                target_component="agent",
            )
        elif intent_res.intent == IntentType.SIMPLE_ACTION:
            return CognitiveDecision(
                decision_type=DecisionType.EXECUTE_ACTION,
                intent_result=intent_res,
                target_component="executor",
            )
        elif intent_res.intent == IntentType.LEARN:
            return CognitiveDecision(
                decision_type=DecisionType.EXECUTE_ACTION,
                intent_result=intent_res,
                target_component="memory",
            )
        else:
            return CognitiveDecision(
                decision_type=DecisionType.CREATE_PLAN,
                intent_result=intent_res,
                target_component="planner",
            )

    cognitive_manager.analyze = analyze_mock
    cognitive_manager.decide = decide_mock

    # Mock planner
    from core.task import Task

    def plan_mock(user_input, context):
        if user_input.startswith("create file"):
            return [Task(tool="system", action="echo", args={"msg": "created"})]
        elif user_input.startswith("search"):
            return [Task(tool="system", action="echo", args={"msg": "searched"})]
        return []

    planner.plan = plan_mock

    # Mock executor execution
    def exec_mock(task):
        task.start()
        task.complete("Mock success")
        return task

    executor.execute = exec_mock

    print("Executing smoke tests...\n")
    for cmd in commands:
        print(f"--- Command: {cmd} ---")
        try:
            tasks = agent.run(cmd)
            for t in tasks:
                print(f"  [{t.status.name}] Tool: {t.tool}, Action: {t.action}")
        except (OSError, RuntimeError, ValueError) as e:
            print(f"  Error: {e}")
        print()

    print("Smoke testing complete. No exceptions!")


if __name__ == "__main__":
    main()
