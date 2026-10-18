from __future__ import annotations

import json
from unittest.mock import MagicMock

from core.cognition.context import ShortTermContext
from core.reasoning.critic import ReasoningCritic
from core.reasoning.execution_plan import ExecutionPlan
from core.reasoning.loop import ReasoningLoop
from core.reasoning.planner import ReasoningPlanner
from core.reasoning.verifier import ReasoningVerifier


class _SequenceLLM:
    def __init__(self, *responses: str) -> None:
        self.responses = list(responses)

    def generate(self, _system_prompt: str, _user_prompt: str):
        if not self.responses:
            raise AssertionError("Unexpected model call")
        return self.responses.pop(0)


def _plan_json(**overrides) -> str:
    payload = {
        "ordered_steps": ["Inspect the requested task", "Perform the validated action"],
        "required_context": [],
        "required_tools": ["browser"],
        "required_models": ["reasoning"],
        "required_missions": [],
        "fallback_strategy": "Ask before any unsafe or irreversible operation.",
        "requires_clarification": False,
        "clarification_question": None,
    }
    payload.update(overrides)
    return json.dumps(payload)


def _complete_critique() -> str:
    return json.dumps({
        "is_complete": True,
        "feedback": "",
        "needs_clarification": False,
        "clarification_question": None,
    })


def test_reasoning_planner_malformed_json_returns_non_executable_clarification() -> None:
    planner = ReasoningPlanner(_SequenceLLM("{not json"))
    plan = planner.plan("Help me with a task", ShortTermContext())

    assert plan.requires_clarification is True
    assert plan.clarification_question
    assert plan.ordered_steps == []
    assert plan.required_tools == []


def test_reasoning_planner_enforces_schema_and_drops_steps_when_clarification_is_required() -> None:
    bad_schema = ReasoningPlanner(_SequenceLLM(_plan_json(required_tools="browser")))
    bad = bad_schema.plan("Do a task", ShortTermContext())
    assert bad.requires_clarification is True
    assert bad.ordered_steps == []

    needs_details = ReasoningPlanner(_SequenceLLM(_plan_json(
        requires_clarification=True,
        clarification_question="Which project should I use?",
    )))
    clarification = needs_details.plan("Update the project", ShortTermContext())
    assert clarification.requires_clarification is True
    assert clarification.clarification_question == "Which project should I use?"
    assert clarification.ordered_steps == []


def test_reasoning_planner_rejects_unsupported_context_and_empty_steps() -> None:
    unsupported = ReasoningPlanner(_SequenceLLM(_plan_json(required_context=["secrets"])))
    empty = ReasoningPlanner(_SequenceLLM(_plan_json(ordered_steps=[])))

    assert unsupported.plan("Do a task", ShortTermContext()).requires_clarification
    assert empty.plan("Do a task", ShortTermContext()).requires_clarification


def test_reasoning_critic_never_treats_malformed_output_as_complete() -> None:
    critic = ReasoningCritic(_SequenceLLM("not json"))
    result = critic.critique("Do a task", ExecutionPlan(ordered_steps=["Step one"]))

    assert result.is_complete is False
    assert result.needs_clarification is False
    assert "invalid" in result.feedback.casefold()


def test_reasoning_verifier_rejects_empty_steps_and_unknown_tools() -> None:
    registry = MagicMock()
    registry.list_tools.return_value = ["browser"]
    verifier = ReasoningVerifier(registry)

    no_steps = verifier.verify(ExecutionPlan(ordered_steps=[]))
    unknown_tool = verifier.verify(ExecutionPlan(
        ordered_steps=["Step one"],
        required_tools=["phantom_tool"],
    ))
    assert no_steps.is_valid is False
    assert any("ordered steps" in error for error in no_steps.errors)
    assert unknown_tool.is_valid is False
    assert any("not available" in error for error in unknown_tool.errors)


def test_reasoning_verifier_does_not_claim_unresolved_missions_available() -> None:
    registry = MagicMock()
    registry.list_tools.return_value = []
    result = ReasoningVerifier(registry).verify(ExecutionPlan(
        ordered_steps=["Run the requested mission"],
        required_missions=["unknown_mission"],
    ))

    assert result.is_valid is False
    assert any("mission registry is connected" in error for error in result.errors)


def test_reasoning_loop_never_returns_unverified_draft_after_iteration_limit() -> None:
    llm = _SequenceLLM(
        _plan_json(required_tools=["missing_tool"]),
        _complete_critique(),
    )
    registry = MagicMock()
    registry.list_tools.return_value = ["browser"]

    result = ReasoningLoop(llm, registry).run(
        "Do a multi-step task", ShortTermContext(), max_iterations=1
    )

    assert result.requires_clarification is True
    assert result.ordered_steps == []
    assert result.required_tools == []
    assert "Nothing was executed" in result.clarification_question


def test_reasoning_loop_does_not_approve_a_draft_when_critique_is_malformed() -> None:
    llm = _SequenceLLM(_plan_json(), "this isn't JSON")
    registry = MagicMock()
    registry.list_tools.return_value = ["browser"]

    result = ReasoningLoop(llm, registry).run(
        "Do a multi-step task", ShortTermContext(), max_iterations=1
    )

    assert result.requires_clarification is True
    assert result.ordered_steps == []
    assert result.required_tools == []


def test_reasoning_loop_rejects_invalid_iteration_bounds() -> None:
    llm = _SequenceLLM()
    registry = MagicMock()
    loop = ReasoningLoop(llm, registry)

    for invalid in (0, -1, 11, True, 1.5):
        try:
            loop.run("Do a task", ShortTermContext(), max_iterations=invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected invalid iteration bound {invalid!r} to be rejected")
    assert llm.responses == []
